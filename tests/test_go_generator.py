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


def test_go_basic_struct_generation():
    schema, schema_path = load_schema("gpu_config.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = GoGenerator.generate(
        schema, package_name="models", schema_file=schema_path, ref_resolver=resolver
    )
    # Package declaration present
    assert "\npackage models" in code or code.startswith("package models")
    # Struct name from title GPUConfig
    assert re.search(r"type GPUConfig struct {", code)
    # Field presence (sample expected fields)
    assert "NoKvOffload" in code  # field name conversion
    assert "MainGpu" in code


def test_go_external_ref_import_handling():
    # user_config references gpu_config
    user_schema, user_path = load_schema("user_config.yaml")
    resolver = SchemaRefResolver(user_path, user_schema)
    code = GoGenerator.generate(
        user_schema, package_name="models", schema_file=user_path, ref_resolver=resolver
    )
    # Ensure referenced GPUConfig field type exists
    assert "GPUConfig" in code or "GpuConfig" in code
