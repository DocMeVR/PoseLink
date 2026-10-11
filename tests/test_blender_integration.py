"""End-to-end check of the add-on inside Blender, on a small made-up character.

    blender -b --factory-startup --python tests/test_blender_integration.py

Builds a body armature, an outfit armature with a cape chain and a shirt mesh, then runs the operators the way
the panel does: detect, link, test poses, hang, toggles, weight check and fix, pose reel, export prep, unlink.
Exits with code 1 when something fails.
"""
import importlib.util
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADDON_DIR = os.path.join(ROOT, "pose_link") if os.path.isdir(os.path.join(ROOT, "pose_link")) else ROOT

SETTINGS = "opl"          # scene property of the add-on
OPS = "opl"               # operator prefix


def load_addon():
    spec = importlib.util.spec_from_file_location("_poselink_test", os.path.join(ADDON_DIR, "__init__.py"),
                                                  submodule_search_locations=[ADDON_DIR])
    module = importlib.util.module_from_spec(spec)
    sys.modules["_poselink_test"] = module
    spec.loader.exec_module(module)
    return module


def settings():
    return getattr(bpy.context.scene, SETTINGS)


def op(name, *args, **kwargs):
    return getattr(getattr(bpy.ops, OPS), name)(*args, **kwargs)


# ---------------------------------------------------------------- the test scene
BODY_BONES = {
    # name: (head, tail, parent)
    "Hips": ((0, 0, 1.0), (0, 0, 1.1), None),
    "Spine": ((0, 0, 1.1), (0, 0, 1.25), "Hips"),
    "Chest": ((0, 0, 1.25), (0, 0, 1.4), "Spine"),
    "Neck": ((0, 0, 1.4), (0, 0, 1.5), "Chest"),
    "Head": ((0, 0, 1.5), (0, 0, 1.7), "Neck"),
}
for side, x in (("L", 1), ("R", -1)):
    BODY_BONES.update({
        f"Shoulder_{side}": ((0.02 * x, 0, 1.38), (0.12 * x, 0, 1.38), "Chest"),
        f"UpperArm_{side}": ((0.12 * x, 0, 1.38), (0.38 * x, 0, 1.38), f"Shoulder_{side}"),
        f"LowerArm_{side}": ((0.38 * x, 0, 1.38), (0.62 * x, 0, 1.38), f"UpperArm_{side}"),
        f"Hand_{side}": ((0.62 * x, 0, 1.38), (0.7 * x, 0, 1.38), f"LowerArm_{side}"),
        f"UpperLeg_{side}": ((0.1 * x, 0, 1.0), (0.1 * x, 0, 0.55), "Hips"),
        f"LowerLeg_{side}": ((0.1 * x, 0, 0.55), (0.1 * x, 0, 0.1), f"UpperLeg_{side}"),
        f"Foot_{side}": ((0.1 * x, 0, 0.1), (0.1 * x, -0.1, 0.02), f"LowerLeg_{side}"),
        f"Toe_{side}": ((0.1 * x, -0.1, 0.02), (0.1 * x, -0.16, 0.02), f"Foot_{side}"),
    })


def make_armature(name, bone_specs):
    data = bpy.data.armatures.new(name)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    for bone_name, (head, tail, _) in bone_specs.items():
        eb = data.edit_bones.new(bone_name)
        eb.head, eb.tail = head, tail
    for bone_name, (_, _, parent) in bone_specs.items():
        if parent:
            data.edit_bones[bone_name].parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def make_mesh(name, armature, points, weights):
    """weights: one {group: weight} per point."""
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(points, [], [])
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.modifiers.new("Armature", "ARMATURE").object = armature
    for index, groups in enumerate(weights):
        for group_name, weight in groups.items():
            group = obj.vertex_groups.get(group_name) or obj.vertex_groups.new(name=group_name)
            group.add([index], weight, "REPLACE")
    return obj


def build_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    body = make_armature("Body", BODY_BONES)
    outfit_bones = {f"RH_{n}": (h, t, f"RH_{p}" if p else None) for n, (h, t, p) in BODY_BONES.items()}
    outfit_bones["Cape_1"] = ((0, 0.08, 1.38), (0, 0.08, 1.0), "RH_Chest")
    outfit_bones["Cape_2"] = ((0, 0.08, 1.0), (0, 0.08, 0.6), "Cape_1")
    outfit = make_armature("Outfit", outfit_bones)
    body_mesh = make_mesh("BodyMesh", body, [(0, 0, 1.2)], [{"Spine": 1.0}])
    body_mesh.shape_key_add(name="Basis")
    body_mesh.shape_key_add(name="Hide")
    five = {"RH_Spine": 0.2, "RH_Chest": 0.2, "RH_Hips": 0.2, "RH_Neck": 0.2, "RH_Head": 0.2}
    shirt = make_mesh("Shirt", outfit, [(0, 0, 1.3), (0, 0, 1.31), (0.2, 0, 1.3)], [five, {}, {"RH_Chest": 1.0}])
    return body, outfit, body_mesh, shirt


# ---------------------------------------------------------------- checks
failures = []


def check(condition, message):
    if not condition:
        failures.append(message)
        print("FAIL:", message)


def world_matrix(armature, bone):
    return armature.matrix_world @ armature.pose.bones[bone].matrix


def direction(armature, bone):
    pb = armature.pose.bones[bone]
    return (pb.tail - pb.head).normalized()


