#!/usr/bin/env python3
"""
fake_remote.py - LAPTOP TEST ONLY. Pretends to be the robot's rt/lowstate on
DDS domain 1 / lo, so walk_trigger.py can be tested with no robot.

Timeline (repeats every 12 s):
  0-3 s   no buttons
  3-3.5 s L1+R1+Y tapped briefly  -> should NOT trigger (too short)
  3.5-6 s no buttons
  6-8 s   L1+R1+Y held 2 s        -> should trigger ONCE
  8-9 s   L1+R1 only              -> should NOT trigger (Y missing)
  9-12 s  no buttons
"""
import struct
import time

from unitree_sdk2py.core.channel import ChannelFactoryInitialize, ChannelPublisher
from unitree_sdk2py.idl.default import unitree_hg_msg_dds__LowState_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

R1, L1, Y = 0, 1, 11


def keys_to_remote(bits):
    keys = 0
    for b in bits:
        keys |= 1 << b
    data = bytearray(40)
    data[2:4] = struct.pack("H", keys)
    return list(data)


ChannelFactoryInitialize(1, "lo")
pub = ChannelPublisher("rt/lowstate", LowState_)
pub.Init()
msg = unitree_hg_msg_dds__LowState_()

print("fake_remote: publishing rt/lowstate on domain 1 / lo (Ctrl+C to stop)", flush=True)
start = time.time()
last_phase = None
while True:
    t = (time.time() - start) % 12
    if 3 <= t < 3.5:
        bits, phase = (L1, R1, Y), "tap L1+R1+Y (0.5 s, should NOT trigger)"
    elif 6 <= t < 8:
        bits, phase = (L1, R1, Y), "hold L1+R1+Y (2 s, should trigger once)"
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
    time.sleep(0.02)
