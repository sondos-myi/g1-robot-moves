# Hands on hips (L1 + R1 + A)

← Part of [g1-robot-moves](https://github.com/sondos-myi/g1-robot-moves): one move per branch. The `main` branch has the map.

Hold **L1 + R1 + A** for 1 s while the robot is in **run mode**, and it puts its hands on its hips for about 6 s, then goes back to run mode by itself.

The move is Unitree's own firmware motion **534 `vq_chayao`** (叉腰, hands on hips v2). Unitree's controller plays it and keeps the robot balanced. `motion_trigger.py` never commands a motor: it only reads the remote and calls `LocoClient.SetFsmId(550534)`.

> **Status (2026-10-11):** works on the real robot and is **installed as a service**, so it runs at every boot with no laptop.

---

## Files

| File | What it does |
|---|---|
| `motion_trigger.py` | Listens for L1 + R1 + A, checks it's safe, then plays motion 534. |
| `g1_motion_trigger.service` | Starts the listener at boot. Log: `~/motion.log`. |
| `fake_remote.py --combo hips` | Laptop-only fake robot pressing L1 + R1 + A. |

## When it plays, and when it refuses

On the combo it checks, in this order, and logs the reason if any check fails:
1. **Unitree is in charge:** all 12 leg motor modes are `1` (not debug mode).
2. **The RL walker isn't running** (no `deploy_real.py`).
3. **The FSM id is exactly 801** (run mode). Standing/preparation (4), walk mode (500), damping (1) and zero torque (0) are refused.

Then it calls `SetFsmId(550534)` and polls the FSM id until the robot is back at 801 (expected: `801 -> 550 -> 801`). Pressing the combo again while the motion plays does nothing. If the robot isn't back at 801 within 30 s, it logs a warning.

It reads the buttons from `rt/lf/lowstate`, the low-rate copy. Reading the 500 Hz `rt/lowstate` from Python takes most of a Jetson CPU core.

### Why L1 + R1 + A
- The only official Unitree combo inside it is L1 + A (damping), and on our firmware that does nothing (see the button map on the `firmware-moves` branch). On the robot, the firmware ignores L1 + R1 + A.
- A **double-tap** of A in run mode is a firmware shortcut (clap). The combo is a 1 s **hold**, so the two don't clash.
- Taken by other things: L1 + R1 + Y (walker), L1 + R1 + B (salute), F1 (voice bot).

---

## Laptop test (no robot)

```bash
# terminal 1: fake robot, Unitree in charge, pressing L1+R1+A
python3 -u fake_remote.py --combo hips --leg-mode 1
# terminal 2
python3 -u motion_trigger.py --domain 1 --iface lo --skip-fsm-check --dry-run
```
Expected: `DRY RUN: all checks passed; would call SetFsmId(550534)` once per 2 s hold. With `--leg-mode 0`, it refuses (debug mode).

`--skip-fsm-check` only works together with `--dry-run`, and it's refused on domain 0 (the real robot).

---

## Installing on the robot

Same ground rules as the salute guide (`salute` branch): one person at a time, only add files, first real runs on the gantry.

**1. Copy the files** (from your laptop, inside this repo):
```bash
ROBOT=192.168.1.38
ssh unitree@$ROBOT 'ls ~/g1_walk_trigger/motion_trigger.py'   # must say "No such file"
scp motion_trigger.py g1_motion_trigger.service unitree@$ROBOT:~/g1_walk_trigger/
```

**2. Dry run** (nothing is sent). Put the robot in run mode, then on the robot:
```bash
cd ~/g1_walk_trigger
python3 -u motion_trigger.py --dry-run
```
Hold L1 + R1 + A. Expected: `Leg modes 111111111111, FSM id 801: OK.` then `DRY RUN: all checks passed`. **The robot itself must do nothing.** If it moves or beeps on the combo, stop: the firmware uses it.

**3. Real run, on the gantry first, then on the floor:**
```bash
python3 -u motion_trigger.py
```
Expected: `Playing hands on hips (534 vq_chayao): SetFsmId(550534).` then `Motion done in ~6 s (FSM 801 -> 550 -> 801).`

**4. Install the service:**
```bash
ls /etc/systemd/system/g1_motion_trigger.service      # must say "No such file"
sudo cp -n ~/g1_walk_trigger/g1_motion_trigger.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now g1_motion_trigger
```
Then reboot and test it with no laptop connected.

## Checking it

```bash
systemctl status g1_motion_trigger --no-pager    # active (running)
tail -f ~/motion.log                             # combos, checks, motions played
```
A healthy start looks like `motion_trigger ready. Hold L1 + R1 + A for 1 s -> hands on hips (534 vq_chayao).`

To test by hand, stop the service first so only one listener runs: `sudo systemctl stop g1_motion_trigger`.

## Undo

```bash
sudo systemctl disable --now g1_motion_trigger
sudo rm /etc/systemd/system/g1_motion_trigger.service
sudo systemctl daemon-reload
rm ~/g1_walk_trigger/motion_trigger.py ~/g1_walk_trigger/g1_motion_trigger.service
```

---

## Using a different firmware motion

Change `MOTION_ID` and `MOTION_NAME` at the top of `motion_trigger.py` (for example `543` = built-in salute). The motion list is on the `firmware-moves` branch. For a second combo, copy the script with a different `COMBO` and its own service and log, and pick a combo that's free in the button map.

## Robot results

| Date | Result |
|---|---|
| 2026-10-11 | Dry run on the robot: `Leg modes 111111111111, FSM id 801: OK`. The firmware ignored the combo. |
| 2026-10-11 | Real run worked. Installed as `g1_motion_trigger.service`; works on its own after boot, no laptop. |
