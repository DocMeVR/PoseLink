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


def _name_key(name):
    """What is left of a bone name when case, separators, '.001', 'Armature|' or 'mixamorig:' and the way the side
    is written do not count: 'upper_arm.L', 'UpperArm_L' and 'LeftUpperArm' all give ('Left', 'upperarm')."""
    words, side = _words(name)
    rest = []
    for i, word in enumerate(words):
        if side is None and word in SIDE_WORDS and i in (0, len(words) - 1):
            side = SIDE_WORDS[word]
        else:
            rest.append(word)
    return side, "".join(rest)


def _shared_affixes(outfit_names, body_names):
    """Prefixes and suffixes that turn at least two outfit bone names into body bone names ('RH_', '_dress')."""
    prefixes, suffixes = Counter(), Counter()
    for outfit_name in outfit_names:
        name = _without_prefixes(outfit_name)
        for body_name in body_names:
            if len(body_name) < 3 or name == body_name:
                continue
            if name.endswith(body_name):
                prefixes[name[: len(name) - len(body_name)]] += 1
            if name.startswith(body_name):
                suffixes[name[len(body_name):]] += 1
    return ({p for p, count in prefixes.items() if count >= 2},
            {s for s, count in suffixes.items() if count >= 2})


def match_bones(outfit, base, overrides=None):
    """Find the body bone each outfit bone follows, by the body's own bone names.

    Returns {outfit bone: (body bone, how)}, how being 'manual', 'exact' or 'similar'. Similar means the same
    name apart from case, separators, a '.001' or 'mixamorig:' style addition, the way the side is written
    (_L, .L, Left) or a prefix or suffix the outfit puts on many bones (RH_). Different words (ForeArm vs
    LowerArm) are not guessed. Bones without a match belong to the outfit only (skirt, cape) and follow their
    parent. `overrides` holds the body bones the user picked by hand; an empty string means no link.
    """
    overrides = overrides or {}
    body = set(base)
    body_by_key = {}
    for name in base:
        body_by_key.setdefault(_name_key(name), []).append(name)

    def similar_body_bone(name):
        if name in body:
            return name
        found = body_by_key.get(_name_key(name), [])
        return found[0] if len(found) == 1 else None   # two body bones look alike: don't guess

    matches = {}
    for name in outfit:
        if name in overrides:
            if overrides[name] in body:
                matches[name] = (overrides[name], "manual")
        elif name in body:
            matches[name] = (name, "exact")

    left = [name for name in outfit if name not in matches and name not in overrides]
    prefixes, suffixes = _shared_affixes(left, base)
    for name in left:
        bare = _without_prefixes(name)
        candidates = ([name, bare]
                      + [bare[len(p):] for p in prefixes if p and bare.startswith(p)]
                      + [bare[: len(bare) - len(s)] for s in suffixes if s and bare.endswith(s)])
        for candidate in candidates:
            found = similar_body_bone(candidate)
            if found:
                matches[name] = (found, "similar")
                break
    return matches
