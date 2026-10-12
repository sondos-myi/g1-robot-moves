#!/usr/bin/env python3
"""
walk_trigger.py - start the unitree_rl_gym walking policy from a remote combo.

This program NEVER sends motor commands. It only:
  1. reads the remote's buttons from rt/lowstate,
  2. waits for L1 + R1 + Y held for HOLD_SECONDS,
  3. checks that the robot is in debug mode (Unitree's controller released:
     all leg motors report mode 0 in rt/lowstate),
  4. checks that no walker is already running,
  5. starts deploy_real.py exactly as you did by hand, logging to ~/walk.log.

Everything after that (start / A / select) is handled by deploy_real.py itself.

Real robot (on the Jetson):
    python3 -u walk_trigger.py
    python3 -u walk_trigger.py --dry-run          # everything except launching

Laptop test against fake_remote.py (domain 1, lo, no robot):
    python3 -u walk_trigger.py --domain 1 --iface lo --dry-run --skip-mode-check
"""
import argparse
import os
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
R1, L1, Y = 0, 1, 11
COMBO = (L1, R1, Y)
COMBO_NAME = "L1 + R1 + Y"
HOLD_SECONDS = 1.0
LEG_JOINTS = range(12)   # motor_state[0..11] = both legs

WALKER_DIR = os.path.expanduser("~/unitree_rl_gym/deploy/deploy_real")
RL_GYM_ROOT = os.path.expanduser("~/unitree_rl_gym")
WALK_LOG = os.path.expanduser("~/walk.log")
# ---------------------------------------------------------------------------


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


class RemoteButtons:
    """Latest button state, updated from the rt/lowstate callback."""

    def __init__(self):
        self.pressed = [False] * 16
        self.last_msg_time = 0.0
        self.leg_modes = None

    def on_lowstate(self, msg: LowState_):
        data = bytes(msg.wireless_remote)
        keys = struct.unpack("H", data[2:4])[0]
        self.pressed = [bool(keys & (1 << i)) for i in range(16)]
        self.leg_modes = [msg.motor_state[i].mode for i in LEG_JOINTS]
        self.last_msg_time = time.time()

    def combo_down(self):
        return all(self.pressed[b] for b in COMBO)


def robot_in_debug_mode(buttons):
    """True only if Unitree's controller has released the legs (debug mode).

    On this G1, MotionSwitcher CheckMode() still says 'ai' after L2+R2, so we
    can't use it. What does change: every leg motor's mode goes 1 -> 0
    (checked with mode_probe.py, 2026-09-30). Anything else counts as NOT safe."""
    modes = buttons.leg_modes
    if modes is None:
        log("No leg motor data yet -> treating as NOT safe")
        return False
    if any(m != 0 for m in modes):
        log(f"Robot is in normal mode (leg motor modes {''.join(map(str, modes))}). "
            "Press L2+R2 (debug mode) first. Not starting.")
        return False
    return True


def walker_already_running():
    """Any deploy_real.py on this machine, whoever started it."""
    r = subprocess.run(["pgrep", "-f", "deploy_real.py"], capture_output=True, text=True)
    return r.returncode == 0


def start_walker(iface):
    env = dict(os.environ, PYTHONPATH=RL_GYM_ROOT)
    logfile = open(WALK_LOG, "a")
    logfile.write(f"\n===== walk_trigger started walker at {datetime.now()} =====\n")
    logfile.flush()
    return subprocess.Popen(
        [sys.executable, "-u", "deploy_real.py", iface, "g1.yaml"],
        cwd=WALKER_DIR,
        env=env,
        stdout=logfile,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )


def main():
    ap = argparse.ArgumentParser(description="Start the RL walker from a remote combo.")
    ap.add_argument("--iface", default="eth0", help="network interface (robot: eth0)")
    ap.add_argument("--domain", type=int, default=0, help="DDS domain (robot: 0, sim: 1)")
    ap.add_argument("--dry-run", action="store_true",
                    help="do every check, but only print instead of starting the walker")
    ap.add_argument("--skip-mode-check", action="store_true",
                    help="skip the debug-mode check (only allowed when --domain is not 0)")
    args = ap.parse_args()

    if args.skip_mode_check and args.domain == 0:
        sys.exit("--skip-mode-check is refused on domain 0 (the real robot).")

    ChannelFactoryInitialize(args.domain, args.iface)

    buttons = RemoteButtons()
    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(buttons.on_lowstate, 10)

    log(f"walk_trigger ready. Hold {COMBO_NAME} for {HOLD_SECONDS:.0f} s to start the walker."
        + ("  [DRY RUN]" if args.dry_run else ""))

    walker = None
    held_since = None
    need_release = False   # after a trigger, the combo must be let go before it can fire again
    warned_no_data = False

    while True:
        time.sleep(0.02)

        # Report when the walker we started has finished
        if walker is not None and walker.poll() is not None:
            log(f"Walker exited (code {walker.returncode}). Ready again.")
            walker = None

        # No robot data?
        if time.time() - buttons.last_msg_time > 1.0:
            if not warned_no_data:
                log("No rt/lowstate data yet (robot off, or wrong --iface/--domain?)")
                warned_no_data = True
            held_since = None
            continue
        if warned_no_data:
            log("Receiving rt/lowstate.")
            warned_no_data = False

        if not buttons.combo_down():
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

        # Combo held long enough: fire once, then wait for release
        need_release = True
        held_since = None
        log(f"{COMBO_NAME} detected.")

        if walker is not None or walker_already_running():
            log("A walker (deploy_real.py) is already running. Not starting another.")
            continue
        if not args.skip_mode_check and not robot_in_debug_mode(buttons):
            continue

        if args.dry_run:
            log("DRY RUN: all checks passed; would start deploy_real.py now.")
            continue

        walker = start_walker(args.iface)
        log(f"Walker started (pid {walker.pid}). Log: {WALK_LOG}. "
            "Remote: start -> stand, A -> walk, select -> stop.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("walk_trigger stopped.")
