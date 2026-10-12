# g1-robot-moves

Moves for our **Unitree G1** humanoid (29 DOF, firmware 1.5.6), started from the robot's own remote with **no laptop needed**.

Each move lives on **its own branch**, with its code, its systemd service and a README that explains how it works, how to install it safely, and what was tested on the real robot. This `main` branch is only the map.

## Branches

| Branch | What it does | Remote | Robot state needed | Status (2026-10-11) |
|---|---|---|---|---|
| [`walker`](../../tree/walker) | Starts the unitree_rl_gym RL walking policy | hold **L1 + R1 + Y** | debug mode (robot on a gantry) | Works with no laptop, but the robot doesn't balance (policy only ~28 Hz on the Jetson). **Parked.** |
| [`salute`](../../tree/salute) | Right-hand salute on `rt/arm_sdk` while Unitree keeps balancing | hold **L1 + R1 + B** | run mode (801), standing or walking | Passed every robot test. Service **not** installed yet. |
| [`hands-on-hips`](../../tree/hands-on-hips) | Plays Unitree's built-in motion 534 (hands on hips, ~6 s) | hold **L1 + R1 + A** | run mode (801) | **Live** on the robot as a service. |
| [`firmware-moves`](../../tree/firmware-moves) | The 79 built-in firmware motions (dances, greetings, gestures), the remote's real button map, and read-only sniffer tools | – | run mode (801) | 3 motions confirmed, 7 more played. Reference + tools. |

To get one branch:
```bash
git clone -b salute https://github.com/sondos-myi/g1-robot-moves.git
```

## Two ways to move the G1

1. **Unitree stays in charge (recommended).** Unitree's controller keeps the robot balanced, and we either send only the arms (`rt/arm_sdk`, the salute) or ask the firmware to play one of its own motions (`SetFsmId(550xxx)`, hands on hips and the firmware moves). Nothing here commands the legs.
2. **Our own controller (debug mode).** L2 + R2 switches Unitree's controller off and an RL policy drives every motor (the walker). The robot is limp until the policy starts, so it must hang on a gantry.

## On the robot

All branches install into **`~/g1_walk_trigger`** on the Jetson. Each move runs as its own service with its own log:

| Branch | Service | Log |
|---|---|---|
| `walker` | `g1_walk_trigger` | `~/trigger.log` (+ `~/walk.log`) |
| `salute` | `g1_salute_trigger` (not installed) | `~/salute.log` |
| `hands-on-hips` | `g1_motion_trigger` | `~/motion.log` |

**FSM ids** (LocoClient API 7001): 0 zero torque · 1 damping · 4 standing · 500 walk mode · 801 run mode · 550 playing a firmware motion.

**Debug mode check:** all 12 leg motor modes are `1` while Unitree is in charge, `0` in debug mode. Every trigger checks this before it does anything; `CheckMode()` doesn't show the difference on our robot.

**Testing a change:** run the branch's laptop test first (`fake_remote.py`, DDS domain 1 on `lo`), then the dry run on the robot, then the gantry.

## Credits

- Walking policy: [unitreerobotics/unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym) (BSD-3-Clause)
- SDK: [unitreerobotics/unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python)
