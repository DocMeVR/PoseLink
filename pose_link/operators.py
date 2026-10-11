"""Operators behind the buttons in the PoseLink panel."""
import json

import bpy
from bpy.props import BoolProperty, IntProperty

from . import linking, poses, toggles, weights
from .properties import get_settings, outfit_armatures, pose_targets


# ---------------------------------------------------------------- setup and linking
class POSELINK_OT_detect(bpy.types.Operator):
    bl_idname = "poselink.detect"
    bl_label = "Find Armatures"
    bl_description = "Find the body armature and every outfit armature that fits it"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        if settings.base is None:
            settings.base = linking.guess_body_armature()
        if settings.base is None:
            self.report({"ERROR"}, "No armature in the scene")
            return {"CANCELLED"}
        known = {entry.obj for entry in settings.outfits if entry.obj}
        for armature in linking.find_outfits(settings.base):
            if armature not in known:
                settings.outfits.add().obj = armature
        for entry in settings.outfits:
            if entry.obj:
                linking.refresh_rows(entry, settings.base)
        found = ", ".join(obj.name for obj in outfit_armatures(settings)) or "none"
        self.report({"INFO"}, f"Base: {settings.base.name}; outfits: {found}")
        return {"FINISHED"}


class POSELINK_OT_add_outfit(bpy.types.Operator):
    bl_idname = "poselink.add_outfit"
    bl_label = "Add Selected Armature"
    bl_description = "Add the selected armatures as outfits"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        known = {entry.obj for entry in settings.outfits}
        added = 0
        for obj in context.selected_objects:
            if obj.type == "ARMATURE" and obj is not settings.base and obj not in known:
                entry = settings.outfits.add()
                entry.obj = obj
                if settings.base:
                    linking.refresh_rows(entry, settings.base)
                added += 1
        if not added:
            self.report({"WARNING"}, "Select an outfit armature first (not the base)")
            return {"CANCELLED"}
        return {"FINISHED"}


class POSELINK_OT_remove_outfit(bpy.types.Operator):
    bl_idname = "poselink.remove_outfit"
    bl_label = "Remove Outfit"
    bl_description = "Unlink the active outfit and remove it from the list"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        if 0 <= settings.outfit_index < len(settings.outfits):
            armature = settings.outfits[settings.outfit_index].obj
            if armature:
                linking.unlink(armature)
            settings.outfits.remove(settings.outfit_index)
            settings.outfit_index = max(0, settings.outfit_index - 1)
        return {"FINISHED"}


class POSELINK_OT_refresh_matches(bpy.types.Operator):
    bl_idname = "poselink.refresh_matches"
    bl_label = "Match Bones Again"
    bl_description = "Match outfit bones to body bones again. Bones you picked by hand are kept"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        for entry in settings.outfits:
            if entry.obj and settings.base:
                linking.refresh_rows(entry, settings.base)
        return {"FINISHED"}


class POSELINK_OT_link(bpy.types.Operator):
    bl_idname = "poselink.link"
    bl_label = "Link"
    bl_description = "Make the outfit armatures follow the base, one Copy Transforms constraint per matched bone"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        if settings.base is None or not settings.outfits:
            bpy.ops.poselink.detect()
        if settings.base is None:
            return {"CANCELLED"}
        linked = 0
        for entry in settings.outfits:
            if entry.obj:
                if not len(entry.rows):
                    linking.refresh_rows(entry, settings.base)
                linked += linking.link(entry, settings.base)
        self.report({"INFO"}, f"Linked {linked} bones")
        return {"FINISHED"}


class POSELINK_OT_unlink(bpy.types.Operator):
    bl_idname = "poselink.unlink"
    bl_label = "Unlink"
    bl_description = "Remove the link constraints from every outfit"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        removed = sum(linking.unlink(obj) for obj in outfit_armatures(get_settings(context)))
        self.report({"INFO"}, f"Removed {removed} constraints")
        return {"FINISHED"}


class POSELINK_OT_pause(bpy.types.Operator):
    bl_idname = "poselink.pause"
    bl_label = "Pause Link"
    bl_description = "Switch the link off or on again without removing it"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        links = [c for obj in outfit_armatures(get_settings(context)) for c in linking.links_of(obj)]
        if links:
            mute = not links[0].mute
            for constraint in links:
                constraint.mute = mute
        return {"FINISHED"}


