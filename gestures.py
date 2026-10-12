"""
gestures.py - arm gesture definitions shared by salute_trigger.py (robot)
and preview_salute.py (MuJoCo, laptop). No SDK or MuJoCo imports here.

Joint numbers are the G1 29-DOF motor order (same as rt/lowstate motor_state,
rt/arm_sdk motor_cmd, and the actuator order in unitree_mujoco's g1_29dof.xml).
Angles are radians.

Sign conventions (checked by rendering the 29-DOF model):
  shoulder_pitch  negative = arm forward/up      (-2.8 = overhead)
  shoulder_roll   left +, right -  = arm out to the side
  elbow           0 = forearm 90 deg forward, +1.57 = straight, negative = more bent
"""

JOINT_NAMES = [
    "left_hip_pitch", "left_hip_roll", "left_hip_yaw", "left_knee",
    "left_ankle_pitch", "left_ankle_roll",
    "right_hip_pitch", "right_hip_roll", "right_hip_yaw", "right_knee",
    "right_ankle_pitch", "right_ankle_roll",
    "waist_yaw", "waist_roll", "waist_pitch",
    "left_shoulder_pitch", "left_shoulder_roll", "left_shoulder_yaw", "left_elbow",
    "left_wrist_roll", "left_wrist_pitch", "left_wrist_yaw",
    "right_shoulder_pitch", "right_shoulder_roll", "right_shoulder_yaw", "right_elbow",
    "right_wrist_roll", "right_wrist_pitch", "right_wrist_yaw",
]
J = {name: i for i, name in enumerate(JOINT_NAMES)}

WAIST = [12, 13, 14]
LEFT_ARM = list(range(15, 22))
RIGHT_ARM = list(range(22, 29))
# The joints we send on rt/arm_sdk. Same set as Unitree's g1_arm7_sdk_dds_example.py:
# both arms + waist. Joints a gesture doesn't move are held where they were at the start.
ARM_SDK_JOINTS = WAIST + LEFT_ARM + RIGHT_ARM
ARM_SDK_WEIGHT_SLOT = 29   # motor_cmd[29].q = how much of the arms we take over (0..1)

# Arms hanging relaxed. Only used as the start pose for the MuJoCo preview;
# on the robot the gesture starts from wherever the arms really are.
REST = {
    J["left_shoulder_pitch"]: 0.2, J["left_shoulder_roll"]: 0.2, J["left_elbow"]: 1.2,
    J["right_shoulder_pitch"]: 0.2, J["right_shoulder_roll"]: -0.2, J["right_elbow"]: 1.2,
}

# Right hand at the forehead. Mesh clearance to the head/torso >= 2.6 cm in the model.
SALUTE = {
    J["right_shoulder_pitch"]: -1.2,
    J["right_shoulder_roll"]: -1.2,
    J["right_shoulder_yaw"]: 0.2,
    J["right_elbow"]: -0.7,
    J["right_wrist_roll"]: 0.0,
    J["right_wrist_pitch"]: 0.3,
    J["right_wrist_yaw"]: 0.0,
}

MAX_JOINT_SPEED = 1.0   # rad/s, peak speed of any joint during a move
MIN_MOVE_TIME = 1.2     # s, even small moves take at least this long
SALUTE_HOLD = 1.5       # s at the forehead
BLEND_IN = 1.0          # s to take the arms over from Unitree (arms hold still)
BLEND_OUT = 1.0         # s to hand them back


def move_time(a, b):
    """Duration so no joint exceeds MAX_JOINT_SPEED.
    Smoothstep peaks at 1.5x the average speed, hence the 1.5."""
    biggest = max(abs(b[j] - a[j]) for j in a)
    return max(MIN_MOVE_TIME, 1.5 * biggest / MAX_JOINT_SPEED)


def salute_plan(start):
    """start: {joint: q} for every joint in ARM_SDK_JOINTS (the robot's current pose).
    Returns [(duration, target_pose), ...] that ends back at start."""
    up = dict(start)
    up.update(SALUTE)
    return [(move_time(start, up), up), (SALUTE_HOLD, up), (move_time(up, start), start)]


def plan_length(plan):
    return sum(d for d, _ in plan)


def sample(plan, start, t):
    """Pose at time t, smoothstep between keyframes (zero speed at each keyframe)."""
    prev = start
    for dur, pose in plan:
        if t <= dur:
            s = t / dur
            s = s * s * (3 - 2 * s)
            return {j: prev[j] * (1 - s) + pose[j] * s for j in pose}
        t -= dur
        prev = pose
    return dict(prev)
