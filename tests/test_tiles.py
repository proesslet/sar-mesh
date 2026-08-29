"""Reading MBTiles packs, and choosing which one is served."""

import sqlite3
from pathlib import Path

import pytest

from sarmesh.web.tiles import BasemapLibrary, TileStore, read_metadata


def write_pack(path: Path, tiles: dict[tuple[int, int, int], bytes]) -> Path:
    """A minimal MBTiles file. Keys are (zoom, column, row) in TMS order."""
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
    connection.execute(
        """
        CREATE TABLE tiles (
            zoom_level INTEGER, tile_column INTEGER,
            tile_row INTEGER, tile_data BLOB
        )
        """
    )
    connection.execute("INSERT INTO metadata VALUES ('name', 'Test Pack')")
    connection.execute("INSERT INTO metadata VALUES ('format', 'png')")
    connection.executemany(
        "INSERT INTO tiles VALUES (?, ?, ?, ?)",
        [(z, x, y, data) for (z, x, y), data in tiles.items()],
    )
    connection.commit()
    connection.close()

    return path


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    # At zoom 2 the TMS row for XYZ y=1 is (2**2 - 1) - 1 = 2.
    return write_pack(tmp_path / "terrain.mbtiles", {(2, 3, 2): b"tile-bytes"})


########################## TileStore ##########################


def test_get_tile_flips_y_from_xyz_to_tms(pack: Path) -> None:
    """MBTiles counts rows from the bottom, Leaflet requests from the top.
    Getting this wrong renders a map that is subtly, vertically mirrored."""
    store = TileStore(pack)

    try:
        assert store.get_tile(2, 3, 1) == b"tile-bytes"
        assert store.get_tile(2, 3, 2) is None
    finally:
        store.close()


def test_get_tile_returns_none_for_a_missing_tile(pack: Path) -> None:
    store = TileStore(pack)

    try:
        assert store.get_tile(5, 0, 0) is None
    finally:
        store.close()


def test_get_tile_after_close_does_not_resurrect_the_store(pack: Path) -> None:
    """A tile request can race a basemap swap; reconnecting here would quietly
    keep serving a pack the library has already discarded."""
    store = TileStore(pack)
    store.close()

    assert store.get_tile(2, 3, 1) is None
    assert store.metadata() == {}


def test_metadata_is_read_as_a_mapping(pack: Path) -> None:
    store = TileStore(pack)

    try:
        assert store.metadata()["name"] == "Test Pack"
    finally:
        store.close()


def test_read_metadata_of_a_non_mbtiles_file_is_none(tmp_path: Path) -> None:
    """A truncated download must not make listing the packs fail."""
    corrupt = tmp_path / "corrupt.mbtiles"
    corrupt.write_bytes(b"not a database")

    assert read_metadata(corrupt) is None


########################## BasemapLibrary ##########################


def test_packs_lists_the_directory(tmp_path: Path, pack: Path) -> None:
    library = BasemapLibrary(tmp_path)

    try:
        assert [p.name for p in library.packs()] == ["terrain.mbtiles"]
    finally:
        library.close()


def test_a_corrupt_pack_is_still_listed(tmp_path: Path) -> None:
    """A bad download is something the operator needs to see, not something
    that should silently vanish from the list."""
    (tmp_path / "corrupt.mbtiles").write_bytes(b"not a database")
    library = BasemapLibrary(tmp_path)

    try:
        [found] = library.packs()
        assert found.name == "corrupt.mbtiles"
        assert found.metadata is None
    finally:
        library.close()


def test_a_partial_download_is_not_listed(tmp_path: Path, pack: Path) -> None:
    write_pack(tmp_path / "half.mbtiles.partial", {})
    library = BasemapLibrary(tmp_path)

    try:
        assert [p.name for p in library.packs()] == ["terrain.mbtiles"]
    finally:
        library.close()


