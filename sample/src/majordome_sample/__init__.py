# -*- coding: utf-8 -*-
from typing import Any
from . import sample as ext


__all__ = sorted([x for x in dir(ext) if not x.startswith("_")])


def __getattr__(name: str) -> Any:
    try:
        return getattr(ext, name)
    except AttributeError:
        raise AttributeError(f"Name '{name}' not found in scope.")


def __dir__() -> list[str]:
    return __all__