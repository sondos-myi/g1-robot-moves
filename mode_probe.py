#!/usr/bin/env python3
"""
mode_probe.py - READ-ONLY. Prints what the robot reports about its mode,
twice a second, so we can see what changes when you press L2+R2.

It never sends motor commands and never changes the mode.

    python3 -u mode_probe.py            # on the Jetson, Ctrl+C to stop
"""
import argparse
import struct
import time
from datetime import datetime

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
from unitree_sdk2py.comm.motion_switcher.motion_switcher_client import MotionSwitcherClient

L2, R2 = 5, 4
LEG_JOINTS = range(0, 12)   # both legs

latest = {"msg": None}


def on_lowstate(msg: LowState_):
    latest["msg"] = msg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iface", default="eth0")
    ap.add_argument("--domain", type=int, default=0)
    args = ap.parse_args()

    ChannelFactoryInitialize(args.domain, args.iface)
    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(on_lowstate, 10)
    msc = MotionSwitcherClient()
    msc.SetTimeout(1.0)
    msc.Init()

    print("time      | switcher name | mode_machine mode_pr | leg motor modes          | max |leg torque| | L2+R2")
    while True:
        try:
            code, result = msc.CheckMode()
            name = repr(result.get("name")) if code == 0 and result else f"err {code}"
        except Exception as e:
            name = f"exc {e}"

        msg = latest["msg"]
        if msg is None:
            print(f"{datetime.now():%H:%M:%S}  | {name:13} | no rt/lowstate yet", flush=True)
        else:
            modes = "".join(str(msg.motor_state[i].mode) for i in LEG_JOINTS)
            max_tau = max(abs(msg.motor_state[i].tau_est) for i in LEG_JOINTS)
            keys = struct.unpack("H", bytes(msg.wireless_remote)[2:4])[0]
            l2r2 = "DOWN" if (keys >> L2) & 1 and (keys >> R2) & 1 else ""
            print(f"{datetime.now():%H:%M:%S}  | {name:13} | {msg.mode_machine:12} {msg.mode_pr:7} | "
                  f"{modes:24} | {max_tau:17.2f} | {l2r2}", flush=True)
        time.sleep(0.5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("stopped.")
