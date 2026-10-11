"""Properties and operators for PoseLink."""
import json

import bpy
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
                       IntVectorProperty, PointerProperty, StringProperty)

from . import core

_items_cache = []


def _is_arm(self, o):
    return o.type == "ARMATURE"


def S(context):
    return context.scene.opl


def outfits(st):
    return [i.obj for i in st.outfits if i.obj]


def pose_targets(st):
    """The base, plus outfit armatures that are NOT linked (those would not follow otherwise)."""
    return [st.base] + [o for o in outfits(st) if not core.link_constraints(o)]


# ---------------------------------------------------------------- properties
def _row_manual(self, context):
    self.method = "manual"


def _pose_items(self, context):
    global _items_cache
    _items_cache = core.pose_names(self)
    return _items_cache


def _on_pose(self, context):
    if self.auto_apply and self.base:
        core.apply_pose(self, self.pose, pose_targets(self), self.amount)


def _swing_arms(st):
    if st.swing_target == "BASE":
        return [(st.base, None)]
    pairs = [(i.obj, i) for i in st.outfits if i.obj]
    return pairs + ([(st.base, None)] if st.swing_target == "ALL" else [])


_chain_cache = {}


def _chains_of(st, arm, item):
    key = (arm.name, len(arm.data.bones), st.swing_filter, st.base.name if st.base else "",
           tuple(r.base_bone for r in item.rows) if item else ())
    if key not in _chain_cache:
        if len(_chain_cache) > 64:
            _chain_cache.clear()
        ch = core.chains(arm, core.body_bones(arm, st.base, item), st.swing_filter)
        _chain_cache[key] = (ch, core.chain_roots(arm, ch))
    return _chain_cache[key]


def swing_now(st):
    n = 0
    for arm, item in _swing_arms(st):
        if arm is None:
            continue
        ch, _ = _chains_of(st, arm, item)
        core.swing(arm, ch, st.swing_mode, st.swing_angle)
        n += len(ch)
    if st.hang:
        hang_now(st)
        bpy.context.view_layer.update()
    return n


def hang_now(st, strength=None):
    """Chains hang toward their rest direction (gravity preview); the swing still applies on top."""
    s = (st.hang_strength if st.hang else 0.0) if strength is None else strength
    changed = False
    for arm, item in _swing_arms(st):
        if arm is None or arm.mode == "EDIT":
            continue
        ch, roots = _chains_of(st, arm, item)
        extra = core.swing_quats(arm, ch, st.swing_mode, st.swing_angle) if st.swing_angle else None
        changed |= core.hang(arm, roots, s, extra)
    return changed


_hang_busy = False


@persistent
def hang_handler(scene, depsgraph=None):
    """Live hang: re-applied after every change (posing, timeline). Stops once nothing changes."""
    global _hang_busy
    st = getattr(scene, "opl", None)
    if _hang_busy or st is None or not st.hang or st.base is None:
        return
    _hang_busy = True
    try:
        hang_now(st)
    except Exception as e:                      # never break the user's session from a handler
        print("PoseLink hang:", e)
    finally:
        _hang_busy = False


def _on_swing(self, context):
    if self.base:
        swing_now(self)


def _on_hang(self, context):
    if self.base:
        context.view_layer.update()
        hang_now(self)
        context.view_layer.update()


class OPL_MapRow(bpy.types.PropertyGroup):
    outfit_bone: StringProperty()
    base_bone: StringProperty(update=_row_manual, description="Base bone this outfit bone follows (empty = none)")
    method: StringProperty(default="none")


class OPL_Outfit(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object, poll=_is_arm)
    rows: CollectionProperty(type=OPL_MapRow)
    row_index: IntProperty()


class OPL_Saved(bpy.types.PropertyGroup):
    name: StringProperty()
    data: StringProperty()


