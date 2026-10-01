"""Public API surface tests."""

import importlib.metadata
import inspect

import pytest

import aiofarmad
from aiofarmad import __all__, client, exceptions, models
from aiofarmad import _endpoints as endpoints


def test_all_entries_are_importable() -> None:
    for name in __all__:
        assert hasattr(aiofarmad, name)


def test_all_matches_the_public_namespace() -> None:
    public = {
        name
        for name in dir(aiofarmad)
        if not name.startswith("_") and not inspect.ismodule(getattr(aiofarmad, name))
    }
    assert public == set(__all__) - {"__version__"}
    assert hasattr(aiofarmad, "__version__")


def test_all_is_sorted() -> None:
    assert list(__all__) == sorted(__all__)


def test_reexports_are_identity_imports() -> None:
    for name in __all__:
        if name == "__version__":
            continue
        symbol = getattr(aiofarmad, name)
        sources = (client, endpoints, exceptions, models)
        defining = [module for module in sources if symbol is getattr(module, name, None)]
        assert defining, f"{name} is not an identity re-export of a submodule symbol"


def test_version_falls_back_when_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raising(_name: object) -> str:
        msg = "aiofarmad is not installed"
        raise importlib.metadata.PackageNotFoundError(msg)

    monkeypatch.setattr(importlib.metadata, "version", raising)
    reloaded = importlib.reload(aiofarmad)
    assert reloaded.__version__ == "0.0.0"
    monkeypatch.undo()
    importlib.reload(aiofarmad)
    assert aiofarmad.__version__ != "0.0.0"
