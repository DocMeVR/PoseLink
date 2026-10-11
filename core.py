"""Logic for PoseLink (needs bpy). UI and operators live in ops.py / ui.py."""
import json
import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector
from mathutils.kdtree import KDTree

from . import bones

LINK = "OutfitLink"           # constraint name used by this add-on
REEL = "OPL_PoseReel"         # action name of the pose reel

# --------------------------------------------------------------------------- avatar discovery
def armature_meshes(arms):
    """Mesh objects deformed by (or parented to) any of the given armatures."""
    arms = set(arms)
    out = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if o.parent in arms or any(m.type == "ARMATURE" and m.object in arms for m in o.modifiers):
            out.append(o)
    return out


def guess_base():
    """The armature with the most humanoid bones (ties -> most meshes)."""
    best, score = None, (-1, -1)
    for o in bpy.data.objects:
        if o.type != "ARMATURE":
            continue
        s = (len(bones.humanoid_roles(o.data.bones.keys())), len(armature_meshes([o])))
        if s > score:
            best, score = o, s
    return best


def outfit_candidates(base):
    if base is None:
        return []
    out = []
    for o in bpy.data.objects:
        if o.type == "ARMATURE" and o is not base and len(match_map(o, base)) >= 5:
            out.append(o)
    return out


def match_map(outfit, base, overrides=None):
    return bones.match_bones(list(outfit.data.bones.keys()), list(base.data.bones.keys()), overrides)


def refresh_rows(item, base):
    """(Re)build the bone mapping rows of an outfit entry, keeping manual edits."""
    manual = {r.outfit_bone: r.base_bone for r in item.rows if r.method == "manual"}
    m = match_map(item.obj, base, manual)
    item.rows.clear()
    for b in item.obj.data.bones:
        r = item.rows.add()
        r.outfit_bone = b.name
        base_bone, method = m.get(b.name, ("", "none"))
        if b.name in manual:
            base_bone, method = manual[b.name], "manual"
        r["base_bone"] = base_bone          # assign without triggering the 'manual' update
        r.method = method


def rest_mismatch(item, base, tol=0.005):
    """Mapped bones whose rest heads differ by more than tol (outfit not fitted to this base)."""
    Mo, Mb = item.obj.matrix_world, base.matrix_world
    off = []
    for r in item.rows:
        if r.base_bone and r.base_bone in base.data.bones and r.outfit_bone in item.obj.data.bones:
            d = (Mo @ item.obj.data.bones[r.outfit_bone].head_local - Mb @ base.data.bones[r.base_bone].head_local).length
            if d > tol:
                off.append((r.outfit_bone, d))
    return off


def _space(con):
    items = {i.identifier for i in con.bl_rna.properties["target_space"].enum_items}
    return "LOCAL_OWNER_ORIENT" if "LOCAL_OWNER_ORIENT" in items else "LOCAL"


def link(item, base):
    outfit = item.obj
    n = 0
    for r in item.rows:
        pb = outfit.pose.bones.get(r.outfit_bone)
        if pb is None:
            continue
        existing = [c for c in pb.constraints if c.name.startswith(LINK)]
        if not r.base_bone or r.base_bone not in base.pose.bones:
            for c in existing:
                pb.constraints.remove(c)
            continue
        con = existing[0] if existing else pb.constraints.new("COPY_TRANSFORMS")
        con.name = LINK
        con.target = base
        con.subtarget = r.base_bone
        con.target_space = _space(con)
        con.owner_space = "LOCAL"
        con.mix_mode = "REPLACE"
        con.influence = 1.0
        con.mute = False
        i = list(pb.constraints).index(con)
        if i:
            pb.constraints.move(i, 0)
        n += 1
    return n


def unlink(arm):
    n = 0
    for pb in arm.pose.bones:
        for c in [c for c in pb.constraints if c.name.startswith(LINK)]:
            pb.constraints.remove(c)
            n += 1
    return n


def link_constraints(arm):
    return [c for pb in arm.pose.bones for c in pb.constraints if c.name.startswith(LINK)]


