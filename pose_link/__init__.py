"""PoseLink: pose a character and all of its outfits together."""

if "bpy" in locals():   # Blender reloads add-ons with F3 > Reload Scripts
    import importlib
    for module in (bone_names, linking, poses, chains, toggles, weights, properties, operators, ui):
        importlib.reload(module)
else:
    import bpy  # noqa: F401
    from . import bone_names, linking, poses, chains, toggles, weights, properties, operators, ui

modules = (properties, operators, ui, chains)


def register():
    for module in modules:
        module.register()


def unregister():
    for module in reversed(modules):
        module.unregister()
