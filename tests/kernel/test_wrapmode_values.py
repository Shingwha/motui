"""WrapMode value tests: the five modes are a stable public vocabulary."""

from __future__ import annotations

import pytest

from motui.kernel.text import WrapMode


def test_five_modes_with_stable_string_values() -> None:
    assert {mode.name: mode.value for mode in WrapMode} == {
        "WORD": "word",
        "CHAR": "char",
        "ELLIPSIS": "ellipsis",
        "CLIP": "clip",
        "OVERFLOW": "overflow",
    }


def test_lookup_returns_the_member_itself() -> None:
    assert WrapMode("word") is WrapMode.WORD
    assert WrapMode("overflow") is WrapMode.OVERFLOW


def test_unknown_value_raises() -> None:
    with pytest.raises(ValueError):
        WrapMode("wrap")
