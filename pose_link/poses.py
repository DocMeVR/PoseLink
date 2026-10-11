"""Test poses: the built-in library, poses the user saved, and the pose reel on the timeline."""
import json
import math

import bpy
from mathutils import Matrix, Quaternion, Vector

from . import bone_names

REEL_NAME = "PoseLink Reel"
OLD_REEL_NAMES = ("OPL_PoseReel",)   # made by the add-on's first version

# Built-in poses, written for a character that faces -Y with its left side at +X and up at +Z
# (they are turned to the real character's facing). Keys are humanoid roles, values [axis, degrees] pairs:
#   X +deg bends forward or tips the head down, Z +deg turns to the character's left, Y +deg tilts to its left.
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
ARMS_DOWN = {"LeftUpperArm": [[Y, 75]], "RightUpperArm": [[Y, -75]],
             "LeftLowerArm": [[Z, -10]], "RightLowerArm": [[Z, 10]]}
POSES = {
    "Rest": {},
    "Idle (arms down)": ARMS_DOWN,
    "A-pose": {"LeftUpperArm": [[Y, 40]], "RightUpperArm": [[Y, -40]]},
    "Head down": {"_base": "Idle (arms down)", "Neck": [[X, 15]], "Head": [[X, 25]]},
    "Head up": {"_base": "Idle (arms down)", "Neck": [[X, -10]], "Head": [[X, -25]]},
    "Head turn left": {"_base": "Idle (arms down)", "Neck": [[Z, 15]], "Head": [[Z, 40]]},
    "Head turn right": {"_base": "Idle (arms down)", "Neck": [[Z, -15]], "Head": [[Z, -40]]},
    "Head tilt left": {"_base": "Idle (arms down)", "Neck": [[Y, 10]], "Head": [[Y, 20]]},
    "Head tilt right": {"_base": "Idle (arms down)", "Neck": [[Y, -10]], "Head": [[Y, -20]]},
    "Look down left": {"_base": "Idle (arms down)", "Neck": [[X, 10], [Z, 10]], "Head": [[X, 20], [Z, 30]]},
    "Shrug": {"_base": "Idle (arms down)", "LeftShoulder": [[Y, -15]], "RightShoulder": [[Y, 15]]},
    "Arms forward": {"LeftUpperArm": [[Z, -80]], "RightUpperArm": [[Z, 80]]},
    "Arms up": {"LeftUpperArm": [[Y, -70]], "RightUpperArm": [[Y, 70]]},
    "Arms crossed": {"LeftUpperArm": [[Y, 45], [Z, -60]], "RightUpperArm": [[Y, -45], [Z, 60]],
                     "LeftLowerArm": [[Z, -90]], "RightLowerArm": [[Z, 90]]},
    "Hand wave": {"_base": "Idle (arms down)", "RightUpperArm": [[Y, 40]], "RightLowerArm": [[Y, 70]]},
    "Lean forward": {"_base": "Idle (arms down)", "Spine": [[X, 15]], "Chest": [[X, 15]]},
    "Lean back": {"_base": "Idle (arms down)", "Spine": [[X, -10]], "Chest": [[X, -10]]},
    "Twist": {"_base": "Idle (arms down)", "Spine": [[Z, 15]], "Chest": [[Z, 15]]},
    "Side bend": {"_base": "Idle (arms down)", "Spine": [[Y, 10]], "Chest": [[Y, 10]]},
    "Walk": {"_base": "Idle (arms down)", "LeftUpperLeg": [[X, -35]], "LeftLowerLeg": [[X, 25]],
             "RightUpperLeg": [[X, 20]]},
    "Sit": {"_base": "Idle (arms down)", "LeftUpperLeg": [[X, -90]], "RightUpperLeg": [[X, -90]],
            "LeftLowerLeg": [[X, 90]], "RightLowerLeg": [[X, 90]]},
    "Sit cross-legged": {"_base": "Idle (arms down)", "LeftUpperLeg": [[X, -80], [Y, 40]],
                         "RightUpperLeg": [[X, -80], [Y, -40]], "LeftLowerLeg": [[X, 130]],
                         "RightLowerLeg": [[X, 130]]},
    "Crouch": {"_base": "Idle (arms down)", "Spine": [[X, 20]], "LeftUpperLeg": [[X, -110]],
               "RightUpperLeg": [[X, -110]], "LeftLowerLeg": [[X, 120]], "RightLowerLeg": [[X, 120]]},
    "Kneel": {"_base": "Idle (arms down)", "LeftUpperLeg": [[X, -90]], "LeftLowerLeg": [[X, 90]],
              "RightUpperLeg": [[X, 10]], "RightLowerLeg": [[X, 90]]},
    "Splits (stretch test)": {"LeftUpperLeg": [[X, -60]], "RightUpperLeg": [[X, 45]]},
}


def resolve(name):
    """The rotations of a built-in pose, including the pose it builds on ('_base')."""
    spec = POSES.get(name, {})
    rotations = {}
    base = spec.get("_base", [])
    for base_name in ([base] if isinstance(base, str) else base):
        rotations.update(resolve(base_name))
    rotations.update({role: rots for role, rots in spec.items() if not role.startswith("_")})
    return rotations


def roles_to_bones(armature):
    return {role: name for name, role in bone_names.humanoid_roles(armature.data.bones.keys()).items()}


