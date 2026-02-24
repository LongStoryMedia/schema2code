"""Tests for OpenAPI spec support in schema2code."""

import os
import sys
import yaml
import pytest
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from src.util.openapi import (
    is_openapi_document,
    extract_schemas,
    build_schema_for_type,
    schema_name_to_filename,
    _rewrite_refs,
    _collect_refs,
)
from src.util.resolver import SchemaRefResolver
from src.util.schema_helpers import is_internal_ref, type_name_from_ref
from src.generators.python import PythonGenerator
from src.generators.typescript import TypeScriptGenerator
from src.generators.go import GoGenerator
from src.main import generate_types_from_openapi


# --- Fixtures ---

MINI_OPENAPI = {
    "openapi": "3.1.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {},
    "components": {
        "schemas": {
            "Address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "zip": {"type": "string"},
                },
                "required": ["street", "city"],
            },
            "Person": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                    "address": {"$ref": "#/components/schemas/Address"},
                },
                "required": ["name"],
            },
            "Team": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "members": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/Person"},
                    },
                },
            },
            "Status": {
                "type": "string",
                "enum": ["active", "inactive", "pending"],
            },
        }
    },
}


# --- is_openapi_document tests ---


def test_detects_openapi_document():
    assert is_openapi_document(MINI_OPENAPI) is True


def test_rejects_plain_json_schema():
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Foo",
        "type": "object",
        "properties": {"name": {"type": "string"}},
    }
    assert is_openapi_document(schema) is False


def test_rejects_missing_components():
    doc = {"openapi": "3.1.0", "info": {}, "paths": {}}
    assert is_openapi_document(doc) is False


def test_rejects_empty_components():
    doc = {"openapi": "3.1.0", "info": {}, "paths": {}, "components": {}}
    assert is_openapi_document(doc) is False


# --- _rewrite_refs tests ---


def test_rewrite_refs_simple():
    schema = {"$ref": "#/components/schemas/Foo"}
    result = _rewrite_refs(schema)
    assert result["$ref"] == "#/definitions/Foo"


def test_rewrite_refs_nested():
    schema = {
        "properties": {
            "bar": {"$ref": "#/components/schemas/Bar"},
            "items": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/Baz"},
            },
        }
    }
    result = _rewrite_refs(schema)
    assert result["properties"]["bar"]["$ref"] == "#/definitions/Bar"
    assert result["properties"]["items"]["items"]["$ref"] == "#/definitions/Baz"


def test_rewrite_refs_in_composition():
    schema = {
        "anyOf": [
            {"$ref": "#/components/schemas/TypeA"},
            {"$ref": "#/components/schemas/TypeB"},
            {"type": "string"},
        ]
    }
    result = _rewrite_refs(schema)
    assert result["anyOf"][0]["$ref"] == "#/definitions/TypeA"
    assert result["anyOf"][1]["$ref"] == "#/definitions/TypeB"
    assert result["anyOf"][2] == {"type": "string"}


def test_rewrite_refs_preserves_non_component_refs():
    schema = {"$ref": "#/definitions/AlreadyLocal"}
    result = _rewrite_refs(schema)
    assert result["$ref"] == "#/definitions/AlreadyLocal"


def test_rewrite_refs_preserves_external_refs():
    schema = {"$ref": "other_file.yaml"}
    result = _rewrite_refs(schema)
    assert result["$ref"] == "other_file.yaml"


# --- extract_schemas tests ---


def test_extract_schemas_returns_all_types():
    schemas_map, definitions = extract_schemas(MINI_OPENAPI)
    assert set(schemas_map.keys()) == {"Address", "Person", "Team", "Status"}
    assert set(definitions.keys()) == {"Address", "Person", "Team", "Status"}


def test_extract_schemas_injects_title():
    schemas_map, _ = extract_schemas(MINI_OPENAPI)
    assert schemas_map["Address"]["title"] == "Address"
    assert schemas_map["Person"]["title"] == "Person"