# --------------------------------------------------------------------------- poses
X, Y, Z = (1, 0, 0), (0, 1, 0), (0, 0, 1)
# Canonical frame: the avatar faces -Y, its left is +X, up is +Z (converted to the real avatar's facing).
#   X +deg: bend forward / head down     Z +deg: turn to the avatar's left     Y +deg: tilt to its left
_IDLE = {"LeftUpperArm": [[Y, 75]], "RightUpperArm": [[Y, -75]], "LeftLowerArm": [[Z, -10]], "RightLowerArm": [[Z, 10]]}
POSES = {
    "Rest": {},
    "Idle (arms down)": _IDLE,
    "A-pose": {"LeftUpperArm": [[Y, 40]], "RightUpperArm": [[Y, -40]]},
    "Head down": {"_base": "Idle (arms down)", "Neck": [[X, 15]], "Head": [[X, 25]]},
    "Head up": {"_base": "Idle (arms down)", "Neck": [[X, -10]], "Head": [[X, -25]]},
    "Head turn left": {"_base": "Idle (arms down)", "Neck": [[Z, 15]], "Head": [[Z, 40]]},
    "Head turn right": {"_base": "Idle (arms down)", "Neck": [[Z, -15]], "Head": [[Z, -40]]},
    "Head tilt left": {"_base": "Idle (arms down)", "Neck": [[Y, 10]], "Head": [[Y, 20]]},
    "Head tilt right": {"_base": "Idle (arms down)", "Neck": [[Y, -10]], "Head": [[Y, -20]]},
    "Look down left": {"_base": "Idle (arms down)", "Neck": [[X, 10], [Z, 10]], "Head": [[X, 20], [Z, 30]]},
    "Shrug": {"_base": "Idle (arms down)", "LeftShoulder": [[Y, -15]], "RightShoulder": [[Y, 15]]},
    "Arms forward": {"LeftUpperArm": [[Z, -80]], "RightUpperArm": [[Z, 80]]},
    "Arms up": {"LeftUpperArm": [[Y, -70]], "RightUpperArm": [[Y, 70]]},
    "Arms crossed": {"LeftUpperArm": [[Y, 45], [Z, -60]], "RightUpperArm": [[Y, -45], [Z, 60]],
                     "LeftLowerArm": [[Z, -90]], "RightLowerArm": [[Z, 90]]},
    "Hand wave": {"_base": "Idle (arms down)", "RightUpperArm": [[Y, 40]], "RightLowerArm": [[Y, 70]]},
    "Lean forward": {"_base": "Idle (arms down)", "Spine": [[X, 15]], "Chest": [[X, 15]]},
    "Lean back": {"_base": "Idle (arms down)", "Spine": [[X, -10]], "Chest": [[X, -10]]},
    "Twist": {"_base": "Idle (arms down)", "Spine": [[Z, 15]], "Chest": [[Z, 15]]},
    "Side bend": {"_base": "Idle (arms down)", "Spine": [[Y, 10]], "Chest": [[Y, 10]]},
    "Walk": {"_base": "Idle (arms down)", "LeftUpperLeg": [[X, -35]], "LeftLowerLeg": [[X, 25]], "RightUpperLeg": [[X, 20]]},
    "Sit": {"_base": "Idle (arms down)", "LeftUpperLeg": [[X, -90]], "RightUpperLeg": [[X, -90]],
            "LeftLowerLeg": [[X, 90]], "RightLowerLeg": [[X, 90]]},
    "Sit cross-legged": {"_base": "Idle (arms down)", "LeftUpperLeg": [[X, -80], [Y, 40]], "RightUpperLeg": [[X, -80], [Y, -40]],
                         "LeftLowerLeg": [[X, 130]], "RightLowerLeg": [[X, 130]]},
    "Crouch": {"_base": "Idle (arms down)", "Spine": [[X, 20]], "LeftUpperLeg": [[X, -110]], "RightUpperLeg": [[X, -110]],
               "LeftLowerLeg": [[X, 120]], "RightLowerLeg": [[X, 120]]},
    "Kneel": {"_base": "Idle (arms down)", "LeftUpperLeg": [[X, -90]], "LeftLowerLeg": [[X, 90]], "RightUpperLeg": [[X, 10]],
              "RightLowerLeg": [[X, 90]]},
    "Splits (stretch test)": {"LeftUpperLeg": [[X, -60]], "RightUpperLeg": [[X, 45]]},
}


def resolve(poses, name):
    spec = poses.get(name, {})
    out = {}
    b = spec.get("_base", [])
    for x in ([b] if isinstance(b, str) else b):
        out.update(resolve(poses, x))
    out.update({k: v for k, v in spec.items() if not k.startswith("_")})
    return out


