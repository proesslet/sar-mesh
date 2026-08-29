"""Where SARMesh decides to keep its data.

A double-clicked bundle inherits a useless working directory, so getting this
wrong means the incident database is written somewhere nobody can find.
"""

from pathlib import Path

import pytest

from sarmesh.storage import paths


def test_database_defaults_to_the_working_directory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SARMESH_DB", raising=False)
    monkeypatch.setattr(paths, "is_frozen", lambda: False)

    assert paths.default_database_path() == Path("sarmesh.db")


def test_a_frozen_build_uses_the_user_data_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SARMESH_DB", raising=False)
    monkeypatch.setattr(paths, "is_frozen", lambda: True)

    assert paths.default_database_path() != Path("sarmesh.db")
    assert paths.default_database_path().is_absolute()


def test_sarmesh_db_overrides_everything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """This is how a build is pointed at a database on removable media."""
    monkeypatch.setenv("SARMESH_DB", str(tmp_path / "incident.db"))
    monkeypatch.setattr(paths, "is_frozen", lambda: True)

    assert paths.default_database_path() == tmp_path / "incident.db"


def test_sarmesh_db_expands_a_home_relative_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SARMESH_DB", "~/incident.db")

    assert paths.default_database_path() == Path.home() / "incident.db"


def test_an_empty_override_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SARMESH_DB", "")
    monkeypatch.setattr(paths, "is_frozen", lambda: False)

    assert paths.default_database_path() == Path("sarmesh.db")


@pytest.mark.skipif(
    paths.sys.platform == "darwin", reason="macOS has no environment override"
)
def test_a_relative_data_dir_variable_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The XDG spec says to ignore a relative path, and the same guard stops a
    malformed LOCALAPPDATA writing the database into the working directory."""
    variable = "LOCALAPPDATA" if paths.sys.platform == "win32" else "XDG_DATA_HOME"
    monkeypatch.setenv(variable, "relative/path")

    assert paths.user_data_dir().is_absolute()


def test_basemap_dir_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Packs are gigabytes; a deployment points at removable media without
    moving the database too."""
    monkeypatch.setenv("SARMESH_BASEMAP_DIR", str(tmp_path / "packs"))

    assert paths.basemap_dir() == tmp_path / "packs"
