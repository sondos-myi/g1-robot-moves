# Walker (L1 + R1 + Y)

← Part of [g1-robot-moves](https://github.com/sondos-myi/g1-robot-moves): one move per branch. The `main` branch has the map.

Start the [unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym) RL walking policy on a **Unitree G1** straight from the robot's remote, **no laptop needed**.

A small listener runs on the robot's Jetson (PC2) as a systemd service. When you hold **L1 + R1 + Y**, it checks that it's safe and then launches `deploy_real.py`. After that, you drive the walker with the remote as usual.

> **Status (2026-10-05): parked.** It starts and walks with no laptop, but the robot doesn't keep its balance: the policy loop only reaches about 28 Hz on the Jetson. The service is still installed on the robot.

> ⚠️ **The robot must hang on a gantry/hoist while the walker starts.** The walker begins in zero torque, and debug mode switches off Unitree's balance controller. A standing robot **will fall**.

---

## Contents

| File | What it is |
|---|---|
| `walk_trigger.py` | The listener. It **only reads** `rt/lowstate` and never sends motor commands. On the combo, it runs the safety checks and starts the walker. |
| `g1_walk_trigger.service` | systemd unit that starts the listener at every boot. |
| `mode_probe.py` | Read-only diagnostic. Prints the robot's mode indicators twice a second (used to find out how to detect debug mode). |
| `fake_remote.py` | Laptop-only test publisher that fakes `rt/lowstate` button presses, so the listener can be tested with no robot. |

---

## How it works

```
remote ──► rt/lowstate ──► walk_trigger.py
                              │  L1+R1+Y held ≥ 1 s (then must be released before it can fire again)
                              │  check 1: no deploy_real.py already running (pgrep, any user)
                              │  check 2: debug mode → all 12 leg motors report mode 0
                              ▼
                 python3 -u deploy_real.py eth0 g1.yaml   (output → ~/walk.log)
```

If either check fails, it logs why and does nothing.

### How debug mode is detected (and why not `CheckMode`)
The first version asked Unitree's `MotionSwitcherClient.CheckMode()` and treated an empty mode name as debug mode. On our G1, **`CheckMode()` still reports `'ai'` after L2+R2**, so that check could never pass.

`mode_probe.py` showed what actually changes when you press L2+R2:

| | `CheckMode` name | `mode_machine` | `mode_pr` | leg `motor_state[0..11].mode` |
|---|---|---|---|---|
| normal (after boot) | `'ai'` | 4 | 0 | `111111111111` |
| after L2 + R2 | `'ai'` | 4 | 0 | `000000000000` |

So the listener now gates on **all 12 leg motor modes == 0**. Missing data or any `1` counts as **not safe**.

---

## Using it (no laptop)

1. Robot **hanging on the gantry**. Power it on and wait for the boot to finish.
2. 🎮 **L2 + R2** → debug mode (the robot goes limp in the rope).
3. 🎮 Hold **L1 + R1 + Y** for about 1–2 s → the walker starts.
4. 🎮 **start** → it moves to the default pose. Lower the hoist.
5. 🎮 **A** → it steps in place. The sticks make it walk.
6. To stop: pull the rope tight, then 🎮 **select** → damping, and the walker exits.

To walk again, repeat from step 2 or 3. Only one walker can run at a time.

Logs on the robot:
- `~/trigger.log`: the listener (combo detected, checks, walker started/exited)
- `~/walk.log`: the walker's own output

---

## Robot setup (what we added to the Jetson)

Everything was **added only**. No existing file, service, or launch file on the robot was changed.

**Environment:** G1 Jetson (PC2), Ubuntu 20.04, Python 3.8.10, `eth0` = 192.168.123.164.

1. **Walking policy:** [unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym), unmodified (commit `276801e`), copied to `~/unitree_rl_gym`. Not installed with pip; it runs with `PYTHONPATH=~/unitree_rl_gym`.
2. **Python packages** (user site `~/.local`, no sudo):
   ```bash
   pip install --user torch==2.4.1      # last version with cp38 aarch64 wheels
   pip install --user scipy==1.10.1     # apt scipy 1.3.3 crashes with numpy 1.24 (np.typeDict removed)
   ```
   `unitree_sdk2_python` was already on the robot (`~/unitree_sdk2_python`).
3. **This branch's files**, in `~/g1_walk_trigger` (every branch of this repo puts its files in that one folder on the robot):
   ```bash
   git clone -b walker https://github.com/sondos-myi/g1-robot-moves.git ~/g1_walk_trigger
   ```
4. **The service**, installed without overwriting anything:
   ```bash
   ls /etc/systemd/system/g1_walk_trigger.service      # must say "No such file"
   sudo cp -n ~/g1_walk_trigger/g1_walk_trigger.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now g1_walk_trigger
   systemctl status g1_walk_trigger --no-pager         # active (running)
   ```

> Don't run `apt --fix-broken install` on the Jetson: apt is in a broken state (chrony vs systemd-timesyncd), and "fixing" it could remove the robot's time sync.

### Service notes
- Runs as `unitree`, with `HOME` set so the `~/.local` packages are found.
- Waits for `eth0` to have an address before starting.
- `Restart=on-failure`: a crashed listener comes back after 5 s.
- **`KillMode=process`**: stopping or restarting the service stops **only the listener**. A walker it already started keeps running, so the robot never drops mid-walk because of the service.

### Uninstall (the robot goes back to exactly how it was)
```bash
sudo systemctl disable --now g1_walk_trigger
sudo rm /etc/systemd/system/g1_walk_trigger.service
sudo systemctl daemon-reload
```

---

## Testing

### On a laptop, no robot (DDS domain 1 on loopback)
```bash
# terminal 1
python3 -u fake_remote.py
# terminal 2
python3 -u walk_trigger.py --domain 1 --iface lo --dry-run
```
Expected: it fires **once** per 2 s hold (every 12 s). It ignores the 0.5 s tap and L1+R1 without Y. (The fake remote reports leg modes 0, so the debug-mode check passes.)

### On the robot, dry run (nothing moves)
Stop the service first so only one listener runs, then:
```bash
sudo systemctl stop g1_walk_trigger
python3 -u walk_trigger.py --dry-run
```
- Before L2+R2, the combo should give `Robot is in normal mode (leg motor modes 111111111111)… Not starting.`
- After L2+R2, the combo should give `DRY RUN: all checks passed; would start deploy_real.py now.`

Then run `sudo systemctl start g1_walk_trigger` again.

### Mode probe (read-only)
```bash
python3 -u mode_probe.py
```

### Flags
| Flag | Meaning |
|---|---|
| `--dry-run` | Do every check, but only print instead of starting the walker. |
| `--iface` | Network interface (robot: `eth0`). |
| `--domain` | DDS domain (robot: 0, sim/laptop test: 1). |
| `--skip-mode-check` | Skip the debug-mode check. **Refused on domain 0** (the real robot). |

---

## Running the walker by hand (without the listener)

On the Jetson:
```bash
pgrep -af deploy_real          # must be empty: only ONE walker at a time
cd ~/unitree_rl_gym/deploy/deploy_real
nohup env PYTHONPATH=~/unitree_rl_gym python3 -u deploy_real.py eth0 g1.yaml > ~/walk.log 2>&1 &
```
From a laptop on the robot's wired network, use its own interface instead, e.g. `deploy_real.py enp8s0 g1.yaml`. The policy then runs **on the laptop**, and pulling the cable makes the robot fall.

---

## Gotchas we hit
- **Use `python3 -u`** under nohup/systemd. Otherwise the output is buffered, the log looks empty, and it's tempting to launch the walker again (we once had 3 copies running).
- **One walker only.** `pgrep -af deploy_real` before starting one by hand. `pkill` would also kill copies started by other people logged in.
- **SSH drops kill foreground jobs.** Started by hand from an SSH session, a Wi-Fi drop would stop the listener *and* its walker. That's why it runs as a service (or under `nohup`).
- **L2+R2 only from the boot / zero-torque state.** Pressed while Unitree's controller has the robot standing, it may be ignored.
- The voice bot on the same robot uses **F1**. L1+R1+Y doesn't clash with it or with the other installed services.

## Credits
- Walking policy and `deploy_real.py`: [unitreerobotics/unitree_rl_gym](https://github.com/unitreerobotics/unitree_rl_gym) (BSD-3-Clause)
- SDK: [unitreerobotics/unitree_sdk2_python](https://github.com/unitreerobotics/unitree_sdk2_python)
