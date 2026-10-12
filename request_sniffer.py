#!/usr/bin/env python3
"""
request_sniffer.py - READ-ONLY. Shows every "do something" request sent to
Unitree's services on the robot's internal network, and WHICH program sent it.

Question it answers: when a remote double-tap (or the phone app) makes the robot
move, does a request travel over the network (then we can see who sends it and
what it says), or does the main board (PC1) do it internally (then nothing shows)?

It listens on:
    rt/api/sport/request            (LocoClient: FSM ids, SetFsmId 550xxx moves, walking)
    rt/api/arm/request              (arm actions: wave, shake hand, ...)
    rt/api/motion_switcher/request  (mode switching)
    rt/api/voice/request            (speech / TTS)
and also prints every button change (from the low-rate rt/lf/lowstate), so presses and requests line up.

It never sends anything. Do NOT run remote_sniffer.py at the same time
(it polls the FSM id, which would show up here as requests).

On the robot:
    python3 -u request_sniffer.py | tee ~/requests.log
"""
import struct
import time
from datetime import datetime

from cyclonedds.builtin import BuiltinDataReader, BuiltinTopicDcpsParticipant, BuiltinTopicDcpsPublication
from unitree_sdk2py.core.channel import ChannelFactory, ChannelFactoryInitialize, ChannelSubscriber
from unitree_sdk2py.idl.unitree_api.msg.dds_ import Request_
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

TOPICS = ["rt/api/sport/request", "rt/api/arm/request",
          "rt/api/motion_switcher/request", "rt/api/voice/request"]
BUTTONS = ["R1", "L1", "START", "SELECT", "R2", "L2", "F1", "F3",
           "A", "B", "X", "Y", "UP", "RIGHT", "DOWN", "LEFT"]


def log(msg):
    print(f"[{datetime.now():%H:%M:%S.%f}"[:-3] + f"] {msg}", flush=True)


def held(keys):
    names = [n for i, n in enumerate(BUTTONS) if keys & (1 << i)]
    return " + ".join(names) if names else "(nothing)"


class Who:
    """Maps DDS writers to the program (process name / pid / host) that owns them."""

    def __init__(self, participant):
        self.pubs = BuiltinDataReader(participant, BuiltinTopicDcpsPublication)
        self.parts = BuiltinDataReader(participant, BuiltinTopicDcpsParticipant)
        self.programs = {}   # participant key -> "name pid@host"
        self.writers = {}    # topic -> set of programs
        self.next_scan = 0.0

    def _describe(self, qos):
        props = {}
        for policy in qos:
            if type(policy).__name__ == "Property":
                props[policy.key] = policy.value
        if props:
            return (f"{props.get('__ProcessName', '?')} pid {props.get('__Pid', '?')}"
                    f" @ {props.get('__Hostname', '?')}")
        return str(qos)[:80]

    def scan(self):
        if time.time() < self.next_scan:
            return
        self.next_scan = time.time() + 1.0
        for p in self.parts.take(N=200):
            try:
                self.programs[str(p.key)] = self._describe(p.qos)
            except Exception:  # noqa: BLE001
                pass
        for w in self.pubs.take(N=200):
            if w.topic_name not in TOPICS:
                continue
            prog = self.programs.get(str(w.participant_key), f"participant {w.participant_key}")
            known = self.writers.setdefault(w.topic_name, set())
            if prog not in known:
                known.add(prog)
                log(f"   SENDER on {w.topic_name}: {prog}")


def main():
    ChannelFactoryInitialize(0, "eth0")
    participant = ChannelFactory()._ChannelFactory__participant
    who = Who(participant)

    keys = {"v": None}

    def on_lowstate(msg: LowState_):
        k = struct.unpack("H", bytes(msg.wireless_remote)[2:4])[0]
        if k != keys["v"]:
            keys["v"] = k
            log(f"BUTTONS: {held(k)}")

    def make_handler(topic):
        short = topic.split("/")[2]
        def handler(req: Request_):
            log(f">> REQUEST to '{short}': api_id {req.header.identity.api_id}  "
                f"parameter {req.parameter!r}")
        return handler

    subs = [ChannelSubscriber("rt/lf/lowstate", LowState_)]   # low-rate copy: much lighter than rt/lowstate
    subs[0].Init(on_lowstate, 10)
    for t in TOPICS:
        s = ChannelSubscriber(t, Request_)
        s.Init(make_handler(t), 10)
        subs.append(s)

    log("request_sniffer (read-only) running. Senders are listed as they are discovered. Ctrl+C to stop.")
    while True:
        who.scan()
        time.sleep(0.05)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("stopped.")