class OPL_Settings(bpy.types.PropertyGroup):
    base: PointerProperty(type=bpy.types.Object, poll=_is_arm, name="Base",
                          description="The avatar's own armature (the one you pose)")
    outfits: CollectionProperty(type=OPL_Outfit)
    outfit_index: IntProperty()
    pose: EnumProperty(name="Test Pose", items=_pose_items, update=_on_pose)
    amount: FloatProperty(name="Strength", default=1.0, min=0.0, max=1.5, subtype="FACTOR", update=_on_pose,
                          description="How far into the pose (use it to see where problems start)")
    auto_apply: BoolProperty(name="Apply on change", default=True)
    custom_poses: CollectionProperty(type=OPL_Saved)
    custom_index: IntProperty()
    new_pose_name: StringProperty(name="Name", default="My pose")
    reel_prev_action: StringProperty()
    reel_prev_range: IntVectorProperty(size=2, default=(1, 250))
    states: CollectionProperty(type=OPL_Saved)
    state_index: IntProperty()
    new_state_name: StringProperty(name="Name", default="Toggle")
    swing_target: EnumProperty(name="Chains on", default="OUTFITS", update=_on_swing, items=[
        ("OUTFITS", "Outfits", "Chains of the outfit armatures (cape, skirt...)"),
        ("BASE", "Base", "Chains of the base armature (hair, ears, tail...)"),
        ("ALL", "All", "Both")])
    swing_mode: EnumProperty(name="Direction", default="OUTWARD", update=_on_swing, items=[
        ("OUTWARD", "Outward", "Away from the body (spin / flare)"), ("GRAVITY", "Gravity", "Droop downward"),
        ("BACK", "Back", "Running / wind from the front"), ("FORWARD", "Forward", "Wind from behind"),
        ("LEFT", "Left", "Sideways to the avatar's left"), ("RIGHT", "Right", "Sideways to the avatar's right")])
    swing_angle: FloatProperty(name="Angle per bone", default=0.0, min=-45.0, max=45.0, update=_on_swing,
                               description="Rotation of every chain bone in degrees, to preview chains swinging")
    swing_filter: StringProperty(name="Name filter", update=_on_swing, description="Only chains whose bone names contain this")
    hang: BoolProperty(name="Hang with gravity (live)", default=False, update=_on_hang,
                       description="Chains keep hanging down while you pose instead of turning rigidly with the "
                                   "chest or hips. Updates live")
    hang_strength: FloatProperty(name="Gravity", default=0.5, min=0.0, max=1.0, subtype="FACTOR", update=_on_hang,
                                 description="How much chains hang down instead of turning with the chest/hips. The top of a "
                                             "chain follows its parent, the hang builds up toward the tip. 0 = rigid, "
                                             "1 = they keep their rest direction")
    weight_scope: EnumProperty(name="Meshes", default="OUTFIT", items=[
        ("SELECTED", "Selected", "Selected mesh objects"), ("OUTFIT", "Outfit meshes", "Meshes of the outfit armatures"),
        ("ALL", "Whole avatar", "Base and outfit meshes")])
    last_report: StringProperty()
    pose_mode_restore: StringProperty()


# ---------------------------------------------------------------- setup / linking
class OPL_OT_detect(bpy.types.Operator):
    bl_idname = "opl.detect"
    bl_label = "Auto Detect"
    bl_description = "Find the base armature and every outfit armature that matches it"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        if st.base is None:
            st.base = core.guess_base()
        if st.base is None:
            self.report({"ERROR"}, "No armature in the scene")
            return {"CANCELLED"}
        have = {i.obj for i in st.outfits if i.obj}
        for o in core.outfit_candidates(st.base):
            if o not in have:
                it = st.outfits.add()
                it.obj = o
        for it in st.outfits:
            if it.obj:
                core.refresh_rows(it, st.base)
        self.report({"INFO"}, f"Base: {st.base.name}; outfits: {', '.join(o.name for o in outfits(st)) or 'none'}")
        return {"FINISHED"}


class OPL_OT_add_outfit(bpy.types.Operator):
    bl_idname = "opl.add_outfit"
    bl_label = "Add Selected Armature"
    bl_description = "Add the selected armature(s) as outfits"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        have = {i.obj for i in st.outfits}
        added = 0
        for o in context.selected_objects:
            if o.type == "ARMATURE" and o is not st.base and o not in have:
                it = st.outfits.add(); it.obj = o
                if st.base:
                    core.refresh_rows(it, st.base)
                added += 1
        if not added:
            self.report({"WARNING"}, "Select an outfit armature (not the base) first")
            return {"CANCELLED"}
        return {"FINISHED"}


