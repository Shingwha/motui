"""The packaging contract: one version, one distribution, one license.

The exact release number lives in ``pyproject.toml``; these tests prove the
module, the installed metadata and the source fallback all read it from
there.  They do not pin the number itself -- a release must not require a
test edit.
"""

from __future__ import annotations

import importlib.metadata
import re
import tomllib
from pathlib import Path

import motui

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
INIT = ROOT / "src" / "motui" / "__init__.py"


def _pyproject() -> dict:
    with PYPROJECT.open("rb") as source:
        return tomllib.load(source)


def test_the_version_is_one_number_across_pyproject_metadata_and_fallback():
    project = _pyproject()["project"]
    version = project["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[a-z]+\d+)?", version), version
    assert motui.__version__ == version
    try:
        installed = importlib.metadata.version("motui")
    except importlib.metadata.PackageNotFoundError:
        installed = version  # a pure source checkout
    assert installed == version

    source = INIT.read_text(encoding="utf-8")
    fallback = re.search(
        r'except PackageNotFoundError:[^\n]*\n\s*__version__\s*=\s*"([^"]+)"',
        source,
    )
    assert fallback is not None, "the source version fallback is gone"
    assert fallback.group(1) == version


def test_the_distribution_metadata_is_the_release_contract():
    project = _pyproject()["project"]
    assert project["name"] == "motui"
    assert project["license"] == "MIT"
    assert (ROOT / "LICENSE").is_file()
    assert (ROOT / project["readme"]).is_file()
    assert project["requires-python"] == ">= 3.12"
    sdist = _pyproject()["tool"]["hatch"]["build"]["targets"]["sdist"]
    assert sdist["exclude"] == ["/specs"]
