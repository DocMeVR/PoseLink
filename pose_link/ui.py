"""The PoseLink tab in the 3D View sidebar."""
import bpy

from . import chains, linking, poses
from .properties import get_settings

MATCH_ICONS = {"exact": "CHECKMARK", "similar": "SORTALPHA", "manual": "GREASEPENCIL", "none": "BLANK1"}


class POSELINK_UL_outfits(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        if item.obj is None:
            layout.label(text="(missing)", icon="ERROR")
            return
        links = linking.links_of(item.obj)
        matched = sum(1 for row in item.rows if row.base_bone)
        if links:
            layout.label(text=item.obj.name, icon="PAUSE" if links[0].mute else "LINKED")
            layout.label(text=f"{len(links)}/{matched} linked")
        else:
            layout.label(text=item.obj.name, icon="UNLINKED")
            layout.label(text=f"{matched} matched")


class POSELINK_UL_bones(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        settings = get_settings(context)
        row = layout.row(align=True)
        row.label(text=item.outfit_bone, icon=MATCH_ICONS.get(item.method, "SORTALPHA"))
        if settings.base:
            row.prop_search(item, "base_bone", settings.base.data, "bones", text="")
        else:
            row.prop(item, "base_bone", text="")

    def filter_items(self, context, data, propname):
        rows = getattr(data, propname)
        text = self.filter_name.lower()
        if not text:
            return [self.bitflag_filter_item] * len(rows), []
        return [self.bitflag_filter_item if text in row.outfit_bone.lower() or text in row.base_bone.lower() else 0
                for row in rows], []


class POSELINK_UL_saved(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        layout.prop(item, "name", text="", emboss=False, icon="BOOKMARKS")


class POSELINK_UL_toggles(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="HIDE_OFF")
        row.operator("poselink.apply_toggle", text="", icon="PLAY").index = list(data.states).index(item)


def draw_hang_row(layout, settings):
    row = layout.row(align=True)
    row.prop(settings, "hang", icon="PHYSICS")
    strength = row.row(align=True)
    strength.active = settings.hang
    strength.prop(settings, "hang_strength", text="", slider=True)


def draw_fit_warning(layout, settings):
    """A red box when the active outfit's bones are not where the body's bones are."""
    if not (0 <= settings.outfit_index < len(settings.outfits)):
        return
    entry = settings.outfits[settings.outfit_index]
    misplaced = linking.misplaced_bones(entry, settings.base) if entry.obj else []
    if misplaced:
        name, distance = max(misplaced, key=lambda item: item[1])
        box = layout.box()
        box.alert = True
        box.label(text=f"{len(misplaced)} bones are not where the base bones are", icon="ERROR")
        box.label(text=f"Furthest: {name}, {distance * 1000:.0f} mm. Made for another body?")


class SidebarPanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PoseLink"


class POSELINK_PT_main(SidebarPanel, bpy.types.Panel):
    bl_label = "PoseLink"

    def draw(self, context):
        settings = get_settings(context)
        layout = self.layout
        row = layout.row(align=True)
        row.prop(settings, "base", text="Base")
        row.operator("poselink.detect", text="", icon="VIEWZOOM")
        if settings.base is None:
            layout.label(text="Press the magnifier to find the armatures", icon="INFO")
            return

        row = layout.row()
        row.template_list("POSELINK_UL_outfits", "", settings, "outfits", settings, "outfit_index", rows=2)
        buttons = row.column(align=True)
        buttons.operator("poselink.add_outfit", text="", icon="ADD")
        buttons.operator("poselink.remove_outfit", text="", icon="REMOVE")
        buttons.operator("poselink.refresh_matches", text="", icon="FILE_REFRESH")

        row = layout.row(align=True)
        row.scale_y = 1.3
        row.operator("poselink.link", icon="LINKED")
        row.operator("poselink.pause", text="", icon="PAUSE")
        row.operator("poselink.unlink", text="", icon="UNLINKED")

        posing = context.mode == "POSE" and context.active_object is settings.base
        row = layout.row()
        row.scale_y = 1.3
        row.operator("poselink.pose_mode", text="Exit Pose Mode" if posing else "Pose Base Armature",
                     icon="OBJECT_DATAMODE" if posing else "POSE_HLT", depress=posing)
        draw_hang_row(layout, settings)
        draw_fit_warning(layout, settings)


class POSELINK_PT_bones(SidebarPanel, bpy.types.Panel):
    bl_label = "Bone Matching"
    bl_parent_id = "POSELINK_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        settings = get_settings(context)
        return settings.base is not None and len(settings.outfits) > 0

    def draw(self, context):
        settings = get_settings(context)
        layout = self.layout
        entry = settings.outfits[min(settings.outfit_index, len(settings.outfits) - 1)]
        counts = {}
        for row in entry.rows:
            counts[row.method] = counts.get(row.method, 0) + 1
        layout.label(text="  ".join(f"{method}: {count}" for method, count in sorted(counts.items())) or "No bones")
        layout.template_list("POSELINK_UL_bones", "", entry, "rows", entry, "row_index", rows=8)
        layout.label(text="Pick another base bone to change a match, then press Link", icon="INFO")
        layout.label(text="'none' bones belong to the outfit and follow their parent")


class POSELINK_PT_poses(SidebarPanel, bpy.types.Panel):
    bl_label = "Test Poses"
    bl_parent_id = "POSELINK_PT_main"

    @classmethod
    def poll(cls, context):
        return get_settings(context).base is not None

    def draw(self, context):
        settings = get_settings(context)
        layout = self.layout
        layout.prop(settings, "pose", text="")
        row = layout.row(align=True)
        row.operator("poselink.apply_pose", text="", icon="TRIA_LEFT").step = -1
        row.operator("poselink.apply_pose", text="Apply").step = 0
        row.operator("poselink.apply_pose", text="", icon="TRIA_RIGHT").step = 1
        row.operator("poselink.rest", icon="ARMATURE_DATA")
        layout.prop(settings, "amount", slider=True)

        box = layout.box()
        box.label(text="Your poses: pose the base, then save", icon="BOOKMARKS")
        row = box.row(align=True)
        row.prop(settings, "new_pose_name", text="")
        row.operator("poselink.save_pose", text="", icon="ADD")
        if settings.custom_poses:
            row = box.row()
            row.template_list("POSELINK_UL_saved", "poses", settings, "custom_poses", settings, "custom_index", rows=2)
            row.operator("poselink.delete_pose", text="", icon="REMOVE")

        if poses.reel_active(settings.base):
            layout.operator("poselink.pose_reel", text="Remove Pose Reel", icon="X").remove = True
            layout.label(text="Scrub the timeline or press Space", icon="PLAY")
        else:
            layout.operator("poselink.pose_reel", text="Make Pose Reel", icon="ACTION").remove = False


class POSELINK_PT_chains(SidebarPanel, bpy.types.Panel):
    bl_label = "Chains"
    bl_parent_id = "POSELINK_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return get_settings(context).base is not None

    def draw(self, context):
        settings = get_settings(context)
        layout = self.layout
        layout.prop(settings, "swing_target", expand=True)
        draw_hang_row(layout, settings)
        layout.prop(settings, "swing_mode")
        layout.prop(settings, "swing_filter", icon="FILTER")
        layout.prop(settings, "swing_angle", slider=True)
        layout.label(text=f"{chains.count_chain_bones(settings)} chain bones", icon="BONE_DATA")
        layout.operator("poselink.reset_chains", icon="LOOP_BACK")


class POSELINK_PT_toggles(SidebarPanel, bpy.types.Panel):
    bl_label = "Toggles"
    bl_parent_id = "POSELINK_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return get_settings(context).base is not None

    def draw(self, context):
        settings = get_settings(context)
        layout = self.layout
        layout.label(text="Set up meshes and shape keys, then save", icon="INFO")
        row = layout.row(align=True)
        row.prop(settings, "new_state_name", text="")
        row.operator("poselink.save_toggle", text="", icon="ADD")
        row = layout.row()
        row.template_list("POSELINK_UL_toggles", "", settings, "states", settings, "state_index", rows=3)
        row.operator("poselink.delete_toggle", text="", icon="REMOVE")


class POSELINK_PT_weights(SidebarPanel, bpy.types.Panel):
    bl_label = "Weight Check"
    bl_parent_id = "POSELINK_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        settings = get_settings(context)
        layout = self.layout
        layout.prop(settings, "weight_scope")
        row = layout.row(align=True)
        row.operator("poselink.check_weights", icon="VIEWZOOM")
        row.operator("poselink.fix_weights", icon="MODIFIER")
        if settings.last_report:
            box = layout.box()
            for line in settings.last_report.splitlines()[:14]:
                box.label(text=line)


class POSELINK_PT_export(SidebarPanel, bpy.types.Panel):
    bl_label = "Export"
    bl_parent_id = "POSELINK_PT_main"

    @classmethod
    def poll(cls, context):
        return get_settings(context).base is not None

    def draw(self, context):
        self.layout.operator("poselink.prepare_export", icon="EXPORT")


classes = (
    POSELINK_UL_outfits, POSELINK_UL_bones, POSELINK_UL_saved, POSELINK_UL_toggles,
    POSELINK_PT_main, POSELINK_PT_bones, POSELINK_PT_poses, POSELINK_PT_chains, POSELINK_PT_toggles,
    POSELINK_PT_weights, POSELINK_PT_export,
)
register, unregister = bpy.utils.register_classes_factory(classes)
