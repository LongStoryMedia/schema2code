import os
import sys
import shutil
import tempfile
import yaml
import pytest
from pathlib import Path

# Ensure src/ is on sys.path so 'schema2code' package (under src) is importable when not installed
ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.util.resolver import SchemaRefResolver  # noqa: E402
from src.util.loader import SchemaLoader  # noqa: E402
from src.generators.python import PythonGenerator  # noqa: E402
from src.generators.typescript import TypeScriptGenerator  # noqa: E402

SAMPLE_DIR = ROOT / "sample_schemas"


def load_schema(name: str):
    path = SAMPLE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), str(path)


@pytest.fixture
def temp_output_dir():
    d = tempfile.mkdtemp(prefix="schema2code_tests_")
    yield d
    shutil.rmtree(d, ignore_errors=True)
