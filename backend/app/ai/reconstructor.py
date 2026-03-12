from __future__ import annotations

import asyncio
import logging
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import trimesh

logger = logging.getLogger(__name__)


def resolve_model(model: str, preset: str) -> str:
    """Resolve effective reconstruction model from explicit model + preset."""
    if model != "auto":
        return model

    if preset == "fast":
        return "triposr"
    if preset in {"balanced", "high"}:
        return "sf3d"
    return "sf3d"


def _depth_to_fallback_mesh(depth_map: np.ndarray) -> trimesh.Trimesh:
    # Simple depth-surface fallback so pipeline is always usable in dev.
    h, w = depth_map.shape
    target = max(32, min(160, max(h, w)))

    ys = np.linspace(0, h - 1, target).astype(np.int32)
    xs = np.linspace(0, w - 1, target).astype(np.int32)
    d = depth_map[np.ix_(ys, xs)]

    x = np.linspace(-1.0, 1.0, target)
    y = np.linspace(-1.0, 1.0, target)
    xx, yy = np.meshgrid(x, y)
    zz = d * 0.5

    vertices = np.column_stack([xx.ravel(), yy.ravel(), zz.ravel()])
    faces: list[list[int]] = []
    for row in range(target - 1):
        for col in range(target - 1):
            i = row * target + col
            faces.append([i, i + target, i + 1])
            faces.append([i + 1, i + target, i + target + 1])

    top = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)
    top.apply_translation([0, 0, 0.1])

    base = trimesh.creation.box(extents=[2.0, 2.0, 0.12])
    base.apply_translation([0.0, 0.0, -0.06])

    return trimesh.util.concatenate([top, base])


async def _run_external(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return process.returncode, stdout.decode(), stderr.decode()


async def reconstruct_mesh_sf3d(image_path: str, depth_map_path: str | None = None) -> str:
    """
    Attempt SF3D execution if repo exists; otherwise use fallback procedural mesh.
    Returns mesh file path.
    """
    sf3d_path = Path(os.getenv("SF3D_PATH", "/app/sf3d"))
    if not sf3d_path.exists():
        sf3d_path = Path(__file__).resolve().parents[3] / "external" / "sf3d"

    if sf3d_path.exists() and (sf3d_path / "run.py").exists():
        output_dir = Path(tempfile.mkdtemp(prefix="sf3d_"))
        cmd = [
            sys.executable,
            str(sf3d_path / "run.py"),
            image_path,
            "--output-dir",
            str(output_dir),
        ]
        rc, _out, err = await _run_external(cmd, cwd=sf3d_path)
        if rc == 0:
            glbs = list(output_dir.glob("*.glb"))
            if glbs:
                return str(glbs[0])
        logger.warning("SF3D failed or produced no output; using fallback. stderr=%s", err.strip())

    depth = np.load(depth_map_path) if depth_map_path else np.zeros((64, 64), dtype=np.float32)
    mesh = _depth_to_fallback_mesh(depth)
    out = tempfile.mktemp(prefix="sf3d_fallback_", suffix=".glb")
    mesh.export(out, file_type="glb")
    return out


async def reconstruct_mesh_triposr(image_path: str) -> str:
    """
    Attempt TripoSR execution if repo exists; otherwise fallback.
    Returns mesh file path.
    """
    triposr_path = Path(os.getenv("TRIPOSR_PATH", "/app/TripoSR"))
    if not triposr_path.exists():
        triposr_path = Path(__file__).resolve().parents[3] / "external" / "TripoSR"

    if triposr_path.exists() and (triposr_path / "run.py").exists():
        output_dir = Path(tempfile.mkdtemp(prefix="triposr_"))
        cmd = [
            sys.executable,
            str(triposr_path / "run.py"),
            image_path,
            "--output-dir",
            str(output_dir),
        ]
        rc, _out, err = await _run_external(cmd, cwd=triposr_path)
        if rc == 0:
            objs = list(output_dir.glob("*.obj"))
            if objs:
                return str(objs[0])
        logger.warning("TripoSR failed or produced no output; using fallback. stderr=%s", err.strip())

    with tempfile.NamedTemporaryFile(suffix=".obj", delete=False) as tmp:
        mesh = trimesh.creation.icosphere(subdivisions=3, radius=1.0)
        mesh.export(tmp.name, file_type="obj")
        return tmp.name