def test_extract_schemas_preserves_existing_title():
    openapi = {
        "openapi": "3.1.0",
        "components": {
            "schemas": {
                "MyType": {
                    "title": "CustomTitle",
                    "type": "object",
                    "properties": {"x": {"type": "string"}},
                }
            }
        },
    }
    schemas_map, _ = extract_schemas(openapi)
    assert schemas_map["MyType"]["title"] == "CustomTitle"


def test_extract_schemas_rewrites_refs():
    schemas_map, _ = extract_schemas(MINI_OPENAPI)
    person = schemas_map["Person"]
    assert person["properties"]["address"]["$ref"] == "#/definitions/Address"


# --- _collect_refs tests ---


def test_collect_refs_finds_definitions():
    schema = {
        "properties": {
            "a": {"$ref": "#/definitions/Foo"},
            "b": {"type": "array", "items": {"$ref": "#/definitions/Bar"}},
        }
    }
    refs = set()
    _collect_refs(schema, refs)
    assert refs == {"Foo", "Bar"}


def test_collect_refs_handles_composition():
    schema = {
        "allOf": [
            {"$ref": "#/definitions/Base"},
            {"properties": {"x": {"$ref": "#/definitions/Extra"}}},
        ]
    }
    refs = set()
    _collect_refs(schema, refs)
    assert refs == {"Base", "Extra"}


# --- build_schema_for_type tests ---


def test_build_schema_includes_referenced_definitions():
    schemas_map, definitions = extract_schemas(MINI_OPENAPI)
    standalone = build_schema_for_type("Team", schemas_map["Team"], definitions)

    assert "definitions" in standalone
    assert "Person" in standalone["definitions"]
    # Person references Address, so Address should also be included (transitive)
    assert "Address" in standalone["definitions"]


def test_build_schema_excludes_self_from_definitions():
    schemas_map, definitions = extract_schemas(MINI_OPENAPI)
    standalone = build_schema_for_type("Person", schemas_map["Person"], definitions)

    if "definitions" in standalone:
        assert "Person" not in standalone["definitions"]


def test_build_schema_no_definitions_when_no_refs():
    schemas_map, definitions = extract_schemas(MINI_OPENAPI)
    standalone = build_schema_for_type("Address", schemas_map["Address"], definitions)
    assert "definitions" not in standalone or len(standalone.get("definitions", {})) == 0


# --- schema_name_to_filename tests ---


def test_filename_python():
    assert schema_name_to_filename("AdminApiKey", "python") == "admin_api_key.py"
    assert schema_name_to_filename("Batch", "python") == "batch.py"


def test_filename_typescript():
    assert schema_name_to_filename("AdminApiKey", "typescript") == "AdminApiKey.ts"


def test_filename_go():
    assert schema_name_to_filename("AdminApiKey", "go") == "admin_api_key.go"


def test_filename_csharp():
    assert schema_name_to_filename("AdminApiKey", "csharp") == "AdminApiKey.cs"


def test_filename_proto():
    assert schema_name_to_filename("AdminApiKey", "proto") == "admin_api_key.proto"


# --- is_internal_ref / type_name_from_ref tests ---


def test_is_internal_ref_definitions():
    assert is_internal_ref("#/definitions/Foo") is True


def test_is_internal_ref_components_schemas():
    assert is_internal_ref("#/components/schemas/Foo") is True


def test_is_internal_ref_external():
    assert is_internal_ref("other_file.yaml") is False


def test_is_internal_ref_other_fragment():
    assert is_internal_ref("#/some/other/path") is False


def test_type_name_from_ref():
    assert type_name_from_ref("#/definitions/MyType") == "MyType"
    assert type_name_from_ref("#/components/schemas/MyType") == "MyType"


# --- SchemaRefResolver with #/components/schemas/ refs ---


