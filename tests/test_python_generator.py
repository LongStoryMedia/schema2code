import re
from pathlib import Path
from src.generators.python import PythonGenerator
from src.util.resolver import SchemaRefResolver
import yaml

SAMPLE_DIR = Path(__file__).parent.parent / "sample_schemas"


def load_schema(name: str):
    path = SAMPLE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), str(path)


def test_no_duplicate_gpuconfig_in_user_config(tmp_path):
    user_schema, user_path = load_schema("user_config.yaml")
    resolver = SchemaRefResolver(user_path, user_schema)
    code = PythonGenerator.generate(
        user_schema, schema_file=user_path, ref_resolver=resolver
    )
    # GPUConfig should appear only as a field type, not a duplicate class definition before UserConfig
    gpu_class_defs = re.findall(r"class GPUConfig\b", code)
    assert (
        len(gpu_class_defs) == 0
    ), "GPUConfig class redefined inside user_config output"
    assert "gpu_config: Annotated[GPUConfig" in code


def test_defaults_present_in_gpu_config(tmp_path):
    schema, schema_path = load_schema("gpu_config.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = PythonGenerator.generate(
        schema, schema_file=schema_path, ref_resolver=resolver
    )
    # Expect default values reflected in Annotated format with explicit defaults
    assert (
        "no_kv_offload: Annotated[Optional[bool], Field(default=False" in code
        and "] = False" in code
    )
    assert (
        "main_gpu: Annotated[Optional[int], Field(default=-1" in code
        and "] = -1" in code
    )
    assert (
        'split_mode: Annotated[Optional[Literal["none", "layer", "row"]], Field(default=\'layer\''
        in code
        and "] = 'layer'" in code
    )
    assert (
        "offload_kqv: Annotated[Optional[bool], Field(default=True" in code
        and "] = True" in code
    )


def test_inline_enum_generation():
    """Test that inline enums generate proper Literal types instead of generic str"""
    schema, schema_path = load_schema("todo_item.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = PythonGenerator.generate(
        schema, schema_file=schema_path, ref_resolver=resolver
    )
    # Expect status and priority fields to use Literal types for enums
    assert (
        'status: Annotated[Literal["not-started", "in-progress", "completed", "cancelled"]'
        in code
    )
    assert 'priority: Annotated[Literal["low", "medium", "high", "urgent"]' in code
    # Ensure Literal is imported
    assert (
        "from typing import List, Dict, Optional, Any, Union, Annotated, Literal"
        in code
    )


def test_array_item_external_ref_detection():
    schema, schema_path = load_schema("message.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = PythonGenerator.generate(
        schema, schema_file=schema_path, ref_resolver=resolver
    )
    # Ensure content uses referenced MessageContent type and not inline definition duplication
    # Should not generate a class named MessageContent inside this file
    assert "class MessageContent(" not in code
    assert "content: Annotated[List[MessageContent]" in code
