import os
from typing import Any, Dict, Optional, Set, List
from ..util.writer import Writer
from ..util.schema_helpers import (
    enum_member_name,
    enum_member_desc,
    process_definitions_and_nested_types,
    to_pascal_case,
)
from ..util.resolver import SchemaRefResolver


class CSharpGenerator:
    @staticmethod
    def generate(
        schema: Dict[str, Any],
        namespace: str = "SchemaTypes",
        schema_file: Optional[str] = None,
        ref_resolver: Optional[SchemaRefResolver] = None,
        is_main: bool = True,
        referenced_by: Optional[str] = None,
    ) -> str:
        """Generate C# types from a JSON schema"""
        # Initialize ref resolver if needed
        if ref_resolver is None and schema_file is not None:
            ref_resolver = SchemaRefResolver(schema_file, schema)

        # Track imports needed for this file
        imports = []

        # Find the main class or enum name for this file
        main_type_name = schema.get("title", "")
        if not main_type_name:
            # Use filename if title is not available
            if schema_file:
                basename = os.path.basename(schema_file)
                filename, _ = os.path.splitext(basename)
                main_type_name = to_pascal_case(filename)
            else:
                main_type_name = "Root"

        # Get imports for external references
        if ref_resolver and schema_file and is_main:
            imports = CSharpGenerator._generate_imports(
                schema, ref_resolver, main_type_name
            )

        # Add header comment
        output = [
            Writer.generate_header_comment("csharp"),
            "using System;",
            "using System.Collections.Generic;",
            "using System.Text.Json.Serialization;",
            "",
            "#nullable enable",
            "",
            f"namespace {namespace}",
            "{",
        ]

        # Handle enum type in the schema
        if "enum" in schema:
            enum_def = CSharpGenerator._generate_enum(schema, 1)
            output.append(enum_def)
            output.append("}")
            return "\n".join(output)

        # Process root type only - we don't generate nested types in the same file
        # Each type should be in its own file
        root_type = CSharpGenerator._generate_class(schema, 1, ref_resolver)
        output.append(root_type)

        output.append("}")

        return "\n".join(output)

    @staticmethod
    def _generate_imports(
        schema: Dict[str, Any], ref_resolver: SchemaRefResolver, current_type_name: str
    ) -> List[str]:
        """Generate imports for external references"""
        # Not needed for C# since we're in the same namespace
        # All classes in the same namespace can reference each other
        return []

    @staticmethod
    def _generate_enum(schema: Dict[str, Any], indent_level: int) -> str:
        """Generate a C# enum from a schema with enum values"""
        indent = "    " * indent_level
        title = schema.get("title", "").replace(" ", "")
        if not title:
            title = "Root"

        description = schema.get("description", "")
        output = []

        if description:
            output.append(f"{indent}/// <summary>")
            output.append(f"{indent}/// {description}")
            output.append(f"{indent}/// </summary>")

        # Add JsonConverter attribute for string enums
        if schema.get("type") == "string":
            output.append(f"{indent}[JsonConverter(typeof(JsonStringEnumConverter))]")

        output.append(f"{indent}public enum {title}")
        output.append(f"{indent}{{")

        enum_values = schema.get("enum", [])
        enum_descriptions = schema.get("enumDescriptions", {})
        enum_names = schema.get("enumNames", {})

        for i, value in enumerate(enum_values):
            member_name = enum_member_name(enum_names, value, i, title)
            desc = enum_member_desc(enum_descriptions, value, i)
            if desc:
                output.append(f"{indent}    /// <summary>")
                output.append(f"{indent}    /// {desc}")
                output.append(f"{indent}    /// </summary>")
            if schema.get("type") == "string":
                output.append(f'{indent}    [JsonPropertyName("{value}")]')
            comma = "," if i < len(enum_values) - 1 else ""
            if schema.get("type") == "string":
                output.append(f"{indent}    {member_name}{comma}")
            else:
                output.append(f"{indent}    {member_name} = {value}{comma}")

        output.append(f"{indent}}}")
        return "\n".join(output)

    @staticmethod
    def _generate_class(
        schema: Dict[str, Any],
        indent_level: int,
        ref_resolver: Optional[SchemaRefResolver] = None,
    ) -> str:
        """Generate a C# class from a schema"""
        indent = "    " * indent_level
        title = schema.get("title", "").replace(" ", "")
        if not title:
            title = "Root"

        description = schema.get("description", "")
        output = []

        if description:
            output.append(f"{indent}/// <summary>")
            output.append(f"{indent}/// {description}")
            output.append(f"{indent}/// </summary>")

        output.append(f"{indent}public class {title}")
        output.append(f"{indent}{{")

        for prop_name, prop_schema in schema.get("properties", {}).items():
            # Convert snake_case to PascalCase for property names
            prop_pascal_case = to_pascal_case(prop_name)

            prop_desc = prop_schema.get("description", "")
            cs_type = CSharpGenerator._get_cs_type(prop_schema, prop_name, ref_resolver)

            if prop_desc:
                output.append(f"{indent}    /// <summary>")
                output.append(f"{indent}    /// {prop_desc}")
                output.append(f"{indent}    /// </summary>")

            output.append(f'{indent}    [JsonPropertyName("{prop_name}")]')

            # Add validation attributes for min/max constraints
            min_value = prop_schema.get("minimum")
            max_value = prop_schema.get("maximum")
            exclusive_min = prop_schema.get("exclusiveMinimum")
            exclusive_max = prop_schema.get("exclusiveMaximum")

            # Add System.ComponentModel.DataAnnotations validation attributes
            prop_type = prop_schema.get("type", "")
            if prop_type in ["integer", "number"]:
                if min_value is not None:
                    output.append(f"{indent}    [Range({min_value}, double.MaxValue)]")
                if max_value is not None:
                    output.append(f"{indent}    [Range(double.MinValue, {max_value})]")
                if exclusive_min is not None:
                    # Exclusive minimum isn't directly supported - would need custom validator
                    pass
                if exclusive_max is not None:
                    # Exclusive maximum isn't directly supported - would need custom validator
                    pass

            # Check if property is required
            is_required = prop_name in schema.get("required", [])

            # Add default value if provided
            default_value = prop_schema.get("default")
            default_str = ""
            if default_value is not None:
                if isinstance(default_value, str):
                    default_str = f' = "{default_value}";'
                elif isinstance(default_value, bool):
                    default_str = f" = {str(default_value).lower()};"
                else:
                    default_str = f" = {default_value};"
            elif is_required:
                default_str = " = default!;"

            if is_required:
                output.append(
                    f"{indent}    public {cs_type} {prop_pascal_case} {{ get; set; }}{default_str}"
                )
            else:
                if default_value is not None:
                    output.append(
                        f"{indent}    public {cs_type}? {prop_pascal_case} {{ get; set; }}{default_str}"
                    )
                else:
                    output.append(
                        f"{indent}    public {cs_type}? {prop_pascal_case} {{ get; set; }}"
                    )

        output.append(f"{indent}}}")

        return "\n".join(output)

    @staticmethod
    def _get_cs_type(
        prop_schema: Dict[str, Any],
        name: str,
        ref_resolver: Optional[SchemaRefResolver] = None,
    ) -> str:
        """Convert JSON schema type to C# type"""
        # Handle references
        if "$ref" in prop_schema and ref_resolver:
            try:
                ref_path = prop_schema["$ref"]

                # Handle definition references within the same file
                if ref_path.startswith("#/definitions/"):
                    def_name = ref_path.split("/")[-1]
                    return def_name

                # Handle direct external references
                if not ref_path.startswith("#"):
                    # Get type name from resolver's mapping
                    if hasattr(ref_resolver, "get_type_for_path"):
                        type_name = ref_resolver.get_type_for_path(ref_path)
                        if type_name:
                            return type_name

                    # Fallback to direct path lookup
                    schema_path = os.path.join(
                        os.path.dirname(ref_resolver.base_path), ref_path
                    )
                    if schema_path in ref_resolver.external_ref_types:
                        return ref_resolver.external_ref_types[schema_path]

                    # Final fallback: extract from filename
                    filename = os.path.basename(ref_path)
                    base_name = os.path.splitext(filename)[0]
                    return to_pascal_case(base_name)

                # Try to resolve the reference
                ref_resolver.resolve_ref(ref_path)  # Just to verify it exists

                # If unable to extract name, fall back to property name
                return to_pascal_case(name)

            except Exception:
                # If reference resolution fails, fall back to string
                pass

        # Handle oneOf, anyOf, allOf, and not schemas
        if "oneOf" in prop_schema:
            # For oneOf in C#, we use object as a base type since there's no union type
            # More sophisticated implementation could generate a custom type with converters
            return "object"

        if "anyOf" in prop_schema:
            # Similar to oneOf for C#
            return "object"

        if "allOf" in prop_schema:
            # For allOf in C#, we'd ideally create a composite type, but as a simplification
            # we'll use the most specific type in the chain (usually last)
            last_schema = prop_schema["allOf"][-1]
            return CSharpGenerator._get_cs_type(last_schema, name, ref_resolver)

        if "not" in prop_schema:
            # C# doesn't have a way to represent "not" schemas directly
            return "object"

        # Handle enum references
        if "enum" in prop_schema:
            enum_name = to_pascal_case(name)
            return enum_name

        schema_type = prop_schema.get("type", "string")
        schema_format = prop_schema.get("format", "")

        if schema_type == "string":
            if schema_format == "date-time":
                return "DateTime"
            elif schema_format == "date":
                return "DateOnly"  # C# 10+ supports DateOnly
            elif schema_format == "time":
                return "TimeOnly"  # C# 10+ supports TimeOnly
            elif schema_format == "duration":
                return "TimeSpan"
            elif schema_format == "uuid":
                return "Guid"
            elif schema_format == "uri" or schema_format == "url":
                return "Uri"
            elif schema_format == "email":
                return "string"
            else:
                return "string"
        elif schema_type == "integer":
            return "long"
        elif schema_type == "number":
            return "double"
        elif schema_type == "boolean":
            return "bool"
        elif schema_type == "array":
            items = prop_schema.get("items", {})
            item_type = CSharpGenerator._get_cs_type(items, f"{name}Item", ref_resolver)
            return f"List<{item_type}>"
        elif schema_type == "object":
            if "properties" in prop_schema:
                # For nested objects with defined properties
                return to_pascal_case(name)
            else:
                # For generic objects without properties, use Dictionary<string, object>
                # Check if additionalProperties is specified
                if "additionalProperties" in prop_schema:
                    add_props = prop_schema["additionalProperties"]
                    if isinstance(add_props, dict) and "type" in add_props:
                        # If additionalProperties specifies a type, use it
                        value_type = CSharpGenerator._get_cs_type(
                            add_props, "value", ref_resolver
                        )
                        return f"Dictionary<string, {value_type}>"

                # Default for objects without defined properties
                return "Dictionary<string, object>"
        else:
            return "object"