def facing(arm):
    """3x3 matrix taking canonical axes (front -Y, left +X) to this armature's space."""
    roles = {r: n for n, r in bones.humanoid_roles(arm.data.bones.keys()).items()}
    front_y = -1.0
    if "LeftFoot" in roles and "LeftToes" in roles:
        d = arm.data.bones[roles["LeftToes"]].head_local - arm.data.bones[roles["LeftFoot"]].head_local
        if abs(d.y) > 1e-4:
            front_y = -1.0 if d.y < 0 else 1.0
    return Matrix.Identity(3) if front_y < 0 else Matrix.Rotation(math.pi, 3, "Z")


def config_library():
    """Poses/states from an embedded avatar_qa config (redhood_config.py text block), if any."""
    txt = bpy.data.texts.get("redhood_config.py")
    if not txt:
        return {}, {}
    try:
        ns = {"__name__": "redhood_config", "__file__": "redhood_config.py"}
        exec(compile(txt.as_string(), "redhood_config.py", "exec"), ns)
        return ns["CONFIG"]["poses"], ns["CONFIG"].get("states", {})
    except Exception as e:
        print("PoseLink: could not read redhood_config.py:", e)
        return {}, {}


def pose_names(settings):
    names = [("lib:" + k, k, "Built-in test pose") for k in POSES]
    names += [("cus:" + p.name, "★ " + p.name, "Your saved pose") for p in settings.custom_poses]
    qa_poses, _ = config_library()
    names += [("qa:" + k, "QA: " + k, "Pose from the avatar_qa config") for k in qa_poses]
    return names


def _rotate_bones(arms, spec, amount, by_role):
    for a in arms:
        frame = facing(a)
        roles = {r: n for n, r in bones.humanoid_roles(a.data.bones.keys()).items()} if by_role else None
        to_arm = a.matrix_world.to_3x3().normalized().inverted()
        for key, rots in spec.items():
            bn = roles.get(key) if by_role else key
            pb = a.pose.bones.get(bn) if bn else None
            if pb is None:
                continue
            rest_inv = a.data.bones[bn].matrix_local.to_3x3().inverted()
            q = Quaternion()
            for axis, deg in rots:
                # built-in poses are written in the armature's canonical frame; config poses in world axes
                ax = (frame @ Vector(axis)) if by_role else (to_arm @ Vector(axis))
                q = Quaternion((rest_inv @ ax).normalized(), math.radians(deg * amount)) @ q
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = q


def clear_pose(arms):
    for a in arms:
        a.data.pose_position = "POSE"
        for pb in a.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)


def apply_pose(settings, key, arms, amount=1.0):
    """key: 'lib:<name>' (humanoid roles), 'cus:<name>' (saved bone rotations), 'qa:<name>' (avatar_qa config)."""
    clear_pose(arms)
    kind, _, name = key.partition(":")
    if kind == "lib":
        _rotate_bones(arms, resolve(POSES, name), amount, by_role=True)
    elif kind == "qa":
        qa_poses, _ = config_library()
        _rotate_bones(arms, resolve(qa_poses, name), amount, by_role=False)
    elif kind == "cus":
        p = next((p for p in settings.custom_poses if p.name == name), None)
        if p:
            data = json.loads(p.data)
            for a in arms:
                for bn, (w, x, y, z, lx, ly, lz) in data.items():
                    pb = a.pose.bones.get(bn)
                    if pb:
                        pb.rotation_mode = "QUATERNION"
                        pb.rotation_quaternion = Quaternion().slerp(Quaternion((w, x, y, z)), amount)
                        pb.location = Vector((lx, ly, lz)) * amount
    bpy.context.view_layer.update()


def capture_pose(arm):
    data = {}
    for pb in arm.pose.bones:
        if pb.matrix_basis != Matrix.Identity(4):
            q = pb.matrix_basis.to_quaternion()
            loc = pb.matrix_basis.to_translation()
            data[pb.name] = [q.w, q.x, q.y, q.z, loc.x, loc.y, loc.z]
    return json.dumps(data)


