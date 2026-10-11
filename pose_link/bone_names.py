"""Bone names: matching outfit bones to the body's bones, and humanoid roles.

Matching goes by the body's own names (see match_bones). The humanoid roles let the built-in test poses find
the arms and legs on any rig, whatever naming style it uses: role names (LeftUpperArm), Cats (Left arm),
Mixamo (mixamorig:LeftForeArm), VRM (J_Bip_L_UpperArm), Blender and Rigify (upper_arm.L) or UpperArm_L.
Plain Python without bpy, so it can be tested outside Blender.
"""
import re
from collections import Counter

FINGERS = {
    "thumb": "Thumb", "thunb": "Thumb",  # "Thunb" is a common typo in shipped models
    "index": "Index", "middle": "Middle", "ring": "Ring",
    "little": "Little", "pinky": "Little", "pinkie": "Little",
}
FINGER_SEGMENTS = ("Proximal", "Intermediate", "Distal")

CENTER_BONES = {
    "hips": "Hips", "hip": "Hips", "pelvis": "Hips",
    "spine": "Spine", "chest": "Chest", "upper chest": "UpperChest", "upperchest": "UpperChest",
    "neck": "Neck", "head": "Head", "jaw": "Jaw",
}
LIMB_BONES = {
    "shoulder": "Shoulder", "clavicle": "Shoulder", "collarbone": "Shoulder",
    "upper arm": "UpperArm", "upperarm": "UpperArm", "arm": "UpperArm", "up arm": "UpperArm", "uparm": "UpperArm",
    "lower arm": "LowerArm", "lowerarm": "LowerArm", "forearm": "LowerArm", "fore arm": "LowerArm",
    "elbow": "LowerArm",
    "hand": "Hand", "wrist": "Hand",
    "upper leg": "UpperLeg", "upperleg": "UpperLeg", "up leg": "UpperLeg", "upleg": "UpperLeg", "thigh": "UpperLeg",
    "leg": "UpperLeg",
    "lower leg": "LowerLeg", "lowerleg": "LowerLeg", "knee": "LowerLeg", "calf": "LowerLeg", "shin": "LowerLeg",
    "foot": "Foot", "ankle": "Foot",
    "toe": "Toes", "toes": "Toes", "toe base": "Toes", "toebase": "Toes",
    "eye": "Eye",
}
SIDE_WORDS = {"l": "Left", "left": "Left", "r": "Right", "right": "Right"}
NOISE_WORDS = {"j", "bip", "bip01", "bip001", "c", "def", "org", "valvebiped"}


def _without_prefixes(name):
    """'Armature|mixamorig:Hips.001' -> 'Hips'."""
    name = name.split("|")[-1]
    name = name.split(":")[-1]
    return re.sub(r"\.\d{3}$", "", name)


def _words(name):
    """Split a bone name into lower case words. Returns (words, side) where side comes from a Japanese prefix."""
    name = _without_prefixes(name)
    side = None
    if name[:1] in "左右":
        side = "Left" if name[0] == "左" else "Right"
        name = name[1:]
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    name = re.sub(r"([A-Za-z])(\d)", r"\1 \2", name)
    name = re.sub(r"(\d)([A-Za-z])", r"\1 \2", name)
    return [word for word in re.split(r"[\s_.\-]+", name.lower()) if word], side


def parse_bone_name(name):
    """Return (side, body part words, trailing number, finger segment) for a bone name.
    'UpperArm_L' -> ('Left', 'upper arm', None, None), 'Index2_R' -> ('Right', 'index', 2, None)."""
    words, side = _words(name)
    while words and words[0] in NOISE_WORDS:
        words = words[1:]
    part, numbers, segment = [], [], None
    for i, word in enumerate(words):
        at_edge = i == 0 or i == len(words) - 1 or words[i - 1] in NOISE_WORDS
        if word in SIDE_WORDS and side is None and at_edge:
            side = SIDE_WORDS[word]
        elif word.isdigit():
            numbers.append(int(word))
        elif word.capitalize() in FINGER_SEGMENTS:
            segment = word.capitalize()
        else:
            part.append(word)
    # Mixamo writes fingers as "LeftHandThumb1"
    if len(part) == 2 and part[0] == "hand" and part[1] in FINGERS:
        part = part[1:]
    return side, " ".join(part), (numbers[-1] if numbers else None), segment


def humanoid_roles(names):
    """{bone name: humanoid role} for the bones that are clearly humanoid bones, one bone per role."""
    lowered = [n.lower() for n in names]
    mixamo = any("mixamorig" in n or "upleg" in n.replace("_", "") for n in lowered)
    roles = {}
    fingers = {}   # (side, finger) -> [(number, bone name)] for fingers numbered 1, 2, 3
    for name in names:
        side, part, number, segment = parse_bone_name(name)
        if part in FINGERS:
            if side is None:
                continue
            finger = FINGERS[part]
            if segment:
                roles[name] = f"{side}{finger}{segment}"
            else:
                fingers.setdefault((side, finger), []).append((number or 0, name))
            continue
        if side is None:
            if part in CENTER_BONES and number is None:
                roles[name] = CENTER_BONES[part]
            elif mixamo and part == "spine" and number in (1, 2):
                roles[name] = "Chest" if number == 1 else "UpperChest"
            continue
        if number is not None or part not in LIMB_BONES:
            continue
        limb = LIMB_BONES[part]
        if part == "leg" and mixamo:    # Mixamo: LeftUpLeg, LeftLeg (= lower leg)
            limb = "LowerLeg"
        roles[name] = f"{side}{limb}"
    for (side, finger), numbered in fingers.items():
        for rank, (_, name) in enumerate(sorted(numbered)[:3]):
            roles[name] = f"{side}{finger}{FINGER_SEGMENTS[rank]}"
    # When two bones claim the same role keep the shorter name ('Chest' over 'Chest.001')
    chosen = {}
    for name, role in roles.items():
        if role not in chosen or len(name) < len(chosen[role]):
            chosen[role] = name
    return {name: role for role, name in chosen.items()}


def _affixes(unmatched, base):
    pre, suf = Counter(), Counter()
    for o in unmatched:
        s = _without_prefixes(o)
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
        s = _without_prefixes(o)
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
