"""Chains: bones that hang off the body (cape, skirt, hair, tail, ears).

Blender turns them rigidly with their parent bone, so a cape flies out when the chest bends. The hang turns
them back toward hanging, live while you pose; the swing adds a fixed turn on top to preview them moving.
"""
import math

import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix, Quaternion, Vector

from . import bone_names
from .poses import facing, roles_to_bones

SWING_DIRECTIONS = {"BACK": Vector((0, 1, 0)), "FORWARD": Vector((0, -1, 0)), "LEFT": Vector((1, 0, 0)),
                    "RIGHT": Vector((-1, 0, 0)), "GRAVITY": Vector((0, 0, -1))}


def body_bones(armature, outfit_entry=None):
    """Bones that are part of the body: humanoid bones, and on an outfit every bone linked to the body."""
    names = set(bone_names.humanoid_roles(armature.data.bones.keys()))
    if outfit_entry is not None:
        names |= {row.outfit_bone for row in outfit_entry.rows if row.base_bone}
    return names


def find_chains(armature, body, name_filter=""):
    """Every bone that is not a body bone but hangs off one."""
    name_filter = name_filter.lower().strip()
    found = []
    for bone in armature.data.bones:
        if bone.name in body:
            continue
        parent = bone.parent
        while parent is not None and parent.name not in body:
            parent = parent.parent
        if parent is None and bone.parent is not None:
            continue   # hangs off something that is not the body
        if name_filter and name_filter not in bone.name.lower():
            continue
        found.append(bone.name)
    return found


def chain_roots(armature, chain_bones):
    """The first bone of every chain: the one whose parent is a body bone."""
    in_chain = set(chain_bones)
    return [name for name in chain_bones
            if armature.data.bones[name].parent is not None and armature.data.bones[name].parent.name not in in_chain]


def swing_rotations(armature, chain_bones, direction, degrees):
    """{bone: local rotation} that turns each chain bone `degrees` toward `direction`.
    OUTWARD points away from the body's middle line, the others are directions in the character's frame."""
    frame = facing(armature)
    bones = roles_to_bones(armature)
    hips = armature.data.bones.get(bones.get("Hips", ""))
    head = armature.data.bones.get(bones.get("Head", ""))
    axis_point = hips.head_local if hips else Vector((0, 0, 0))
    axis = (head.head_local - hips.head_local).normalized() if hips and head else Vector((0, 0, 1))
    rotations = {}
    for name in chain_bones:
        bone = armature.data.bones[name]
        along = (bone.tail_local - bone.head_local).normalized()
        if direction == "OUTWARD":
            offset = bone.head_local - axis_point
            outward = offset - axis * offset.dot(axis)
            target = outward.normalized() if outward.length > 1e-5 else frame @ Vector((0, 1, 0))
        else:
            target = frame @ SWING_DIRECTIONS[direction]
        turn_axis = along.cross(target)
        if turn_axis.length < 1e-4 or not degrees:
            rotations[name] = Quaternion()
            continue
        local_axis = (bone.matrix_local.to_3x3().inverted() @ turn_axis).normalized()
        rotations[name] = Quaternion(local_axis, math.radians(degrees))
    return rotations


def swing(armature, chain_bones, direction, degrees):
    for name, rotation in swing_rotations(armature, chain_bones, direction, degrees).items():
        pose_bone = armature.pose.bones[name]
        pose_bone.rotation_mode = "QUATERNION"
        pose_bone.rotation_quaternion = rotation
    bpy.context.view_layer.update()


def _bones_below(armature, root):
    """The chain under `root`, parents before children, and how many bones its longest branch has."""
    first = armature.data.bones[root]
    ordered, queue = [], [first]
    while queue:
        bone = queue.pop(0)
        ordered.append(bone)
        queue.extend(bone.children)
    depth_of_root = len(first.parent_recursive)
    return ordered, max(len(bone.parent_recursive) - depth_of_root + 1 for bone in ordered)


