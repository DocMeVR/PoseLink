"""Sidebar UI (View3D > Sidebar > PoseLink)."""
import bpy

from . import core
from .ops import S

METHOD_ICON = {"exact": "CHECKMARK", "affix": "SORTALPHA", "humanoid": "ARMATURE_DATA", "manual": "GREASEPENCIL",
               "none": "BLANK1"}


class OPL_UL_outfits(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        if item.obj is None:
            layout.label(text="(missing)", icon="ERROR")
            return
        cons = core.link_constraints(item.obj)
        mapped = sum(1 for r in item.rows if r.base_bone)
        ic = "LINKED" if cons and not cons[0].mute else ("PAUSE" if cons else "UNLINKED")
        layout.label(text=item.obj.name, icon=ic)
        layout.label(text=f"{len(cons)}/{mapped} linked" if cons else f"{mapped} matched")


class OPL_UL_rows(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        st = S(context)
        row = layout.row(align=True)
        row.label(text=item.outfit_bone, icon=METHOD_ICON.get(item.method, "BLANK1"))
        if st.base:
            row.prop_search(item, "base_bone", st.base.data, "bones", text="")
        else:
            row.prop(item, "base_bone", text="")

    def filter_items(self, context, data, propname):
        rows = getattr(data, propname)
        flt = [self.bitflag_filter_item] * len(rows)
        if self.filter_name:
            f = self.filter_name.lower()
            flt = [self.bitflag_filter_item if f in r.outfit_bone.lower() or f in r.base_bone.lower() else 0 for r in rows]
        return flt, []


class OPL_UL_saved(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        layout.prop(item, "name", text="", emboss=False, icon="BOOKMARKS")


class OPL_UL_states(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_prop):
        row = layout.row(align=True)
        row.prop(item, "name", text="", emboss=False, icon="HIDE_OFF")
        idx = list(data.states).index(item)
        row.operator("opl.state_apply", text="", icon="PLAY").index = idx


def _hang_row(lay, st):
    row = lay.row(align=True)
    row.prop(st, "hang", text="Hang chains (gravity)", icon="PHYSICS")
    sub = row.row(align=True)
    sub.active = st.hang
    sub.prop(st, "hang_strength", text="", slider=True)


class _Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "PoseLink"


class OPL_PT_main(_Base, bpy.types.Panel):
    bl_label = "PoseLink"

    def draw(self, context):
        st = S(context)
        lay = self.layout
        row = lay.row(align=True)
        row.prop(st, "base", text="Base")
        row.operator("opl.detect", text="", icon="VIEWZOOM")
        if st.base is None:
            lay.label(text="Press the magnifier to find your avatar", icon="INFO")
            return
        row = lay.row()
        row.template_list("OPL_UL_outfits", "", st, "outfits", st, "outfit_index", rows=2)
        col = row.column(align=True)
        col.operator("opl.add_outfit", text="", icon="ADD")
        col.operator("opl.remove_outfit", text="", icon="REMOVE")
        col.operator("opl.refresh_map", text="", icon="FILE_REFRESH")
        row = lay.row(align=True)
        row.scale_y = 1.3
        row.operator("opl.link", icon="LINKED")
        row.operator("opl.mute", text="", icon="PAUSE")
        row.operator("opl.unlink", text="", icon="UNLINKED")
        in_pose = context.mode == "POSE" and context.active_object is st.base
        row = lay.row()
        row.scale_y = 1.3
        row.operator("opl.pose_mode", text="Exit Pose Mode" if in_pose else "Pose Base Armature",
                     icon="OBJECT_DATAMODE" if in_pose else "POSE_HLT", depress=in_pose)
        _hang_row(lay, st)
        if st.outfits and 0 <= st.outfit_index < len(st.outfits):
            it = st.outfits[st.outfit_index]
            if it.obj:
                off = core.rest_mismatch(it, st.base)
                if off:
                    box = lay.box()
                    box.alert = True
                    worst = max(off, key=lambda x: x[1])
                    box.label(text=f"{len(off)} bones not at the base position", icon="ERROR")
                    box.label(text=f"worst {worst[0]}: {worst[1] * 1000:.0f} mm (outfit fitted to another body?)")


class OPL_PT_mapping(_Base, bpy.types.Panel):
    bl_label = "Bone Matching"
    bl_parent_id = "OPL_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        st = S(context)
        return st.base is not None and len(st.outfits) > 0

    def draw(self, context):
        st = S(context)
        lay = self.layout
        it = st.outfits[min(st.outfit_index, len(st.outfits) - 1)]
        counts = {}
        for r in it.rows:
            counts[r.method] = counts.get(r.method, 0) + 1
        lay.label(text="  ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "no bones")
        lay.label(text="'none' = outfit-only bone, follows its parent", icon="INFO")
        lay.template_list("OPL_UL_rows", "", it, "rows", it, "row_index", rows=8)
        lay.label(text="Change a base bone to override the match, then press Link again")


class OPL_PT_pose(_Base, bpy.types.Panel):
    bl_label = "Test Poses"
    bl_parent_id = "OPL_PT_main"

    @classmethod
    def poll(cls, context):
        return S(context).base is not None

    def draw(self, context):
        st = S(context)
        lay = self.layout
        lay.prop(st, "pose", text="")
        row = lay.row(align=True)
        row.operator("opl.apply_pose", text="", icon="TRIA_LEFT").step = -1
        row.operator("opl.apply_pose", text="Apply").step = 0
        row.operator("opl.apply_pose", text="", icon="TRIA_RIGHT").step = 1
        row.operator("opl.rest", icon="ARMATURE_DATA")
        lay.prop(st, "amount", slider=True)
        box = lay.box()
        box.label(text="Your poses (pose the base, then save)", icon="BOOKMARKS")
        row = box.row(align=True)
        row.prop(st, "new_pose_name", text="")
        row.operator("opl.save_pose", text="", icon="ADD")
        if st.custom_poses:
            row = box.row()
            row.template_list("OPL_UL_saved", "poses", st, "custom_poses", st, "custom_index", rows=2)
            row.operator("opl.delete_pose", text="", icon="REMOVE")
        row = lay.row(align=True)
        if core.reel_active(st.base):
            row.operator("opl.reel", text="Remove Pose Reel", icon="X").remove = True
            lay.label(text="Scrub the timeline or press Space", icon="PLAY")
        else:
            row.operator("opl.reel", text="Make Pose Reel (timeline)", icon="ACTION").remove = False


class OPL_PT_chains(_Base, bpy.types.Panel):
    bl_label = "Chain Swing"
    bl_parent_id = "OPL_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return S(context).base is not None

    def draw(self, context):
        st = S(context)
        lay = self.layout
        lay.prop(st, "swing_target", expand=True)
        _hang_row(lay, st)
        lay.prop(st, "swing_mode")
        lay.prop(st, "swing_filter", icon="FILTER")
        lay.prop(st, "swing_angle", slider=True)
        n = 0
        for i in st.outfits:
            if i.obj and st.swing_target in ("OUTFITS", "ALL"):
                n += len(core.chains(i.obj, core.body_bones(i.obj, st.base, i), st.swing_filter))
        if st.swing_target in ("BASE", "ALL"):
            n += len(core.chains(st.base, core.body_bones(st.base, st.base), st.swing_filter))
        lay.label(text=f"{n} chain bones", icon="BONE_DATA")
        lay.operator("opl.swing_reset", icon="LOOP_BACK")


class OPL_PT_toggles(_Base, bpy.types.Panel):
    bl_label = "Toggles"
    bl_parent_id = "OPL_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context):
        return S(context).base is not None

    def draw(self, context):
        st = S(context)
        lay = self.layout
        lay.label(text="Set up meshes + shape keys, then save", icon="INFO")
        row = lay.row(align=True)
        row.prop(st, "new_state_name", text="")
        row.operator("opl.state_capture", text="", icon="ADD")
        row = lay.row()
        row.template_list("OPL_UL_states", "", st, "states", st, "state_index", rows=3)
        row.operator("opl.state_delete", text="", icon="REMOVE")


class OPL_PT_weights(_Base, bpy.types.Panel):
    bl_label = "Weight Check"
    bl_parent_id = "OPL_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        st = S(context)
        lay = self.layout
        lay.prop(st, "weight_scope")
        row = lay.row(align=True)
        row.operator("opl.weights_check", icon="VIEWZOOM")
        row.operator("opl.weights_fix", icon="MODIFIER")
        if st.last_report:
            box = lay.box()
            for line in st.last_report.splitlines()[:14]:
                box.label(text=line)


class OPL_PT_finish(_Base, bpy.types.Panel):
    bl_label = "Finish"
    bl_parent_id = "OPL_PT_main"

    @classmethod
    def poll(cls, context):
        return S(context).base is not None

    def draw(self, context):
        self.layout.operator("opl.export_prep", icon="EXPORT")


CLASSES = (OPL_UL_outfits, OPL_UL_rows, OPL_UL_saved, OPL_UL_states, OPL_PT_main, OPL_PT_mapping, OPL_PT_pose,
           OPL_PT_chains, OPL_PT_toggles, OPL_PT_weights, OPL_PT_finish)
