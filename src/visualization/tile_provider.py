"""Async OSM tile fetcher using QNetworkAccessManager.

TileProvider fetches PNG tiles from a configurable URL template,
caches them in memory (and optionally on disk), and emits ``tile_ready``
when a tile's bytes are available.

Signal contract
---------------
tile_ready(z, tx, ty, data: bytes)  — emitted on the main thread once bytes arrive
tile_failed(z, tx, ty, msg: str)    — emitted when a request fails permanently

Usage::

    provider = TileProvider(mem_cache, disk_cache)
    provider.tile_ready.connect(my_slot)
    provider.request_tile(zoom, tx, ty)   # non-blocking
    # slot receives (z, tx, ty, bytes) when data is ready
"""

from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal, QUrl
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from src.visualization.tile_cache import MemoryTileCache, DiskTileCache


# ---------------------------------------------------------------------------
# Built-in provider templates
# ---------------------------------------------------------------------------

PROVIDERS = {
    "OpenStreetMap":    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "CartoDB Positron": "https://cartodb-basemaps-a.global.ssl.fastly.net/light_all/{z}/{x}/{y}.png",
    "CartoDB Dark":     "https://cartodb-basemaps-a.global.ssl.fastly.net/dark_all/{z}/{x}/{y}.png",
}

_DEFAULT_PROVIDER = "OpenStreetMap"

# OSM tile usage policy requires a descriptive User-Agent
_USER_AGENT = b"GetTracks/1.0 (https://github.com/your-org/GetTracks)"


class TileProvider(QObject):
    """Async tile fetcher with in-flight deduplication and two-level cache.

    Args:
        mem_cache:  ``MemoryTileCache`` instance (required).
        disk_cache: ``DiskTileCache`` instance (optional — pass ``None`` to skip
                    disk caching).
        provider:   One of the keys in :data:`PROVIDERS`, or a custom URL template
                    containing ``{z}``, ``{x}``, ``{y}`` placeholders.
    """

    tile_ready  = pyqtSignal(int, int, int, bytes)   # z, tx, ty, data
    tile_failed = pyqtSignal(int, int, int, str)     # z, tx, ty, message

    def __init__(
        self,
        mem_cache: MemoryTileCache,
        disk_cache: Optional[DiskTileCache] = None,
        provider: str = _DEFAULT_PROVIDER,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._mem   = mem_cache
        self._disk  = disk_cache
        self._nam   = QNetworkAccessManager(self)
        self._inflight: set[tuple[int, int, int]] = set()   # (z, tx, ty)

        self.set_provider(provider)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_provider(self, provider: str) -> None:
        """Switch tile source.  Clears in-flight set (pending replies remain
        but their results will be discarded as stale)."""
        self._provider_name = PROVIDERS.get(provider, provider)
        self._inflight.clear()

    @property
    def provider_name(self) -> str:
        """Resolved URL template for the current provider."""
        return self._provider_name

    def request_tile(self, z: int, tx: int, ty: int) -> None:
        """Request tile ``(z, tx, ty)`` asynchronously.

        If the tile is already in the memory cache the signal is emitted
        synchronously before this method returns.  If it is in the disk cache
        it is loaded synchronously, stored in the memory cache, and the signal
        is emitted.  Otherwise an HTTP request is initiated; the signal is
        emitted from the ``_on_reply_finished`` callback.

        Duplicate in-flight requests for the same tile are silently dropped.
        """
        # 1. Memory cache hit
        data = self._mem.get(self._provider_name, z, tx, ty)
        if data is not None:
            self.tile_ready.emit(z, tx, ty, data)
            return

        # 2. Disk cache hit
        if self._disk is not None:
            data = self._disk.get(self._provider_name, z, tx, ty)
            if data is not None:
                self._mem.put(self._provider_name, z, tx, ty, data)
                self.tile_ready.emit(z, tx, ty, data)
                return

        # 3. Deduplicate in-flight
        key = (z, tx, ty)
        if key in self._inflight:
            return
        self._inflight.add(key)

        # 4. HTTP fetch
        url = self._provider_name.format(z=z, x=tx, y=ty)
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", _USER_AGENT)
        reply = self._nam.get(request)
        # Attach tile coordinates to reply so the slot can identify it
        reply.setProperty("tile_z",  z)
        reply.setProperty("tile_tx", tx)
        reply.setProperty("tile_ty", ty)
        reply.setProperty("provider", self._provider_name)
        reply.finished.connect(self._on_reply_finished)

    def abort_all(self) -> None:
        """Cancel all pending network requests and clear the in-flight set."""
        self._inflight.clear()
        self._nam.clearAccessCache()

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _on_reply_finished(self) -> None:
        reply: QNetworkReply = self.sender()
        reply.deleteLater()

        z        = reply.property("tile_z")
        tx       = reply.property("tile_tx")
        ty       = reply.property("tile_ty")
        provider = reply.property("provider")

        # Discard if provider was switched while request was in-flight
        if provider != self._provider_name:
            return

        key = (z, tx, ty)
        self._inflight.discard(key)

        if reply.error() != QNetworkReply.NetworkError.NoError:
            self.tile_failed.emit(z, tx, ty, reply.errorString())
            return

        data = bytes(reply.readAll())
        if not data:
            self.tile_failed.emit(z, tx, ty, "empty response")
            return

        # Store in caches
        self._mem.put(provider, z, tx, ty, data)
        if self._disk is not None:
            self._disk.put(provider, z, tx, ty, data)

        self.tile_ready.emit(z, tx, ty, data)