class OPL_OT_remove_outfit(bpy.types.Operator):
    bl_idname = "opl.remove_outfit"
    bl_label = "Remove Outfit"
    bl_description = "Unlink and remove the active outfit from the list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        if 0 <= st.outfit_index < len(st.outfits):
            o = st.outfits[st.outfit_index].obj
            if o:
                core.unlink(o)
            st.outfits.remove(st.outfit_index)
            st.outfit_index = max(0, st.outfit_index - 1)
        return {"FINISHED"}


class OPL_OT_refresh_map(bpy.types.Operator):
    bl_idname = "opl.refresh_map"
    bl_label = "Re-match Bones"
    bl_description = "Match outfit bones to base bones again (your manual choices are kept)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        for it in st.outfits:
            if it.obj and st.base:
                core.refresh_rows(it, st.base)
        return {"FINISHED"}


class OPL_OT_link(bpy.types.Operator):
    bl_idname = "opl.link"
    bl_label = "Link"
    bl_description = "Make the outfit armatures follow the base (one Copy Transforms per matched bone)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        if st.base is None or not st.outfits:
            bpy.ops.opl.detect()
        if st.base is None:
            return {"CANCELLED"}
        total = 0
        for it in st.outfits:
            if it.obj:
                if not len(it.rows):
                    core.refresh_rows(it, st.base)
                total += core.link(it, st.base)
        self.report({"INFO"}, f"Linked {total} bones")
        return {"FINISHED"}


class OPL_OT_unlink(bpy.types.Operator):
    bl_idname = "opl.unlink"
    bl_label = "Unlink"
    bl_description = "Remove the link constraints from all outfits"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = sum(core.unlink(o) for o in outfits(S(context)))
        self.report({"INFO"}, f"Removed {n} constraints")
        return {"FINISHED"}


class OPL_OT_mute(bpy.types.Operator):
    bl_idname = "opl.mute"
    bl_label = "Pause Link"
    bl_description = "Switch the link off / on without deleting it"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        cons = [c for o in outfits(S(context)) for c in core.link_constraints(o)]
        if cons:
            m = not cons[0].mute
            for c in cons:
                c.mute = m
        return {"FINISHED"}


# ---------------------------------------------------------------- posing
class OPL_OT_pose_mode(bpy.types.Operator):
    bl_idname = "opl.pose_mode"
    bl_label = "Pose Base Armature"
    bl_description = "Enter Pose Mode on the base armature (the outfits follow) / leave it again"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        base = st.base
        if base is None:
            return {"CANCELLED"}
        if context.mode == "POSE" and context.active_object is base:
            bpy.ops.object.mode_set(mode="OBJECT")
            info = json.loads(st.pose_mode_restore or "{}")
            for o in context.selected_objects:
                o.select_set(False)
            for n in info.get("selected", []):
                ob = bpy.data.objects.get(n)
                if ob:
                    ob.select_set(True)
            act = bpy.data.objects.get(info.get("active", ""))
            context.view_layer.objects.active = act
            if info.get("base_hidden"):
                base.hide_set(True)
            st.pose_mode_restore = ""
            return {"FINISHED"}
        info = {"active": context.active_object.name if context.active_object else "",
                "selected": [o.name for o in context.selected_objects], "base_hidden": base.hide_get()}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        base.hide_viewport = False
        base.hide_set(False)
        for o in context.selected_objects:
            o.select_set(False)
        base.select_set(True)
        context.view_layer.objects.active = base
        bpy.ops.object.mode_set(mode="POSE")
        st.pose_mode_restore = json.dumps(info)
        return {"FINISHED"}


class OPL_OT_apply_pose(bpy.types.Operator):
    bl_idname = "opl.apply_pose"
    bl_label = "Apply Pose"
    bl_description = "Apply the chosen test pose (arrows: previous / next pose)"
    bl_options = {"REGISTER", "UNDO"}
    step: IntProperty(default=0)

    def execute(self, context):
        st = S(context)
        if st.base is None:
            self.report({"ERROR"}, "Set the base armature first (Auto Detect)")
            return {"CANCELLED"}
        keys = [k for k, _, _ in core.pose_names(st)]
        if self.step and keys:
            i = keys.index(st.pose) if st.pose in keys else 0
            auto = st.auto_apply
            st.auto_apply = False
            st.pose = keys[(i + self.step) % len(keys)]
            st.auto_apply = auto
        core.apply_pose(st, st.pose, pose_targets(st), st.amount)
        return {"FINISHED"}


