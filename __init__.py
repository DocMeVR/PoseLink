bl_info = {
    "name": "PoseLink",
    "author": "DocMe",
    "version": (1, 0, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > PoseLink",
    "description": "Pose a character and all of its outfits together (bone link), test poses and pose reel, "
                   "chain swing and gravity hang preview, toggles, weight check and fix",
    "category": "Rigging",
}

if "bpy" in locals():
    import importlib
    from . import bones, core, ops, ui
    for m in (bones, core, ops, ui):
        importlib.reload(m)

import bpy

from . import ops, ui


def register():
    for c in ops.CLASSES + ui.CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.opl = bpy.props.PointerProperty(type=ops.OPL_Settings)
    for h in (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.frame_change_post):
        if ops.hang_handler not in h:
            h.append(ops.hang_handler)


def unregister():
    for h in (bpy.app.handlers.depsgraph_update_post, bpy.app.handlers.frame_change_post):
        for f in [f for f in h if getattr(f, "__name__", "") == "hang_handler"]:
            h.remove(f)
    del bpy.types.Scene.opl
    for c in reversed(ops.CLASSES + ui.CLASSES):
        bpy.utils.unregister_class(c)
