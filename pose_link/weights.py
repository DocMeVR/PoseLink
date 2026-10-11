"""Weight checks for meshes that go to a game engine, and the matching fixes.

Most engines keep only 4 bones per vertex and need the weights to add up to 1. Vertices that sit on top of each
other (a split seam) need the same weights, or the seam tears open when the character moves.
"""
import numpy as np
from mathutils.kdtree import KDTree

MAX_BONES = 4
SEAM_TOLERANCE = 0.0005   # metres; closer than this counts as the same spot


def _weight_table(obj):
    """(group names, vertices x groups array of weights)."""
    names = [group.name for group in obj.vertex_groups]
    table = np.zeros((len(obj.data.vertices), len(names)))
    for vertex in obj.data.vertices:
        for element in vertex.groups:
            if element.group < len(names):
                table[vertex.index, element.group] = element.weight
    return names, table


def _deforming_bones(obj):
    armature = next((m.object for m in obj.modifiers if m.type == "ARMATURE" and m.object), None)
    names = {bone.name for bone in armature.data.bones if bone.use_deform} if armature else set()
    return names, armature


def _same_spot_groups(obj, tolerance):
    """For every vertex the id of its group of vertices at the same spot (union-find over a KD tree)."""
    points = np.array([obj.matrix_world @ v.co for v in obj.data.vertices])
    tree = KDTree(len(points))
    for index, point in enumerate(points):
        tree.insert(point, index)
    tree.balance()
    parent = np.arange(len(points))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for index, point in enumerate(points):
        for (_, other, _) in tree.find_range(point, tolerance):
            if other != index:
                a, b = find(index), find(other)
                if a != b:
                    parent[a] = b
    return np.array([find(index) for index in range(len(points))])


def check(obj, tolerance=SEAM_TOLERANCE, max_bones=MAX_BONES):
    """Counts of each problem; 0 everywhere means the mesh is fine."""
    deforming, armature = _deforming_bones(obj)
    names, table = _weight_table(obj)
    bone_columns = [i for i, name in enumerate(names) if name in deforming]
    bone_weights = table[:, bone_columns] if bone_columns else np.zeros((len(table), 0))
    totals = bone_weights.sum(axis=1)
    bones_per_vertex = (bone_weights > 1e-4).sum(axis=1)

    torn = 0
    spots = _same_spot_groups(obj, tolerance)
    _, spot_of_vertex, vertices_per_spot = np.unique(spots, return_inverse=True, return_counts=True)
    for spot in np.nonzero(vertices_per_spot > 1)[0]:
        members = spot_of_vertex == spot
        spread = np.abs(table[members] - table[members].mean(axis=0)).sum(axis=1).max()
        if spread > 0.01:
            torn += int(members.sum())

    return {
        "armature": armature.name if armature else None,
        "unweighted": int((totals < 1e-4).sum()),
        "unnormalized": int(((np.abs(totals - 1) > 0.01) & (totals >= 1e-4)).sum()),
        "over_limit": int((bones_per_vertex > max_bones).sum()),
        "split_seam": torn,
        "empty_groups": sum(1 for i in range(len(names)) if table[:, i].max() <= 1e-4),
        "no_bone_groups": sum(1 for i, name in enumerate(names) if name not in deforming and table[:, i].max() > 1e-4),
    }


def fix(obj, tolerance=SEAM_TOLERANCE, max_bones=MAX_BONES, weld=True, limit=True, normalize=True, clean=True,
        drop_empty=True):
    """Fix what check() reports. Returns how many vertices changed and how many groups were removed."""
    deforming, _ = _deforming_bones(obj)
    names, table = _weight_table(obj)
    before = table.copy()

    if weld:   # vertices on the same spot get the average of their weights
        spots = _same_spot_groups(obj, tolerance)
        unique_spots, spot_of_vertex, vertices_per_spot = np.unique(spots, return_inverse=True, return_counts=True)
        sums = np.zeros((len(unique_spots), table.shape[1]))
        np.add.at(sums, spot_of_vertex, table)
        shared = vertices_per_spot[spot_of_vertex] > 1
        table[shared] = (sums[spot_of_vertex] / vertices_per_spot[spot_of_vertex][:, None])[shared]
    if clean:
        table[table < 0.001] = 0
    bone_columns = np.array([i for i, name in enumerate(names) if name in deforming], dtype=np.int64)
    if limit and len(bone_columns) > max_bones:
        bone_weights = table[:, bone_columns]
        smallest = np.argsort(-bone_weights, axis=1)[:, max_bones:]
        np.put_along_axis(bone_weights, smallest, 0, axis=1)
        table[:, bone_columns] = bone_weights
    if normalize and len(bone_columns):
        totals = table[:, bone_columns].sum(axis=1, keepdims=True)
        weighted = totals[:, 0] > 1e-6
        table[np.ix_(weighted, bone_columns)] /= totals[weighted]

    changed = np.nonzero(np.abs(table - before).sum(axis=1) > 1e-5)[0]
    if len(changed):
        for group in obj.vertex_groups:
            group.remove(changed.tolist())
        # write vertices with the same weight in one call per group, which is much faster on big meshes
        rounded = np.round(table[changed] * 4096) / 4096
        for column, name in enumerate(names):
            weights = rounded[:, column]
            nonzero = np.nonzero(weights > 0)[0]
            for weight in np.unique(weights[nonzero]):
                vertices = changed[nonzero[weights[nonzero] == weight]].tolist()
                obj.vertex_groups[name].add(vertices, float(weight), "REPLACE")

    removed = 0
    if drop_empty:
        for column, name in reversed(list(enumerate(names))):
            if table[:, column].max() <= 1e-4:
                obj.vertex_groups.remove(obj.vertex_groups[name])
                removed += 1
    return {"changed_verts": int(len(changed)), "removed_groups": removed}