class OPL_OT_rest(bpy.types.Operator):
    bl_idname = "opl.rest"
    bl_label = "Rest"
    bl_description = "Clear the pose of the base and all outfits (chains too)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        if st.base:
            core.clear_pose([st.base] + outfits(st))
            context.view_layer.update()
        return {"FINISHED"}


class OPL_OT_save_pose(bpy.types.Operator):
    bl_idname = "opl.save_pose"
    bl_label = "Save Current Pose"
    bl_description = "Store the base armature's current pose as a test pose (saved in this .blend)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        if st.base is None:
            return {"CANCELLED"}
        name = st.new_pose_name.strip() or "My pose"
        p = next((p for p in st.custom_poses if p.name == name), None) or st.custom_poses.add()
        p.name = name
        p.data = core.capture_pose(st.base)
        self.report({"INFO"}, f"Saved pose '{name}'")
        return {"FINISHED"}


class OPL_OT_delete_pose(bpy.types.Operator):
    bl_idname = "opl.delete_pose"
    bl_label = "Delete Saved Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        if 0 <= st.custom_index < len(st.custom_poses):
            st.custom_poses.remove(st.custom_index)
            st.custom_index = max(0, st.custom_index - 1)
        return {"FINISHED"}


class OPL_OT_reel(bpy.types.Operator):
    bl_idname = "opl.reel"
    bl_label = "Pose Reel"
    bl_description = "Keyframe every test pose on the timeline (10 frames apart) so you can scrub or play through them"
    bl_options = {"REGISTER", "UNDO"}
    remove: BoolProperty(default=False)

    def execute(self, context):
        st = S(context)
        if st.base is None:
            return {"CANCELLED"}
        if self.remove:
            core.remove_reel(st, st.base)
            self.report({"INFO"}, "Pose reel removed")
            return {"FINISHED"}
        keys = [k for k, _, _ in core.pose_names(st) if not k.startswith("qa:")]
        n = core.build_reel(st, st.base, keys)
        self.report({"INFO"}, f"Pose reel: {n} poses on frames 1-{1 + (n - 1) * 10}. Press Space to play.")
        return {"FINISHED"}


# ---------------------------------------------------------------- chains
class OPL_OT_swing_reset(bpy.types.Operator):
    bl_idname = "opl.swing_reset"
    bl_label = "Reset Chains"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        st.swing_angle = 0.0
        return {"FINISHED"}


# ---------------------------------------------------------------- toggle states
class OPL_OT_state_capture(bpy.types.Operator):
    bl_idname = "opl.state_capture"
    bl_label = "Save Toggle State"
    bl_description = "Remember which meshes are visible and the shape key values, for example hood up or hood down"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        if st.base is None:
            return {"CANCELLED"}
        name = st.new_state_name.strip() or "Toggle"
        s = next((s for s in st.states if s.name == name), None) or st.states.add()
        s.name = name
        s.data = core.capture_state(core.armature_meshes([st.base] + outfits(st)))
        return {"FINISHED"}


class OPL_OT_state_apply(bpy.types.Operator):
    bl_idname = "opl.state_apply"
    bl_label = "Apply Toggle State"
    bl_options = {"REGISTER", "UNDO"}
    index: IntProperty(default=-1)

    def execute(self, context):
        st = S(context)
        i = self.index if self.index >= 0 else st.state_index
        if 0 <= i < len(st.states):
            core.apply_state(st, st.states[i].data)
            st.state_index = i
        return {"FINISHED"}


class OPL_OT_state_delete(bpy.types.Operator):
    bl_idname = "opl.state_delete"
    bl_label = "Delete Toggle State"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        if 0 <= st.state_index < len(st.states):
            st.states.remove(st.state_index)
            st.state_index = max(0, st.state_index - 1)
        return {"FINISHED"}


class OPL_OT_state_import(bpy.types.Operator):
    bl_idname = "opl.state_import"
    bl_label = "Import QA States"
    bl_description = "Create toggle states from the avatar_qa config in this .blend"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        got = core.states_from_config(core.armature_meshes([st.base] + outfits(st)) if st.base else [])
        for name, data in got.items():
            s = next((s for s in st.states if s.name == name), None) or st.states.add()
            s.name, s.data = name, data
        self.report({"INFO"}, f"Imported {len(got)} states")
        return {"FINISHED"}


