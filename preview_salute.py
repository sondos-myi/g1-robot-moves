#!/usr/bin/env python3
"""
preview_salute.py - LAPTOP ONLY. Shows the salute in the MuJoCo viewer, with the
same joint targets and timing that salute_trigger.py sends to the robot.

The robot is posed frame by frame (no physics, legs frozen standing), so this
shows what the arms do, not how the robot balances.

    python3 preview_salute.py
    python3 preview_salute.py --model ~/unitree_mujoco/unitree_robots/g1/scene_29dof.xml

Needs: pip install --user mujoco   (the Jetson doesn't need this file)
"""
import argparse
import os
import time

import mujoco
import mujoco.viewer

import gestures as G
from gestures import BLEND_IN, BLEND_OUT

STANCE = {"left_hip_pitch": -0.1, "left_knee": 0.3, "left_ankle_pitch": -0.2,
          "right_hip_pitch": -0.1, "right_knee": 0.3, "right_ankle_pitch": -0.2}
PELVIS_HEIGHT = 0.76
PAUSE = 1.5   # s between repeats


def set_pose(model, data, arm_pose):
    data.qpos[:] = 0
    data.qpos[2] = PELVIS_HEIGHT
    data.qpos[3] = 1.0   # upright quaternion
    for name, q in STANCE.items():
        data.qpos[model.joint(name + "_joint").qposadr] = q
    for j, q in arm_pose.items():
        data.qpos[model.joint(G.JOINT_NAMES[j] + "_joint").qposadr] = q
    mujoco.mj_forward(model, data)


def main():
    ap = argparse.ArgumentParser(description="Preview the salute in MuJoCo.")
    ap.add_argument("--model", default=os.path.expanduser(
        "~/unitree_mujoco/unitree_robots/g1/scene_29dof.xml"))
    args = ap.parse_args()

    model = mujoco.MjModel.from_xml_path(args.model)
    data = mujoco.MjData(model)

    start = {j: G.REST.get(j, 0.0) for j in G.ARM_SDK_JOINTS}
    plan = G.salute_plan(start)
    cycle = BLEND_IN + G.plan_length(plan) + BLEND_OUT + PAUSE
    print(f"Salute: {G.plan_length(plan):.1f} s of motion, "
          f"{BLEND_IN + G.plan_length(plan) + BLEND_OUT:.1f} s with the blend in/out "
          f"(the arms don't move during the blend). Close the window to quit.")

    with mujoco.viewer.launch_passive(model, data) as viewer:
        viewer.cam.lookat[:] = [0, 0, 0.95]
        viewer.cam.distance = 2.2
        viewer.cam.azimuth = 155
        viewer.cam.elevation = -8
        t0 = time.monotonic()
        while viewer.is_running():
            t = (time.monotonic() - t0) % cycle - BLEND_IN
            if 0 <= t <= G.plan_length(plan):
                set_pose(model, data, G.sample(plan, start, t))
            else:
                set_pose(model, data, start)
            viewer.sync()
            time.sleep(1 / 60)


if __name__ == "__main__":
    main()