# ---------------------------------------------------------------- posing
class POSELINK_OT_pose_mode(bpy.types.Operator):
    bl_idname = "poselink.pose_mode"
    bl_label = "Pose Base Armature"
    bl_description = "Go into Pose Mode on the base armature (the outfits follow), or back out of it"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        body = settings.base
        if body is None:
            return {"CANCELLED"}
        if context.mode == "POSE" and context.active_object is body:
            self._leave(context, settings, body)
        else:
            self._enter(context, settings, body)
        return {"FINISHED"}

    @staticmethod
    def _enter(context, settings, body):
        # remember the selection so leaving pose mode can give it back
        remembered = {"active": context.active_object.name if context.active_object else "",
                      "selected": [obj.name for obj in context.selected_objects],
                      "base_hidden": body.hide_get()}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        body.hide_viewport = False
        body.hide_set(False)
        for obj in context.selected_objects:
            obj.select_set(False)
        body.select_set(True)
        context.view_layer.objects.active = body
        bpy.ops.object.mode_set(mode="POSE")
        settings.pose_mode_restore = json.dumps(remembered)

    @staticmethod
    def _leave(context, settings, body):
        bpy.ops.object.mode_set(mode="OBJECT")
        remembered = json.loads(settings.pose_mode_restore or "{}")
        for obj in context.selected_objects:
            obj.select_set(False)
        for name in remembered.get("selected", []):
            obj = bpy.data.objects.get(name)
            if obj:
                obj.select_set(True)
        context.view_layer.objects.active = bpy.data.objects.get(remembered.get("active", ""))
        if remembered.get("base_hidden"):
            body.hide_set(True)
        settings.pose_mode_restore = ""


class POSELINK_OT_apply_pose(bpy.types.Operator):
    bl_idname = "poselink.apply_pose"
    bl_label = "Apply Pose"
    bl_description = "Apply the chosen test pose. The arrows go to the previous or next pose"
    bl_options = {"REGISTER", "UNDO"}

    step: IntProperty(default=0)

    def execute(self, context):
        settings = get_settings(context)
        if settings.base is None:
            self.report({"ERROR"}, "Set the base armature first")
            return {"CANCELLED"}
        keys = [key for key, _, _ in poses.pose_items(settings)]
        if self.step and keys:
            current = keys.index(settings.pose) if settings.pose in keys else 0
            auto_apply = settings.auto_apply
            settings.auto_apply = False   # apply once below, not twice
            settings.pose = keys[(current + self.step) % len(keys)]
            settings.auto_apply = auto_apply
        poses.apply_pose(settings, settings.pose, pose_targets(settings), settings.amount)
        return {"FINISHED"}


class POSELINK_OT_rest(bpy.types.Operator):
    bl_idname = "poselink.rest"
    bl_label = "Rest"
    bl_description = "Clear the pose of the base and every outfit, chains too"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        if settings.base:
            poses.clear_pose([settings.base] + outfit_armatures(settings))
            context.view_layer.update()
        return {"FINISHED"}


class POSELINK_OT_save_pose(bpy.types.Operator):
    bl_idname = "poselink.save_pose"
    bl_label = "Save Current Pose"
    bl_description = "Keep the base armature's current pose as a test pose, saved in this .blend"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        if settings.base is None:
            return {"CANCELLED"}
        name = settings.new_pose_name.strip() or "My pose"
        saved = next((p for p in settings.custom_poses if p.name == name), None) or settings.custom_poses.add()
        saved.name = name
        saved.data = poses.capture_pose(settings.base)
        self.report({"INFO"}, f"Saved pose '{name}'")
        return {"FINISHED"}


class POSELINK_OT_delete_pose(bpy.types.Operator):
    bl_idname = "poselink.delete_pose"
    bl_label = "Delete Saved Pose"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        if 0 <= settings.custom_index < len(settings.custom_poses):
            settings.custom_poses.remove(settings.custom_index)
            settings.custom_index = max(0, settings.custom_index - 1)
        return {"FINISHED"}


class POSELINK_OT_pose_reel(bpy.types.Operator):
    bl_idname = "poselink.pose_reel"
    bl_label = "Pose Reel"
    bl_description = "Key every test pose on the timeline, 10 frames apart, to scrub or play through them"
    bl_options = {"REGISTER", "UNDO"}

    remove: BoolProperty(default=False)

    def execute(self, context):
        settings = get_settings(context)
        if settings.base is None:
            return {"CANCELLED"}
        if self.remove:
            poses.remove_reel(settings, settings.base)
            self.report({"INFO"}, "Pose reel removed")
            return {"FINISHED"}
        count = poses.build_reel(settings, settings.base, [key for key, _, _ in poses.pose_items(settings)])
        self.report({"INFO"}, f"Pose reel: {count} poses on frames 1-{1 + (count - 1) * 10}. Press Space to play")
        return {"FINISHED"}


class POSELINK_OT_reset_chains(bpy.types.Operator):
    bl_idname = "poselink.reset_chains"
    bl_label = "Reset Chains"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        get_settings(context).swing_angle = 0.0   # the update puts every chain bone back
        return {"FINISHED"}


# ---------------------------------------------------------------- toggles
class POSELINK_OT_save_toggle(bpy.types.Operator):
    bl_idname = "poselink.save_toggle"
    bl_label = "Save Toggle"
    bl_description = "Remember which meshes are visible and the shape key values, for example hood up or hood down"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        if settings.base is None:
            return {"CANCELLED"}
        name = settings.new_state_name.strip() or "Toggle"
        saved = next((s for s in settings.states if s.name == name), None) or settings.states.add()
        saved.name = name
        saved.data = toggles.capture(linking.meshes_of([settings.base] + outfit_armatures(settings)))
        return {"FINISHED"}


