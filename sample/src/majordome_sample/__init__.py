# -*- coding: utf-8 -*-
from typing import Any
from .sample import *


__all__ = sorted([x for x in dir(sample) if not x.startswith("_")])


def __getattr__(name: str) -> Any:
    if name in sample:
        return sample[name]
    raise ImportError(f"No module named {name}")


def __dir__() -> list[str]:
    return __all__