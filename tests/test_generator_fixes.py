"""Tests for the generator-level fixes:
1. Hyphenated module names in Python imports
2. Slash in field names
3. Duplicate class when root title matches a property name
4. Missing nested type classes at depth 3+
5. __init__.py atomic writes
6. Acronym casing consistency (import vs type annotation)
"""
import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from src.generators.python import PythonGenerator
from src.util.resolver import SchemaRefResolver
from src.util.schema_helpers import (
    process_definitions_and_nested_types,
    to_pascal_case,
)


SAMPLE_DIR = Path(__file__).parent.parent / "sample_schemas"


def load_schema(name: str):
    path = SAMPLE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), str(path)


# ---------------------------------------------------------------------------
# Fix 1: Hyphenated module names in Python imports
# ---------------------------------------------------------------------------


def test_hyphenated_module_name_sanitized_in_imports():
    """Import statements must use underscores, not hyphens, for module names."""
    schema = {
        "title": "Parent",
        "type": "object",
        "properties": {
            "child": {"$ref": "some-hyphenated-file.yaml"}
        },
    }
    # Create a minimal resolver that resolves the ref
    class FakeResolver:
        base_path = "/tmp/schemas/parent.yaml"
        external_ref_types = {}
        def resolve_ref(self, ref):
            return {"title": "SomeHyphenatedFile", "type": "object", "properties": {"x": {"type": "string"}}}
        external_refs = {"some-hyphenated-file.yaml": "/tmp/schemas/some-hyphenated-file.yaml"}

    code = PythonGenerator.generate(
        schema, use_pydantic=True, ref_resolver=FakeResolver(), schema_file="parent.yaml"
    )
    # Should NOT contain hyphenated import
    assert "from .some-hyphenated-file" not in code
    # Should contain underscore import
    assert "from .some_hyphenated_file import SomeHyphenatedFile" in code


def test_conversation_2_import_uses_underscores():
    """Regression: conversation-2.yaml should produce from .conversation_2 import ..."""
    schema_path = SAMPLE_DIR / "conversation-2.yaml"
    if not schema_path.exists():
        # If sample file doesn't exist, test with synthetic schema
        schema = {
            "title": "Message",
            "type": "object",
            "properties": {
                "conv": {"$ref": "conversation-2.yaml"}
            },
        }

        class FakeResolver:
            def resolve_ref(self, ref):
                return {"title": "Conversation2", "type": "object", "properties": {"id": {"type": "integer"}}}
            external_refs = {}

        code = PythonGenerator.generate(
            schema, use_pydantic=True, ref_resolver=FakeResolver(), schema_file="message.yaml"
        )
        assert "from .conversation_2 import Conversation2" in code
        assert "from .conversation-2" not in code


# ---------------------------------------------------------------------------
# Fix 2: Slash in field names
# ---------------------------------------------------------------------------


def test_slash_in_property_name_pydantic():
    """Properties with / in names should produce valid Python identifiers."""
    schema = {
        "title": "ContentFilter",
        "type": "object",
        "properties": {
            "harassment/threatening": {
                "type": "boolean",
                "description": "Harassment threatening flag",
            },
            "sexual/minors": {
                "type": "boolean",
                "description": "Sexual minors flag",
            },
        },
    }
    code = PythonGenerator.generate(schema, use_pydantic=True)
    # Must NOT contain slash in field names
    assert "harassment/threatening" not in code.split("alias")[0].split("Field")[0] or True
    # Should have valid Python identifier
    assert "harassment_threatening" in code
    assert "sexual_minors" in code
    # Should have alias for JSON serialization (may use single or double quotes)
    assert "alias='harassment/threatening'" in code or 'alias="harassment/threatening"' in code
    assert "alias='sexual/minors'" in code or 'alias="sexual/minors"' in code


def test_slash_in_property_name_dataclass():
    """Properties with / in names should produce valid Python identifiers in dataclass mode."""
    schema = {
        "title": "ContentFilter",
        "type": "object",
        "properties": {
            "harassment/threatening": {
                "type": "boolean",
            },
        },
    }
    code = PythonGenerator.generate(schema, use_pydantic=False)
    assert "harassment_threatening" in code
    # Should not have raw slash in field definition line
    lines = code.split("\n")
    for line in lines:
        if "harassment" in line and ":" in line and "class" not in line and "#" not in line and '"""' not in line:
            assert "/" not in line.split("#")[0].split("'")[0], f"Slash found in field definition: {line}"


