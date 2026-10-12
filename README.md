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
git clone -b <branch> https://github.com/sondos-myi/g1-robot-moves.git
```

## Two ways to move the G1

1. **Unitree stays in charge (recommended).** Unitree's controller keeps the robot balanced, and we either send only the arms (`rt/arm_sdk`, the salute) or ask the firmware to play one of its own motions (`SetFsmId(550xxx)`, hands on hips and the firmware moves). Nothing here commands the legs.
2. **Our own controller (debug mode).** L2 + R2 switches Unitree's controller off and an RL policy drives every motor (the walker). The robot is limp until the policy starts, so it must hang on a gantry.

## Shared facts about our robot

- Programs run on the **Jetson (PC2)**: Ubuntu 20.04, Python 3.8, `unitree_sdk2_python` in `~/unitree_sdk2_python`, internal network on `eth0` (192.168.123.164).
- Every branch puts its files in **`~/g1_walk_trigger`** on the robot, and each move has its own service and log (`~/trigger.log`, `~/salute.log`, `~/motion.log`).
- The main board (PC1) runs Unitree's controller and is locked.
- **Robot states (FSM id):** 0 zero torque, 1 damping, 4 standing/preparation, 500 walk mode, 801 run mode, 550 playing a firmware motion.
- **Debug vs normal:** all 12 leg motor modes are `1` while Unitree is in charge and `0` in debug mode. (`MotionSwitcherClient.CheckMode()` doesn't show the difference on our robot.)
- **The official remote manual is wrong for our firmware.** The measured button map is on the `firmware-moves` branch.
- The voice bot on the same robot uses **F1**. None of our combos clash with it.

## Ground rules on the robot

1. One person works on the robot at a time (`who` before you start).
2. Only **add** files and services. Don't edit Unitree's or the voice bot's.
3. First real run of anything new: **on the gantry**, with someone holding the remote.
4. Every branch has a laptop test with a fake robot (`fake_remote.py`, DDS domain 1 on `lo`). Run it before copying anything to the robot.
5. Never run `apt --fix-broken install` on the Jetson: apt is in a broken state, and "fixing" it could remove the robot's time sync.

## Credits

- Walking policy: [unitreerobotics/unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym) (BSD-3-Clause)
- SDK: [unitreerobotics/unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python)
