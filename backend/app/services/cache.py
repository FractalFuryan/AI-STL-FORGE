import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models import GenerationParams

logger = logging.getLogger(__name__)

try:
    import blake3

    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False


class STLCache:
    def __init__(
        self,
        cache_dir: str = "cache",
        max_size_mb: int = 500,
        ttl_hours: int = 24,
        cleanup_interval_seconds: int = 3600,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.ttl_seconds = ttl_hours * 3600
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.metadata_file = self.cache_dir / "metadata.json"
        self.stats_file = self.cache_dir / "stats.json"
        self.metadata: dict[str, dict[str, Any]] = self._load_metadata()
        self._stats: dict[str, Any] = self._load_stats()
        self._cleanup_task: asyncio.Task[None] | None = None

    def _load_metadata(self) -> dict[str, dict[str, Any]]:
        if not self.metadata_file.exists():
            return {}

        try:
            return json.loads(self.metadata_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_metadata(self) -> None:
        self.metadata_file.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

    def _load_stats(self) -> dict[str, Any]:
        defaults = {
            "total_hits": 0,
            "total_misses": 0,
            "total_bytes_saved": 0,
            "cleanup_runs": 0,
            "created_at": datetime.now().isoformat(),
        }

        if not self.stats_file.exists():
            return defaults

        try:
            loaded = json.loads(self.stats_file.read_text(encoding="utf-8"))
            defaults.update(loaded)
            return defaults
        except (json.JSONDecodeError, OSError):
            return defaults

    def _save_stats(self) -> None:
        self.stats_file.write_text(json.dumps(self._stats, indent=2), encoding="utf-8")

    def _calculate_size(self) -> int:
        total = 0
        stale_keys = []
        for key in list(self.metadata.keys()):
            path = self.path_for_key(key)
            if path.exists():
                total += path.stat().st_size
            else:
                stale_keys.append(key)

        if stale_keys:
            for key in stale_keys:
                self.metadata.pop(key, None)
            self._save_metadata()

        return total

    def _remove_entry(self, key: str) -> None:
        path = self.path_for_key(key)
        if path.exists():
            path.unlink()
        self.metadata.pop(key, None)

    def _cleanup_expired(self) -> int:
        now = time.time()
        expired = []
        for key, meta in self.metadata.items():
            if now - float(meta.get("timestamp", 0)) > self.ttl_seconds:
                expired.append(key)

        for key in expired:
            self._remove_entry(key)

        if expired:
            self._save_metadata()
            self._stats["cleanup_runs"] += 1
            self._save_stats()
        return len(expired)

    def _cleanup_lru(self, target_size: int) -> int:
        current_size = self._calculate_size()
        if current_size <= target_size:
            return 0

        removed = 0
        entries = sorted(
            self.metadata.items(),
            key=lambda item: float(item[1].get("timestamp", 0)),
        )

        for key, _meta in entries:
            if current_size <= target_size:
                break
            path = self.path_for_key(key)
            size = path.stat().st_size if path.exists() else int(self.metadata.get(key, {}).get("size", 0))
            self._remove_entry(key)
            current_size -= size
            removed += 1

        if removed:
            self._save_metadata()
            self._stats["cleanup_runs"] += 1
            self._save_stats()
        return removed

    async def _periodic_cleanup(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_seconds)
                expired = self._cleanup_expired()
                removed = self._cleanup_lru(self.max_size_bytes)
                if expired or removed:
                    logger.info("Cache cleanup complete (expired=%s lru_removed=%s)", expired, removed)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Cache cleanup task error: %s", exc)
                await asyncio.sleep(60)

    def start_background_cleanup(self) -> None:
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())

    async def stop_background_cleanup(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    def generate_key(self, image_bytes: bytes, params: dict[str, Any], version: str = "2.0") -> str:
        payload = {
            "params": params,
            "mesh_version": "2.1",
            "ai_model": "depth-anything-v2" if params.get("mode") == "ai-depth" else None,
            "api_version": version,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

        if HAS_BLAKE3:
            hasher = blake3.blake3()
            hasher.update(image_bytes)
            hasher.update(encoded)
            return hasher.hexdigest()

        digest = hashlib.sha256(image_bytes + encoded).hexdigest()
        return digest[:32]

    def key_for(self, image_bytes: bytes, params: GenerationParams) -> str:
        return self.generate_key(image_bytes, params.model_dump())

    def path_for_key(self, key: str) -> Path:
        return self.cache_dir / f"{key}.stl"

    def get(self, key: str) -> bytes | None:
        meta = self.metadata.get(key)
        if meta is None:
            self._stats["total_misses"] += 1
            self._save_stats()
            return None

        now = time.time()
        if now - float(meta.get("timestamp", 0)) > self.ttl_seconds:
            self._remove_entry(key)
            self._save_metadata()
            self._stats["total_misses"] += 1
            self._save_stats()
            return None

        path = self.path_for_key(key)
        if not path.exists():
            self.metadata.pop(key, None)
            self._save_metadata()
            self._stats["total_misses"] += 1
            self._save_stats()
            return None

        meta["timestamp"] = now
        meta["hits"] = int(meta.get("hits", 0)) + 1
        self._save_metadata()

        self._stats["total_hits"] += 1
        self._stats["total_bytes_saved"] += int(meta.get("size", 0))
        self._save_stats()
        return path.read_bytes()

    def set(self, key: str, data: bytes) -> None:
        self._cleanup_expired()

        if self._calculate_size() + len(data) > self.max_size_bytes:
            self._cleanup_lru(max(self.max_size_bytes - len(data), 0))

        path = self.path_for_key(key)
        path.write_bytes(data)
        self.metadata[key] = {
            "size": len(data),
            "created_at": datetime.now().isoformat(),
            "timestamp": time.time(),
            "hits": 1,
        }
        self._save_metadata()

    def is_healthy(self) -> bool:
        try:
            probe = self.cache_dir / ".health"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            self._calculate_size()
            return True
        except Exception:
            return False

    def clear(self) -> int:
        removed = len(self.metadata)
        for key in list(self.metadata.keys()):
            self._remove_entry(key)
        self.metadata = {}
        self._save_metadata()
        return removed

    def get_stats(self) -> dict[str, float | int | str | None]:
        timestamps = [float(meta.get("timestamp", 0)) for meta in self.metadata.values()]
        oldest = min(timestamps) if timestamps else None
        newest = max(timestamps) if timestamps else None

        total_requests = int(self._stats["total_hits"]) + int(self._stats["total_misses"])
        hit_rate = (int(self._stats["total_hits"]) / total_requests) if total_requests else 0.0

        return {
            "cache_size_mb": self._calculate_size() / (1024 * 1024),
            "cache_entries": len(self.metadata),
            "max_cache_mb": self.max_size_bytes / (1024 * 1024),
            "ttl_hours": self.ttl_seconds / 3600,
            "total_hits": int(self._stats["total_hits"]),
            "total_misses": int(self._stats["total_misses"]),
            "total_hit_rate": hit_rate,
            "total_bytes_saved_mb": int(self._stats["total_bytes_saved"]) / (1024 * 1024),
            "cleanup_runs": int(self._stats["cleanup_runs"]),
            "created_at": str(self._stats.get("created_at")),
            "oldest_entry_age_hours": ((time.time() - oldest) / 3600) if oldest else None,
            "newest_entry_age_hours": ((time.time() - newest) / 3600) if newest else None,
        }

    def stats(self) -> dict[str, float | int | str | None]:
        return self.get_stats()
