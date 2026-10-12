#!/usr/bin/env python3
"""
salute_trigger.py - make the G1 salute with its right hand from a remote combo,
while Unitree's own controller keeps it standing/walking and balanced.

How it works:
  1. reads the remote's buttons from rt/lowstate,
  2. waits for L1 + R1 + B held for HOLD_SECONDS,
  3. checks that Unitree's controller is in charge (NOT debug mode: all leg
     motors report mode 1) and that the robot isn't in zero torque or damping
     (LocoClient FSM id is not 0 or 1),
  4. checks that the RL walker (deploy_real.py) isn't running,
  5. plays the salute on rt/arm_sdk:
       take over the arms gently (blend weight 0 -> 1 in 1 s, holding the current pose)
       -> hand to the forehead -> hold -> back to the starting pose
       -> hand the arms back to Unitree (weight 1 -> 0 in 1 s).

It never commands the legs. The arms and waist are sent on rt/arm_sdk, the same
way as Unitree's g1_arm7_sdk_dds_example.py. Joints the salute doesn't move
(left arm, waist) are held where they were when the combo fired.

Safety stops (the arms are handed back to Unitree over 0.5 s):
  - rt/lowstate stops arriving for more than 0.25 s,
  - the legs switch to debug mode in the middle of a salute,
  - Ctrl+C, or `systemctl stop` (SIGTERM).

Real robot (on the Jetson):
    python3 -u salute_trigger.py --dry-run     # every check, prints, sends NOTHING
    python3 -u salute_trigger.py

Laptop test against fake_remote.py (domain 1, lo, no robot):
    python3 -u fake_remote.py --combo salute --leg-mode 1
    python3 -u salute_trigger.py --domain 1 --iface lo --skip-fsm-check
"""
import argparse
import json
import signal
import struct
import subprocess
import sys
import time
from datetime import datetime

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher, ChannelSubscriber
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowCmd_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_, LowState_
from unitree_sdk2py.utils.crc import CRC

import gestures as G
from gestures import BLEND_IN, BLEND_OUT

# ---- settings -------------------------------------------------------------
# Button bit numbers inside wireless_remote[2:4] (same as KeyMap in
# unitree_rl_gym/deploy/deploy_real/common/remote_controller.py)
R1, L1, B = 0, 1, 9
COMBO = (L1, R1, B)
COMBO_NAME = "L1 + R1 + B"
HOLD_SECONDS = 1.0
LEG_JOINTS = range(12)       # motor_state[0..11] = both legs

CONTROL_DT = 0.02            # 50 Hz, like Unitree's arm_sdk example
KP, KD = 60.0, 1.5           # gains from Unitree's arm_sdk example
ABORT_BLEND_OUT = 0.5        # s to hand them back after a safety stop
STATE_TIMEOUT = 0.25         # s without rt/lowstate -> safety stop

LOCO_API_GET_FSM_ID = 7001   # LocoClient "get FSM id" (registered by LocoClient.Init on all SDK versions)
UNSAFE_FSM_IDS = {0: "zero torque", 1: "damping"}
# ---------------------------------------------------------------------------


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


class StopRequested(Exception):
    pass


def on_sigterm(signum, frame):
    raise StopRequested()


class RobotState:
    """Latest rt/lowstate, updated from the subscriber callback."""

    def __init__(self):
        self.pressed = [False] * 16
        self.last_msg_time = 0.0
        self.leg_modes = None
        self.q = None

    def on_lowstate(self, msg: LowState_):
        data = bytes(msg.wireless_remote)
        keys = struct.unpack("H", data[2:4])[0]
        self.pressed = [bool(keys & (1 << i)) for i in range(16)]
        self.leg_modes = [msg.motor_state[i].mode for i in LEG_JOINTS]
        self.q = [msg.motor_state[i].q for i in range(29)]
        self.last_msg_time = time.time()

    def fresh(self):
        return time.time() - self.last_msg_time < STATE_TIMEOUT

    def combo_down(self):
        return all(self.pressed[b] for b in COMBO)

    def unitree_in_charge(self):
        """Leg motor modes: 1 = Unitree's controller has the legs, 0 = debug mode (L2+R2).
        Checked with mode_probe.py on 2026-09-30."""
        return self.leg_modes is not None and all(m == 1 for m in self.leg_modes)


