"""Actual implementation package when using a src/ layout.

Tests currently import `schema2code.util.resolver` expecting a standard
package layout. We provide this namespace under src/schema2code matching
setuptools best practices.
"""

from src import generators  # type: ignore  # noqa: F401
from src import util  # type: ignore  # noqa: F401
from src import main as _main  # type: ignore

__all__ = ["generators", "util", "main"]


def main():  # pragma: no cover - thin wrapper
    return _main.main()
