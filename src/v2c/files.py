"""Reading input files, plain or gzip-compressed, decided by content.

latin-1 maps every byte to one character, so a stray non-ASCII byte reaches the
lexer and is reported with its location instead of failing the decode with no
location at all.
"""

from __future__ import annotations

import gzip
import zlib
from collections.abc import Iterator
from typing import TextIO

from .errors import Location, V2CError

_GZIP_MAGIC = b"\x1f\x8b"
_GZIP_ERRORS = (EOFError, zlib.error, gzip.BadGzipFile)


def read_text(path: str) -> str:
    with _open(path) as f:
        try:
            return f.read()
        except _GZIP_ERRORS as exc:
            raise _corrupt(path, exc) from None


def iter_lines(path: str) -> Iterator[str]:
    with _open(path) as f:
        try:
            yield from f
        except _GZIP_ERRORS as exc:
            raise _corrupt(path, exc) from None


def _open(path: str) -> TextIO:
    with open(path, "rb") as f:
        compressed = f.read(2) == _GZIP_MAGIC
    if compressed:
        return gzip.open(path, "rt", encoding="latin-1")
    return open(path, encoding="latin-1")


def _corrupt(path: str, exc: Exception) -> V2CError:
    return V2CError(f"corrupt gzip data: {exc}", Location(path, 1))