def get_fsm_id(loco):
    """Ask Unitree's locomotion service which state it is in. Returns (ok, id_or_reason)."""
    try:
        code, data = loco._Call(LOCO_API_GET_FSM_ID, "{}")
    except Exception as e:  # noqa: BLE001 - any failure means "unknown", which is not safe
        return False, f"call failed: {e}"
    if code != 0:
        return False, f"error code {code}"
    try:
        return True, json.loads(data).get("data")
    except (ValueError, AttributeError):
        return False, f"unreadable reply {data!r}"


def walker_running():
    """Any deploy_real.py on this machine, whoever started it."""
    return subprocess.run(["pgrep", "-f", "deploy_real.py"], capture_output=True).returncode == 0


def checks_pass(state, loco, skip_fsm_check):
    """All the reasons NOT to salute. Logs the reason and returns False if any applies."""
    modes = "".join(map(str, state.leg_modes or []))
    if not state.unitree_in_charge():
        log(f"Leg motor modes {modes or '?'}: Unitree's controller is not in charge "
            "(debug mode?). Not saluting.")
        return False
    if walker_running():
        log("The RL walker (deploy_real.py) is running. Not saluting.")
        return False
    if skip_fsm_check:
        log(f"Leg modes {modes} OK. FSM check skipped (test mode).")
        return True
    ok, fsm = get_fsm_id(loco)
    if not ok:
        log(f"Could not read the robot's FSM id ({fsm}). Not saluting.")
        return False
    if fsm in UNSAFE_FSM_IDS:
        log(f"Robot FSM id {fsm} ({UNSAFE_FSM_IDS[fsm]}). Stand the robot up first. Not saluting.")
        return False
    log(f"Leg modes {modes}, FSM id {fsm}: OK.")
    return True


class ArmSdk:
    """Sends rt/arm_sdk commands for G.ARM_SDK_JOINTS plus the blend weight."""

    def __init__(self):
        self.pub = ChannelPublisher("rt/arm_sdk", LowCmd_)
        self.pub.Init()
        self.cmd = unitree_hg_msg_dds__LowCmd_()
        self.crc = CRC()

    def send(self, pose, weight):
        for j in G.ARM_SDK_JOINTS:
            m = self.cmd.motor_cmd[j]
            m.q = float(pose[j])
            m.dq = 0.0
            m.kp = KP
            m.kd = KD
            m.tau = 0.0
        self.cmd.motor_cmd[G.ARM_SDK_WEIGHT_SLOT].q = float(min(max(weight, 0.0), 1.0))
        self.cmd.crc = self.crc.Crc(self.cmd)
        self.pub.Write(self.cmd)


