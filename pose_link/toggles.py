"""Toggles: saved sets of mesh visibility and shape key values, such as hood up and hood down."""
import json

import bpy


def capture(meshes):
    """Which meshes are visible and every shape key that is not at 0, as text for the .blend."""
    visible = {obj.name: not obj.hide_get() for obj in meshes}
    shape_keys = {}
    for obj in meshes:
        if obj.data.shape_keys:
            values = {key.name: round(key.value, 4) for key in obj.data.shape_keys.key_blocks[1:]
                      if abs(key.value) > 1e-4}
            if values:
                shape_keys[obj.name] = values
    return json.dumps({"vis": visible, "keys": shape_keys})


def apply(settings, data):
    """Switch to a saved toggle. A shape key used by any other toggle goes to 0 when this one doesn't set it,
    so switching from 'hood down' to 'hood up' also resets the keys only 'hood down' uses."""
    toggle = json.loads(data)
    for name, visible in toggle.get("vis", {}).items():
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_viewport = False
            obj.hide_set(not visible)
    used_anywhere = {}
    for saved in settings.states:
        for obj_name, values in json.loads(saved.data).get("keys", {}).items():
            used_anywhere.setdefault(obj_name, set()).update(values)
    this_toggle = toggle.get("keys", {})
    for obj_name, key_names in used_anywhere.items():
        obj = bpy.data.objects.get(obj_name)
        if not (obj and obj.data.shape_keys):
            continue
        for key_name in key_names:
            key = obj.data.shape_keys.key_blocks.get(key_name)
            if key:
                key.value = this_toggle.get(obj_name, {}).get(key_name, 0.0)
