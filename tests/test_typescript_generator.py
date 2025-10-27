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


def test_message_imports_referenced_types(tmp_path):
    schema, schema_path = load_schema("message.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = TypeScriptGenerator.generate(
        schema, schema_file=schema_path, ref_resolver=resolver
    )
    # Should import MessageRole and MessageContent
    assert "import { MessageRole }" in code
    assert "import { MessageContent }" in code
    # Interface should reference MessageContent[] for content
    assert re.search(r"content:\s*MessageContent\[];", code)


def test_index_exports_casing(tmp_path):
    # Simulate generating multiple related types to a directory
    schema, schema_path = load_schema("gpu_config.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = TypeScriptGenerator.generate(
        schema, schema_file=schema_path, ref_resolver=resolver
    )
    # Write to temp dir to invoke index export generation
    out_dir = tmp_path / "ts"
    out_dir.mkdir()
    (out_dir / "GpuConfig.ts").write_text(code, encoding="utf-8")
    # Generate index
    TypeScriptGenerator.generate_index_exports(str(out_dir))
    index_text = (out_dir / "index.ts").read_text(encoding="utf-8")
    assert "export { GPUConfig } from './GpuConfig';" in index_text
