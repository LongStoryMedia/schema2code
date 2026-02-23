"""Tests that type names with acronyms (API, MCP, URL, etc.) are preserved
consistently between import statements and type references in generated code."""

import re
from pathlib import Path
from src.generators.python import PythonGenerator
from src.generators.typescript import TypeScriptGenerator
from src.util.resolver import SchemaRefResolver
import yaml

SAMPLE_DIR = Path(__file__).parent.parent / "sample_schemas"


def load_schema(name: str):
    path = SAMPLE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), str(path)


def test_python_pydantic_union_preserves_acronym_type_names():
    """Import names and union type references must match for acronym titles."""
    schema, schema_path = load_schema("acronym_union.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = PythonGenerator.generate(
        schema, schema_file=schema_path, ref_resolver=resolver
    )
    # Imports should use the title-derived name (APIRequest, not ApiRequest)
    assert "from .acronym_api_request import APIRequest" in code
    assert "from .acronym_api_response import APIResponse" in code
    # The union type alias must use the same names as the imports
    assert "APIMessage = Union[APIRequest, APIResponse]" in code


def test_python_dataclass_union_preserves_acronym_type_names():
    """Dataclass mode should also preserve acronym type names in unions."""
    schema, schema_path = load_schema("acronym_union.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = PythonGenerator.generate(
        schema,
        use_pydantic=False,
        schema_file=schema_path,
        ref_resolver=resolver,
    )
    assert "from .acronym_api_request import APIRequest" in code
    assert "from .acronym_api_response import APIResponse" in code
    assert "APIMessage = Union[APIRequest, APIResponse]" in code


def test_python_property_ref_preserves_acronym_type_names():
    """When a property references an external schema with an acronym title,
    the type annotation and import should use the title-derived name."""
    schema = {
        "title": "Wrapper",
        "type": "object",
        "properties": {
            "request": {"$ref": "acronym_api_request.yaml"},
        },
    }
    schema_path = str(SAMPLE_DIR / "wrapper_test.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = PythonGenerator.generate(
        schema, schema_file=schema_path, ref_resolver=resolver
    )
    # The import should use the title-derived name
    assert "from .acronym_api_request import APIRequest" in code
    # The property type annotation should use APIRequest, not ApiRequest
    assert "Optional[APIRequest]" in code


def test_typescript_property_ref_preserves_acronym_type_names():
    """TypeScript generator should resolve acronym type names from schema titles."""
    schema = {
        "title": "Wrapper",
        "type": "object",
        "properties": {
            "request": {"$ref": "acronym_api_request.yaml"},
        },
    }
    schema_path = str(SAMPLE_DIR / "wrapper_test.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = TypeScriptGenerator.generate(
        schema, schema_file=schema_path, ref_resolver=resolver
    )
    # Import should use title-derived name
    assert "import { APIRequest }" in code
    # Property type should use APIRequest
    assert "request?: APIRequest" in code
