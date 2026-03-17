"""Tests for MemoryTileCache and DiskTileCache — no Qt required."""

import os
import pytest

from src.visualization.tile_cache import MemoryTileCache, DiskTileCache


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24   # minimal fake PNG header


@pytest.fixture
def mem():
    return MemoryTileCache(max_size=4)


@pytest.fixture
def disk_cache(tmp_path):
    return DiskTileCache(str(tmp_path / "tiles"))


# ---------------------------------------------------------------------------
# MemoryTileCache — basic get/put
# ---------------------------------------------------------------------------

class TestMemoryCacheBasic:
    def test_miss_returns_none(self, mem):
        assert mem.get("osm", 5, 10, 20) is None

    def test_put_and_get(self, mem):
        mem.put("osm", 5, 10, 20, FAKE_PNG)
        assert mem.get("osm", 5, 10, 20) == FAKE_PNG

    def test_different_keys_independent(self, mem):
        mem.put("osm", 5, 10, 20, b"tile_A")
        mem.put("osm", 5, 10, 21, b"tile_B")
        assert mem.get("osm", 5, 10, 20) == b"tile_A"
        assert mem.get("osm", 5, 10, 21) == b"tile_B"

    def test_provider_key_is_distinct(self, mem):
        mem.put("osm",   5, 0, 0, b"osm_data")
        mem.put("carto", 5, 0, 0, b"carto_data")
        assert mem.get("osm",   5, 0, 0) == b"osm_data"
        assert mem.get("carto", 5, 0, 0) == b"carto_data"

    def test_overwrite_same_key(self, mem):
        mem.put("osm", 1, 0, 0, b"old")
        mem.put("osm", 1, 0, 0, b"new")
        assert mem.get("osm", 1, 0, 0) == b"new"
        assert len(mem) == 1


# ---------------------------------------------------------------------------
# MemoryTileCache — LRU eviction
# ---------------------------------------------------------------------------

class TestMemoryCacheLRU:
    def test_len_bounded_by_max_size(self, mem):
        for i in range(10):
            mem.put("osm", 0, i, 0, b"data")
        assert len(mem) <= mem.max_size

    def test_oldest_evicted_first(self, mem):
        # Fill to capacity
        for i in range(4):
            mem.put("osm", 0, i, 0, b"data")
        # Access tile 0 to make it recently used
        mem.get("osm", 0, 0, 0)
        # Add one more — should evict tile 1 (oldest)
        mem.put("osm", 0, 4, 0, b"data")
        assert mem.get("osm", 0, 0, 0) is not None  # still present
        assert mem.get("osm", 0, 1, 0) is None       # evicted

    def test_get_refreshes_lru(self, mem):
        # Fill cache (max_size=4): tiles 0,1,2,3 — tile 0 is LRU
        for i in range(4):
            mem.put("osm", 0, i, 0, b"data")
        # Access tile 0 → it becomes MRU; LRU is now tile 1
        mem.get("osm", 0, 0, 0)
        # Add 3 new tiles — evicts tiles 1, 2, 3 (not 0)
        for i in range(4, 7):
            mem.put("osm", 0, i, 0, b"data")
        assert mem.get("osm", 0, 0, 0) is not None  # survived as MRU
        assert mem.get("osm", 0, 1, 0) is None       # evicted


# ---------------------------------------------------------------------------
# MemoryTileCache — invalidate / clear
# ---------------------------------------------------------------------------

class TestMemoryCacheInvalidate:
    def test_invalidate_removes_entry(self, mem):
        mem.put("osm", 3, 2, 1, b"data")
        mem.invalidate("osm", 3, 2, 1)
        assert mem.get("osm", 3, 2, 1) is None

    def test_invalidate_missing_is_noop(self, mem):
        mem.invalidate("osm", 99, 99, 99)   # should not raise

    def test_clear_empties_cache(self, mem):
        for i in range(4):
            mem.put("osm", 0, i, 0, b"data")
        mem.clear()
        assert len(mem) == 0

    def test_clear_allows_new_puts(self, mem):
        mem.put("osm", 0, 0, 0, b"data")
        mem.clear()
        mem.put("osm", 0, 0, 0, b"new_data")
        assert mem.get("osm", 0, 0, 0) == b"new_data"


# ---------------------------------------------------------------------------
# MemoryTileCache — validation
# ---------------------------------------------------------------------------

class TestMemoryCacheValidation:
    def test_empty_data_raises(self, mem):
        with pytest.raises(ValueError):
            mem.put("osm", 0, 0, 0, b"")

    def test_max_size_one(self):
        tiny = MemoryTileCache(max_size=1)
        tiny.put("osm", 0, 0, 0, b"first")
        tiny.put("osm", 0, 0, 1, b"second")
        assert len(tiny) == 1
        assert tiny.get("osm", 0, 0, 1) == b"second"
        assert tiny.get("osm", 0, 0, 0) is None

    def test_max_size_zero_raises(self):
        with pytest.raises(ValueError):
            MemoryTileCache(max_size=0)


