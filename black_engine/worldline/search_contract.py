from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator


@contextmanager
def managed_search(begin: Callable[..., Any], release: Callable[[Any], None], *args: Any, **kwargs: Any) -> Iterator[Any]:
    handle = begin(*args, **kwargs)
    try:
        yield handle
    finally:
        release(handle)