def rest_direction(armature, bone):
    b = armature.data.bones[bone]
    return (b.tail_local - b.head_local).normalized()


def run():
    addon = load_addon()
    addon.register()
    try:
        body, outfit, body_mesh, shirt = build_scene()
        st = settings()

        op("detect")
        check(st.base == body, f"detect should pick Body as the base, got {st.base}")
        check([i.obj for i in st.outfits] == [outfit], "detect should find the outfit armature")
        mapped = {r.outfit_bone: r.base_bone for r in st.outfits[0].rows if r.base_bone}
        check(mapped.get("RH_UpperArm_L") == "UpperArm_L", "RH_UpperArm_L should match UpperArm_L")
        check("Cape_1" not in mapped, "the cape is an outfit-only bone")

        op("link")
        links = [c for pb in outfit.pose.bones for c in pb.constraints if c.type == "COPY_TRANSFORMS"]
        check(len(links) == len(mapped), f"one link per matched bone: {len(links)} vs {len(mapped)}")

        st.pose = "lib:Arms up"
        bpy.context.view_layer.update()
        diff = (world_matrix(body, "UpperArm_L") - world_matrix(outfit, "RH_UpperArm_L")).to_3x3()
        check(max(abs(v) for row in diff for v in row) < 1e-5, "linked outfit bone should follow the body bone")
        check(body.pose.bones["UpperArm_L"].matrix_basis.to_quaternion().angle > math.radians(30),
              "Arms up should rotate the upper arm")

        op("apply_pose", step=1)
        check(st.pose != "lib:Arms up", "the next-pose arrow should move to another pose")

        op("rest")
        chest = body.pose.bones["Chest"]
        chest.rotation_mode = "QUATERNION"
        chest.rotation_quaternion = Quaternion((1, 0, 0), math.radians(40))   # bend, not twist
        bpy.context.view_layer.update()
        rigid = math.degrees(direction(outfit, "Cape_1").angle(rest_direction(outfit, "Cape_1")))
        check(rigid > 35, f"without hang the cape turns with the chest ({rigid:.1f} deg)")
        st.hang_strength = 1.0
        st.hang = True
        for _ in range(3):
            bpy.context.view_layer.update()
        hung = math.degrees(direction(outfit, "Cape_2").angle(rest_direction(outfit, "Cape_2")))
        check(hung < 0.1, f"with gravity 1 the cape keeps hanging ({hung:.2f} deg)")
        st.hang = False
        bpy.context.view_layer.update()

        key = body_mesh.data.shape_keys.key_blocks["Hide"]
        key.value = 1.0
        shirt.hide_set(True)
        st.new_state_name = "Shirt off"
        op("state_capture")
        key.value = 0.0
        shirt.hide_set(False)
        st.new_state_name = "Shirt on"
        op("state_capture")
        op("state_apply", index=0)
        check(key.value == 1.0 and shirt.hide_get(), "applying a toggle restores shape keys and visibility")
        op("state_apply", index=1)
        check(key.value == 0.0 and not shirt.hide_get(), "the other toggle switches back")

        op("weights_check")
        report = st.last_report
        check("Shirt" in report and "over limit 1" in report and "unweighted 1" in report,
              f"weight check should report the shirt's problems, got: {report!r}")
        op("weights_fix", "EXEC_DEFAULT")
        op("weights_check")
        check("over limit" not in st.last_report, f"fix should limit to 4 bones, got: {st.last_report!r}")

        chest.rotation_quaternion = Quaternion((1, 0, 0), math.radians(20))
        st.new_pose_name = "Bow"
        op("save_pose")
        op("rest")
        st.pose = "cus:Bow"
        bpy.context.view_layer.update()
        check(chest.matrix_basis.to_quaternion().angle > math.radians(19), "a saved pose applies again")

        op("reel")
        check(body.animation_data and body.animation_data.action, "the pose reel puts an action on the base")
        op("reel", remove=True)
        check(not (body.animation_data and body.animation_data.action), "removing the reel clears the action")

        op("pose_mode")
        check(bpy.context.mode == "POSE" and bpy.context.active_object == body, "Pose Base Armature enters pose mode")
        op("pose_mode")
        check(bpy.context.mode == "OBJECT", "pressing it again leaves pose mode")

        st.pose = "lib:Arms up"
        st.hang = True
        op("export_prep")
        check(not st.hang, "export prep switches hang off")
        check(all(pb.matrix_basis.to_quaternion().angle < 1e-6 for pb in body.pose.bones), "export prep rests the pose")

        op("mute")
        links = [c for pb in outfit.pose.bones for c in pb.constraints if c.type == "COPY_TRANSFORMS"]
        check(links and all(c.mute for c in links), "pause mutes every link")
        op("unlink")
        links = [c for pb in outfit.pose.bones for c in pb.constraints if c.type == "COPY_TRANSFORMS"]
        check(not links, "unlink removes every link")
    finally:
        addon.unregister()
    check(not hasattr(bpy.types.Scene, SETTINGS), "unregister removes the scene settings")


if __name__ == "__main__":
    try:
        run()
    except Exception as error:
        import traceback
        traceback.print_exc()
        failures.append(repr(error))
    print("test_blender_integration:", "OK" if not failures else f"{len(failures)} FAILED")
    sys.exit(1 if failures else 0)
