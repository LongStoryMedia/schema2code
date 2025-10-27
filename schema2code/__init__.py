"""Shim package for in-repo execution.

The actual implementation modules live under `src/schema2code`. When the
package is installed via setuptools this layout is handled automatically.
During direct test runs (pytest) without installation, tests may import
`schema2code.*` while only the repository root is on `sys.path`. This shim
adds `src` to the import path so those imports succeed without requiring an
editable install.
"""

from __future__ import annotations

import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.abspath(__file__))
_PARENT = _os.path.dirname(_ROOT)
_SRC = _os.path.join(_PARENT, "src")

if _os.path.isdir(_SRC) and _SRC not in _sys.path:
    _sys.path.insert(0, _SRC)

__all__ = []
