"""
OpenAPI document parser and schema extractor for schema2code.

Detects OpenAPI documents and extracts individual schemas from
components.schemas, rewriting $ref paths from #/components/schemas/X
to #/definitions/X so the existing pipeline can process them.
"""

import copy
import os
from typing import Any, Dict, List, Tuple

from .schema_helpers import to_pascal_case


def is_openapi_document(data: Dict[str, Any]) -> bool:
    """Check if a loaded document is an OpenAPI specification."""
    return (
        isinstance(data, dict)
        and "openapi" in data
        and isinstance(data.get("components"), dict)
        and isinstance(data.get("components", {}).get("schemas"), dict)
    )


def _rewrite_refs(schema: Any) -> Any:
    """
    Recursively rewrite all $ref values from #/components/schemas/X
    to #/definitions/X throughout a schema dict/list structure.
    """
    if isinstance(schema, dict):
        result = {}
        for key, value in schema.items():
            if key == "$ref" and isinstance(value, str):
                if value.startswith("#/components/schemas/"):
                    result[key] = value.replace(
                        "#/components/schemas/", "#/definitions/", 1
                    )
                else:
                    result[key] = value
            else:
                result[key] = _rewrite_refs(value)
        return result
    elif isinstance(schema, list):
        return [_rewrite_refs(item) for item in schema]
    return schema


def extract_schemas(
    openapi_data: Dict[str, Any],
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """
    Extract all schemas from an OpenAPI document's components.schemas section.

    Returns:
        A tuple of:
        - schemas_map: Dict mapping schema name -> standalone schema dict
          (with title injected, $refs rewritten to #/definitions/ format)
        - definitions: Dict of all schemas as a definitions map (for resolver)
    """
    components_schemas = openapi_data.get("components", {}).get("schemas", {})

    # Deep copy to avoid mutating the original
    schemas = copy.deepcopy(components_schemas)

    # Build a definitions-style map with rewritten refs
    definitions = {}
    schemas_map = {}

    for schema_name, schema_dict in schemas.items():
        if not isinstance(schema_dict, dict):
            continue

        # Rewrite all $ref paths from #/components/schemas/X to #/definitions/X
        rewritten = _rewrite_refs(schema_dict)

        # Inject title if missing (use the components/schemas key name)
        if "title" not in rewritten:
            rewritten["title"] = schema_name

        definitions[schema_name] = rewritten
        schemas_map[schema_name] = rewritten

    return schemas_map, definitions


def build_schema_for_type(
    schema_name: str,
    schema_dict: Dict[str, Any],
    all_definitions: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build a standalone JSON Schema document for a single type, embedding
    any referenced definitions so the existing pipeline can resolve them.

    The resulting schema has:
    - The type's own properties/composition at the root level
    - A 'definitions' section containing all schemas from the OpenAPI doc
      that this type references (directly or transitively)

    Args:
        schema_name: The name of the type being generated
        schema_dict: The type's schema dict (already rewritten)
        all_definitions: The full definitions map from extract_schemas()

    Returns:
        A standalone schema dict ready for generate_types pipeline
    """
    # Start with the schema itself as the root
    standalone = dict(schema_dict)

    # Collect all referenced definitions (transitive closure)
    referenced = set()
    _collect_refs(schema_dict, referenced)

    # Build a definitions section with only referenced types
    if referenced:
        defs = {}
        # Use a queue to handle transitive refs without mutating the set during iteration
        to_process = list(referenced)
        seen = set(referenced)
        while to_process:
            ref_name = to_process.pop()
            if ref_name != schema_name and ref_name in all_definitions:
                defs[ref_name] = all_definitions[ref_name]
                # Collect transitive refs from this definition
                transitive = set()
                _collect_refs(all_definitions[ref_name], transitive)
                for t_ref in transitive:
                    if t_ref not in seen:
                        seen.add(t_ref)
                        to_process.append(t_ref)
        if defs:
            standalone["definitions"] = defs

    return standalone


def _collect_refs(schema: Any, refs: set) -> None:
    """Recursively collect all #/definitions/X references from a schema."""
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key == "$ref" and isinstance(value, str):
                if value.startswith("#/definitions/"):
                    ref_name = value.split("/")[-1]
                    refs.add(ref_name)
            else:
                _collect_refs(value, refs)
    elif isinstance(schema, list):
        for item in schema:
            _collect_refs(item, refs)


def schema_name_to_filename(schema_name: str, language: str) -> str:
    """
    Convert an OpenAPI schema name to an appropriate output filename.

    Args:
        schema_name: PascalCase schema name from components/schemas
        language: Target language (python, typescript, go, etc.)

    Returns:
        The output filename (without directory)
    """
    if language == "python":
        # Convert PascalCase to snake_case
        import re
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", schema_name)
        snake = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        return f"{snake}.py"
    elif language == "typescript":
        return f"{schema_name}.ts"
    elif language == "go":
        # Convert PascalCase to snake_case
        import re
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", schema_name)
        snake = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        return f"{snake}.go"
    elif language in ("csharp", "dotnet"):
        return f"{schema_name}.cs"
    elif language in ("proto", "protobuf"):
        import re
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", schema_name)
        snake = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
        return f"{snake}.proto"
    else:
        return f"{schema_name}.txt"
