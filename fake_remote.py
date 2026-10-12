#!/usr/bin/env python3
"""
fake_remote.py - LAPTOP TEST ONLY. Pretends to be the robot's rt/lowstate on
DDS domain 1 / lo, so walk_trigger.py and salute_trigger.py can be tested
with no robot.

    python3 -u fake_remote.py                               # walker test: L1+R1+Y, legs in debug mode (0)
    python3 -u fake_remote.py --combo salute --leg-mode 1   # salute test: L1+R1+B, Unitree in charge (1)
    python3 -u fake_remote.py --combo hips --leg-mode 1     # motion_trigger test: L1+R1+A

Timeline (repeats every 12 s), shown for the chosen combo:
  0-3 s   no buttons
  3-3.5 s combo tapped briefly    -> should NOT trigger (too short)
  3.5-6 s no buttons
  6-8 s   combo held 2 s          -> should trigger ONCE
  8-9 s   L1+R1 only              -> should NOT trigger (third button missing)
  9-12 s  no buttons
"""
import argparse
import struct
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowState_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

R1, L1, A, B, Y = 0, 1, 8, 9, 11
COMBOS = {"walk": ((L1, R1, Y), "L1+R1+Y"), "salute": ((L1, R1, B), "L1+R1+B"),
          "hips": ((L1, R1, A), "L1+R1+A")}


def keys_to_remote(bits):
    keys = 0
    for b in bits:
        keys |= 1 << b
    data = bytearray(40)
    data[2:4] = struct.pack("H", keys)
    return list(data)


ap = argparse.ArgumentParser(description="Fake rt/lowstate for laptop tests (domain 1 / lo).")
ap.add_argument("--combo", choices=COMBOS, default="walk")
ap.add_argument("--leg-mode", type=int, choices=(0, 1), default=0,
                help="mode reported by the 12 leg motors: 0 = debug mode, 1 = Unitree in charge")
args = ap.parse_args()
combo, name = COMBOS[args.combo]

ChannelFactoryInitialize(1, "lo")
pub = ChannelPublisher("rt/lowstate", LowState_)
pub.Init()
pub_lf = ChannelPublisher("rt/lf/lowstate", LowState_)   # motion_trigger.py reads the low-rate copy
pub_lf.Init()
msg = unitree_hg_msg_dds__LowState_()
for i in range(12):
    msg.motor_state[i].mode = args.leg_mode

print(f"fake_remote: publishing rt/lowstate on domain 1 / lo, combo {name}, "
      f"leg mode {args.leg_mode} (Ctrl+C to stop)", flush=True)
start = time.time()
last_phase = None
while True:
    t = (time.time() - start) % 12
    if 3 <= t < 3.5:
        bits, phase = combo, f"tap {name} (0.5 s, should NOT trigger)"
    elif 6 <= t < 8:
        bits, phase = combo, f"hold {name} (2 s, should trigger once)"
    elif 8 <= t < 9:
        bits, phase = (L1, R1), "L1+R1 only (should NOT trigger)"
    else:
        bits, phase = (), "no buttons"
    if phase != last_phase:
        print(f"fake_remote: {phase}", flush=True)
        last_phase = phase
    msg.tick += 1
    msg.wireless_remote = keys_to_remote(bits)
    pub.Write(msg)
    pub_lf.Write(msg)
    time.sleep(0.02)
