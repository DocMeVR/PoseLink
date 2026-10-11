# PoseLink

Pose a character and all of its outfits together in Blender. Outfits that come with their own armature follow the
body's armature, so you can try poses, see where clothing stretches or clips, and fix it.

3D View → Sidebar (N) → **PoseLink** tab. Blender 4.2 or newer.

## Quick start
1. Press the **magnifier** next to *Base*: it finds the character's armature and every outfit armature that fits it.
2. Press **Link**: each outfit bone now follows the matching body bone.
3. Press **Pose Base Armature**, pose the body, and the outfits follow. The same button says **Exit Pose Mode**
   while you're in it, and puts your selection back.
4. Tick **Hang chains (gravity)** so capes, skirts and tails hang down while you bend the chest or hips. Without it
   Blender turns them rigidly with their parent bone, so a cape flies out sideways like a stiff board.

## Sections
| Section | What it does |
|---|---|
| Outfit list | Several outfits at once. **+** adds the selected armature, **−** removes (and unlinks), ⟳ matches again. Status: linked or paused. A red box warns when outfit bones are not where the body bones are (an outfit made for a different body). |
| Bone Matching | Every outfit bone and the body bone it follows. Icons: ✓ same name, AZ prefix or suffix stripped (`RH_Hips`, `Hips.001`), armature = humanoid match across naming schemes (humanoid role names, Cats, Mixamo, VRM, Blender `.L/.R`), pencil = your choice. Pick a different body bone or clear it, then press **Link** again. *none* = outfit-only bone (skirt, cape, ears), follows its parent. |
| Test Poses | 25 built-in poses (idle, head down/up/turn/tilt, shrug, arms forward/up/crossed, wave, lean, twist, side bend, walk, sit, cross-legged, crouch, kneel, splits) that work on any humanoid rig, whichever way it faces. ◀ Apply ▶ steps through them, **Strength** scales the pose so you can find where a problem starts. **Your poses**: pose the body, type a name, press +. **Make Pose Reel** keys every pose on the timeline: scrub or press Space, and remove it again with one click. |
| Chain Swing | **Hang chains (gravity)** (also on the main panel) lets chains hang while you pose, live: the top of each chain still turns with the chest or hips and the hang builds up toward the tip. **Gravity** 0 = rigid with the parent, 0.5 (default) = the tip keeps half of the parent's turn, 1 = every bone keeps its rest direction. The swing turns every chain that is not part of the body (cape, skirt, hair, tails, ears) outward, down, back, forward or sideways on top, with a per-bone angle slider and a name filter (for example `Hair`, `Cape`). Works on outfit chains, body chains or both. |
| Toggles | Save which meshes are visible and the shape key values (for example hood up and hood down), then switch with ▶. |
| Weight Check | Checks outfit meshes (or the selected ones, or everything) for problems that break in game engines: unweighted vertices, more than 4 bones per vertex, weights that don't add up to 1, **torn split seams** (overlapping vertices with different weights), empty groups, groups without a bone. **Fix** asks first and can be undone. |
| Finish | **Prepare for Export**: rest pose, removes the pose reel, resets chains, switches hang off. |

The links are ordinary Copy Transforms constraints named `OutfitLink`; they don't export to FBX. Press
**Prepare for Export** before exporting so nothing is posed.

## Install
Build the extension zip, it lands in `dist/`:

    mkdir dist
    blender --command extension build --source-dir . --output-dir dist

Then Blender → Edit → Preferences → Get Extensions → ⌄ → **Install from Disk…** → the zip from `dist/`.

## Code
| File | |
|---|---|
| `bones.py` | bone name parsing and humanoid matching (no bpy, unit tested) |
| `core.py` | linking, poses, pose reel, chain swing and hang, toggles, weight check and fix |
| `ops.py` | settings (`scene.opl`), operators (`opl.*`), live hang handler |
| `ui.py` | sidebar panels |

Internal names (`scene.opl`, `opl.*` operators, the `OutfitLink` constraint) are kept from the add-on's first
name, Outfit Pose Link, so .blend files made with it keep their links, toggles and saved poses.

## Tests
`python -m unittest discover -s tests -p "test_bones.py"` (bone matching, plain Python).
`blender -b --python tests/test_hang_blender.py` (needs Blender): hang math on a throw-away armature, loads the
add-on from this folder.

## How this was made

The code in this repository was written by AI (Claude, by Anthropic). The idea, the design, every feature, the testing on real avatars and the decisions on how it should behave are mine (DocMe). I planned it and directed the work; the AI typed it out. Bug reports and pull requests are welcome, and anything that gets merged goes through my own review.

## License

MIT. See `LICENSE.md`.
