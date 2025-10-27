import re
from pathlib import Path
import yaml
from src.generators.go import GoGenerator
from src.util.resolver import SchemaRefResolver

SAMPLE_DIR = Path(__file__).parent.parent / "sample_schemas"


def load_schema(name: str):
    path = SAMPLE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), str(path)


def test_go_imports_for_formats():
    schema, schema_path = load_schema("format_test.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = GoGenerator.generate(
        schema, package_name="models", schema_file=schema_path, ref_resolver=resolver
    )
    # Expect imports block with time, github.com/google/uuid, net/url
    assert "import (" in code
    assert '"time"' in code
    assert '"github.com/google/uuid"' in code
    assert '"net/url"' in code
