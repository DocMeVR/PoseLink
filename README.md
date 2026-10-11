# PoseLink

A Blender extension for posing a character together with its outfits. Clothing that comes with its own armature
follows the body's armature, so you can try poses, see where it stretches or clips, and fix it before export.

## Features

- Links outfit armatures to the body armature by bone name, with one click
- 25 test poses that work on any humanoid rig, plus your own saved poses
- A pose reel that keys every pose on the timeline, to scrub through them
- Capes, skirts and tails hang down while you pose instead of turning stiffly with the chest
- Toggles: save which meshes are visible and the shape key values (hood up, hood down) and switch between them
- A weight check for game engines: unweighted vertices, more than 4 bones, torn seams, with a fix
- Prepare for Export puts everything back in rest pose

## Requirements

Blender 4.2 or newer.

## Installation

1. Download `pose_link-x.y.z.zip` from the latest [release](https://github.com/DocMeVR/PoseLink/releases/latest).
2. In Blender go to *Edit > Preferences > Get Extensions*, open the menu at the top right and pick
   *Install from Disk...*.
3. Choose the zip. PoseLink shows up in the 3D View sidebar (press `N`) as the **PoseLink** tab.

## Usage

1. Press the magnifier next to *Base*. PoseLink picks the body armature and every outfit armature that fits it.
2. Press **Link**. Each outfit bone now follows the body bone with the same name.
3. Press **Pose Base Armature** and pose the body, or pick a test pose. The outfits follow. Press the button again
   to leave Pose Mode; your selection comes back.
4. Tick **Hang chains (gravity)** if the outfit has a cape, skirt or tail.

Before exporting press **Prepare for Export**. The links are ordinary Copy Transforms constraints named `PoseLink`
and are not exported.

## Panels

**Outfit list.** Several outfits can be linked at once. **+** adds the selected armature, **−** removes one (and
unlinks it), the arrows match the bones again. A red box warns when the outfit's bones are not where the body's
bones are, which usually means the outfit was made for a different body.

**Bone Matching.** Shows which body bone each outfit bone follows. Bones match when they have the same name, or
nearly the same: case, `_` `.` `-` and spaces, a `.001` at the end, a `mixamorig:` in front, the side written as
`_L`, `.L` or `Left`, and a prefix or suffix the outfit puts on all its bones (`RH_Hips`) don't count. Names that
use different words (`ForeArm` and `LowerArm`) are not guessed: pick the body bone yourself and press **Link**
again. Bones marked *none* belong to the outfit only, like skirt or cape bones, and follow their parent.

**Test Poses.** The arrows step through the poses and **Strength** goes part of the way into one, to find where a
problem starts. Your own poses are saved in the .blend. **Make Pose Reel** keys all poses 10 frames apart.

**Chains.** Bones that hang off the body: capes, skirts, hair, tails. With **Hang chains** on they keep hanging
while you pose. **Gravity** 0 leaves them rigid, 1 keeps them in their rest direction, and in between the top
follows the body while the tip hangs. The swing turns every chain bone outward, down, back, forward or sideways on
top, to see how the chains look while moving. The name filter limits it to some chains (`Hair`, `Cape`).

**Toggles.** Show or hide meshes and set shape keys, then save it under a name. Switching to a toggle also sets
the shape keys other toggles use back to 0.

**Weight Check.** Checks the outfit meshes (or the selected ones, or everything) for what breaks in game engines:
vertices without weights, more than 4 bones per vertex, weights that don't add up to 1, split seams whose
vertices have different weights, empty groups and groups without a bone. **Fix Weights** asks first and can be
undone.

## Development

The add-on lives in `pose_link/`.

| File | What's in it |
|---|---|
| `bone_names.py` | matching outfit bones to body bones, humanoid roles for the test poses (no bpy) |
| `linking.py` | finding the armatures, linking and unlinking |
| `poses.py` | the test poses, saved poses and the pose reel |
| `chains.py` | chains, swing and the live hang |
| `toggles.py` | saving and switching toggles |
| `weights.py` | weight check and fix |
| `properties.py` | the settings stored with the scene (`scene.poselink`) |
| `operators.py`, `ui.py` | the buttons and the panels |

Tests:

    python -m unittest discover -s tests -p "test_bone_names.py"
    blender -b --factory-startup --python tests/test_hang_blender.py
    blender -b --factory-startup --python tests/test_blender_integration.py

To build the zip yourself (it lands in `dist/`):

    mkdir dist
    blender --command extension build --source-dir pose_link --output-dir dist

Releases come from release-please: conventional commits on `main` open a release pull request that bumps the
version in `pose_link/blender_manifest.toml` and writes the changelog. Merging it publishes the release with the
zip attached.

## How this was made

The code in this repository was written by AI (Claude, by Anthropic). The idea, the design, every feature, the testing on real characters and the decisions on how it should behave are mine (DocMe). I planned it and directed the work; the AI typed it out. Bug reports and pull requests are welcome, and anything that gets merged goes through my own review.

## License

MIT. See `LICENSE.md`.