class POSELINK_OT_apply_toggle(bpy.types.Operator):
    bl_idname = "poselink.apply_toggle"
    bl_label = "Apply Toggle"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)

    def execute(self, context):
        settings = get_settings(context)
        index = self.index if self.index >= 0 else settings.state_index
        if 0 <= index < len(settings.states):
            toggles.apply(settings, settings.states[index].data)
            settings.state_index = index
        return {"FINISHED"}


class POSELINK_OT_delete_toggle(bpy.types.Operator):
    bl_idname = "poselink.delete_toggle"
    bl_label = "Delete Toggle"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        if 0 <= settings.state_index < len(settings.states):
            settings.states.remove(settings.state_index)
            settings.state_index = max(0, settings.state_index - 1)
        return {"FINISHED"}


# ---------------------------------------------------------------- weights and export
def _meshes_to_check(context, settings):
    if settings.weight_scope == "SELECTED":
        return [obj for obj in context.selected_objects if obj.type == "MESH"]
    armatures = outfit_armatures(settings) + ([settings.base] if settings.weight_scope == "ALL" else [])
    return linking.meshes_of(armatures)


class POSELINK_OT_check_weights(bpy.types.Operator):
    bl_idname = "poselink.check_weights"
    bl_label = "Check Weights"
    bl_description = "Report what breaks in game engines: unweighted vertices, more than 4 bones, torn seams"

    def execute(self, context):
        settings = get_settings(context)
        lines = []
        for obj in _meshes_to_check(context, settings):
            problems = [f"{name.replace('_', ' ')} {count}"
                        for name, count in weights.check(obj).items() if name != "armature" and count]
            lines.append(f"{'⚠' if problems else '✓'} {obj.name}: " + (", ".join(problems) or "ok"))
        settings.last_report = "\n".join(lines) or "No meshes"
        self.report({"INFO"}, f"Checked {len(lines)} meshes")
        return {"FINISHED"}


class POSELINK_OT_fix_weights(bpy.types.Operator):
    bl_idname = "poselink.fix_weights"
    bl_label = "Fix Weights"
    bl_description = ("Give vertices on the same spot the same weights, keep 4 bones per vertex, make the weights "
                      "add up to 1, drop tiny weights and empty groups. Ctrl+Z undoes it")
    bl_options = {"REGISTER", "UNDO"}

    weld: BoolProperty(name="Weld split seams", default=True)
    limit: BoolProperty(name="Keep 4 bones per vertex", default=True)
    normalize: BoolProperty(name="Normalize", default=True)
    clean: BoolProperty(name="Remove weights below 0.001", default=True)
    drop_empty: BoolProperty(name="Remove empty groups", default=True)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        settings = get_settings(context)
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        lines = []
        for obj in _meshes_to_check(context, settings):
            result = weights.fix(obj, weld=self.weld, limit=self.limit, normalize=self.normalize,
                                 clean=self.clean, drop_empty=self.drop_empty)
            lines.append(f"{obj.name}: {result['changed_verts']} vertices changed, "
                         f"{result['removed_groups']} groups removed")
        settings.last_report = "\n".join(lines) or "No meshes"
        return {"FINISHED"}


class POSELINK_OT_prepare_export(bpy.types.Operator):
    bl_idname = "poselink.prepare_export"
    bl_label = "Prepare for Export"
    bl_description = ("Rest pose everywhere, remove the pose reel and reset the chains. "
                      "The links stay; they don't export")
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        settings = get_settings(context)
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if settings.base:
            poses.remove_reel(settings, settings.base)
            # set without the update callbacks, the pose is cleared right after anyway
            settings["swing_angle"] = 0.0
            settings["hang"] = False
            poses.clear_pose([settings.base] + outfit_armatures(settings))
            context.view_layer.update()
        self.report({"INFO"}, "Ready to export: everything is in rest pose")
        return {"FINISHED"}


classes = (
    POSELINK_OT_detect, POSELINK_OT_add_outfit, POSELINK_OT_remove_outfit, POSELINK_OT_refresh_matches,
    POSELINK_OT_link, POSELINK_OT_unlink, POSELINK_OT_pause,
    POSELINK_OT_pose_mode, POSELINK_OT_apply_pose, POSELINK_OT_rest, POSELINK_OT_save_pose,
    POSELINK_OT_delete_pose, POSELINK_OT_pose_reel, POSELINK_OT_reset_chains,
    POSELINK_OT_save_toggle, POSELINK_OT_apply_toggle, POSELINK_OT_delete_toggle,
    POSELINK_OT_check_weights, POSELINK_OT_fix_weights, POSELINK_OT_prepare_export,
)
register, unregister = bpy.utils.register_classes_factory(classes)
