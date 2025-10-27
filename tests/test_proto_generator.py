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


def test_proto_message_generation_field_numbers():
    schema, schema_path = load_schema("gpu_config.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = ProtoGenerator.generate(
        schema, package_name="models", schema_file=schema_path, ref_resolver=resolver
    )
    # Root message name
    assert "message GPUConfig {" in code
    # Field numbering sequential
    # Only capture top-level message field numbers (lines starting with two spaces and a type)
    field_numbers = []
    in_enum = False
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("enum "):
            in_enum = True
            continue
        if in_enum and stripped == "}":
            in_enum = False
            continue
        if in_enum:
            continue
        if line.startswith("  ") and "=" in line and stripped.endswith(";"):
            m = re.search(r"= (\d+);", line)
            if m:
                field_numbers.append(int(m.group(1)))
    assert field_numbers == sorted(field_numbers)
    assert field_numbers[0] == 1


def test_proto_external_import_for_reference():
    user_schema, user_path = load_schema("user_config.yaml")
    resolver = SchemaRefResolver(user_path, user_schema)
    code = ProtoGenerator.generate(
        user_schema, package_name="models", schema_file=user_path, ref_resolver=resolver
    )
    # Should include import for gpu_config.proto if referenced
    assert "GPUConfig" in code
