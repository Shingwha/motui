"""The packaging contract: the version and the distribution's metadata agree.

``motui.__version__`` reads the installed metadata, with the source string
only as a never-installed checkout's fallback; ``pyproject.toml`` is the one
place the number is written, and the PyPI-facing metadata -- the MIT license
expression and its file, the readme, the classifiers and the sdist's
``specs`` exclusion -- is pinned here so a release cannot drift away from it.
"""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path
from typing import Any

import motui

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
LICENSE = ROOT / "LICENSE"

#: The classifiers the first release is published under, verbatim.
CLASSIFIERS = [
    "Development Status :: 5 - Production/Stable",
    "Environment :: Console",
    "Intended Audience :: Developers",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3 :: Only",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Software Development :: Libraries :: Python Modules",
    "Topic :: Terminals",
]


def _pyproject() -> dict[str, Any]:
    """The repository's parsed ``pyproject.toml``."""
    with PYPROJECT.open("rb") as source:
        return tomllib.load(source)


def _project() -> dict[str, Any]:
    """Its ``[project]`` table."""
    return _pyproject()["project"]


def test_the_version_is_1_1_0():
    """One number, bumped once per release: this release is 1.1.0."""
    assert motui.__version__ == "1.1.0"


def test_the_version_matches_pyproject_and_the_installed_metadata():
    """One number in one place: the module, the metadata and pyproject agree."""
    assert motui.__version__ == importlib.metadata.version("motui")
    assert motui.__version__ == _project()["version"]


def test_the_version_stays_out_of_the_curated_root_surface():
    """``__version__`` is packaging metadata, not one of the 33 names."""
    assert "__version__" not in motui.__all__


def test_the_distribution_names_and_urls_are_declared():
    """The name is the import name, and the three URLs answer."""
    project = _project()
    assert project["name"] == "motui"
    urls = project["urls"]
    assert set(urls) == {"Homepage", "Repository", "Issues"}
    assert all(url.startswith("https://") for url in urls.values())


def test_the_license_is_the_mit_expression_with_its_file():
    """PEP 639: the expression declares the terms and LICENSE carries them."""
    project = _project()
    assert project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert LICENSE.is_file()
    text = LICENSE.read_text(encoding="utf-8")
    assert text.startswith("MIT License\n")
    assert "Copyright (c) 2026 Shingwha" in text


def test_no_license_classifier_duplicates_the_expression():
    """The retired ``License ::`` classifiers stay out of pyproject."""
    classifiers = _project()["classifiers"]
    assert classifiers
    assert [c for c in classifiers if c.startswith("License ::")] == []


def test_the_readme_and_the_classifiers_are_declared():
    """The long description and the first release's classifier set."""
    project = _project()
    assert project["readme"] == "README.md"
    assert (ROOT / project["readme"]).is_file()
    assert project["classifiers"] == CLASSIFIERS


def test_the_sdist_excludes_the_process_specs():
    """D8: the spec archive stays in the repository, out of every sdist."""
    targets = _pyproject()["tool"]["hatch"]["build"]["targets"]
    assert targets["sdist"]["exclude"] == ["/specs"]
