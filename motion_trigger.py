#!/usr/bin/env python3
"""
motion_trigger.py - play one of Unitree's built-in firmware motions (FSM 550)
from a remote combo. Default: L1 + R1 + A -> 534 vq_chayao (叉腰 hands on hips, ~6 s).

Unitree's own controller plays and balances the motion (LocoClient.SetFsmId(550534)),
so this script never commands any motor. It only:
  1. reads the remote's buttons from rt/lf/lowstate (the low-rate copy; rt/lowstate at 500 Hz
     costs most of a CPU core in Python),
  2. waits for L1 + R1 + A held for HOLD_SECONDS (then it must be released),
  3. checks: Unitree in charge (all 12 leg motor modes == 1, not debug mode),
     the RL walker (deploy_real.py) is not running, and the FSM id is exactly
     801 (run mode, where firmware motions were tested on 2026-10-06),
  4. calls SetFsmId(550000 + motion id),
  5. watches the FSM id until the robot is back at 801 and logs how long it took.
     Combos pressed while a motion plays are ignored.

Why L1 + R1 + A: the only Unitree combo inside it is L1 + A (damping). Our salute
uses L1 + R1 + B, which contains L1 + B (zero torque), and the firmware ignored
that on the robot. Still: test on the gantry with this script NOT running first.

Real robot (on the Jetson):
    python3 -u motion_trigger.py --dry-run     # every check, prints, sends NOTHING
    python3 -u motion_trigger.py

Laptop test against fake_remote.py (domain 1, lo, no robot):
    python3 -u fake_remote.py --combo hips --leg-mode 1
    python3 -u motion_trigger.py --domain 1 --iface lo --skip-fsm-check --dry-run
"""
import argparse
import json
import signal
import struct
import subprocess
import sys
import time
from datetime import datetime

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

# ---- settings -------------------------------------------------------------
# Button bit numbers inside wireless_remote[2:4] (same as KeyMap in
# unitree_rl_gym/deploy/deploy_real/common/remote_controller.py)
R1, L1, A = 0, 1, 8
COMBO = (L1, R1, A)
COMBO_NAME = "L1 + R1 + A"
HOLD_SECONDS = 1.0
LEG_JOINTS = range(12)       # motor_state[0..11] = both legs

MOTION_ID = 534              # vq_chayao, 叉腰 hands on hips (v2), ~6 s
MOTION_NAME = "hands on hips (534 vq_chayao)"
FSM_MOTION_BASE = 550000     # SetFsmId(550000 + id) plays firmware motion <id>
FSM_RUN_MODE = 801           # the only state we allow starting from
MOTION_TIMEOUT = 30.0        # s to wait for the FSM to come back to 801

LOCO_API_GET_FSM_ID = 7001   # LocoClient "get FSM id" (raw call; the robot's SDK has no GetFsmId method)
STATE_TIMEOUT = 1.0          # s without rt/lowstate -> treated as "no data"
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

    def on_lowstate(self, msg: LowState_):
        keys = struct.unpack("H", bytes(msg.wireless_remote)[2:4])[0]
        self.pressed = [bool(keys & (1 << i)) for i in range(16)]
        self.leg_modes = [msg.motor_state[i].mode for i in LEG_JOINTS]
        self.last_msg_time = time.time()

    def fresh(self):
        return time.time() - self.last_msg_time < STATE_TIMEOUT

    def combo_down(self):
        return all(self.pressed[b] for b in COMBO)

    def unitree_in_charge(self):
        """Leg motor modes: 1 = Unitree's controller has the legs, 0 = debug mode (L2+R2)."""
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
    """All the reasons NOT to play. Logs the reason and returns False if any applies."""
    modes = "".join(map(str, state.leg_modes or []))
    if not state.unitree_in_charge():
        log(f"Leg motor modes {modes or '?'}: Unitree's controller is not in charge "
            "(debug mode?). Not playing.")
        return False
    if walker_running():
        log("The RL walker (deploy_real.py) is running. Not playing.")
        return False
    if skip_fsm_check:
        log(f"Leg modes {modes} OK. FSM check skipped (test mode).")
        return True
    ok, fsm = get_fsm_id(loco)
    if not ok:
        log(f"Could not read the robot's FSM id ({fsm}). Not playing.")
        return False
    if fsm != FSM_RUN_MODE:
        log(f"Robot FSM id is {fsm}, not {FSM_RUN_MODE} (run mode). "
            "Put the robot in run mode first. Not playing.")
        return False
    log(f"Leg modes {modes}, FSM id {fsm}: OK.")
    return True