def build_reel(settings, base, keys, step=10):
    """Keyframe every test pose on the base armature (frames 1, 1+step, ...) so the timeline scrubs through them."""
    sc = bpy.context.scene
    ad = base.animation_data or base.animation_data_create()
    if ad.action is None or ad.action.name != REEL:
        settings.reel_prev_action = ad.action.name if ad.action else ""
        settings.reel_prev_range = (sc.frame_start, sc.frame_end)
    old = bpy.data.actions.get(REEL)
    if old:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new(REEL)
    act.use_fake_user = False
    ad.action = act
    roles = set(bones.humanoid_roles(base.data.bones.keys()))
    for i, k in enumerate(keys):
        f = 1 + i * step
        apply_pose(settings, k, [base])
        for pb in base.pose.bones:
            if pb.name in roles or pb.matrix_basis != Matrix.Identity(4):
                pb.rotation_mode = "QUATERNION"
                pb.keyframe_insert("rotation_quaternion", frame=f, group=pb.name)
                pb.keyframe_insert("location", frame=f, group=pb.name)
    sc.frame_start, sc.frame_end = 1, 1 + (len(keys) - 1) * step
    sc.frame_set(1)
    return len(keys)


def remove_reel(settings, base):
    sc = bpy.context.scene
    if base and base.animation_data and base.animation_data.action and base.animation_data.action.name == REEL:
        prev = bpy.data.actions.get(settings.reel_prev_action) if settings.reel_prev_action else None
        base.animation_data.action = prev
        sc.frame_start, sc.frame_end = settings.reel_prev_range
    act = bpy.data.actions.get(REEL)
    if act:
        bpy.data.actions.remove(act)
    if base:
        clear_pose([base])


def reel_active(base):
    return bool(base and base.animation_data and base.animation_data.action and base.animation_data.action.name == REEL)


# --------------------------------------------------------------------------- chain swing and hang
def body_bones(arm, base, item=None):
    names = set(bones.humanoid_roles(arm.data.bones.keys()))
    if item is not None:
        names |= {r.outfit_bone for r in item.rows if r.base_bone}
    return names


def chains(arm, body, name_filter=""):
    """Bones that are not body bones but hang off one (cape, skirt, hair, ears, tails...): every chain bone."""
    out = []
    flt = name_filter.lower().strip()
    for b in arm.data.bones:
        if b.name in body:
            continue
        p = b.parent
        while p is not None and p.name not in body:
            p = p.parent
        if p is None and b.parent is not None:
            continue                        # not attached to the body at all
        if flt and flt not in b.name.lower():
            continue
        out.append(b.name)
    return out


def swing_quats(arm, chain_bones, mode, degrees):
    """Per-bone local rotation that moves each chain bone's tip in the given direction (canonical frame)."""
    frame = facing(arm)
    roles = {r: n for n, r in bones.humanoid_roles(arm.data.bones.keys()).items()}
    hb = arm.data.bones.get(roles.get("Hips", ""))
    hd = arm.data.bones.get(roles.get("Head", ""))
    axis_base = hb.head_local if hb else Vector((0, 0, 0))
    axis_dir = ((hd.head_local - hb.head_local).normalized() if hb and hd else Vector((0, 0, 1)))
    want = {"BACK": Vector((0, 1, 0)), "FORWARD": Vector((0, -1, 0)), "LEFT": Vector((1, 0, 0)),
            "RIGHT": Vector((-1, 0, 0)), "GRAVITY": Vector((0, 0, -1))}
    out = {}
    for bn in chain_bones:
        b = arm.data.bones[bn]
        bdir = (b.tail_local - b.head_local).normalized()
        if mode == "OUTWARD":
            rel = b.head_local - axis_base
            radial = rel - axis_dir * rel.dot(axis_dir)
            d = radial.normalized() if radial.length > 1e-5 else frame @ Vector((0, 1, 0))
        else:
            d = frame @ want[mode]
        ax = bdir.cross(d)
        if ax.length < 1e-4 or not degrees:
            out[bn] = Quaternion()
            continue
        loc_axis = (b.matrix_local.to_3x3().inverted() @ ax).normalized()
        out[bn] = Quaternion(loc_axis, math.radians(degrees))
    return out


def swing(arm, chain_bones, mode, degrees):
    """Rotate every chain bone so its tip moves in the given direction (canonical frame), degrees per bone."""
    for bn, q in swing_quats(arm, chain_bones, mode, degrees).items():
        pb = arm.pose.bones[bn]
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = q
    bpy.context.view_layer.update()


