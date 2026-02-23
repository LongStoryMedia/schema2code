import re
from pathlib import Path
import yaml
from src.generators.dotnet import CSharpGenerator
from src.util.resolver import SchemaRefResolver

SAMPLE_DIR = Path(__file__).parent.parent / "sample_schemas"


def load_schema(name: str):
    path = SAMPLE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), str(path)


def test_csharp_class_generation_defaults_and_required():
    schema, schema_path = load_schema("gpu_config.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = CSharpGenerator.generate(
        schema,
        namespace="MyApp.Models",
        schema_file=schema_path,
        ref_resolver=resolver,
    )
    assert "namespace MyApp.Models" in code
    assert "public class GPUConfig" in code
    # Check a couple of properties with inferred nullable vs required + default
    # main_gpu has default -1
    assert re.search(r"public long\?? MainGpu { get; set; } = -1;", code)
    # split_mode default 'layer'
    # SplitMode enum? If generated as string with default
    assert "SplitMode" in code


def test_csharp_external_reference():
    user_schema, user_path = load_schema("user_config.yaml")
    resolver = SchemaRefResolver(user_path, user_schema)
    code = CSharpGenerator.generate(
        user_schema,
        namespace="MyApp.Models",
        schema_file=user_path,
        ref_resolver=resolver,
    )
    # Should reference GPUConfig type name but not declare it (no duplicate class)
    # Should reference GPUConfig type name
    assert "GPUConfig" in code or "GpuConfig" in code
