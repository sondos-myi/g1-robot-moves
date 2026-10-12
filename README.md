# Salute (L1 + R1 + B)

← Part of [g1-robot-moves](https://github.com/sondos-myi/g1-robot-moves): one move per branch. The `main` branch has the map.

Hold **L1 + R1 + B** while the robot stands or walks under Unitree's own controller, and it salutes with its right hand. Only the arms are sent (`rt/arm_sdk`), so Unitree keeps balancing.

## Putting the salute on the robot (safely)

This guide is for anyone on the team installing the **salute** (`salute` branch) on our G1. Follow it top to bottom. Every step **adds** something. Nothing on the robot gets edited or deleted, and each part can be undone (see [Undo](#undo-everything)).

> **Status (2026-10-11):** stages A–D below have **passed on the real robot**. The salute works standing and while walking (the robot stops, salutes, then keeps walking). The files are on the robot in `~/g1_walk_trigger`, but **the service (section 6) is not installed**, so the salute only works when someone starts `salute_trigger.py` by hand. Details in [Robot test results](#robot-test-results).

---

## What you're installing

| File | On the robot? | What it does |
|---|---|---|
| `salute_trigger.py` | yes | Listens for **L1 + R1 + B** (held 1 s). If it's safe, it plays the salute on `rt/arm_sdk`. |
| `gestures.py` | yes | The salute's joint angles, speed limit and timing. Used by the trigger and the preview. |
| `arm_sdk_monitor.py` | yes | Read-only. Shows what's being sent on `rt/arm_sdk`. |
| `g1_salute_trigger.service` | yes | Starts the salute listener at boot. |
| `preview_salute.py` | no (laptop) | Shows the salute in MuJoCo. |
| `fake_remote.py` | no (laptop) | Fake robot for laptop tests. |

### How the salute stays balanced
Unitree's own controller keeps the robot standing or walking the whole time. The salute only sends **arm and waist** targets on `rt/arm_sdk`, the same way Unitree's `g1_arm7_sdk_dds_example.py` does, and never touches the legs. Only the right arm moves. The left arm and waist are held where they were.

1. **Take over:** over 1 s, the blend weight goes 0 → 1 while the arms are held still.
2. **Salute:** hand to the forehead (no joint faster than 1 rad/s), hold 1.5 s, then back to the starting pose.
3. **Hand back:** over 1 s, the blend weight goes 1 → 0, and Unitree has the arms again.

### When it refuses to salute (and logs why)
- The robot is in **debug mode** (L2+R2), so Unitree's controller isn't balancing. Leg motor modes are not all `1`.
- The robot is in **zero torque or damping** (Unitree FSM id 0 or 1), or the FSM id can't be read.
- The **RL walker** (`deploy_real.py`) is running.

### When it stops halfway (arms handed back to Unitree over 0.5 s)
- Robot data (`rt/lowstate`) stops arriving for more than 0.25 s.
- The legs switch to debug mode mid-salute.
- Ctrl+C, or `systemctl stop` / SIGTERM.

### It doesn't clash with the walker
| | Walker (`g1_walk_trigger`) | Salute (`g1_salute_trigger`) |
|---|---|---|
| Combo | L1 + R1 + **Y** | L1 + R1 + **B** |
| Needs | debug mode (leg modes `0`) | Unitree in charge (leg modes `1`) |
| Moves | the whole robot (RL policy) | right arm only |

The two need opposite modes, so at most one of them can ever act. The voice bot uses **F1**.

---

## Ground rules
1. **One person works on the robot at a time.** Before starting anything, check who's logged in (`who`) and what's running (step 3).
2. **Only add.** Don't overwrite files you didn't create. Don't edit the voice bot or Unitree's services.
3. **Never run `apt --fix-broken install` on the Jetson.** apt is in a broken state (chrony vs systemd-timesyncd), and "fixing" it could remove the robot's time sync.
4. **First real runs happen on the gantry**, with someone holding the remote.
5. **Never type the sudo password into a script or a file.** Type it only when `sudo` asks.

---

## 1. On your laptop: get the branch and test it

```bash
git clone -b salute https://github.com/sondos-myi/g1-robot-moves.git g1-salute
cd g1-salute
```

You need [unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python) installed. The preview also needs `pip install --user mujoco` and [unitree_mujoco](https://github.com/unitreerobotics/unitree_mujoco) in `~/unitree_mujoco`.

**a) Watch the salute** (optional):
```bash
python3 preview_salute.py
```

**b) Test the listener against a fake robot.** Use three terminals, all inside `g1-salute`:
```bash
# terminal 1: fake robot, Unitree in charge (leg mode 1), pressing L1+R1+B
python3 -u fake_remote.py --combo salute --leg-mode 1
# terminal 2: watch what gets sent
python3 -u arm_sdk_monitor.py --domain 1 --iface lo
# terminal 3: the listener (laptop test mode)
python3 -u salute_trigger.py --domain 1 --iface lo --skip-fsm-check
```
What you should see, in a cycle that repeats every 12 s:
- The 0.5 s tap and "L1+R1 only" do nothing.
- The 2 s hold gives **one** salute. In terminal 2, the weight goes 0 → 1, the right arm goes to about `[-1.20 -1.20 +0.20 -0.70 +0.00 +0.30 +0.00]` and comes back, then the weight returns to 0.
- If you restart terminal 1 with `--leg-mode 0`, the listener says `Unitree's controller is not in charge (debug mode?). Not saluting.`
- If you stop terminal 1 mid-salute, you get `SAFETY STOP: rt/lowstate stopped arriving`.

`--skip-fsm-check` only exists for this test, because there's no Unitree loco service on a laptop. It's **refused on the real robot** (domain 0).

---

## 2. Connect to the robot

Either:
- **Ethernet:** plug into the robot and give your laptop `192.168.123.99/24` (any free `192.168.123.x`). Then `ssh unitree@192.168.123.164`.
- **Wi-Fi:** be on the same network as the robot. It is `192.168.1.38` on "TCF Main 5Ghz" (it was `192.168.1.196` before, so it can change). Then `ssh unitree@192.168.1.38`.

---

## 3. Look before you copy

On the robot:
```bash
who                                                  # anyone else logged in? agree who's driving
pgrep -af "deploy_real|walk_trigger|salute_trigger"  # what's running now
ls ~/g1_walk_trigger                                 # what's already installed
ls ~/g1_walk_trigger/salute_trigger.py ~/g1_walk_trigger/gestures.py   # should say "No such file"
```
- If the salute files **already exist**, someone has installed them. Compare them with yours (`diff`) instead of copying over them.
- The walker's `walk_trigger.py` (`walker` branch) and its service keep running while you add files. Adding new files doesn't affect them.

---

## 4. Copy the new files

Run this from **your laptop**, inside `g1-salute`. Replace `ROBOT` with the robot's IP.
```bash
ROBOT=192.168.1.38
# 1) make sure none of these exist yet (each should say "No such file")
ssh unitree@$ROBOT 'cd ~/g1_walk_trigger && ls salute_trigger.py gestures.py arm_sdk_monitor.py g1_salute_trigger.service'
# 2) copy only the new files
scp salute_trigger.py gestures.py arm_sdk_monitor.py g1_salute_trigger.service unitree@$ROBOT:~/g1_walk_trigger/
```
Don't copy `walk_trigger.py` or `fake_remote.py`. The robot doesn't need anything new from them.

Check it on the robot:
```bash
cd ~/g1_walk_trigger
python3 -c "import gestures, salute_trigger; print('imports OK')"
python3 salute_trigger.py --help
```

---

## 5. Test on the robot, in stages

Make sure the service isn't installed yet, so only **your** copy runs. Do each stage in order, and don't skip a stage that didn't pass.

### Stage A: is anything else using the arms? (read-only, any robot state)
```bash
python3 -u arm_sdk_monitor.py
```
It should print `silent` every 0.5 s. If it shows messages, something else on the robot uses `rt/arm_sdk` (for example, a voice-bot gesture playing). **Stop and find out what it is before going on.**

### Stage B: dry run (sends nothing to the arms)
Hang the robot on the gantry and power it on. In one SSH terminal:
```bash
python3 -u salute_trigger.py --dry-run
```
Hold **L1 + R1 + B** for about 1–2 s in each of these states, and note what it prints:

| Robot state | Expected |
|---|---|
| Just booted (zero torque) | `Robot FSM id 0 (zero torque)… Not saluting.` |
| After L2+R2 (debug mode) | `Leg motor modes 000000000000 … Not saluting.` |
| Standing under Unitree's control (your usual remote sequence) | `Leg modes 111111111111, FSM id 801: OK.` then `DRY RUN: all checks passed` |

801 is run mode. See [Robot test results](#robot-test-results).

Also watch the robot while you press L1+R1+B: **Unitree's controller itself should do nothing.** If the robot reacts to that combo (moves or beeps), stop. We'd need a different combo.

If you get `Could not read the robot's FSM id`, the check can't confirm the robot is safe, so it refuses. Don't work around it. Report what it printed.

### Stage C: first real salute (on the gantry)
- The robot is standing under Unitree's control, still on the gantry with a little slack in the rope.
- One person holds the remote. Nobody stands within arm's reach of the right arm.

Use two SSH terminals:
```bash
# terminal 1
python3 -u arm_sdk_monitor.py
# terminal 2
python3 -u salute_trigger.py
```
Hold **L1 + R1 + B**. The right hand should rise slowly to the forehead, hold, and come back, about 7–9 s in total. **Ctrl+C in terminal 2** stops it, and the arms are handed back to Unitree within 0.5 s.

### Stage D: on the ground
Same as stage C, but with the robot standing on the floor and a spotter. After that, try it while the robot walks slowly.

---

## 6. Install the service (salute available at every boot)

Only do this after stage D passes. On the robot:
```bash
ls /etc/systemd/system/g1_salute_trigger.service      # must say "No such file"
sudo cp -n ~/g1_walk_trigger/g1_salute_trigger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now g1_salute_trigger
systemctl status g1_salute_trigger --no-pager         # active (running)
tail -f ~/salute.log                                   # the listener's log
```
`cp -n` never overwrites an existing file.

To test by hand again later, stop the service first: `sudo systemctl stop g1_salute_trigger`. Stopping it mid-salute is safe, because the arms are handed back before it exits.

---

## Robot test results

| Stage | Result |
|---|---|
| A: arm_sdk monitor | **Passed (2026-10-05).** One short burst right at the start (200–240 msg/s, weight 0.38 → 0, then silent), most likely Unitree releasing the arms after a mode switch. A rerun while idle was silent. Rule: don't trigger the salute during a mode switch or a built-in gesture. |
| B: dry run | **Passed (2026-10-05)** in run mode: `Leg modes 111111111111, FSM id 801`. |
| C: gantry | **Passed (2026-10-05).** The salute fired correctly with the robot standing. |
| D: ground | **Passed (2026-10-06)**, standing and while walking. While walking, the robot stops, salutes, then keeps walking. That's the behaviour we want. |
| Retune | **2026-10-06.** With the first angles the hand stopped at the chin (gravity sag; the sim showed the forehead). New `SALUTE`: shoulder pitch −1.2, elbow −0.7. The hand is higher now, with a small gap between hand and head. The robot runs this version (its old copy is `gestures.py.bak`). |
| 6: service | **Not installed** (checked 2026-10-11): `g1_salute_trigger` isn't running on the robot. |

**FSM ids on our firmware:** 801 = run mode (the salute was tested here), 4 = standing/preparation, 500 = walk mode, 0 = zero torque, 1 = damping.

Firmware 1.5.6 also has a built-in salute: motion **543 `vq_jingli`** (`SetFsmId(550543)`, 4.1 s, played on the robot 2026-10-06). Unitree's controller plays it with the whole body, so it may replace this custom one.

---

## Undo everything

```bash
# remove the service (only if you installed it)
sudo systemctl disable --now g1_salute_trigger
sudo rm /etc/systemd/system/g1_salute_trigger.service
sudo systemctl daemon-reload
# remove the files this branch added
cd ~/g1_walk_trigger && rm salute_trigger.py gestures.py arm_sdk_monitor.py g1_salute_trigger.service
```
After that, the robot is exactly as it was before. The walker isn't affected.

---

## Troubleshooting

| Message | Meaning |
|---|---|
| `No rt/lowstate data yet` | Wrong network interface (the robot uses `eth0`), or the robot is off. |
| `Leg motor modes 000000000000` | Debug mode. Reboot the robot (or use the RL walker instead). |
| `Robot FSM id 0 / 1` | Zero torque or damping. Stand the robot up with the remote first. |
| `Could not read the robot's FSM id` | Unitree's loco service didn't answer. Don't bypass it; report it. |
| `The RL walker (deploy_real.py) is running` | Stop the walker first (select on the remote). |
| `SAFETY STOP: …` | It stopped mid-salute and gave the arms back. Read the reason. |

## Tuning (in `gestures.py`)
- `SALUTE`: the target angles of the right arm.
- `MAX_JOINT_SPEED` (1.0 rad/s): raise it slowly, and only after the robot runs have passed.
- `SALUTE_HOLD`, `BLEND_IN`, `BLEND_OUT`: timings.

After any change, run `preview_salute.py` and the fake-remote test on the laptop before copying the change to the robot.