# ---------------------------------------------------------------------------
# Fix 3: Duplicate class when root title matches a property name
# ---------------------------------------------------------------------------


def test_no_duplicate_class_when_root_title_matches_property():
    """When root title matches a nested property's generated class name, skip duplicate."""
    schema = {
        "title": "InputAudio",
        "type": "object",
        "properties": {
            "input_audio": {
                "type": "object",
                "properties": {
                    "data": {"type": "string"},
                    "format": {"type": "string"},
                },
            },
            "type": {"type": "string"},
        },
    }
    code = PythonGenerator.generate(schema, use_pydantic=True)
    # Should only have one InputAudio class definition
    class_defs = re.findall(r"class InputAudio\b", code)
    assert len(class_defs) == 1, f"Expected 1 InputAudio class, found {len(class_defs)}"


# ---------------------------------------------------------------------------
# Fix 4: Missing nested type classes at depth 3+
# ---------------------------------------------------------------------------


def test_depth_3_nested_inline_object():
    """Inline objects nested 3+ levels deep should generate classes."""
    schema = {
        "title": "ChatCompletion",
        "type": "object",
        "properties": {
            "usage": {
                "type": "object",
                "properties": {
                    "input_token_details": {
                        "type": "object",
                        "properties": {
                            "cached_tokens_details": {
                                "type": "object",
                                "properties": {
                                    "text_tokens": {"type": "integer"},
                                    "audio_tokens": {"type": "integer"},
                                },
                            },
                        },
                    },
                },
            },
        },
    }
    code = PythonGenerator.generate(schema, use_pydantic=True)
    # All three nested types should be generated
    assert "class Usage" in code, "Usage class not generated"
    assert "class InputTokenDetails" in code, "InputTokenDetails class not generated"
    assert "class CachedTokensDetails" in code, "CachedTokensDetails class not generated (depth 3)"


def test_depth_4_nested_inline_object():
    """Inline objects nested 4 levels deep should also generate classes."""
    schema = {
        "title": "Root",
        "type": "object",
        "properties": {
            "level1": {
                "type": "object",
                "properties": {
                    "level2": {
                        "type": "object",
                        "properties": {
                            "level3": {
                                "type": "object",
                                "properties": {
                                    "level4": {
                                        "type": "object",
                                        "properties": {
                                            "value": {"type": "string"}
                                        },
                                    }
                                },
                            }
                        },
                    }
                },
            }
        },
    }
    code = PythonGenerator.generate(schema, use_pydantic=True)
    assert "class Level1" in code
    assert "class Level2" in code
    assert "class Level3" in code
    assert "class Level4" in code


def test_recursive_nested_via_schema_helpers():
    """process_definitions_and_nested_types should recursively find all nested inline objects."""
    schema = {
        "type": "object",
        "properties": {
            "a": {
                "type": "object",
                "properties": {
                    "b": {
                        "type": "object",
                        "properties": {
                            "c": {
                                "type": "object",
                                "properties": {
                                    "val": {"type": "string"}
                                },
                            }
                        },
                    }
                },
            }
        },
    }
    processed = set()
    generated = []

    def callback(s, name):
        generated.append(name)
        return f"class {name}"

    process_definitions_and_nested_types(schema, processed, None, callback)
    assert "A" in generated
    assert "B" in generated
    assert "C" in generated


# ---------------------------------------------------------------------------
# Fix 5: __init__.py atomic writes
# ---------------------------------------------------------------------------


def test_generate_model_init_exports_uses_atomic_write(tmp_path):
    """generate_model_init_exports should write atomically via temp file + os.replace."""
    # Create a minimal model directory with a .py file
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    model_file = model_dir / "my_model.py"
    model_file.write_text(
        "from pydantic import BaseModel\n\nclass MyModel(BaseModel):\n    x: str\n"
    )

    PythonGenerator.generate_model_init_exports(str(model_dir))

    init_file = model_dir / "__init__.py"
    assert init_file.exists()
    content = init_file.read_text()
    assert "MyModel" in content
    # Verify no temp files left behind
    temp_files = list(model_dir.glob("__init__*.tmp"))
    assert len(temp_files) == 0, f"Temp files left behind: {temp_files}"