# ---------------------------------------------------------------- weights / export / QA
def _weight_meshes(context, st):
    if st.weight_scope == "SELECTED":
        return [o for o in context.selected_objects if o.type == "MESH"]
    arms = outfits(st) + ([st.base] if st.weight_scope == "ALL" else [])
    return core.armature_meshes(arms)


class OPL_OT_weights_check(bpy.types.Operator):
    bl_idname = "opl.weights_check"
    bl_label = "Check Weights"
    bl_description = "Report problems that break in game engines: unweighted verts, more than 4 bones, torn split seams..."

    def execute(self, context):
        st = S(context)
        lines = []
        for o in _weight_meshes(context, st):
            r = core.check_weights(o)
            bad = [f"{k.replace('_', ' ')} {v}" for k, v in r.items() if k != "armature" and v]
            lines.append(f"{'⚠' if bad else '✓'} {o.name}: " + (", ".join(bad) if bad else "ok"))
        st.last_report = "\n".join(lines) or "No meshes"
        self.report({"INFO"}, f"Checked {len(lines)} meshes")
        return {"FINISHED"}


class OPL_OT_weights_fix(bpy.types.Operator):
    bl_idname = "opl.weights_fix"
    bl_label = "Fix Weights"
    bl_description = ("Weld weights of overlapping verts (torn seams), limit to 4 bones, normalize, drop tiny "
                      "weights and empty groups. Undo with Ctrl+Z")
    bl_options = {"REGISTER", "UNDO"}
    weld: BoolProperty(name="Weld split seams", default=True)
    limit: BoolProperty(name="Limit to 4 bones", default=True)
    normalize: BoolProperty(name="Normalize", default=True)
    clean: BoolProperty(name="Remove weights < 0.001", default=True)
    drop_empty: BoolProperty(name="Remove empty groups", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        st = S(context)
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        lines = []
        for o in _weight_meshes(context, st):
            r = core.fix_weights(o, weld=self.weld, limit=self.limit, normalize=self.normalize, clean=self.clean,
                                 drop_empty=self.drop_empty)
            lines.append(f"{o.name}: {r['changed_verts']} verts changed, {r['removed_groups']} groups removed")
        st.last_report = "\n".join(lines) or "No meshes"
        return {"FINISHED"}


class OPL_OT_export_prep(bpy.types.Operator):
    bl_idname = "opl.export_prep"
    bl_label = "Prepare for Export"
    bl_description = "Rest pose everywhere, remove the pose reel and reset chains (links stay; they do not export)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        st = S(context)
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if st.base:
            core.remove_reel(st, st.base)
            st["swing_angle"] = 0.0
            st["hang"] = False
            core.clear_pose([st.base] + outfits(st))
            context.view_layer.update()
        self.report({"INFO"}, "Ready to export: everything is in rest pose")
        return {"FINISHED"}


class OPL_OT_run_qa(bpy.types.Operator):
    bl_idname = "opl.run_qa"
    bl_label = "Run Avatar QA"
    bl_description = "Run the embedded avatar_qa suite (text block run_avatar_qa.py); report in avatar_qa_report.txt"

    def execute(self, context):
        txt = bpy.data.texts.get("run_avatar_qa.py")
        if txt is None:
            self.report({"ERROR"}, "No run_avatar_qa.py text block in this file")
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        ns = {"__name__": "__main__"}
        exec(compile(txt.as_string(), "run_avatar_qa.py", "exec"), ns)
        s = ns["rep"]["summary"]
        self.report({"INFO"}, f"QA: PASS {s['PASS']}  WARN {s['WARN']}  FAIL {s['FAIL']} (see avatar_qa_report.txt)")
        return {"FINISHED"}


CLASSES = (OPL_MapRow, OPL_Outfit, OPL_Saved, OPL_Settings,
           OPL_OT_detect, OPL_OT_add_outfit, OPL_OT_remove_outfit, OPL_OT_refresh_map, OPL_OT_link, OPL_OT_unlink,
           OPL_OT_mute, OPL_OT_pose_mode, OPL_OT_apply_pose, OPL_OT_rest, OPL_OT_save_pose, OPL_OT_delete_pose,
           OPL_OT_reel, OPL_OT_swing_reset, OPL_OT_state_capture, OPL_OT_state_apply, OPL_OT_state_delete,
           OPL_OT_state_import, OPL_OT_weights_check, OPL_OT_weights_fix, OPL_OT_export_prep,
           OPL_OT_run_qa)