def test_a_pinned_pack_outside_the_directory_is_listed(
    tmp_path: Path, pack: Path
) -> None:
    library = BasemapLibrary(tmp_path / "empty", pinned=pack)

    try:
        assert [p.name for p in library.packs()] == ["terrain.mbtiles"]
    finally:
        library.close()


def test_select_serves_the_named_pack(tmp_path: Path, pack: Path) -> None:
    library = BasemapLibrary(tmp_path)

    try:
        library.select("terrain.mbtiles")

        assert library.active_name == "terrain.mbtiles"
        assert library.store is not None
        assert library.store.get_tile(2, 3, 1) == b"tile-bytes"
    finally:
        library.close()


def test_select_an_unknown_pack_raises(tmp_path: Path) -> None:
    library = BasemapLibrary(tmp_path)

    try:
        with pytest.raises(KeyError):
            library.select("missing.mbtiles")
    finally:
        library.close()


def test_select_none_turns_the_basemap_off(tmp_path: Path, pack: Path) -> None:
    library = BasemapLibrary(tmp_path)

    try:
        library.select("terrain.mbtiles")
        library.select(None)

        assert library.active_name is None
        assert library.store is None
    finally:
        library.close()


def test_revision_changes_on_every_swap(tmp_path: Path, pack: Path) -> None:
    """Tile URLs are identical between packs; without this the browser keeps
    serving the previous pack's tiles from cache."""
    write_pack(tmp_path / "other.mbtiles", {})
    library = BasemapLibrary(tmp_path)

    try:
        start = library.revision
        library.select("terrain.mbtiles")
        library.select("other.mbtiles")

        assert library.revision == start + 2
    finally:
        library.close()


def test_reselecting_the_same_pack_does_not_bump_the_revision(
    tmp_path: Path, pack: Path
) -> None:
    library = BasemapLibrary(tmp_path)

    try:
        library.select("terrain.mbtiles")
        revision = library.revision
        library.select("terrain.mbtiles")

        assert library.revision == revision
    finally:
        library.close()


def test_select_default_prefers_the_pinned_pack(tmp_path: Path, pack: Path) -> None:
    other = write_pack(tmp_path / "other.mbtiles", {})
    library = BasemapLibrary(tmp_path, pinned=pack)

    try:
        library.select_default(saved=other.name)

        assert library.active_name == "terrain.mbtiles"
    finally:
        library.close()


def test_select_default_restores_the_saved_pack(tmp_path: Path, pack: Path) -> None:
    library = BasemapLibrary(tmp_path)

    try:
        library.select_default(saved="terrain.mbtiles")

        assert library.active_name == "terrain.mbtiles"
    finally:
        library.close()


def test_select_default_tolerates_a_deleted_pack(tmp_path: Path) -> None:
    """A pack removed between runs must not stop the app from starting."""
    library = BasemapLibrary(tmp_path)

    try:
        library.select_default(saved="gone.mbtiles")

        assert library.active_name is None
    finally:
        library.close()


########################## Import paths ##########################


def test_import_path_is_inside_the_library(tmp_path: Path) -> None:
    library = BasemapLibrary(tmp_path)

    assert library.import_path("terrain.mbtiles") == (
        tmp_path.resolve() / "terrain.mbtiles"
    )


@pytest.mark.parametrize(
    "name",
    [
        "../escape.mbtiles",
        "../../etc/escape.mbtiles",
        "nested/terrain.mbtiles",
        "/absolute/terrain.mbtiles",
        ".hidden.mbtiles",
        ".mbtiles",
        "terrain.sqlite",
        "terrain",
        "",
    ],
    ids=repr,
)
def test_import_path_rejects_anything_but_a_plain_filename(
    tmp_path: Path, name: str
) -> None:
    """An uploaded name reaching outside the library must never produce a
    writable path."""
    library = BasemapLibrary(tmp_path)

    with pytest.raises(ValueError):
        library.import_path(name)
