"""Finding the body and outfit armatures and linking outfit bones to body bones."""
import bpy

from . import bone_names

LINK_NAME = "PoseLink"
# Files linked with the add-on's first version (Outfit Pose Link) use this name; still recognised
OLD_LINK_NAMES = ("OutfitLink",)


def is_link(constraint):
    return constraint.name.startswith((LINK_NAME,) + OLD_LINK_NAMES)


def meshes_of(armatures):
    """Mesh objects deformed by, or parented to, any of the armatures."""
    armatures = set(armatures)
    meshes = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        deformed = any(m.type == "ARMATURE" and m.object in armatures for m in obj.modifiers)
        if deformed or obj.parent in armatures:
            meshes.append(obj)
    return meshes


def guess_body_armature():
    """The armature with the most humanoid bones; on a tie the one with more meshes."""
    best, best_score = None, (-1, -1)
    for obj in bpy.data.objects:
        if obj.type != "ARMATURE":
            continue
        score = (len(bone_names.humanoid_roles(obj.data.bones.keys())), len(meshes_of([obj])))
        if score > best_score:
            best, best_score = obj, score
    return best


def bone_matches(outfit, body, overrides=None):
    return bone_names.match_bones(list(outfit.data.bones.keys()), list(body.data.bones.keys()), overrides)


def find_outfits(body):
    """Other armatures that share at least five bones with the body."""
    if body is None:
        return []
    return [obj for obj in bpy.data.objects
            if obj.type == "ARMATURE" and obj is not body and len(bone_matches(obj, body)) >= 5]


def refresh_rows(outfit_entry, body):
    """Fill the outfit's bone list again, keeping the body bones the user picked by hand."""
    picked = {row.outfit_bone: row.base_bone for row in outfit_entry.rows if row.method == "manual"}
    matches = bone_matches(outfit_entry.obj, body, picked)
    outfit_entry.rows.clear()
    for bone in outfit_entry.obj.data.bones:
        row = outfit_entry.rows.add()
        row.outfit_bone = bone.name
        body_bone, method = matches.get(bone.name, ("", "none"))
        if bone.name in picked:
            body_bone, method = picked[bone.name], "manual"
        row["base_bone"] = body_bone   # item assignment skips the update that would mark the row as manual
        row.method = method


def misplaced_bones(outfit_entry, body, tolerance=0.005):
    """[(outfit bone, distance)] for linked bones whose rest position is away from the body bone.
    A long list means the outfit was made for a different body."""
    outfit = outfit_entry.obj
    misplaced = []
    for row in outfit_entry.rows:
        if not row.base_bone or row.base_bone not in body.data.bones or row.outfit_bone not in outfit.data.bones:
            continue
        outfit_head = outfit.matrix_world @ outfit.data.bones[row.outfit_bone].head_local
        body_head = body.matrix_world @ body.data.bones[row.base_bone].head_local
        distance = (outfit_head - body_head).length
        if distance > tolerance:
            misplaced.append((row.outfit_bone, distance))
    return misplaced


def _target_space(constraint):
    # LOCAL_OWNER_ORIENT keeps bones with different roll in line; older Blender versions only have LOCAL
    spaces = {item.identifier for item in constraint.bl_rna.properties["target_space"].enum_items}
    return "LOCAL_OWNER_ORIENT" if "LOCAL_OWNER_ORIENT" in spaces else "LOCAL"


def link(outfit_entry, body):
    """Give every matched outfit bone a Copy Transforms constraint to its body bone. Returns how many."""
    outfit = outfit_entry.obj
    linked = 0
    for row in outfit_entry.rows:
        pose_bone = outfit.pose.bones.get(row.outfit_bone)
        if pose_bone is None:
            continue
        existing = [c for c in pose_bone.constraints if is_link(c)]
        if not row.base_bone or row.base_bone not in body.pose.bones:
            for constraint in existing:
                pose_bone.constraints.remove(constraint)
            continue
        constraint = existing[0] if existing else pose_bone.constraints.new("COPY_TRANSFORMS")
        constraint.name = LINK_NAME
        constraint.target = body
        constraint.subtarget = row.base_bone
        constraint.target_space = _target_space(constraint)
        constraint.owner_space = "LOCAL"
        constraint.mix_mode = "REPLACE"
        constraint.influence = 1.0
        constraint.mute = False
        position = list(pose_bone.constraints).index(constraint)
        if position:
            pose_bone.constraints.move(position, 0)   # first, so the user's own constraints still apply on top
        linked += 1
    return linked


def unlink(armature):
    removed = 0
    for pose_bone in armature.pose.bones:
        for constraint in [c for c in pose_bone.constraints if is_link(c)]:
            pose_bone.constraints.remove(constraint)
            removed += 1
    return removed


def links_of(armature):
    return [c for pose_bone in armature.pose.bones for c in pose_bone.constraints if is_link(c)]
