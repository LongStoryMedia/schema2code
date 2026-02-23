import re
from pathlib import Path
import yaml
from src.generators.typescript import TypeScriptGenerator
from src.util.resolver import SchemaRefResolver

SAMPLE_DIR = Path(__file__).parent.parent / "sample_schemas"


def load_schema(name: str):
    path = SAMPLE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), str(path)


def test_typescript_multiple_enums_and_index(tmp_path):
    schema, schema_path = load_schema("enum_bundle.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = TypeScriptGenerator.generate(
        schema, schema_file=schema_path, ref_resolver=resolver
    )
    # Should create inline union types for enums
    assert re.search(r"status\?\:\s*'pending'\s*\|\s*'running'\s*\|\s*'done';", code)
    assert re.search(r"level\?\:\s*'low'\s*\|\s*'medium'\s*\|\s*'high';", code)
    # flags array: type should be 'alpha' | 'beta'[]
    assert re.search(r"flags\?\:\s*'alpha'\s*\|\s*'beta'\[\];", code)
    # Write file and generate index exports
    out_dir = tmp_path / "ts"
    out_dir.mkdir()
    (out_dir / "EnumBundle.ts").write_text(code, encoding="utf-8")
    TypeScriptGenerator.generate_index_exports(str(out_dir))
    index_text = (out_dir / "index.ts").read_text(encoding="utf-8")
    assert "export { EnumBundle }" in index_text
