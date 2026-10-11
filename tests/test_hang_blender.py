"""Run inside Blender (needs bpy): hang = chain bones turn part of the way back toward their rest direction,
like cloth hanging under gravity.

    blender -b --python tests/test_hang_blender.py      (or exec it in a running Blender)
Builds a throw-away armature and removes it again.
"""
import math
import os
import sys

import bpy
from mathutils import Quaternion, Vector

import importlib.util

# load the add-on from this repo (not whatever is installed) under a private name
_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pose_link")
_spec = importlib.util.spec_from_file_location("_poselink_src", os.path.join(_ROOT, "__init__.py"),
                                               submodule_search_locations=[_ROOT])
_pkg = importlib.util.module_from_spec(_spec)
sys.modules["_poselink_src"] = _pkg
_spec.loader.exec_module(_pkg)
from _poselink_src import chains  # noqa: E402


def _arm():
    data = bpy.data.armatures.new("_opl_test_arm")
    ob = bpy.data.objects.new("_opl_test_arm", data)
    bpy.context.scene.collection.objects.link(ob)
    prev = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    chest = data.edit_bones.new("Chest"); chest.head = (0, 0, 1.0); chest.tail = (0, 0, 1.2)
    cape = data.edit_bones.new("Cape_1"); cape.head = (0.1, 0.05, 1.2); cape.tail = (0.1, 0.05, 0.9); cape.parent = chest
    tip = data.edit_bones.new("Cape_2"); tip.head = (0.1, 0.05, 0.9); tip.tail = (0.12, 0.05, 0.6); tip.parent = cape
    tip.use_connect = True
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.objects.active = prev
    return ob


def _dir(ob, bn):
    pb = ob.pose.bones[bn]
    return (pb.tail - pb.head).normalized()


def _rest_dir(ob, bn):
    b = ob.data.bones[bn]
    return (b.tail_local - b.head_local).normalized()


def _bend(ob, deg):
    pb = ob.pose.bones["Chest"]
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = Quaternion((1, 0, 0), math.radians(deg))   # bone-local X: bends the chest
    bpy.context.view_layer.update()


def run():
    ob = _arm()
    fails = []
    try:
        _bend(ob, 40)
        rigid = _dir(ob, "Cape_1")
        if rigid.angle(_rest_dir(ob, "Cape_1")) < math.radians(35):
            fails.append("setup: chain root should follow the bent parent")
        chains.hang(ob, ["Cape_1"], 1.0)
        bpy.context.view_layer.update()
        a = math.degrees(_dir(ob, "Cape_1").angle(_rest_dir(ob, "Cape_1")))
        if a > 0.01:
            fails.append(f"strength 1: root should hang in its rest direction, off by {a:.3f} deg")
        a = math.degrees(_dir(ob, "Cape_2").angle(_rest_dir(ob, "Cape_2")))
        if a > 0.01:
            fails.append(f"strength 1: the rest of the chain should follow the root, off by {a:.3f} deg")
        head = ob.pose.bones["Cape_1"].head.copy()
        chains.hang(ob, ["Cape_1"], 0.5)
        bpy.context.view_layer.update()
        # the hang builds up along the chain (2 bones here): the root keeps sqrt(0.5) of the 40 deg bend,
        # the tip ends up with half of it - the top follows the chest, the hem hangs
        a = math.degrees(_dir(ob, "Cape_1").angle(_rest_dir(ob, "Cape_1")))
        if abs(a - 40 * math.sqrt(0.5)) > 0.05:
            fails.append(f"strength 0.5: root expected {40 * math.sqrt(0.5):.2f} deg from rest, got {a:.3f}")
        a = math.degrees(_dir(ob, "Cape_2").angle(_rest_dir(ob, "Cape_2")))
        if abs(a - 20) > 0.05:
            fails.append(f"strength 0.5: tip expected 20 deg from rest, got {a:.3f}")
        if (ob.pose.bones["Cape_1"].head - head).length > 1e-6:
            fails.append("hang must not move the root's head (it stays attached to the parent)")
        changed = chains.hang(ob, ["Cape_1"], 0.5)
        if changed:
            fails.append("re-applying the same hang must report no change (keeps the live handler from looping)")
        chains.hang(ob, ["Cape_1"], 0.0)
        bpy.context.view_layer.update()
        a = math.degrees(_dir(ob, "Cape_1").angle(rigid))
        if a > 0.01:
            fails.append(f"strength 0: root should move rigidly with the parent, off by {a:.3f} deg")
        _bend(ob, 0)
        chains.hang(ob, ["Cape_1"], 1.0)
        q = ob.pose.bones["Cape_1"].rotation_quaternion
        if abs(q.angle) > 1e-5:
            fails.append("at rest the hang rotation must be identity")
    finally:
        data = ob.data
        bpy.data.objects.remove(ob)
        bpy.data.armatures.remove(data)
    return fails


if __name__ == "__main__":
    f = run()
    print("test_hang_blender:", "OK" if not f else "FAIL\n  " + "\n  ".join(f))