def test_resolver_handles_components_schemas_ref():
    """Resolver should resolve #/definitions/ refs (the rewritten form of #/components/schemas/)."""
    schemas_map, definitions = extract_schemas(MINI_OPENAPI)
    standalone = build_schema_for_type("Person", schemas_map["Person"], definitions)
    resolver = SchemaRefResolver("test.yaml", standalone)

    # The ref was rewritten to #/definitions/Address
    resolved = resolver.resolve_ref("#/definitions/Address")
    assert resolved["type"] == "object"
    assert "street" in resolved["properties"]


# --- End-to-end: generate Python from mini OpenAPI ---


def test_generate_python_from_openapi():
    output_files = generate_types_from_openapi(
        MINI_OPENAPI,
        "python",
        "test_openapi.yaml",
        output="output/models.py",
        use_pydantic=True,
    )

    # Should generate files for each schema
    filenames = {os.path.basename(f) for f in output_files.keys()}
    assert "person.py" in filenames
    assert "address.py" in filenames
    assert "team.py" in filenames
    assert "status.py" in filenames

    # Check Person references Address
    person_file = [v for k, v in output_files.items() if "person" in k.lower()][0]
    assert "class Person" in person_file
    assert "name" in person_file

    # Check Address has its fields
    address_file = [v for k, v in output_files.items() if "address" in k.lower()][0]
    assert "class Address" in address_file
    assert "street" in address_file

    # Check Status is an enum
    status_file = [v for k, v in output_files.items() if "status" in k.lower()][0]
    assert "Status" in status_file
    assert "active" in status_file.lower() or "ACTIVE" in status_file


def test_generate_typescript_from_openapi():
    output_files = generate_types_from_openapi(
        MINI_OPENAPI,
        "typescript",
        "test_openapi.yaml",
        output="output/models.ts",
    )

    filenames = {os.path.basename(f) for f in output_files.keys()}
    assert "Person.ts" in filenames
    assert "Address.ts" in filenames
    assert "Team.ts" in filenames
    assert "Status.ts" in filenames

    person_file = [v for k, v in output_files.items() if "Person" in k][0]
    assert "interface Person" in person_file or "Person" in person_file


def test_generate_go_from_openapi():
    output_files = generate_types_from_openapi(
        MINI_OPENAPI,
        "go",
        "test_openapi.yaml",
        output="output/models.go",
        package_name="models",
    )

    filenames = {os.path.basename(f) for f in output_files.keys()}
    assert "person.go" in filenames
    assert "address.go" in filenames


# --- Test with real OpenAPI spec file if available ---


@pytest.fixture
def openai_spec():
    spec_path = ROOT / "openai.documented.yml"
    if not spec_path.exists():
        pytest.skip("openai.documented.yml not found")
    with open(spec_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_openai_spec_is_detected(openai_spec):
    assert is_openapi_document(openai_spec) is True


def test_openai_spec_extract_schemas(openai_spec):
    schemas_map, definitions = extract_schemas(openai_spec)
    # The OpenAI spec has hundreds of schemas
    assert len(schemas_map) > 100
    # Check some known types exist
    assert "Batch" in schemas_map
    assert "AdminApiKey" in schemas_map


def test_openai_spec_batch_schema_standalone(openai_spec):
    schemas_map, definitions = extract_schemas(openai_spec)
    standalone = build_schema_for_type("Batch", schemas_map["Batch"], definitions)

    # Batch references BatchError, BatchRequestCounts, etc.
    assert standalone["title"] == "Batch"
    assert "properties" in standalone


def test_openai_spec_generate_single_python_type(openai_spec):
    """Generate a single type from the OpenAI spec to verify the pipeline works."""
    schemas_map, definitions = extract_schemas(openai_spec)

    # Pick a simple type
    standalone = build_schema_for_type(
        "BatchRequestCounts", schemas_map["BatchRequestCounts"], definitions
    )
    resolver = SchemaRefResolver("openai.yaml", standalone)
    code = PythonGenerator.generate(standalone, True, "openai.yaml", resolver)

    assert "class BatchRequestCounts" in code