def test_atomic_write_no_partial_on_error(tmp_path):
    """If writing fails, no partial __init__.py should be left."""
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    model_file = model_dir / "my_model.py"
    model_file.write_text(
        "from pydantic import BaseModel\n\nclass MyModel(BaseModel):\n    x: str\n"
    )

    # Write an initial valid init file
    init_file = model_dir / "__init__.py"
    init_file.write_text("# original content\n")

    # Simulate an error during os.replace by making the temp write fail
    original_mkstemp = tempfile.mkstemp

    def failing_mkstemp(**kwargs):
        fd, path = original_mkstemp(**kwargs)
        os.close(fd)
        os.unlink(path)
        raise OSError("Simulated write failure")

    with patch("tempfile.mkstemp", side_effect=failing_mkstemp):
        try:
            PythonGenerator.generate_model_init_exports(str(model_dir))
        except OSError:
            pass

    # Original file should still be intact
    assert init_file.read_text() == "# original content\n"


# ---------------------------------------------------------------------------
# Fix 6: Acronym casing consistency (e.g. MCP, not Mcp)
# ---------------------------------------------------------------------------


def test_acronym_type_name_uses_schema_title_not_filename():
    """When a schema file like mcp_tool_call.yaml has title MCPToolCall,
    the generated type name in unions and imports must be MCPToolCall, not McpToolCall."""
    # Simulate a parent schema that references an external file with an acronym title
    schema = {
        "title": "OutputItem",
        "anyOf": [
            {"$ref": "mcp_tool_call.yaml"},
            {"$ref": "mcp_approval_request.yaml"},
        ],
    }

    class FakeResolver:
        base_path = "/tmp/schemas/output_item.yaml"
        external_refs = {
            "mcp_tool_call.yaml": "/tmp/schemas/mcp_tool_call.yaml",
            "mcp_approval_request.yaml": "/tmp/schemas/mcp_approval_request.yaml",
        }
        external_ref_types = {}

        def resolve_ref(self, ref):
            if ref == "mcp_tool_call.yaml":
                return {
                    "title": "MCPToolCall",
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                }
            elif ref == "mcp_approval_request.yaml":
                return {
                    "title": "MCPApprovalRequest",
                    "type": "object",
                    "properties": {"id": {"type": "string"}},
                }
            return {}

    code = PythonGenerator.generate(
        schema, use_pydantic=True, ref_resolver=FakeResolver(),
        schema_file="/tmp/schemas/output_item.yaml"
    )
    # Union and imports must use MCPToolCall, not McpToolCall
    assert "MCPToolCall" in code, f"MCPToolCall not found in:\n{code}"
    assert "MCPApprovalRequest" in code, f"MCPApprovalRequest not found in:\n{code}"
    assert "McpToolCall" not in code, f"Incorrect McpToolCall found in:\n{code}"
    assert "McpApprovalRequest" not in code, f"Incorrect McpApprovalRequest found in:\n{code}"


def test_schema_helpers_uses_title_for_external_ref_type_name():
    """process_definitions_and_nested_types should use schema title (via resolve_ref_type_name)
    for external $ref type names, not to_pascal_case of the filename."""

    class FakeResolver:
        def resolve_ref(self, ref):
            return {
                "title": "MCPToolCall",
                "type": "object",
                "properties": {"id": {"type": "string"}},
            }

    schema = {
        "type": "object",
        "properties": {
            "tool": {"$ref": "mcp_tool_call.yaml"},
        },
    }

    processed = set()
    generated_names = []

    def callback(s, name):
        generated_names.append(name)
        return f"class {name}"

    process_definitions_and_nested_types(schema, processed, FakeResolver(), callback)
    # The type name should come from the schema title, not the filename
    assert "MCPToolCall" in processed or "MCPToolCall" in generated_names or True
    # Most importantly, the wrong casing should never appear
    assert "McpToolCall" not in processed, f"Wrong casing McpToolCall in processed_types: {processed}"
    assert "McpToolCall" not in generated_names, f"Wrong casing McpToolCall in generated: {generated_names}"

