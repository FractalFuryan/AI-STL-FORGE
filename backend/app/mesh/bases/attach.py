from __future__ import annotations

import trimesh


def attach_base(mesh: trimesh.Trimesh, base_mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Align mesh above base and combine into one printable manifold candidate."""
    mesh = mesh.copy()
    base_mesh = base_mesh.copy()

    mesh_min = mesh.bounds[0]
    mesh_center_x = float((mesh.bounds[0][0] + mesh.bounds[1][0]) / 2)
    mesh_center_y = float((mesh.bounds[0][1] + mesh.bounds[1][1]) / 2)
    mesh.apply_translation([-mesh_center_x, -mesh_center_y, -float(mesh_min[2])])

    base_min_z = float(base_mesh.bounds[0][2])
    base_max_z = float(base_mesh.bounds[1][2])
    base_mesh.apply_translation([0.0, 0.0, -base_min_z])

    mesh.apply_translation([0.0, 0.0, base_max_z])
    return trimesh.util.concatenate([base_mesh, mesh])
