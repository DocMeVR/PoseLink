"""Settings stored with the scene (scene.poselink)."""
import bpy
from bpy.app.handlers import persistent
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
                       IntVectorProperty, PointerProperty, StringProperty)

from . import chains, linking, poses


def get_settings(context):
    return context.scene.poselink


def outfit_armatures(settings):
    return [entry.obj for entry in settings.outfits if entry.obj]


def pose_targets(settings):
    """The armatures a test pose is applied to: the body, plus outfits that are not linked (those would stay put)."""
    return [settings.base] + [obj for obj in outfit_armatures(settings) if not linking.links_of(obj)]


def _is_armature(self, obj):
    return obj.type == "ARMATURE"


def _mark_manual(self, context):
    self.method = "manual"


_pose_item_cache = []   # Blender needs the strings of dynamic enum items to stay alive


def _pose_items(self, context):
    global _pose_item_cache
    _pose_item_cache = poses.pose_items(self)
    return _pose_item_cache


def _apply_chosen_pose(self, context):
    if self.auto_apply and self.base:
        poses.apply_pose(self, self.pose, pose_targets(self), self.amount)


def _update_swing(self, context):
    if self.base:
        chains.apply_swing(self)


def _update_hang(self, context):
    if self.base:
        context.view_layer.update()
        chains.apply_hang(self)
        context.view_layer.update()


class PoseLinkBoneRow(bpy.types.PropertyGroup):
    outfit_bone: StringProperty()
    base_bone: StringProperty(update=_mark_manual, description="Body bone this outfit bone follows (empty: none)")
    method: StringProperty(default="none")   # exact, similar, manual or none


class PoseLinkOutfit(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object, poll=_is_armature)
    rows: CollectionProperty(type=PoseLinkBoneRow)
    row_index: IntProperty()


class PoseLinkSaved(bpy.types.PropertyGroup):
    """A saved pose or toggle: a name and its data as text."""
    name: StringProperty()
    data: StringProperty()


class PoseLinkSettings(bpy.types.PropertyGroup):
    base: PointerProperty(type=bpy.types.Object, poll=_is_armature, name="Base",
                          description="The character's own armature, the one you pose")
    outfits: CollectionProperty(type=PoseLinkOutfit)
    outfit_index: IntProperty()

    pose: EnumProperty(name="Test Pose", items=_pose_items, update=_apply_chosen_pose)
    amount: FloatProperty(name="Strength", default=1.0, min=0.0, max=1.5, subtype="FACTOR",
                          update=_apply_chosen_pose,
                          description="How far into the pose, to find where a problem starts")
    auto_apply: BoolProperty(name="Apply on change", default=True)
    custom_poses: CollectionProperty(type=PoseLinkSaved)
    custom_index: IntProperty()
    new_pose_name: StringProperty(name="Name", default="My pose")
    reel_prev_action: StringProperty()
    reel_prev_range: IntVectorProperty(size=2, default=(1, 250))

    states: CollectionProperty(type=PoseLinkSaved)
    state_index: IntProperty()
    new_state_name: StringProperty(name="Name", default="Toggle")

    swing_target: EnumProperty(name="Chains on", default="OUTFITS", update=_update_swing, items=[
        ("OUTFITS", "Outfits", "Chains of the outfit armatures (cape, skirt)"),
        ("BASE", "Base", "Chains of the body armature (hair, ears, tail)"),
        ("ALL", "All", "Both"),
    ])
    swing_mode: EnumProperty(name="Direction", default="OUTWARD", update=_update_swing, items=[
        ("OUTWARD", "Outward", "Away from the body, like spinning"),
        ("GRAVITY", "Gravity", "Down"),
        ("BACK", "Back", "Backward, like running"),
        ("FORWARD", "Forward", "Forward, like wind from behind"),
        ("LEFT", "Left", "To the character's left"),
        ("RIGHT", "Right", "To the character's right"),
    ])
    swing_angle: FloatProperty(name="Angle per bone", default=0.0, min=-45.0, max=45.0, update=_update_swing,
                               description="Turn every chain bone by this many degrees, to see the chains swing")
    swing_filter: StringProperty(name="Name filter", update=_update_swing,
                                 description="Only chains whose bone names contain this")
    hang: BoolProperty(name="Hang chains (gravity)", default=False, update=_update_hang,
                       description="Chains keep hanging down while you pose, instead of turning rigidly with "
                                   "the chest or hips")
    hang_strength: FloatProperty(name="Gravity", default=0.5, min=0.0, max=1.0, subtype="FACTOR",
                                 update=_update_hang,
                                 description="How much the chains hang. The top of a chain follows its parent and "
                                             "the hang builds up toward the tip. 0: rigid, 1: always hanging")

    weight_scope: EnumProperty(name="Meshes", default="OUTFIT", items=[
        ("SELECTED", "Selected", "The selected meshes"),
        ("OUTFIT", "Outfit meshes", "Meshes of the outfit armatures"),
        ("ALL", "Everything", "Body and outfit meshes"),
    ])
    last_report: StringProperty()
    pose_mode_restore: StringProperty()


# Before 1.0 the add-on was called Outfit Pose Link and kept these settings under other names.
OLD_SETTINGS = "opl"
OLD_LEFTOVERS = ("opl", "opl_base", "opl_pose")


def _copy_values(target, values):
    """Copy saved values into a property group, lists included. Plain values are written as items so no update
    callback runs halfway through the copy; object pointers have to go through the property."""
    for name, value in values.items():
        prop = target.bl_rna.properties.get(name)
        if prop is None:
            continue
        if prop.type == "COLLECTION":
            collection = getattr(target, name)
            collection.clear()
            for item_values in value:
                _copy_values(collection.add(), item_values)
        elif prop.type == "POINTER":
            if isinstance(value, bpy.types.ID):
                setattr(target, name, value)
        else:
            try:
                target[name] = value
            except (TypeError, ValueError):
                pass   # a value the new settings can't hold: keep the default


def take_over_old_settings(scene):
    """Move settings saved under the old name to scene.poselink. Returns True when something was moved."""
    stored = scene.bl_system_properties_get() if hasattr(scene, "bl_system_properties_get") else None
    if stored is None or OLD_SETTINGS not in stored:
        return False
    settings = scene.poselink
    if settings.base is None and not len(settings.outfits) and not len(settings.states):
        _copy_values(settings, stored[OLD_SETTINGS].to_dict())
    for name in OLD_LEFTOVERS:
        if name in stored:
            del stored[name]
    return True


def _take_over_everywhere():
    if not hasattr(bpy.types.Scene, "poselink"):   # the add-on was switched off before the timer ran
        return
    for scene in bpy.data.scenes:
        take_over_old_settings(scene)


@persistent
def _on_file_load(*_args):
    _take_over_everywhere()


classes = (PoseLinkBoneRow, PoseLinkOutfit, PoseLinkSaved, PoseLinkSettings)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.poselink = PointerProperty(type=PoseLinkSettings)
    bpy.app.handlers.load_post.append(_on_file_load)
    # bpy.data can't be changed while add-ons register at startup, so do the current file right after
    bpy.app.timers.register(_take_over_everywhere, first_interval=0.1)


def unregister():
    if _on_file_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_file_load)
    del bpy.types.Scene.poselink
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
