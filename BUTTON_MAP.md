# The remote's real button map (our G1, firmware 1.5.6)

**The official remote manual (V1.1) is wrong for our robot.** Most of its L1 combos do nothing on our firmware. This page lists what we measured on 2026-10-11 with `remote_sniffer.py`, plus every combo our own programs use.

## FSM ids (the robot's state, read with LocoClient API 7001)

| FSM id | State |
|---|---|
| 0 | Zero torque |
| 1 | Damping |
| 4 | Standing / preparation |
| 500 | Walk mode |
| 801 | Run mode (all our moves start from here) |
| 550 | Playing a firmware motion (goes back to 801 by itself) |

## What Unitree's firmware does (measured)

| State | Buttons | Result |
|---|---|---|
| Damping (1) | **L2 + UP** | Stands up → 4 |
| Standing (4) | **L2 + B** | Damping → 1 |
| Run mode (801) | L2 + B | Nothing |
| Run mode (801) | **double-tap A** | Clap |
| Run mode (801) | **double-tap X** | Air kiss |
| Run mode (801) | **double-tap Y** | ~4.9 s motion (left-hand wave?) |
| Run mode (801) | **double-tap B** | ~23 s motion (a dance?) |
| Run mode (801) | single tap of A / B / X / Y | Nothing |
| Standing (4) and run mode (801) | L1 + UP / LEFT / RIGHT / DOWN / X / Y / A / B | **Nothing.** The manual says L1+B = zero torque and L1+A = damping; neither happens. |
| Zero torque, after boot | L2 + R2 | Debug mode (legs limp, leg motor modes `0`). Used by the RL walker. |

- **The double-tap shortcuts live inside the main board (PC1).** While they played, `request_sniffer.py` saw no request on any service topic, so no program we can read sends them. They might be configurable in the phone app (not checked).
- Not explained yet: once, the robot went 4 → 1 → 4 → 500 → 801 with no remote buttons pressed (maybe the phone app).

## Combos our programs use

| Combo | Program | Needs | Status (2026-10-11) |
|---|---|---|---|
| L1 + R1 + **Y** (hold 1 s) | `walk_trigger.py` (`walker` branch) | debug mode | Service installed; walker parked (balance problem) |
| L1 + R1 + **B** (hold 1 s) | `salute_trigger.py` (`salute` branch) | run mode | Works, but its service isn't installed |
| L1 + R1 + **A** (hold 1 s) | `motion_trigger.py` (`hands-on-hips` branch): motion 534 | run mode | Service installed, works |
| **F1** | voice bot (unitree_converse / Nashmi_Bot) | – | Running |
| F1 + START | previous team's `yaokong` program on the Jetson: "remote mode" | – | Its binary `g1_action_yaokong` is missing |
| SELECT + F1 + F3 | `yaokong`: runs `~/unitree_dance/run_g1_tracking.sh` | – | That script is missing |

**Free for new moves:** any combo not in these tables. Use a **hold**, not a double-tap, so it can't clash with the firmware shortcuts.

---

## The tools (both read-only, run on the robot)

| Tool | What it shows |
|---|---|
| `remote_sniffer.py` | Every change in held buttons, FSM id/mode (7001/7002), balance mode (7003), stand height (7005) and leg motor modes. Press one combo at a time and watch what changes. |
| `request_sniffer.py` | Every request sent to Unitree's sport, arm, motion_switcher and voice services, and **which program sent it**, next to the button presses. Answers "does this button make some program send a command, or is it inside PC1?" |

```bash
python3 -u remote_sniffer.py  | tee ~/sniff.log
python3 -u request_sniffer.py | tee ~/requests.log
```

> ⚠️ **Run only one at a time.** `remote_sniffer.py` reads the 500 Hz `rt/lowstate`. With two Python sniffers on it, the Jetson got so overloaded that SSH logged in but hung, and the robot had to be rebooted. Also, `remote_sniffer.py` polls the FSM id, and those polls would show up in `request_sniffer.py` as requests.
