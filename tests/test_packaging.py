"""Packaging tests: version and typing marker."""

import tomllib
from pathlib import Path

import aiofarmad

REPO = Path(__file__).resolve().parent.parent


def test_version_is_defined() -> None:
    assert aiofarmad.__version__ != "0.0.0"
    assert aiofarmad.__version__


def test_pyproject_name_and_python() -> None:
    data = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert data["project"]["name"] == "aiofarmad"
    assert data["project"]["requires-python"] == ">=3.14"
    assert data["project"]["license"] == "MIT"


def test_py_typed_ships_with_the_package() -> None:
    marker = Path(aiofarmad.__file__).parent / "py.typed"
    assert marker.is_file()