def facing(armature):
    """Rotation from the pose library's frame (front -Y) to the armature's frame, judged by the left foot."""
    bones = roles_to_bones(armature)
    if "LeftFoot" in bones and "LeftToes" in bones:
        data_bones = armature.data.bones
        foot_to_toes = data_bones[bones["LeftToes"]].head_local - data_bones[bones["LeftFoot"]].head_local
        if foot_to_toes.y > 1e-4:
            return Matrix.Rotation(math.pi, 3, "Z")   # toes point to +Y: the character faces backwards
    return Matrix.Identity(3)


def pose_items(settings):
    """Enum items for the pose list: 'lib:<name>' built-in, 'cus:<name>' saved by the user."""
    items = [("lib:" + name, name, "Built-in test pose") for name in POSES]
    items += [("cus:" + p.name, "★ " + p.name, "Your saved pose") for p in settings.custom_poses]
    return items


def clear_pose(armatures):
    for armature in armatures:
        armature.data.pose_position = "POSE"
        for pose_bone in armature.pose.bones:
            pose_bone.matrix_basis = Matrix.Identity(4)


def _pose_by_role(armatures, rotations, amount):
    for armature in armatures:
        frame = facing(armature)
        bones = roles_to_bones(armature)
        for role, steps in rotations.items():
            pose_bone = armature.pose.bones.get(bones.get(role, ""))
            if pose_bone is None:
                continue
            to_bone = armature.data.bones[pose_bone.name].matrix_local.to_3x3().inverted()
            rotation = Quaternion()
            for axis, degrees in steps:
                bone_axis = (to_bone @ (frame @ Vector(axis))).normalized()
                rotation = Quaternion(bone_axis, math.radians(degrees * amount)) @ rotation
            pose_bone.rotation_mode = "QUATERNION"
            pose_bone.rotation_quaternion = rotation


def _pose_saved(armatures, data, amount):
    for armature in armatures:
        for bone_name, (w, x, y, z, loc_x, loc_y, loc_z) in data.items():
            pose_bone = armature.pose.bones.get(bone_name)
            if pose_bone is None:
                continue
            pose_bone.rotation_mode = "QUATERNION"
            pose_bone.rotation_quaternion = Quaternion().slerp(Quaternion((w, x, y, z)), amount)
            pose_bone.location = Vector((loc_x, loc_y, loc_z)) * amount


def apply_pose(settings, key, armatures, amount=1.0):
    """Pose the armatures with a pose from pose_items. amount 0..1 goes part of the way."""
    clear_pose(armatures)
    kind, _, name = key.partition(":")
    if kind == "lib":
        _pose_by_role(armatures, resolve(name), amount)
    elif kind == "cus":
        saved = next((p for p in settings.custom_poses if p.name == name), None)
        if saved:
            _pose_saved(armatures, json.loads(saved.data), amount)
    bpy.context.view_layer.update()


def capture_pose(armature):
    """The armature's current pose as text, for saving with the .blend."""
    data = {}
    for pose_bone in armature.pose.bones:
        if pose_bone.matrix_basis != Matrix.Identity(4):
            rotation = pose_bone.matrix_basis.to_quaternion()
            location = pose_bone.matrix_basis.to_translation()
            data[pose_bone.name] = [rotation.w, rotation.x, rotation.y, rotation.z, *location]
    return json.dumps(data)


def _is_reel(action):
    return action is not None and action.name in (REEL_NAME,) + OLD_REEL_NAMES


def reel_active(body):
    return bool(body and body.animation_data and _is_reel(body.animation_data.action))


def build_reel(settings, body, keys, step=10):
    """Key every pose on the body armature, `step` frames apart, so the timeline plays through them."""
    scene = bpy.context.scene
    anim = body.animation_data or body.animation_data_create()
    if not _is_reel(anim.action):
        settings.reel_prev_action = anim.action.name if anim.action else ""
        settings.reel_prev_range = (scene.frame_start, scene.frame_end)
    for name in (REEL_NAME,) + OLD_REEL_NAMES:
        if name in bpy.data.actions:
            bpy.data.actions.remove(bpy.data.actions[name])
    anim.action = bpy.data.actions.new(REEL_NAME)
    humanoid = set(bone_names.humanoid_roles(body.data.bones.keys()))
    for index, key in enumerate(keys):
        frame = 1 + index * step
        apply_pose(settings, key, [body])
        for pose_bone in body.pose.bones:
            if pose_bone.name in humanoid or pose_bone.matrix_basis != Matrix.Identity(4):
                pose_bone.rotation_mode = "QUATERNION"
                pose_bone.keyframe_insert("rotation_quaternion", frame=frame, group=pose_bone.name)
                pose_bone.keyframe_insert("location", frame=frame, group=pose_bone.name)
    scene.frame_start, scene.frame_end = 1, 1 + (len(keys) - 1) * step
    scene.frame_set(1)
    return len(keys)


def remove_reel(settings, body):
    """Remove the reel and give the body back the action and frame range it had before."""
    scene = bpy.context.scene
    if reel_active(body):
        previous = bpy.data.actions.get(settings.reel_prev_action) if settings.reel_prev_action else None
        body.animation_data.action = previous
        scene.frame_start, scene.frame_end = settings.reel_prev_range
    for name in (REEL_NAME,) + OLD_REEL_NAMES:
        if name in bpy.data.actions:
            bpy.data.actions.remove(bpy.data.actions[name])
    if body:
        clear_pose([body])
