from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
import trimesh

logger = logging.getLogger(__name__)


@dataclass
class FigureDimensions:
    """Default action figure proportions in millimeters."""

    height: float = 300.0
    head_height: float = 30.0
    torso_height: float = 100.0
    leg_height: float = 120.0
    arm_length: float = 80.0
    shoulder_width: float = 70.0
    waist_width: float = 50.0


class ActionFigureGenerator:
    """Generate stylized articulated action figures from 2D images."""

    def __init__(self) -> None:
        self.dimensions = FigureDimensions()
        self.joints: dict[str, dict[str, Any]] = {
            "neck": {"type": "ball", "range": 45},
            "shoulder_left": {"type": "ball", "range": 180},
            "shoulder_right": {"type": "ball", "range": 180},
            "elbow_left": {"type": "hinge", "range": 135},
            "elbow_right": {"type": "hinge", "range": 135},
            "hip_left": {"type": "ball", "range": 120},
            "hip_right": {"type": "ball", "range": 120},
            "knee_left": {"type": "hinge", "range": 135},
            "knee_right": {"type": "hinge", "range": 135},
            "waist": {"type": "swivel", "range": 90},
        }

    async def generate_from_image(
        self,
        image: np.ndarray,
        style: str = "realistic",
        scale: str = "1:6",
        articulated: bool = True,
    ) -> trimesh.Trimesh:
        pose = await self.extract_pose(image)
        silhouette = self.extract_silhouette(image)

        body = self._generate_body(pose, silhouette, style)

        if articulated:
            body = self._add_articulation(body)

        target_height = self._get_scale_height(scale)
        current_height = float(body.bounds[1][2] - body.bounds[0][2])
        if current_height > 0:
            body.apply_scale(target_height / current_height)

        body.apply_translation([0.0, 0.0, -body.bounds[0][2]])
        return body

    async def extract_pose(self, image: np.ndarray) -> dict[str, dict[str, float]]:
        """
        Extract a sparse pose map.
        Prefers MediaPipe when available, falls back to geometric anchors.
        """
        try:
            import mediapipe as mp  # type: ignore

            mp_pose = mp.solutions.pose
            with mp_pose.Pose(static_image_mode=True) as pose:
                results = pose.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                if not results.pose_landmarks:
                    raise ValueError("No pose detected in image")

                landmarks: dict[str, dict[str, float]] = {}
                for idx, landmark in enumerate(results.pose_landmarks.landmark):
                    landmarks[mp_pose.PoseLandmark(idx).name] = {
                        "x": float(landmark.x),
                        "y": float(landmark.y),
                        "z": float(landmark.z),
                        "visibility": float(landmark.visibility),
                    }
                return landmarks
        except Exception as exc:  # pragma: no cover - optional dependency path
            logger.info("MediaPipe unavailable or pose extraction failed: %s", exc)

        h, w = image.shape[:2]
        return {
            "NOSE": {"x": 0.5, "y": 0.15, "z": 0.0, "visibility": 0.8},
            "LEFT_SHOULDER": {"x": 0.4, "y": 0.35, "z": 0.0, "visibility": 0.7},
            "RIGHT_SHOULDER": {"x": 0.6, "y": 0.35, "z": 0.0, "visibility": 0.7},
            "LEFT_HIP": {"x": 0.45, "y": 0.55, "z": 0.0, "visibility": 0.7},
            "RIGHT_HIP": {"x": 0.55, "y": 0.55, "z": 0.0, "visibility": 0.7},
            "IMAGE_SIZE": {"x": float(w), "y": float(h), "z": 0.0, "visibility": 1.0},
        }

    def extract_silhouette(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        mask = np.zeros(gray.shape[:2], np.uint8)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        rect = (5, 5, gray.shape[1] - 10, gray.shape[0] - 10)
        cv2.grabCut(image, mask, rect, bgd_model, fgd_model, 2, cv2.GC_INIT_WITH_RECT)
        return np.where((mask == 2) | (mask == 0), 0, 1).astype(np.uint8)

    def _generate_body(
        self,
        pose: dict[str, dict[str, float]],
        silhouette: np.ndarray,
        style: str,
    ) -> trimesh.Trimesh:
        parts: list[trimesh.Trimesh] = [
            self._create_torso(silhouette),
            self._create_head(style),
        ]
        parts.extend(self._create_limbs())
        return trimesh.util.concatenate(parts)

    def _create_torso(self, silhouette: np.ndarray) -> trimesh.Trimesh:
        h, w = silhouette.shape
        torso_region = silhouette[h // 4 : h // 2, :]
        torso_width_ratio = float(np.clip(np.sum(torso_region, axis=1).mean() / max(w, 1), 0.15, 0.85))
        torso_width = torso_width_ratio * self.dimensions.shoulder_width

        torso = trimesh.creation.cylinder(
            radius=max(8.0, torso_width / 2.0),
            height=self.dimensions.torso_height,
            sections=32,
        )
        torso.apply_translation([0.0, 0.0, self.dimensions.torso_height / 2.0])
        chest = trimesh.creation.icosphere(subdivisions=2, radius=max(7.0, torso_width * 0.35))
        chest.apply_translation([0.0, 0.0, self.dimensions.torso_height * 0.8])
        return trimesh.util.concatenate([torso, chest])

    def _create_head(self, style: str) -> trimesh.Trimesh:
        head = trimesh.creation.icosphere(subdivisions=2, radius=self.dimensions.head_height / 2.0)
        if style == "cartoon":
            head.apply_scale([1.1, 1.0, 0.9])
        if style == "anime":
            head.apply_scale([1.15, 0.95, 0.95])
        head.apply_translation([0.0, 0.0, self.dimensions.torso_height + self.dimensions.head_height * 0.65])
        return head

    def _create_limbs(self) -> list[trimesh.Trimesh]:
        limbs: list[trimesh.Trimesh] = []
        shoulder_x = self.dimensions.shoulder_width * 0.55

        for sign in (-1.0, 1.0):
            upper_arm = trimesh.creation.cylinder(
                radius=self.dimensions.shoulder_width * 0.12,
                height=self.dimensions.arm_length * 0.48,
                sections=16,
            )
            lower_arm = trimesh.creation.cylinder(
                radius=self.dimensions.shoulder_width * 0.10,
                height=self.dimensions.arm_length * 0.45,
                sections=16,
            )
            upper_arm.apply_translation([sign * shoulder_x, 0.0, self.dimensions.torso_height * 0.75])
            lower_arm.apply_translation([sign * shoulder_x, 0.0, self.dimensions.torso_height * 0.35])
            limbs.extend([upper_arm, lower_arm])

        hip_x = self.dimensions.waist_width * 0.30
        for sign in (-1.0, 1.0):
            upper_leg = trimesh.creation.cylinder(
                radius=self.dimensions.waist_width * 0.18,
                height=self.dimensions.leg_height * 0.50,
                sections=16,
            )
            lower_leg = trimesh.creation.cylinder(
                radius=self.dimensions.waist_width * 0.14,
                height=self.dimensions.leg_height * 0.50,
                sections=16,
            )
            upper_leg.apply_translation([sign * hip_x, 0.0, -self.dimensions.leg_height * 0.05])
            lower_leg.apply_translation([sign * hip_x, 0.0, -self.dimensions.leg_height * 0.55])
            limbs.extend([upper_leg, lower_leg])

        return limbs

    def _add_articulation(self, mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        radius = self.dimensions.shoulder_width * 0.09
        joint_positions = [
            [0.0, 0.0, self.dimensions.torso_height * 0.95],
            [-self.dimensions.shoulder_width * 0.55, 0.0, self.dimensions.torso_height * 0.75],
            [self.dimensions.shoulder_width * 0.55, 0.0, self.dimensions.torso_height * 0.75],
            [-self.dimensions.waist_width * 0.30, 0.0, 0.0],
            [self.dimensions.waist_width * 0.30, 0.0, 0.0],
            [0.0, 0.0, self.dimensions.torso_height * 0.30],
        ]

        joint_shells: list[trimesh.Trimesh] = []
        for pos in joint_positions:
            socket = trimesh.creation.icosphere(subdivisions=1, radius=radius * 1.05)
            socket.apply_translation(pos)
            ball = trimesh.creation.icosphere(subdivisions=1, radius=radius)
            ball.apply_translation(pos)
            joint_shells.extend([socket, ball])

        return trimesh.util.concatenate([mesh] + joint_shells)

    def _get_scale_height(self, scale: str) -> float:
        return {
            "1:6": 300.0,
            "1:12": 150.0,
            "1:18": 100.0,
            "28mm": 28.0,
            "32mm": 32.0,
            "54mm": 54.0,
        }.get(scale, 300.0)