def chain_roots(arm, chain_bones):
    """First bone of every chain (its parent is a body bone)."""
    cb = set(chain_bones)
    return [bn for bn in chain_bones if arm.data.bones[bn].parent is not None and arm.data.bones[bn].parent.name not in cb]


def _chain_tree(arm, root):
    """Bones of the chain under `root`, parents first, and the chain length (bones on the longest path)."""
    b0 = arm.data.bones[root]
    order, todo = [], [b0]
    while todo:
        b = todo.pop(0)
        order.append(b)
        todo.extend(b.children)
    base = len(b0.parent_recursive)
    return order, max(len(b.parent_recursive) - base + 1 for b in order)


def hang(arm, roots, strength, extra=None):
    """Gravity preview: every bone of the chains under `roots` turns part of the way back toward its rest
    direction (armature space), so the top of a chain still follows its parent and the hang builds up toward the
    tip. strength 0 = rigid with the parent, 1 = every bone keeps its rest direction; in between the tip keeps
    (1 - strength) of the parent's rotation. `extra` = optional local rotation per bone on top (the swing).
    Reads the evaluated pose of the chain parents. Returns True if anything changed (lets a live handler stop)."""
    s = min(max(strength, 0.0), 1.0)
    extra = extra or {}
    changed = False
    for root in roots:
        if root not in arm.data.bones or arm.data.bones[root].parent is None:
            continue
        order, n = _chain_tree(arm, root)
        c = 1.0 if s >= 1.0 else 1.0 - (1.0 - s) ** (1.0 / n)     # per-bone share, compounds to s at the tip
        X = {}                                                       # armature-space pose computed here
        for b in order:
            pb = arm.pose.bones[b.name]
            px = X.get(b.parent.name)
            if px is None:
                px = pb.parent.matrix
            inherited = px @ b.parent.matrix_local.inverted() @ b.matrix_local
            qi = inherited.to_3x3().normalized().to_quaternion()
            qt = qi.slerp(b.matrix_local.to_3x3().normalized().to_quaternion(), c) if c > 0 else qi
            q = (qi.inverted() @ qt) @ extra.get(b.name, Quaternion())
            if pb.rotation_mode != "QUATERNION":
                pb.rotation_mode = "QUATERNION"
                changed = True
            if pb.rotation_quaternion.rotation_difference(q).angle > 1e-5:
                pb.rotation_quaternion = q
                changed = True
            loc, _, sc = pb.matrix_basis.decompose()
            X[b.name] = inherited @ Matrix.LocRotScale(loc, q, sc)
    return changed


# --------------------------------------------------------------------------- toggle states (visibility + shape keys)
def capture_state(meshes):
    vis = {o.name: not o.hide_get() for o in meshes}
    keys = {}
    for o in meshes:
        if o.data.shape_keys:
            nz = {k.name: round(k.value, 4) for k in o.data.shape_keys.key_blocks[1:] if abs(k.value) > 1e-4}
            if nz:
                keys[o.name] = nz
    return json.dumps({"vis": vis, "keys": keys})


def apply_state(settings, data):
    st = json.loads(data)
    for n, v in st.get("vis", {}).items():
        o = bpy.data.objects.get(n)
        if o:
            o.hide_viewport = False
            o.hide_set(not v)
    # every shape key mentioned by ANY state is driven: this state's value, else 0
    mentioned = {}
    for s in settings.states:
        for on, kv in json.loads(s.data).get("keys", {}).items():
            mentioned.setdefault(on, set()).update(kv)
    mine = st.get("keys", {})
    for on, names in mentioned.items():
        o = bpy.data.objects.get(on)
        if not (o and o.data.shape_keys):
            continue
        for kn in names:
            kb = o.data.shape_keys.key_blocks.get(kn)
            if kb:
                kb.value = mine.get(on, {}).get(kn, 0.0)


def states_from_config(meshes):
    """Convert avatar_qa config states (hide list + shape keys) into toggle-state JSON."""
    _, cfg_states = config_library()
    hidden_any = {n for s in cfg_states.values() for n in s.get("hide", [])}
    out = {}
    for name, s in cfg_states.items():
        vis = {n: n not in s.get("hide", []) for n in hidden_any}
        out[name] = json.dumps({"vis": vis, "keys": s.get("shape_keys", {})})
    return out


