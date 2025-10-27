import re
from pathlib import Path
import yaml
from src.generators.proto import ProtoGenerator
from src.util.resolver import SchemaRefResolver

SAMPLE_DIR = Path(__file__).parent.parent / "sample_schemas"


def load_schema(name: str):
    path = SAMPLE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), str(path)


def test_proto_map_additional_properties():
    schema, schema_path = load_schema("map_example.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = ProtoGenerator.generate(
        schema, package_name="models", schema_file=schema_path, ref_resolver=resolver
    )
    # attributes -> map<string, string>
    assert "map<string, string> attributes" in code
    # counts -> map<string, int32>
    assert "map<string, int32> counts" in code or "map<string, int64> counts" in code
    # generic -> map<string, string>
    assert "map<string, string> additional_properties" in code
