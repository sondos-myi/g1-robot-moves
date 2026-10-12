#!/usr/bin/env python3
"""
arm_sdk_monitor.py - READ-ONLY. Prints what is being sent on rt/arm_sdk.

Use it to:
  - check that nothing else on the robot is already using rt/arm_sdk before
    the first salute (it should print "silent"),
  - watch a salute's blend weight and right-arm targets, on the robot or
    in the laptop test.

    python3 -u arm_sdk_monitor.py                       # robot (domain 0, eth0)
    python3 -u arm_sdk_monitor.py --domain 1 --iface lo # laptop test
    python3 -u arm_sdk_monitor.py --csv salute.csv      # also save every message
"""
import argparse
import signal
import time
from datetime import datetime

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowCmd_

import gestures as G

ap = argparse.ArgumentParser(description="Print rt/arm_sdk traffic (read-only).")
ap.add_argument("--iface", default="eth0")
ap.add_argument("--domain", type=int, default=0)
ap.add_argument("--csv", help="also write every received message to this CSV file")
args = ap.parse_args()

latest = {"msg": None, "count": 0}
csv = open(args.csv, "w") if args.csv else None
if csv:
    csv.write("time,weight," + ",".join(G.JOINT_NAMES[j] for j in G.ARM_SDK_JOINTS) + "\n")


def on_cmd(msg: LowCmd_):
    latest["msg"] = msg
    latest["count"] += 1
    if csv:
        row = [f"{time.time():.4f}", f"{msg.motor_cmd[G.ARM_SDK_WEIGHT_SLOT].q:.4f}"]
        row += [f"{msg.motor_cmd[j].q:.4f}" for j in G.ARM_SDK_JOINTS]
        csv.write(",".join(row) + "\n")


def on_sigterm(signum, frame):
    raise KeyboardInterrupt  # stop like Ctrl+C, so the CSV gets closed


signal.signal(signal.SIGTERM, on_sigterm)
ChannelFactoryInitialize(args.domain, args.iface)
sub = ChannelSubscriber("rt/arm_sdk", LowCmd_)
sub.Init(on_cmd, 10)
print("arm_sdk_monitor: listening on rt/arm_sdk (Ctrl+C to stop)", flush=True)

last_count = 0
try:
    while True:
        time.sleep(0.5)
        n = latest["count"] - last_count
        last_count = latest["count"]
        now = f"{datetime.now():%H:%M:%S}"
        if n == 0:
            print(f"[{now}] silent", flush=True)
            continue
        m = latest["msg"]
        arm = " ".join(f"{m.motor_cmd[j].q:+.2f}" for j in G.RIGHT_ARM)
        print(f"[{now}] {n * 2:3d} msg/s  weight {m.motor_cmd[G.ARM_SDK_WEIGHT_SLOT].q:.2f}  "
              f"right arm [{arm}]", flush=True)
except KeyboardInterrupt:
    pass
finally:
    if csv:
        csv.close()