def play_salute(arm, state):
    """Blend in, salute, blend out. Raises StopRequested (after handing the arms
    back) if Ctrl+C / SIGTERM arrives mid-gesture."""
    start = {j: state.q[j] for j in G.ARM_SDK_JOINTS}
    plan = G.salute_plan(start)
    total = BLEND_IN + G.plan_length(plan) + BLEND_OUT
    log(f"Saluting ({total:.1f} s).")

    pose, weight = dict(start), 0.0
    t0 = time.monotonic()
    tick = 0
    stop = None
    try:
        while True:
            t = tick * CONTROL_DT
            if not state.fresh():
                stop = "rt/lowstate stopped arriving"
                break
            if not state.unitree_in_charge():
                stop = "legs switched to debug mode"
                break
            if t < BLEND_IN:
                pose, weight = start, t / BLEND_IN
            elif t < BLEND_IN + G.plan_length(plan):
                pose, weight = G.sample(plan, start, t - BLEND_IN), 1.0
            elif t < total:
                pose, weight = start, 1.0 - (t - BLEND_IN - G.plan_length(plan)) / BLEND_OUT
            else:
                arm.send(start, 0.0)
                log("Salute done. Arms handed back to Unitree.")
                return
            arm.send(pose, weight)
            tick += 1
            time.sleep(max(0.0, t0 + tick * CONTROL_DT - time.monotonic()))
    except (KeyboardInterrupt, StopRequested):
        log("Stop requested mid-salute. Handing the arms back to Unitree.")
        hand_back(arm, pose, weight)
        raise StopRequested()
    log(f"SAFETY STOP: {stop}. Handing the arms back to Unitree.")
    hand_back(arm, pose, weight)


def hand_back(arm, pose, weight):
    """Ramp the blend weight to 0 while holding the last commanded pose.
    A second SIGTERM during the ramp is ignored so the ramp always finishes."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    steps = max(1, int(ABORT_BLEND_OUT / CONTROL_DT))
    for i in range(steps, -1, -1):
        arm.send(pose, weight * i / steps)
        time.sleep(CONTROL_DT)
    signal.signal(signal.SIGTERM, on_sigterm)


def main():
    ap = argparse.ArgumentParser(description="Salute with the right hand on a remote combo.")
    ap.add_argument("--iface", default="eth0", help="network interface (robot: eth0)")
    ap.add_argument("--domain", type=int, default=0, help="DDS domain (robot: 0, laptop test: 1)")
    ap.add_argument("--dry-run", action="store_true",
                    help="do every check and print, but send NOTHING to the arms")
    ap.add_argument("--skip-fsm-check", action="store_true",
                    help="skip the FSM-id check (only allowed when --domain is not 0)")
    args = ap.parse_args()

    if args.skip_fsm_check and args.domain == 0:
        sys.exit("--skip-fsm-check is refused on domain 0 (the real robot).")

    signal.signal(signal.SIGTERM, on_sigterm)
    ChannelFactoryInitialize(args.domain, args.iface)

    state = RobotState()
    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(state.on_lowstate, 10)

    loco = None
    if not args.skip_fsm_check:
        from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
        loco = LocoClient()
        loco.SetTimeout(2.0)
        loco.Init()

    # In a dry run the arm_sdk publisher is never even created.
    arm = None if args.dry_run else ArmSdk()

    log(f"salute_trigger ready. Hold {COMBO_NAME} for {HOLD_SECONDS:.0f} s to salute."
        + ("  [DRY RUN]" if args.dry_run else ""))

    held_since = None
    need_release = False
    warned_no_data = False

    while True:
        time.sleep(0.02)

        if time.time() - state.last_msg_time > 1.0:
            if not warned_no_data:
                log("No rt/lowstate data yet (robot off, or wrong --iface/--domain?)")
                warned_no_data = True
            held_since = None
            continue
        if warned_no_data:
            log("Receiving rt/lowstate.")
            warned_no_data = False

        if not state.combo_down():
            held_since = None
            need_release = False
            continue
        if need_release:
            continue
        if held_since is None:
            held_since = time.time()
            continue
        if time.time() - held_since < HOLD_SECONDS:
            continue

        need_release = True
        held_since = None
        log(f"{COMBO_NAME} detected.")
        if not checks_pass(state, loco, args.skip_fsm_check):
            continue

        if args.dry_run:
            start = {j: state.q[j] for j in G.ARM_SDK_JOINTS}
            plan = G.salute_plan(start)
            log(f"DRY RUN: all checks passed; would salute now "
                f"({BLEND_IN + G.plan_length(plan) + BLEND_OUT:.1f} s). Nothing sent.")
            continue

        play_salute(arm, state)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, StopRequested):
        log("salute_trigger stopped.")
