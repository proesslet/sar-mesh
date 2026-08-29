"""Tile maths and URL validation for offline basemap downloads.

The download itself is not exercised: it fetches from a third-party server, and
what is worth pinning down is everything that runs before the first request.
"""

import pytest

from sarmesh.services.basemaps import (
    MAX_LATITUDE,
    Bounds,
    check_bulk_allowed,
    count_tiles,
    deepest_zoom_within,
    expand_template,
    tile_bounds,
    validate_template,
)

TEMPLATE = "https://tiles.example.com/{z}/{x}/{y}.png"


########################## Bounds ##########################


def test_normalised_orders_the_corners() -> None:
    """The operator can drag a box in any direction."""
    bounds = Bounds(west=10.0, south=50.0, east=-10.0, north=40.0).normalised()

    assert (bounds.west, bounds.east) == (-10.0, 10.0)
    assert (bounds.south, bounds.north) == (40.0, 50.0)


def test_normalised_clamps_to_the_mercator_cutoff() -> None:
    """Web Mercator cannot represent the poles."""
    bounds = Bounds(west=-1.0, south=-90.0, east=1.0, north=90.0).normalised()

    assert bounds.south == -MAX_LATITUDE
    assert bounds.north == MAX_LATITUDE


########################## Tile maths ##########################


def test_the_whole_world_is_one_tile_at_zoom_zero() -> None:
    world = Bounds(west=-180.0, south=-85.0, east=180.0, north=85.0).normalised()

    assert tile_bounds(world, 0) == (0, 0, 0, 0)
    assert count_tiles(world, 0, 0) == 1


def test_tile_indices_stay_in_range_at_the_antimeridian() -> None:
    """x_of(180) computes exactly 2**zoom, one past the last valid index."""
    world = Bounds(west=-180.0, south=-85.0, east=180.0, north=85.0).normalised()

    x0, y0, x1, y1 = tile_bounds(world, 4)

    assert (x0, x1) == (0, 15)
    assert (y0, y1) == (0, 15)


def test_north_maps_to_the_smaller_y() -> None:
    """y counts down from the north; a flip here inverts every download."""
    bounds = Bounds(west=-1.0, south=40.0, east=1.0, north=50.0)

    _, y0, _, y1 = tile_bounds(bounds, 8)

    assert y0 < y1


def test_count_tiles_sums_every_zoom_level() -> None:
    world = Bounds(west=-180.0, south=-85.0, east=180.0, north=85.0).normalised()

    # 1 + 4 + 16 tiles for zooms 0, 1 and 2.
    assert count_tiles(world, 0, 2) == 21


def test_deepest_zoom_within_a_budget() -> None:
    """ "Too many tiles, lower the zoom" leaves the operator guessing by how
    much, and every guess costs another round trip."""
    world = Bounds(west=-180.0, south=-85.0, east=180.0, north=85.0).normalised()

    assert deepest_zoom_within(world, min_zoom=0, limit=21) == 2
    assert deepest_zoom_within(world, min_zoom=0, limit=20) == 1


def test_deepest_zoom_is_none_when_even_the_minimum_does_not_fit() -> None:
    world = Bounds(west=-180.0, south=-85.0, east=180.0, north=85.0).normalised()

    assert deepest_zoom_within(world, min_zoom=8, limit=10) is None


########################## URL templates ##########################


def test_expand_substitutes_the_coordinates() -> None:
    assert expand_template(TEMPLATE, 5, 1, 2) == "https://tiles.example.com/5/1/2.png"


def test_expand_drops_the_retina_placeholder() -> None:
    """SARMesh stores plain tiles, so {r} resolves to nothing."""
    assert expand_template("https://x/{z}/{x}/{y}{r}.png", 1, 1, 1).endswith("1.png")


def test_expand_spreads_subdomains_deterministically() -> None:
    """The same tile always comes from the same host, so it stays cacheable."""
    template = "https://{s}.example.com/{z}/{x}/{y}.png"

    assert expand_template(template, 0, 0, 0) == expand_template(template, 0, 0, 0)
    assert {expand_template(template, 0, x, 0).split(".")[0] for x in range(3)} == {
        "https://a",
        "https://b",
        "https://c",
    }


def test_a_valid_template_passes() -> None:
    validate_template(TEMPLATE)


@pytest.mark.parametrize(
    "template",
    [
        pytest.param("https://x/{x}/{y}.png", id="no {z}"),
        pytest.param("https://x/{z}/{y}.png", id="no {x}"),
        pytest.param("https://x/{z}/{x}.png", id="no {y}"),
    ],
)
def test_a_template_missing_a_coordinate_is_rejected(template: str) -> None:
    with pytest.raises(ValueError, match="must contain"):
        validate_template(template)


@pytest.mark.parametrize(
    "template",
    [
        pytest.param("file:///etc/{z}/{x}/{y}", id="file"),
        pytest.param("ftp://x/{z}/{x}/{y}.png", id="ftp"),
        pytest.param("/local/{z}/{x}/{y}.png", id="no scheme"),
    ],
)
def test_a_non_http_template_is_rejected(template: str) -> None:
    """Otherwise the URL field is a way to read the local disk."""
    with pytest.raises(ValueError, match="http"):
        validate_template(template)


def test_an_unfillable_placeholder_is_rejected() -> None:
    """Sent literally it would fail every single tile, and the operator would
    find out at the end of a long download."""
    with pytest.raises(ValueError, match="apikey"):
        validate_template("https://x/{z}/{x}/{y}.png?key={apikey}")


@pytest.mark.parametrize(
    "host",
    ["tile.openstreetmap.org", "a.tile.openstreetmap.org", "tile.osm.org"],
)
def test_bulk_download_is_refused_for_hosts_that_forbid_it(host: str) -> None:
    """The consequence lands on the team as a banned IP at the worst moment."""
    with pytest.raises(ValueError, match="bulk"):
        check_bulk_allowed(f"https://{host}/{{z}}/{{x}}/{{y}}.png")


def test_bulk_download_is_refused_behind_a_subdomain_placeholder() -> None:
    """{s} must not be able to hide the real hostname."""
    with pytest.raises(ValueError, match="bulk"):
        check_bulk_allowed("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")


def test_bulk_download_is_allowed_elsewhere() -> None:
    check_bulk_allowed(TEMPLATE)


def test_a_lookalike_host_is_not_blocked() -> None:
    """The check is host-suffix based, not substring based."""
    check_bulk_allowed("https://tile.openstreetmap.org.evil.com/{z}/{x}/{y}.png")
