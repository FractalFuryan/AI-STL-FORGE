import io
import time

import numpy as np
import trimesh
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter, sobel

from app.models import GenerationParams
from app.services.depth_estimator import depth_estimator


class STLGenerator:
    def __init__(self) -> None:
        self._healthy = True
        self._last_health_check = 0.0
        self._health_check_interval = 60.0

    def is_healthy(self) -> bool:
        now = time.time()
        if now - self._last_health_check < self._health_check_interval:
            return self._healthy

        try:
            _ = self.heightmap_to_mesh(np.zeros((2, 2), dtype=np.float32), GenerationParams())
            self._healthy = True
        except Exception:
            self._healthy = False
        finally:
            self._last_health_check = now

        return self._healthy

    async def image_to_heightmap_async(self, image_bytes: bytes, params: GenerationParams) -> np.ndarray:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)

        if params.mode == "ai-depth":
            rgb = image.convert("RGB")
            rgb.thumbnail((params.resolution, params.resolution), Image.Resampling.LANCZOS)
            arr = await depth_estimator.estimate_depth(rgb)
            arr = (arr - arr.min()) / (arr.max() - arr.min() + 1e-6)

            if params.smooth_sigma > 0:
                arr = gaussian_filter(arr, sigma=params.smooth_sigma)

            return arr * params.max_height

        return self.image_to_heightmap(image_bytes, params)

    def image_to_heightmap(self, image_bytes: bytes, params: GenerationParams) -> np.ndarray:
        image = Image.open(io.BytesIO(image_bytes)).convert("L")
        image = ImageOps.exif_transpose(image)
        image.thumbnail((params.resolution, params.resolution), Image.Resampling.LANCZOS)

        arr = np.asarray(image, dtype=np.float32)
        arr = (arr - arr.min()) / (arr.max() - arr.min() + 1e-6)
        arr = np.power(arr, params.gamma)

        if params.mode == "lithophane":
            arr = 1.0 - arr

        if params.smooth_sigma > 0:
            arr = gaussian_filter(arr, sigma=params.smooth_sigma)

        if params.mode == "lithophane":
            min_t = 0.8
            max_t = params.max_height
            return min_t + arr * (max_t - min_t)

        if params.mode == "emboss":
            # Add edge boost to make embossed details pop.
            dx = sobel(arr, axis=0)
            dy = sobel(arr, axis=1)
            edges = np.sqrt(dx * dx + dy * dy)
            embossed = np.clip(np.clip((arr - 0.38) / 0.62, 0.0, 1.0) * (1.0 + edges), 0.0, 1.0)
            return embossed * params.max_height

        if params.mode == "relief":
            # Keep a baseline lift with additional detail on top.
            baseline = 0.18 * params.max_height
            detail = arr * (0.82 * params.max_height)
            return baseline + detail

        return arr * params.max_height

    def heightmap_to_mesh(self, heightmap: np.ndarray, params: GenerationParams) -> trimesh.Trimesh:
        h, w = heightmap.shape
        scale_x = params.target_width_mm / max(w - 1, 1)
        scale_y = params.target_width_mm * (h / max(w, 1)) / max(h - 1, 1)

        top_vertices = np.zeros((h * w, 3), dtype=np.float32)
        base_vertices = np.zeros((h * w, 3), dtype=np.float32)

        for y in range(h):
            for x in range(w):
                idx = y * w + x
                z = float(heightmap[y, x])
                top_vertices[idx] = [x * scale_x, y * scale_y, z]
                base_vertices[idx] = [x * scale_x, y * scale_y, -params.base_thickness]

        vertices = np.vstack([top_vertices, base_vertices])
        base_offset = h * w

        faces: list[list[int]] = []

        # Top and bottom surfaces.
        for y in range(h - 1):
            for x in range(w - 1):
                v0 = y * w + x
                v1 = y * w + (x + 1)
                v2 = (y + 1) * w + x
                v3 = (y + 1) * w + (x + 1)

                faces.extend([[v0, v1, v2], [v1, v3, v2]])

                b0 = base_offset + v0
                b1 = base_offset + v1
                b2 = base_offset + v2
                b3 = base_offset + v3
                faces.extend([[b0, b2, b1], [b1, b2, b3]])

        # Front and back walls.
        for x in range(w - 1):
            t0 = x
            t1 = x + 1
            b0 = base_offset + x
            b1 = base_offset + x + 1
            faces.extend([[t0, b0, t1], [t1, b0, b1]])

            tf0 = (h - 1) * w + x
            tf1 = (h - 1) * w + x + 1
            bf0 = base_offset + tf0
            bf1 = base_offset + tf1
            faces.extend([[tf0, tf1, bf0], [tf1, bf1, bf0]])

        # Left and right walls.
        for y in range(h - 1):
            t0 = y * w
            t1 = (y + 1) * w
            b0 = base_offset + t0
            b1 = base_offset + t1
            faces.extend([[t0, t1, b0], [t1, b1, b0]])

            tr0 = y * w + (w - 1)
            tr1 = (y + 1) * w + (w - 1)
            br0 = base_offset + tr0
            br1 = base_offset + tr1
            faces.extend([[tr0, br0, tr1], [tr1, br0, br1]])

        mesh = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)
        mesh.update_faces(mesh.nondegenerate_faces())
        mesh.update_faces(mesh.unique_faces())
        mesh.remove_unreferenced_vertices()
        mesh.fix_normals()

        if params.adaptive_remesh and len(mesh.faces) > 10_000:
            try:
                mesh = mesh.simplify_quadric_decimation(10_000)
            except Exception:
                pass

        return mesh

    def generate_stl(self, image_bytes: bytes, params: GenerationParams) -> bytes:
        heightmap = self.image_to_heightmap(image_bytes, params)
        mesh = self.heightmap_to_mesh(heightmap, params)
        return mesh.export(file_type="stl")

    async def generate_stl_async(self, image_bytes: bytes, params: GenerationParams) -> bytes:
        heightmap = await self.image_to_heightmap_async(image_bytes, params)
        mesh = self.heightmap_to_mesh(heightmap, params)
        return mesh.export(file_type="stl")