def hang(armature, roots, gravity, extra=None):
    """Turn every bone below `roots` part of the way back toward its rest direction.

    The top of a chain still follows its parent and the hang builds up toward the tip: gravity 0 leaves the
    chain rigid with its parent, 1 keeps every bone in its rest direction, and in between the tip keeps
    (1 - gravity) of the parent's turn. `extra` is a local rotation per bone added on top (the swing).
    Reads the evaluated pose of the chains' parents. Returns True when a bone changed, so the live
    handler knows when to stop.
    """
    gravity = min(max(gravity, 0.0), 1.0)
    extra = extra or {}
    changed = False
    for root in roots:
        if root not in armature.data.bones or armature.data.bones[root].parent is None:
            continue
        chain, length = _bones_below(armature, root)
        # each bone takes this share, so that over the whole chain it adds up to `gravity`
        share = 1.0 if gravity >= 1.0 else 1.0 - (1.0 - gravity) ** (1.0 / length)
        posed = {}   # pose matrices of this chain as we set them; Blender only evaluates them later
        for bone in chain:
            pose_bone = armature.pose.bones[bone.name]
            parent_matrix = posed.get(bone.parent.name)
            if parent_matrix is None:
                parent_matrix = pose_bone.parent.matrix
            inherited = parent_matrix @ bone.parent.matrix_local.inverted() @ bone.matrix_local
            follow = inherited.to_3x3().normalized().to_quaternion()
            rest = bone.matrix_local.to_3x3().normalized().to_quaternion()
            target = follow.slerp(rest, share) if share > 0 else follow
            rotation = (follow.inverted() @ target) @ extra.get(bone.name, Quaternion())
            if pose_bone.rotation_mode != "QUATERNION":
                pose_bone.rotation_mode = "QUATERNION"
                changed = True
            if pose_bone.rotation_quaternion.rotation_difference(rotation).angle > 1e-5:
                pose_bone.rotation_quaternion = rotation
                changed = True
            location, _, scale = pose_bone.matrix_basis.decompose()
            posed[bone.name] = inherited @ Matrix.LocRotScale(location, rotation, scale)
    return changed


# ---------------------------------------------------------------- with the scene settings
_chain_cache = {}


def _armatures_to_move(settings):
    """[(armature, outfit entry or None)] for the "Chains on" setting."""
    if settings.swing_target == "BASE":
        return [(settings.base, None)]
    pairs = [(entry.obj, entry) for entry in settings.outfits if entry.obj]
    if settings.swing_target == "ALL":
        pairs.append((settings.base, None))
    return pairs


def chains_of(settings, armature, outfit_entry):
    """(chain bones, chain roots) of one armature. Cached: the live hang asks on every change in the scene."""
    key = (armature.name, len(armature.data.bones), settings.swing_filter,
           settings.base.name if settings.base else "",
           tuple(row.base_bone for row in outfit_entry.rows) if outfit_entry else ())
    if key not in _chain_cache:
        if len(_chain_cache) > 64:
            _chain_cache.clear()
        bones = find_chains(armature, body_bones(armature, outfit_entry), settings.swing_filter)
        _chain_cache[key] = (bones, chain_roots(armature, bones))
    return _chain_cache[key]


def count_chain_bones(settings):
    return sum(len(chains_of(settings, armature, entry)[0])
               for armature, entry in _armatures_to_move(settings) if armature)


def apply_swing(settings):
    for armature, entry in _armatures_to_move(settings):
        if armature is not None:
            swing(armature, chains_of(settings, armature, entry)[0], settings.swing_mode, settings.swing_angle)
    if settings.hang:
        apply_hang(settings)
        bpy.context.view_layer.update()


def apply_hang(settings, gravity=None):
    """Hang every chain with the scene's gravity (0 when hang is off, which leaves only the swing)."""
    if gravity is None:
        gravity = settings.hang_strength if settings.hang else 0.0
    changed = False
    for armature, entry in _armatures_to_move(settings):
        if armature is None or armature.mode == "EDIT":
            continue
        bones, roots = chains_of(settings, armature, entry)
        extra = (swing_rotations(armature, bones, settings.swing_mode, settings.swing_angle)
                 if settings.swing_angle else None)
        changed |= hang(armature, roots, gravity, extra)
    return changed


_hang_running = False


@persistent
def hang_live(scene, depsgraph=None):
    """Runs after every change and on frame changes while hang is on. Stops once nothing changes any more."""
    global _hang_running
    settings = getattr(scene, "poselink", None)
    if _hang_running or settings is None or not settings.hang or settings.base is None:
        return
    _hang_running = True
    try:
        apply_hang(settings)
    except Exception as error:   # a handler must never break the user's session
        print("PoseLink hang:", error)
    finally:
        _hang_running = False


HANDLER_LISTS = (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.frame_change_post)


def register():
    for handlers in HANDLER_LISTS:
        if hang_live not in handlers:
            handlers.append(hang_live)


def unregister():
    for handlers in HANDLER_LISTS:
        for handler in [h for h in handlers if getattr(h, "__name__", "") == "hang_live"]:
            handlers.remove(handler)