# --------------------------------------------------------------------------- weights (rules for game engine export)
def _weights(o):
    names = [g.name for g in o.vertex_groups]
    W = np.zeros((len(o.data.vertices), len(names)))
    for v in o.data.vertices:
        for g in v.groups:
            if g.group < len(names):
                W[v.index, g.group] = g.weight
    return names, W


def _deform_names(o):
    arm = next((m.object for m in o.modifiers if m.type == "ARMATURE" and m.object), None)
    return ({b.name for b in arm.data.bones if b.use_deform} if arm else set()), arm


def _clusters(o, tol):
    co = np.array([o.matrix_world @ v.co for v in o.data.vertices])
    kd = KDTree(len(co))
    for i, c in enumerate(co):
        kd.insert(c, i)
    kd.balance()
    parent = np.arange(len(co))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for i, c in enumerate(co):
        for (_, j, _) in kd.find_range(c, tol):
            if j != i:
                ra, rb = find(i), find(j)
                if ra != rb:
                    parent[ra] = rb
    return np.array([find(i) for i in range(len(co))])


def check_weights(o, tol=0.0005, max_inf=4):
    deform, arm = _deform_names(o)
    names, W = _weights(o)
    d = [j for j, n in enumerate(names) if n in deform]
    Wd = W[:, d] if d else np.zeros((len(W), 0))
    s = Wd.sum(1)
    infl = (Wd > 1e-4).sum(1)
    roots = _clusters(o, tol)
    torn = 0
    uniq, inv, cnt = np.unique(roots, return_inverse=True, return_counts=True)
    for k in np.nonzero(cnt > 1)[0]:
        m = inv == k
        if np.abs(W[m] - W[m].mean(0)).sum(1).max() > 0.01:
            torn += int(m.sum())
    return {
        "armature": arm.name if arm else None,
        "unweighted": int((s < 1e-4).sum()),
        "unnormalized": int(((np.abs(s - 1) > 0.01) & (s >= 1e-4)).sum()),
        "over_limit": int((infl > max_inf).sum()),
        "split_seam": torn,
        "empty_groups": sum(1 for j in range(len(names)) if W[:, j].max() <= 1e-4),
        "no_bone_groups": sum(1 for j, n in enumerate(names) if n not in deform and W[:, j].max() > 1e-4),
    }


def fix_weights(o, tol=0.0005, max_inf=4, weld=True, limit=True, normalize=True, clean=True, drop_empty=True):
    deform, arm = _deform_names(o)
    names, W = _weights(o)
    W0 = W.copy()
    if weld:
        roots = _clusters(o, tol)
        uniq, inv, cnt = np.unique(roots, return_inverse=True, return_counts=True)
        S = np.zeros((len(uniq), W.shape[1]))
        np.add.at(S, inv, W)
        multi = cnt[inv] > 1
        W[multi] = (S[inv] / cnt[inv][:, None])[multi]
    if clean:
        W[W < 0.001] = 0
    dcols = np.array([j for j, n in enumerate(names) if n in deform], dtype=np.int64)
    if limit and len(dcols) > max_inf:
        Wd = W[:, dcols]
        drop = np.argsort(-Wd, axis=1)[:, max_inf:]
        np.put_along_axis(Wd, drop, 0, axis=1)
        W[:, dcols] = Wd
    if normalize and len(dcols):
        s = W[:, dcols].sum(1, keepdims=True)
        ok = s[:, 0] > 1e-6
        W[np.ix_(ok, dcols)] /= s[ok]
    changed = np.nonzero(np.abs(W - W0).sum(1) > 1e-5)[0]
    if len(changed):
        idx = changed.tolist()
        for g in o.vertex_groups:
            g.remove(idx)
        Wq = np.round(W[changed] * 4096) / 4096
        for j, n in enumerate(names):
            col = Wq[:, j]
            nz = np.nonzero(col > 0)[0]
            for u in np.unique(col[nz]):
                o.vertex_groups[n].add(changed[nz[col[nz] == u]].tolist(), float(u), "REPLACE")
    removed = 0
    if drop_empty:
        for j, n in reversed(list(enumerate(names))):
            if W[:, j].max() <= 1e-4:
                o.vertex_groups.remove(o.vertex_groups[n])
                removed += 1
    return {"changed_verts": int(len(changed)), "removed_groups": removed}
