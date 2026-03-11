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
        self._max_faces = 500_000

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

    def _load_image(self, image_bytes: bytes) -> Image.Image:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        return image.copy()

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

    def _postprocess_mesh(self, mesh: trimesh.Trimesh, params: GenerationParams) -> trimesh.Trimesh:
        mesh.update_faces(mesh.nondegenerate_faces())
        mesh.update_faces(mesh.unique_faces())
        mesh.remove_unreferenced_vertices()
        try:
            mesh.fix_normals()
        except Exception:
            # Continue with exportable geometry even if winding repair fails.
            pass

        if params.adaptive_remesh and len(mesh.faces) > 10_000:
            try:
                mesh = mesh.simplify_quadric_decimation(10_000)
            except Exception:
                pass

        # Align base to Z=0 for slicer-friendly output.
        z_min = float(mesh.bounds[0][2])
        if z_min != 0.0:
            mesh.apply_translation([0.0, 0.0, -z_min])

        return mesh

    def heightmap_to_mesh(self, heightmap: np.ndarray, params: GenerationParams) -> trimesh.Trimesh:
        h, w = heightmap.shape
        estimated_faces = ((h - 1) * (w - 1) * 4) + ((h - 1) * 4) + ((w - 1) * 4)
        if estimated_faces > self._max_faces:
            raise ValueError(f"Generated mesh exceeds face limit ({self._max_faces}).")

        scale_x = params.target_width_mm / max(w - 1, 1)
        scale_y = params.target_width_mm * (h / max(w, 1)) / max(h - 1, 1)

        x = np.arange(w, dtype=np.float32) * scale_x
        y = np.arange(h, dtype=np.float32) * scale_y
        xx, yy = np.meshgrid(x, y)

        top_vertices = np.column_stack([xx.ravel(), yy.ravel(), heightmap.ravel()])
        base_vertices = np.column_stack(
            [xx.ravel(), yy.ravel(), np.full(h * w, -params.base_thickness, dtype=np.float32)]
        )
        vertices = np.vstack([top_vertices, base_vertices])

        grid = np.arange(h * w, dtype=np.int64).reshape(h, w)
        base_offset = h * w

        top_tri1 = np.column_stack([grid[:-1, :-1].ravel(), grid[:-1, 1:].ravel(), grid[1:, :-1].ravel()])
        top_tri2 = np.column_stack([grid[:-1, 1:].ravel(), grid[1:, 1:].ravel(), grid[1:, :-1].ravel()])
        bottom_tri1 = np.column_stack(
            [
                (base_offset + grid[:-1, :-1]).ravel(),
                (base_offset + grid[1:, :-1]).ravel(),
                (base_offset + grid[:-1, 1:]).ravel(),
            ]
        )
        bottom_tri2 = np.column_stack(
            [
                (base_offset + grid[:-1, 1:]).ravel(),
                (base_offset + grid[1:, 1:]).ravel(),
                (base_offset + grid[1:, :-1]).ravel(),
            ]
        )

        walls: list[np.ndarray] = []
        walls.append(np.column_stack([grid[0, :-1], base_offset + grid[0, :-1], grid[0, 1:]]))
        walls.append(np.column_stack([grid[0, 1:], base_offset + grid[0, :-1], base_offset + grid[0, 1:]]))
        walls.append(np.column_stack([grid[-1, :-1], grid[-1, 1:], base_offset + grid[-1, :-1]]))
        walls.append(np.column_stack([grid[-1, 1:], base_offset + grid[-1, 1:], base_offset + grid[-1, :-1]]))
        walls.append(np.column_stack([grid[:-1, 0], grid[1:, 0], base_offset + grid[:-1, 0]]))
        walls.append(np.column_stack([grid[1:, 0], base_offset + grid[1:, 0], base_offset + grid[:-1, 0]]))
        walls.append(np.column_stack([grid[:-1, -1], base_offset + grid[:-1, -1], grid[1:, -1]]))
        walls.append(np.column_stack([grid[1:, -1], base_offset + grid[:-1, -1], base_offset + grid[1:, -1]]))

        faces = np.vstack([top_tri1, top_tri2, bottom_tri1, bottom_tri2, *walls])
        mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        return self._postprocess_mesh(mesh, params)

    def _create_cookie_cutter_mesh(self, image: Image.Image, params: GenerationParams) -> trimesh.Trimesh:
        try:
            import cv2
        except ImportError as exc:
            raise ValueError("Cookie cutter mode requires opencv-python-headless.") from exc

        img = np.array(image.convert("L"), dtype=np.uint8)
        edges = cv2.Canny(img, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise ValueError("No shape detected in image for cookie cutter mode.")

        contour = max(contours, key=cv2.contourArea)
        epsilon = 0.01 * cv2.arcLength(contour, True)
        simplified = cv2.approxPolyDP(contour, epsilon, True)
        points = simplified[:, 0, :].astype(np.float32)
        if len(points) < 3:
            raise ValueError("Detected contour is too simple for cookie cutter mode.")

        points -= points.min(axis=0)
        max_dim = float(np.max(points.max(axis=0)))
        if max_dim <= 0:
            raise ValueError("Invalid contour geometry.")
        scale = min(params.target_width_mm, 80.0) / max_dim
        points *= scale

        cutter_height = max(5.0, params.max_height)
        wall_thickness = max(0.8, min(params.base_thickness, 4.0))

        offset = points.astype(np.float64)
        center = offset.mean(axis=0)
        normals = center - offset
        lengths = np.linalg.norm(normals, axis=1, keepdims=True) + 1e-6
        inner = offset + (normals / lengths) * wall_thickness

        if len(inner) < 3:
            raise ValueError("Could not create inner cookie cutter wall.")

        n = len(offset)
        vertices = []
        for pt in offset:
            vertices.append([pt[0], pt[1], 0.0])
            vertices.append([pt[0], pt[1], cutter_height])
        for pt in inner:
            vertices.append([pt[0], pt[1], 0.0])
            vertices.append([pt[0], pt[1], cutter_height])

        faces: list[list[int]] = []
        inner_base = 2 * n
        for i in range(n):
            j = (i + 1) % n

            o0, o1 = 2 * i, 2 * j
            o0t, o1t = o0 + 1, o1 + 1
            i0, i1 = inner_base + 2 * i, inner_base + 2 * j
            i0t, i1t = i0 + 1, i1 + 1

            faces.extend([[o0, o1, o0t], [o1, o1t, o0t]])
            faces.extend([[i0, i0t, i1], [i1, i0t, i1t]])
            faces.extend([[o0t, i0t, o1t], [o1t, i0t, i1t]])
            faces.extend([[o0, o1, i0], [o1, i1, i0]])

        mesh = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=False)
        return self._postprocess_mesh(mesh, params)

    def generate_stl(self, image_bytes: bytes, params: GenerationParams) -> bytes:
        if params.mode == "cookie-cutter":
            mesh = self._create_cookie_cutter_mesh(self._load_image(image_bytes), params)
        else:
            heightmap = self.image_to_heightmap(image_bytes, params)
            mesh = self.heightmap_to_mesh(heightmap, params)
        return mesh.export(file_type="stl")

    async def generate_stl_async(self, image_bytes: bytes, params: GenerationParams) -> bytes:
        if params.mode == "cookie-cutter":
            mesh = self._create_cookie_cutter_mesh(self._load_image(image_bytes), params)
        else:
            heightmap = await self.image_to_heightmap_async(image_bytes, params)
            mesh = self.heightmap_to_mesh(heightmap, params)
        return mesh.export(file_type="stl")