# ---------------------------------------------------------------------------
# DiskTileCache — basic get/put
# ---------------------------------------------------------------------------

class TestDiskCacheBasic:
    def test_miss_returns_none(self, disk_cache):
        assert disk_cache.get("osm", 5, 10, 20) is None

    def test_put_and_get(self, disk_cache):
        disk_cache.put("osm", 5, 10, 20, FAKE_PNG)
        assert disk_cache.get("osm", 5, 10, 20) == FAKE_PNG

    def test_put_creates_file(self, disk_cache, tmp_path):
        disk_cache.put("osm", 3, 1, 2, b"abc")
        assert disk_cache.exists("osm", 3, 1, 2)

    def test_different_providers_separate(self, disk_cache):
        disk_cache.put("osm",   7, 0, 0, b"osm_tile")
        disk_cache.put("carto", 7, 0, 0, b"carto_tile")
        assert disk_cache.get("osm",   7, 0, 0) == b"osm_tile"
        assert disk_cache.get("carto", 7, 0, 0) == b"carto_tile"

    def test_overwrite(self, disk_cache):
        disk_cache.put("osm", 1, 0, 0, b"old")
        disk_cache.put("osm", 1, 0, 0, b"new")
        assert disk_cache.get("osm", 1, 0, 0) == b"new"

    def test_exists_false_before_put(self, disk_cache):
        assert not disk_cache.exists("osm", 0, 0, 0)

    def test_exists_true_after_put(self, disk_cache):
        disk_cache.put("osm", 0, 0, 0, b"data")
        assert disk_cache.exists("osm", 0, 0, 0)


# ---------------------------------------------------------------------------
# DiskTileCache — atomic write (no leftover .tmp)
# ---------------------------------------------------------------------------

class TestDiskCacheAtomic:
    def test_no_tmp_file_left_after_put(self, disk_cache, tmp_path):
        disk_cache.put("osm", 2, 3, 4, b"data")
        # Walk the tile directory looking for any .tmp files
        tile_root = str(tmp_path / "tiles")
        tmp_files = []
        for root, _dirs, files in os.walk(tile_root):
            for f in files:
                if f.endswith(".tmp"):
                    tmp_files.append(f)
        assert tmp_files == []


# ---------------------------------------------------------------------------
# DiskTileCache — invalidate / clear
# ---------------------------------------------------------------------------

class TestDiskCacheInvalidate:
    def test_invalidate_removes_file(self, disk_cache):
        disk_cache.put("osm", 4, 1, 1, b"data")
        disk_cache.invalidate("osm", 4, 1, 1)
        assert not disk_cache.exists("osm", 4, 1, 1)
        assert disk_cache.get("osm", 4, 1, 1) is None

    def test_invalidate_missing_is_noop(self, disk_cache):
        disk_cache.invalidate("osm", 99, 99, 99)  # should not raise

    def test_clear_removes_all_files(self, disk_cache, tmp_path):
        for z in range(3):
            disk_cache.put("osm", z, 0, 0, b"data")
        disk_cache.clear()
        tile_root = str(tmp_path / "tiles")
        assert not os.path.isdir(tile_root)

    def test_get_after_clear_returns_none(self, disk_cache):
        disk_cache.put("osm", 1, 0, 0, b"data")
        disk_cache.clear()
        assert disk_cache.get("osm", 1, 0, 0) is None


# ---------------------------------------------------------------------------
# DiskTileCache — validation
# ---------------------------------------------------------------------------

class TestDiskCacheValidation:
    def test_empty_data_raises(self, disk_cache):
        with pytest.raises(ValueError):
            disk_cache.put("osm", 0, 0, 0, b"")


# ---------------------------------------------------------------------------
# DiskTileCache — long provider URL slug
# ---------------------------------------------------------------------------

class TestDiskCacheProviderSlug:
    def test_long_provider_url_stored_and_retrieved(self, disk_cache):
        long_url = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        disk_cache.put(long_url, 5, 10, 20, b"tile_data")
        assert disk_cache.get(long_url, 5, 10, 20) == b"tile_data"

    def test_different_long_urls_distinct(self, disk_cache):
        url_a = "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png"
        url_b = "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png"
        disk_cache.put(url_a, 5, 0, 0, b"a_data")
        disk_cache.put(url_b, 5, 0, 0, b"b_data")
        assert disk_cache.get(url_a, 5, 0, 0) == b"a_data"
        assert disk_cache.get(url_b, 5, 0, 0) == b"b_data"
