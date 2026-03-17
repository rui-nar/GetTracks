"""Tile caching — in-memory LRU and disk-backed storage.

Both caches store raw PNG bytes so they remain Qt-free and fully testable
without a QApplication instance.
"""

import os
import hashlib
from collections import OrderedDict
from typing import Optional


class MemoryTileCache:
    """LRU in-memory cache for tile bytes.

    Args:
        max_size: Maximum number of tiles to keep in memory (default 256).
    """

    def __init__(self, max_size: int = 256) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self._max_size = max_size
        self._data: OrderedDict[tuple, bytes] = OrderedDict()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, provider: str, z: int, tx: int, ty: int) -> Optional[bytes]:
        """Return cached bytes or None if not present."""
        key = (provider, z, tx, ty)
        if key not in self._data:
            return None
        # Move to end (most-recently used)
        self._data.move_to_end(key)
        return self._data[key]

    def put(self, provider: str, z: int, tx: int, ty: int, data: bytes) -> None:
        """Store tile bytes, evicting the LRU entry if at capacity."""
        if not data:
            raise ValueError("tile data must not be empty")
        key = (provider, z, tx, ty)
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = data
        if len(self._data) > self._max_size:
            self._data.popitem(last=False)  # evict LRU (first item)

    def invalidate(self, provider: str, z: int, tx: int, ty: int) -> None:
        """Remove a single tile entry (no-op if not present)."""
        self._data.pop((provider, z, tx, ty), None)

    def clear(self) -> None:
        """Evict all entries."""
        self._data.clear()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._data)

    @property
    def max_size(self) -> int:
        return self._max_size


class DiskTileCache:
    """Persistent tile cache stored on disk.

    Layout::

        <cache_dir>/<provider_slug>/<z>/<tx>/<ty>.png

    Writes are atomic: data is written to a ``.tmp`` sibling file then
    renamed so a crash mid-write never leaves a corrupt tile on disk.

    Args:
        cache_dir: Root directory for cached tiles.
    """

    _EXT = ".png"

    def __init__(self, cache_dir: str) -> None:
        self._root = cache_dir

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, provider: str, z: int, tx: int, ty: int) -> Optional[bytes]:
        """Return bytes from disk or None if not cached."""
        path = self._tile_path(provider, z, tx, ty)
        try:
            with open(path, "rb") as fh:
                return fh.read()
        except FileNotFoundError:
            return None

    def put(self, provider: str, z: int, tx: int, ty: int, data: bytes) -> None:
        """Atomically write tile bytes to disk."""
        if not data:
            raise ValueError("tile data must not be empty")
        path = self._tile_path(provider, z, tx, ty)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)

    def invalidate(self, provider: str, z: int, tx: int, ty: int) -> None:
        """Delete a cached tile file (no-op if not present)."""
        path = self._tile_path(provider, z, tx, ty)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    def clear(self) -> None:
        """Delete all cached tile files under the root directory."""
        import shutil
        if os.path.isdir(self._root):
            shutil.rmtree(self._root)

    def exists(self, provider: str, z: int, tx: int, ty: int) -> bool:
        """Return True if the tile file is present on disk."""
        return os.path.isfile(self._tile_path(provider, z, tx, ty))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _provider_slug(self, provider: str) -> str:
        """Convert an arbitrary provider URL/name to a safe directory name."""
        slug = provider.replace("://", "_").replace("/", "_").replace(".", "_")
        # Truncate + append short hash to avoid path-length issues on Windows
        if len(slug) > 40:
            h = hashlib.md5(provider.encode()).hexdigest()[:8]
            slug = slug[:32] + "_" + h
        return slug

    def _tile_path(self, provider: str, z: int, tx: int, ty: int) -> str:
        return os.path.join(
            self._root,
            self._provider_slug(provider),
            str(z),
            str(tx),
            str(ty) + self._EXT,
        )
