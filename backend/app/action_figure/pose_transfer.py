from __future__ import annotations

from typing import Dict, List

import numpy as np
from scipy.spatial.transform import Rotation
import trimesh


class PoseTransfer:
    """Apply simple linear blend skinning transforms between poses."""

    def __init__(self) -> None:
        self.skeleton = self._create_skeleton()

    def _create_skeleton(self) -> Dict[str, list[float]]:
        return {
            "root": [0, 0, 0],
            "spine": [0, 0, 50],
            "chest": [0, 0, 100],
            "neck": [0, 0, 140],
            "head": [0, 0, 160],
            "shoulder_left": [-30, 0, 120],
            "shoulder_right": [30, 0, 120],
            "elbow_left": [-40, 0, 80],
            "elbow_right": [40, 0, 80],
            "wrist_left": [-40, 0, 40],
            "wrist_right": [40, 0, 40],
            "hip_left": [-20, 0, 0],
            "hip_right": [20, 0, 0],
            "knee_left": [-20, 0, -50],
            "knee_right": [20, 0, -50],
            "ankle_left": [-20, 0, -100],
            "ankle_right": [20, 0, -100],
        }

    def apply_pose(self, mesh: trimesh.Trimesh, source_pose: Dict, target_pose: Dict) -> trimesh.Trimesh:
        weights = self._compute_skin_weights(mesh)
        transforms = self._compute_bone_transforms(source_pose, target_pose)
        vertices = self._linear_blend_skinning(mesh.vertices, weights, transforms)
        return trimesh.Trimesh(vertices=vertices, faces=mesh.faces, process=False)

    def _compute_skin_weights(self, mesh: trimesh.Trimesh) -> np.ndarray:
        n_vertices = len(mesh.vertices)
        n_bones = len(self.skeleton)
        weights = np.zeros((n_vertices, n_bones), dtype=np.float64)

        for i, bone_pos in enumerate(self.skeleton.values()):
            distances = np.linalg.norm(mesh.vertices - np.asarray(bone_pos, dtype=np.float64), axis=1)
            weights[:, i] = 1.0 / (distances + 1e-6)

        weights /= np.sum(weights, axis=1, keepdims=True)
        return weights

    def _compute_bone_transforms(self, source_pose: Dict, target_pose: Dict) -> List[np.ndarray]:
        transforms: List[np.ndarray] = []
        for bone_name in self.skeleton.keys():
            if bone_name not in source_pose or bone_name not in target_pose:
                transforms.append(np.eye(4))
                continue

            source_vec = np.asarray(source_pose[bone_name], dtype=np.float64)
            target_vec = np.asarray(target_pose[bone_name], dtype=np.float64)

            source_norm = np.linalg.norm(source_vec)
            target_norm = np.linalg.norm(target_vec)
            if source_norm < 1e-8 or target_norm < 1e-8:
                rot = np.eye(3)
            else:
                rot = Rotation.align_vectors(
                    (target_vec / target_norm).reshape(1, -1),
                    (source_vec / source_norm).reshape(1, -1),
                )[0].as_matrix()

            trans = target_vec - source_vec
            transform = np.eye(4)
            transform[:3, :3] = rot
            transform[:3, 3] = trans
            transforms.append(transform)

        return transforms

    def _linear_blend_skinning(
        self,
        vertices: np.ndarray,
        weights: np.ndarray,
        transforms: List[np.ndarray],
    ) -> np.ndarray:
        new_vertices = np.zeros_like(vertices)
        for i, v in enumerate(vertices):
            v_h = np.append(v, 1.0)
            accum = np.zeros(3, dtype=np.float64)
            for j, transform in enumerate(transforms):
                accum += weights[i, j] * (transform @ v_h)[:3]
            new_vertices[i] = accum
        return new_vertices
