#!/usr/bin/env python3
"""
remote_sniffer.py - READ-ONLY. Find out what each remote combo really does on
this robot. It never sends a command; it only reads.

Every time the set of held buttons changes it prints them, and every time the
robot's state changes it prints that too, so you can see which combo caused what:
  - buttons      (rt/lowstate wireless_remote)
  - FSM id       (LocoClient 7001: 0 zero torque, 1 damping, 801 run mode, 550 firmware motion, ...)
  - FSM mode     (LocoClient 7002)
  - balance mode (LocoClient 7003)
  - stand height (LocoClient 7005)
  - leg motor modes (1 = Unitree in charge, 0 = debug mode)

On the robot:
    python3 -u remote_sniffer.py | tee ~/sniff.log
Press one combo at a time, wait ~2 s, release, and note what you did.
"""
import json
import struct
import time
from datetime import datetime

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_
from unitree_sdk2py.g1.loco.g1_loco_client import LocoClient

# bit -> name inside wireless_remote[2:4] (same as KeyMap in unitree_rl_gym)
BUTTONS = ["R1", "L1", "START", "SELECT", "R2", "L2", "F1", "F3",
           "A", "B", "X", "Y", "UP", "RIGHT", "DOWN", "LEFT"]
GETTERS = {"FSM id": 7001, "FSM mode": 7002, "balance mode": 7003, "stand height": 7005}
POLL = 0.25


def log(msg):
    print(f"[{datetime.now():%H:%M:%S.%f}"[:-3] + f"] {msg}", flush=True)


class State:
    def __init__(self):
        self.keys = 0
        self.leg_modes = ""
        self.t = 0.0

    def on_lowstate(self, msg: LowState_):
        self.keys = struct.unpack("H", bytes(msg.wireless_remote)[2:4])[0]
        self.leg_modes = "".join(str(msg.motor_state[i].mode) for i in range(12))
        self.t = time.time()


def held(keys):
    names = [n for i, n in enumerate(BUTTONS) if keys & (1 << i)]
    return " + ".join(names) if names else "(nothing)"


def read(loco, api):
    try:
        code, data = loco._Call(api, "{}")
    except Exception as e:  # noqa: BLE001
        return f"err {e}"
    if code != 0:
        return f"code {code}"
    try:
        v = json.loads(data).get("data")
        return round(v, 3) if isinstance(v, float) else v
    except (ValueError, AttributeError):
        return data


def main():
    ChannelFactoryInitialize(0, "eth0")
    st = State()
    sub = ChannelSubscriber("rt/lowstate", LowState_)
    sub.Init(st.on_lowstate, 10)
    loco = LocoClient()
    loco.SetTimeout(1.0)
    loco.Init()
    for api in GETTERS.values():
        loco._RegistApi(api, 0)   # harmless if already registered

    log("remote_sniffer (read-only) running. Press combos one at a time. Ctrl+C to stop.")
    last_keys, last_legs, last = None, None, {}
    next_poll = 0.0
    while True:
        time.sleep(0.01)
        if st.t == 0.0:
            continue
        if st.keys != last_keys:
            log(f"BUTTONS: {held(st.keys)}")
            last_keys = st.keys
        if st.leg_modes != last_legs:
            log(f"   leg motor modes: {st.leg_modes}")
            last_legs = st.leg_modes
        if time.time() >= next_poll:
            next_poll = time.time() + POLL
            for name, api in GETTERS.items():
                v = read(loco, api)
                if last.get(name) != v:
                    log(f"   {name}: {last.get(name, '?')} -> {v}")
                    last[name] = v


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("stopped.")