def play_motion(loco):
    """SetFsmId(550xxx), then wait until the FSM is back at 801."""
    target = FSM_MOTION_BASE + MOTION_ID
    log(f"Playing {MOTION_NAME}: SetFsmId({target}).")
    try:
        code = loco.SetFsmId(target)
    except Exception as e:  # noqa: BLE001
        log(f"SetFsmId failed: {e}")
        return
    if code != 0:
        log(f"SetFsmId returned code {code}. The motion did not start.")
        return

    t0 = time.time()
    seen = []
    while time.time() - t0 < MOTION_TIMEOUT:
        time.sleep(0.2)
        ok, fsm = get_fsm_id(loco)
        if ok and (not seen or seen[-1] != fsm):
            seen.append(fsm)
        if ok and fsm == FSM_RUN_MODE and len(seen) > 1:
            log(f"Motion done in {time.time() - t0:.1f} s (FSM {' -> '.join(map(str, seen))}).")
            return
    log(f"WARNING: FSM not back at {FSM_RUN_MODE} after {MOTION_TIMEOUT:.0f} s "
        f"(seen: {' -> '.join(map(str, seen)) or 'nothing'}). Check the robot.")


def main():
    ap = argparse.ArgumentParser(description="Play a firmware motion on a remote combo.")
    ap.add_argument("--iface", default="eth0", help="network interface (robot: eth0)")
    ap.add_argument("--domain", type=int, default=0, help="DDS domain (robot: 0, laptop test: 1)")
    ap.add_argument("--dry-run", action="store_true",
                    help="do every check and print, but do NOT start the motion")
    ap.add_argument("--skip-fsm-check", action="store_true",
                    help="skip the FSM-id check (only allowed when --domain is not 0)")
    args = ap.parse_args()

    if args.skip_fsm_check and args.domain == 0:
        sys.exit("--skip-fsm-check is refused on domain 0 (the real robot).")
    if args.skip_fsm_check and not args.dry_run:
        sys.exit("--skip-fsm-check only works together with --dry-run.")

    signal.signal(signal.SIGTERM, on_sigterm)
    ChannelFactoryInitialize(args.domain, args.iface)

    state = RobotState()
    sub = ChannelSubscriber("rt/lf/lowstate", LowState_)   # low-rate copy: light on the Jetson CPU
    sub.Init(state.on_lowstate, 10)

    loco = None
    if not args.skip_fsm_check:
        from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient
        loco = LocoClient()
        loco.SetTimeout(2.0)
        loco.Init()

    log(f"motion_trigger ready. Hold {COMBO_NAME} for {HOLD_SECONDS:.0f} s -> {MOTION_NAME}."
        + ("  [DRY RUN]" if args.dry_run else ""))

    held_since = None
    need_release = False
    warned_no_data = False

    while True:
        time.sleep(0.02)

        if not state.fresh():
            if not warned_no_data:
                log("No rt/lf/lowstate data (robot off, or wrong --iface/--domain?)")
                warned_no_data = True
            held_since = None
            continue
        if warned_no_data:
            log("Receiving rt/lf/lowstate.")
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
            log(f"DRY RUN: all checks passed; would call SetFsmId({FSM_MOTION_BASE + MOTION_ID}) "
                "now. Nothing sent.")
            continue
        play_motion(loco)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, StopRequested):
        log("motion_trigger stopped.")
