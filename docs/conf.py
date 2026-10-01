"""Sphinx configuration for the aiofarmad documentation."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

project = "aiofarmad"
author = "Daan Vervacke"
copyright = "2026, Daan Vervacke"  # noqa: A001
try:
    release = _version("aiofarmad")
except PackageNotFoundError:  # pragma: no cover
    release = "0.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

html_theme = "furo"
