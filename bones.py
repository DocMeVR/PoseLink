"""Bone-name logic: humanoid roles for common naming schemes, and outfit -> base bone matching.

Pure Python (no bpy) so it can be unit tested outside Blender.
Schemes handled: humanoid role names (LeftUpperArm), Cats (Left arm, Left elbow), Mixamo (mixamorig:LeftForeArm),
VRM (J_Bip_L_UpperArm), Blender/Rigify-style (upper_arm.L), and suffix styles like UpperArm_L / Wrist_L.
"""
import re
from collections import Counter

FINGERS = {"thumb": "Thumb", "thunb": "Thumb", "index": "Index", "middle": "Middle", "ring": "Ring",
           "little": "Little", "pinky": "Little", "pinkie": "Little"}
SEGMENTS = ("Proximal", "Intermediate", "Distal")
CENTER = {"hips": "Hips", "hip": "Hips", "pelvis": "Hips", "spine": "Spine", "chest": "Chest",
          "upper chest": "UpperChest", "upperchest": "UpperChest", "neck": "Neck", "head": "Head", "jaw": "Jaw"}
LIMBS = {
    "shoulder": "Shoulder", "clavicle": "Shoulder", "collarbone": "Shoulder",
    "upper arm": "UpperArm", "upperarm": "UpperArm", "arm": "UpperArm", "up arm": "UpperArm", "uparm": "UpperArm",
    "lower arm": "LowerArm", "lowerarm": "LowerArm", "forearm": "LowerArm", "fore arm": "LowerArm", "elbow": "LowerArm",
    "hand": "Hand", "wrist": "Hand",
    "upper leg": "UpperLeg", "upperleg": "UpperLeg", "up leg": "UpperLeg", "upleg": "UpperLeg", "thigh": "UpperLeg",
    "leg": "UpperLeg",
    "lower leg": "LowerLeg", "lowerleg": "LowerLeg", "knee": "LowerLeg", "calf": "LowerLeg", "shin": "LowerLeg",
    "foot": "Foot", "ankle": "Foot",
    "toe": "Toes", "toes": "Toes", "toe base": "Toes", "toebase": "Toes",
    "eye": "Eye",
}
SIDE_TOKENS = {"l": "Left", "left": "Left", "r": "Right", "right": "Right"}
DROP_TOKENS = {"j", "bip", "bip01", "bip001", "c", "def", "org", "valvebiped"}
HUMANOID_ROLES = (["Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "Jaw"]
                  + [f"{s}{p}" for s in ("Left", "Right") for p in ("Eye", "Shoulder", "UpperArm", "LowerArm", "Hand",
                                                                     "UpperLeg", "LowerLeg", "Foot", "Toes")]
                  + [f"{s}{f}{g}" for s in ("Left", "Right") for f in ("Thumb", "Index", "Middle", "Ring", "Little")
                     for g in SEGMENTS])


def _strip(name):
    s = name.split("|")[-1]
    s = s.split(":")[-1]                       # mixamorig:Hips
    s = re.sub(r"\.\d{3}$", "", s)             # Blender duplicate suffix .001
    return s


def tokens(name):
    s = _strip(name)
    jp_side = None
    if s[:1] in "左右":
        jp_side = "Left" if s[0] == "左" else "Right"
        s = s[1:]
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    s = re.sub(r"([A-Za-z])(\d)", r"\1 \2", s)
    s = re.sub(r"(\d)([A-Za-z])", r"\1 \2", s)
    toks = [t for t in re.split(r"[\s_.\-]+", s.lower()) if t]
    return toks, jp_side


def parse(name, mixamo=False):
    """-> (side or None, core string, number or None, segment name or None)"""
    toks, side = tokens(name)
    while toks and toks[0] in DROP_TOKENS:
        toks = toks[1:]
    core, nums, seg = [], [], None
    for i, t in enumerate(toks):
        if t in SIDE_TOKENS and side is None and (i == 0 or i == len(toks) - 1 or toks[i - 1] in DROP_TOKENS):
            side = SIDE_TOKENS[t]
        elif t.isdigit():
            nums.append(int(t))
        elif t.capitalize() in SEGMENTS:
            seg = t.capitalize()
        else:
            core.append(t)
    # Mixamo "LeftHandThumb1": drop the 'hand' in front of a finger name
    if len(core) == 2 and core[0] == "hand" and core[1] in FINGERS:
        core = core[1:]
    return side, " ".join(core), (nums[-1] if nums else None), seg


def humanoid_roles(names):
    """{bone name: humanoid role} for the bones that clearly are humanoid bones."""
    mixamo = any("mixamorig" in n.lower() or "upleg" in n.lower().replace("_", "") for n in names)
    out = {}
    fingers = {}
    for n in names:
        side, core, num, seg = parse(n, mixamo)
        if core in FINGERS:
            if side is None:
                continue
            key = (side, FINGERS[core])
            if seg:
                out[n] = f"{side}{FINGERS[core]}{seg}"
            else:
                fingers.setdefault(key, []).append((num if num is not None else 0, n))
            continue
        if side is None:
            if core in CENTER and num is None:
                out[n] = CENTER[core]
            elif mixamo and core == "spine" and num in (1, 2):
                out[n] = "Chest" if num == 1 else "UpperChest"
            continue
        if num is not None:
            continue
        part = LIMBS.get(core)
        if part is None:
            continue
        if core == "leg" and mixamo:
            part = "LowerLeg"
        out[n] = f"{side}{part}"
    for (side, finger), lst in fingers.items():
        for rank, (_, n) in enumerate(sorted(lst)):
            if rank < 3:
                out[n] = f"{side}{finger}{SEGMENTS[rank]}"
    # one bone per role (keep the shortest name, e.g. 'Chest' over 'Chest.001')
    best = {}
    for n, r in out.items():
        if r not in best or len(n) < len(best[r]):
            best[r] = n
    return {n: r for r, n in best.items()}


def _affixes(unmatched, base):
    pre, suf = Counter(), Counter()
    for o in unmatched:
        s = _strip(o)
        for b in base:
            if len(b) < 3 or s == b:
                continue
            if s.endswith(b):
                pre[s[: len(s) - len(b)]] += 1
            if s.startswith(b):
                suf[s[len(b):]] += 1
    return {p for p, c in pre.items() if c >= 2}, {x for x, c in suf.items() if c >= 2}


def match_bones(outfit, base, overrides=None):
    """{outfit bone: (base bone, method)}; method in manual / exact / affix / humanoid. Unmatched bones are left out
    (they are outfit-only bones such as skirt or cape chains and simply follow their parents)."""
    overrides = overrides or {}
    base_set = set(base)
    out = {}
    for o in outfit:
        if o in overrides:
            if overrides[o] in base_set:
                out[o] = (overrides[o], "manual")
            continue
        if o in base_set:
            out[o] = (o, "exact")
    rest = [o for o in outfit if o not in out and o not in overrides]
    lower = {b.lower(): b for b in base}
    pre, suf = _affixes(rest, base)
    for o in rest:
        s = _strip(o)
        cands = [s] + [s[len(p):] for p in pre if p and s.startswith(p)] + [s[: len(s) - len(x)] for x in suf if x and s.endswith(x)]
        for c in cands:
            if c in base_set:
                out[o] = (c, "affix"); break
            if c.lower() in lower:
                out[o] = (lower[c.lower()], "affix"); break
    rest = [o for o in rest if o not in out]
    if rest:
        ro = humanoid_roles(outfit)
        rb = {r: b for b, r in humanoid_roles(base).items()}
        for o in rest:
            r = ro.get(o)
            if r and r in rb:
                out[o] = (rb[r], "humanoid")
    return out
