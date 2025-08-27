import os
import sys
import re
from typing import Any, Dict, Optional, List, Set
from ..util.resolver import SchemaRefResolver
from ..util.writer import Writer
from ..util.schema_helpers import (
    enum_member_name,
    enum_member_desc,
    process_definitions_and_nested_types,
)


class PythonGenerator:
    @staticmethod
    def generate(
        schema: Dict[str, Any],
        use_pydantic: bool = True,
        schema_file: Optional[str] = None,
        ref_resolver: Optional[SchemaRefResolver] = None,
        is_main: bool = True,
    ) -> str:
        """Generate Python types from a JSON schema"""
        # Initialize ref resolver if needed
        if ref_resolver is None and schema_file is not None:
            ref_resolver = SchemaRefResolver(schema_file, schema)

        # Track already processed types to avoid duplicates
        processed_types = set()

        # Track used external types
        used_external_types = set()

        # Add header comment
        header = [Writer.generate_header_comment("python")]

        # Track required imports based on used types
        imports = [
            "from typing import List, Dict, Optional, Any, Union",
            "from datetime import datetime, date, time, timedelta",
        ]

        # Scan for and generate imports from external references
        if ref_resolver and schema_file is not None:
            PythonGenerator._find_used_external_types(
                schema, ref_resolver, used_external_types
            )
            if used_external_types:
                ext_imports = PythonGenerator._generate_imports(
                    ref_resolver, schema_file, used_external_types
                )
                imports.extend(ext_imports)

        # Add enum import if schema contains an enum
        if "enum" in schema:
            if use_pydantic:
                imports.append("from enum import Enum")
                imports.append(
                    "from pydantic import BaseModel, Field, AnyUrl, EmailStr, constr"
                )
            else:
                imports.append("from enum import Enum")
                imports.append("from dataclasses import dataclass")
        else:
            # Add conditional imports based on used formats
            for _, prop_schema in schema.get("properties", {}).items():
                schema_format = prop_schema.get("format", "")
                if schema_format == "uuid":
                    imports.append("import uuid")
                    break

            if use_pydantic:
                imports.append(
                    "from pydantic import BaseModel, Field, AnyUrl, EmailStr, conint, confloat"
                )
            else:
                imports.append("from dataclasses import dataclass")

        output = header + ["\n".join(imports), ""]

        # Process definitions but skip any that are imported from external references
        def type_callback(sch, name):
            # Skip processing if it's an external reference
            if ref_resolver:
                # Check if it's a direct external reference
                if (
                    name in schema.get("definitions", {})
                    and "$ref" in schema["definitions"][name]
                    and not schema["definitions"][name]["$ref"].startswith("#")
                ):
                    # This is an external reference, so we don't generate the class
                    return None

                # Check if it's imported via an external reference
                # If the class is imported from another file, we should skip generating it
                imported_types = [
                    imp.split(" ")[-1]
                    for imp in imports
                    if imp.startswith("from .") and " import " in imp
                ]
                if name in imported_types:
                    return None

            return PythonGenerator._generate_type(
                sch, use_pydantic, ref_resolver, processed_types
            )

        definition_outputs = process_definitions_and_nested_types(
            schema, processed_types, ref_resolver, type_callback
        )

        # Filter out None values (which are skipped external references)
        definition_outputs = [out for out in definition_outputs if out is not None]
        output += definition_outputs

        # Process root type - but skip if it's imported
        # Get the root type title
        root_title = schema.get("title", "").replace(" ", "")
        if not root_title:
            root_title = "Root"

        # Check if it's imported
        imported_types = [
            imp.split(" ")[-1]
            for imp in imports
            if imp.startswith("from .") and " import " in imp
        ]
        if root_title in imported_types:
            # Skip generating the root type if it's imported
            pass
        else:
            root_type = PythonGenerator._generate_type(
                schema, use_pydantic, ref_resolver, processed_types
            )
            if root_type:
                output.append(root_type)

        return "\n\n".join(output)

    @staticmethod
    def _find_used_external_types(
        schema: Dict[str, Any],
        ref_resolver: SchemaRefResolver,
        used_external_types: Set[str],
    ) -> None:
        """Find all external types used in the schema"""

        def process_ref(ref_path: str, external_refs: Dict[str, str]) -> None:
            """Helper to process a reference path"""
            if not ref_path.startswith("#"):
                # This is an external reference
                schema_path = os.path.join(
                    os.path.dirname(ref_resolver.base_path), ref_path
                )

                # First add any type from the external_refs mapping
                if ref_path in external_refs:
                    schema_path = external_refs[ref_path]
                    type_name = ref_resolver.external_ref_types.get(schema_path, "")
                    if type_name:
                        used_external_types.add(type_name)

                # Then try to load and process the referenced schema
                try:
                    ref_schema = ref_resolver.resolve_ref(ref_path)
                    if ref_schema:
                        # Add the schema's title if it has one
                        if isinstance(ref_schema, dict):
                            title = ref_schema.get("title", "")
                            if title:
                                title = title.replace(" ", "")
                                used_external_types.add(title)

                        # Process nested references
                        process_schema(ref_schema, external_refs)
                except ValueError:
                    pass  # Skip if we can't resolve the reference

            elif ref_path.startswith("#/definitions/"):
                # This is an internal reference
                def_name = ref_path.split("/")[-1]
                if def_name in ref_resolver.definition_to_external_map:
                    # This definition points to an external schema
                    ext_path = ref_resolver.definition_to_external_map[def_name]
                    process_ref(ext_path, external_refs)

        def process_schema(
            current_schema: Dict[str, Any], external_refs: Dict[str, str]
        ) -> None:
            """Helper to process a schema for references"""
            # Process all properties for references
            for _, prop_schema in current_schema.get("properties", {}).items():
                # Process direct property references
                if "$ref" in prop_schema:
                    process_ref(prop_schema["$ref"], external_refs)

                # Check for arrays that might contain references
                if prop_schema.get("type") == "array" and "items" in prop_schema:
                    items = prop_schema["items"]
                    if isinstance(items, dict):
                        if "$ref" in items:
                            process_ref(items["$ref"], external_refs)
                        elif "properties" in items:
                            process_schema(items, external_refs)

                # Check for nested objects that might have references
                if prop_schema.get("type") == "object" and "properties" in prop_schema:
                    process_schema(prop_schema, external_refs)

            # Process any definitions
            for def_schema in current_schema.get("definitions", {}).values():
                if "$ref" in def_schema:
                    process_ref(def_schema["$ref"], external_refs)
                elif isinstance(def_schema, dict):
                    process_schema(def_schema, external_refs)

        # Start processing with the root schema
        process_schema(schema, ref_resolver.external_refs)

    @staticmethod
    def _generate_imports(
        ref_resolver: SchemaRefResolver,
        _: str,
        used_external_types: Optional[Set[str]] = None,
    ) -> List[str]:
        """Generate Python import statements for external references"""
        imports = []

        # Track processed imports to avoid duplicates
        processed_imports = set()

        def add_import(ref_path: str, type_name: str) -> None:
            """Helper to add an import statement"""
            # Clean up the ref path to get just the base filename
            ref_path = ref_path.replace("./", "").replace("../", "")
            basename = os.path.splitext(os.path.basename(ref_path))[0]
            import_stmt = f"from .{basename} import {type_name}"

            if import_stmt not in processed_imports:
                imports.append(import_stmt)
                processed_imports.add(import_stmt)

        def process_ref(ref_path: str) -> None:
            """Helper to process a reference"""
            if not ref_path.startswith("#"):
                # Get schema path and see if we have an external type for it
                schema_path = os.path.join(
                    os.path.dirname(ref_resolver.base_path), ref_path
                )
                ref_type = ref_resolver.external_ref_types.get(schema_path)

                if ref_type:
                    if used_external_types is None or ref_type in used_external_types:
                        add_import(ref_path, ref_type)

                # Always try to load and check the schema itself
                try:
                    ref_schema = ref_resolver.resolve_ref(ref_path)
                    if ref_schema and isinstance(ref_schema, dict):
                        # First check if it has a title
                        title = ref_schema.get("title", "").replace(" ", "")
                        if title:
                            if (
                                used_external_types is None
                                or title in used_external_types
                            ):
                                add_import(ref_path, title)

                        # Process nested references
                        process_schema(ref_schema)
                except ValueError:
                    pass  # Skip if we can't resolve the reference

        def process_schema(schema: Dict[str, Any]) -> None:
            """Helper to process a schema for references"""
            # Process properties
            for _, prop_schema in schema.get("properties", {}).items():
                # Check direct property references
                if "$ref" in prop_schema:
                    process_ref(prop_schema["$ref"])

                    # Also check if the referenced schema needs processing
                    try:
                        ref_schema = ref_resolver.resolve_ref(prop_schema["$ref"])
                        if ref_schema and isinstance(ref_schema, dict):
                            process_schema(ref_schema)
                    except ValueError:
                        pass

                # Check array items for references
                if prop_schema.get("type") == "array" and "items" in prop_schema:
                    items = prop_schema["items"]
                    if isinstance(items, dict):
                        if "$ref" in items:
                            process_ref(items["$ref"])
                        elif "properties" in items:
                            process_schema(items)

                # Check nested objects
                if prop_schema.get("type") == "object" and "properties" in prop_schema:
                    process_schema(prop_schema)

        # Process schema and its definitions
        for ref_path, schema_path in ref_resolver.external_refs.items():
            type_name = ref_resolver.external_ref_types.get(schema_path, "")
            if type_name:
                if used_external_types is None or type_name in used_external_types:
                    add_import(ref_path, type_name)

        # Process the root schema and its references
        if ref_resolver.root_schema:
            process_schema(ref_resolver.root_schema)

        # Process all referenced schemas
        if ref_resolver.loaded_schemas:
            for schema in ref_resolver.loaded_schemas.values():
                process_schema(schema)

        return sorted(imports)

    @staticmethod
    def _generate_type(
        schema: Dict[str, Any],
        use_pydantic: bool,
        ref_resolver: Optional[SchemaRefResolver] = None,
        processed_types: Optional[set] = None,
    ) -> str:
        """Generate a single Python type from a schema"""
        if processed_types is None:
            processed_types = set()

        title = schema.get("title", "").replace(" ", "")
        if not title:
            title = "Root"

        description = schema.get("description", "")
        required = schema.get("required", [])

        # Handle enum type
        if "enum" in schema:
            # Generate an enum class
            output = []
            enum_values = schema.get("enum", [])
            enum_descriptions = schema.get("enumDescriptions", {})
            enum_names = schema.get("enumNames", {})

            # Use enumNames for member names for both string and integer enums
            if use_pydantic:
                if schema.get("type") == "string":
                    output.append(f"class {title}(str, Enum):")
                else:
                    output.append(f"class {title}(Enum):")

                # Add class docstring under the class declaration
                if description:
                    output.append(f'    """{description}"""')
                if not enum_values:
                    output.append("    pass")
                    return "\n".join(output)
                for i, value in enumerate(enum_values):
                    enum_name = enum_member_name(enum_names, value, i, title)
                    desc = enum_member_desc(enum_descriptions, value, i)
                    if isinstance(value, str):
                        output.append(f"    {enum_name} = '{value}'")
                    else:
                        output.append(f"    {enum_name} = {value}")

                    # Add enum value description as docstring instead of comment
                    if desc:
                        output.append(f'    """{desc}"""')
            else:
                output.append(f"class {title}(Enum):")
                # Add class docstring under the class declaration
                if description:
                    output.append(f'    """{description}"""')

                if not enum_values:
                    output.append("    pass")
                    return "\n".join(output)
                for i, value in enumerate(enum_values):
                    enum_name = enum_member_name(enum_names, value, i, title)
                    desc = enum_member_desc(enum_descriptions, value, i)
                    if isinstance(value, str):
                        output.append(f"    {enum_name} = '{value}'")
                    else:
                        output.append(f"    {enum_name} = {value}")

                    # Add enum value description as docstring instead of comment
                    if desc:
                        output.append(f'    """{desc}"""')
            return "\n".join(output)

        if use_pydantic:
            output = []
            output.append(f"class {title}(BaseModel):")

            # Add class docstring under the class declaration with proper indentation
            if description:
                output.append(f'    """{description}"""')

            if not schema.get("properties"):
                output.append("    pass")
                return "\n".join(output)

            for prop_name, prop_schema in schema.get("properties", {}).items():
                field_type = PythonGenerator._get_python_type(
                    prop_schema, prop_name, use_pydantic, ref_resolver
                )

                field_desc = prop_schema.get("description", "")
                is_required = prop_name in required

                # Get min/max constraints if present
                min_value = prop_schema.get("minimum")
                max_value = prop_schema.get("maximum")
                exclusive_min = prop_schema.get("exclusiveMinimum")
                exclusive_max = prop_schema.get("exclusiveMaximum")

                # Get default value if present
                default_value = prop_schema.get("default")

                # Build the Field constraints
                field_params = []

                # Handle default value
                if default_value is not None:
                    if isinstance(default_value, str):
                        field_params.append(f'default="{default_value}"')
                    else:
                        field_params.append(f"default={default_value}")
                elif not is_required:
                    field_params.append("default=None")
                else:
                    field_params.append("...")

                # Handle description
                if field_desc:
                    # Escape quotes in field descriptions to avoid syntax errors
                    field_desc = field_desc.replace('"', '\\"')
                    field_params.append(f'description="{field_desc}"')

                # Handle min/max constraints
                if min_value is not None:
                    field_params.append(f"ge={min_value}")
                if max_value is not None:
                    field_params.append(f"le={max_value}")
                if exclusive_min is not None:
                    field_params.append(f"gt={exclusive_min}")
                if exclusive_max is not None:
                    field_params.append(f"lt={exclusive_max}")

                # Combine field params
                field_param_str = ", ".join(field_params)

                # Create the field definition
                if not is_required:
                    output.append(
                        f"    {prop_name}: Optional[{field_type}] = Field({field_param_str})"
                    )
                else:
                    output.append(
                        f"    {prop_name}: {field_type} = Field({field_param_str})"
                    )

                # Add field docstring with proper indentation
                if field_desc:
                    field_desc_formatted = field_desc.replace("\n", " ")
                    output.append(f'    """{field_desc_formatted}"""')

            # Add Config class
            output.extend(["", "    class Config:", '        extra = "ignore"'])
        else:
            output = []
            output.append("@dataclass")
            output.append(f"class {title}:")

            # Add class docstring under the class declaration with proper indentation
            if description:
                output.append(f'    """{description}"""')

            if not schema.get("properties"):
                output.append("    pass")
                return "\n".join(output)

            for prop_name, prop_schema in schema.get("properties", {}).items():
                field_type = PythonGenerator._get_python_type(
                    prop_schema, prop_name, use_pydantic, ref_resolver
                )

                field_desc = prop_schema.get("description", "")
                is_required = prop_name in required

                # Get default value if present
                default_value = prop_schema.get("default")

                # Get min/max constraints if present (we'll add these in comments for dataclasses)
                min_value = prop_schema.get("minimum")
                max_value = prop_schema.get("maximum")
                exclusive_min = prop_schema.get("exclusiveMinimum")
                exclusive_max = prop_schema.get("exclusiveMaximum")

                # Build constraints comments if needed
                constraints = []
                if min_value is not None:
                    constraints.append(f"minimum: {min_value}")
                if max_value is not None:
                    constraints.append(f"maximum: {max_value}")
                if exclusive_min is not None:
                    constraints.append(f"exclusive minimum: {exclusive_min}")
                if exclusive_max is not None:
                    constraints.append(f"exclusive maximum: {exclusive_max}")

                constraint_str = ", ".join(constraints)
                if constraint_str:
                    constraint_str = f" ({constraint_str})"

                # Add field with appropriate default value
                if is_required and default_value is None:
                    output.append(f"    {prop_name}: {field_type}")
                else:
                    if default_value is not None:
                        if isinstance(default_value, str):
                            output.append(
                                f'    {prop_name}: {field_type} = "{default_value}"'
                            )
                        else:
                            output.append(
                                f"    {prop_name}: {field_type} = {default_value}"
                            )
                    else:
                        output.append(f"    {prop_name}: Optional[{field_type}] = None")

                # Add field docstring with proper indentation
                if field_desc or constraint_str:
                    doc = field_desc.replace("\n", " ") if field_desc else ""
                    doc += constraint_str
                    output.append(f'    """{doc}"""')

        return "\n".join(output)

    @staticmethod
    def _get_python_type(
        prop_schema: Dict[str, Any],
        name: str,
        use_pydantic: bool,
        ref_resolver: Optional[SchemaRefResolver] = None,
    ) -> str:
        """Convert JSON schema type to Python type"""
        # Handle references
        if "$ref" in prop_schema and ref_resolver:
            ref_path = prop_schema["$ref"]
            try:
                # First try to resolve the referenced schema
                ref_schema = ref_resolver.resolve_ref(ref_path)
                if ref_schema and isinstance(ref_schema, dict):
                    title = ref_schema.get("title", "")
                    if title:
                        return title.replace(" ", "")

                # If we couldn't get a title, try looking up in external_ref_types
                if not ref_path.startswith("#"):
                    schema_path = os.path.join(
                        os.path.dirname(ref_resolver.base_path), ref_path
                    )
                    if schema_path in ref_resolver.external_ref_types:
                        return ref_resolver.external_ref_types[schema_path]
                elif ref_path.startswith("#/definitions/"):
                    return ref_path.split("/")[-1]

                # If still nothing, try to construct a type name from the file
                if not ref_path.startswith("#"):
                    filename = os.path.basename(ref_path)
                    base_name = os.path.splitext(filename)[0]
                    return "".join(x.capitalize() for x in base_name.split("_"))

                # As a last resort, use the property name
                return "".join(x.capitalize() for x in name.split("_"))

            except ValueError:
                print(
                    f"Warning: Unable to resolve reference {prop_schema['$ref']}",
                    file=sys.stderr,
                )

        # Handle oneOf, anyOf, allOf, and not
        if "oneOf" in prop_schema:
            # For oneOf, create a Union type of all possible types
            types = [
                PythonGenerator._get_python_type(
                    schema, f"{name}Option{i}", use_pydantic, ref_resolver
                )
                for i, schema in enumerate(prop_schema["oneOf"])
            ]
            return f"Union[{', '.join(types)}]"

        if "anyOf" in prop_schema:
            # For anyOf, similar to oneOf but semantically different (can match multiple schemas)
            types = [
                PythonGenerator._get_python_type(
                    schema, f"{name}Option{i}", use_pydantic, ref_resolver
                )
                for i, schema in enumerate(prop_schema["anyOf"])
            ]
            return f"Union[{', '.join(types)}]"

        if "allOf" in prop_schema:
            # For allOf, we'd ideally create an intersection type, but Python doesn't have that
            # So we'll use the most specific type (usually the last one in the allOf list)
            # This is a simplification - a proper implementation would merge the schemas
            last_schema = prop_schema["allOf"][-1]
            return PythonGenerator._get_python_type(
                last_schema, name, use_pydantic, ref_resolver
            )

        if "not" in prop_schema:
            # Python doesn't have a direct way to represent "not" schemas
            # We'll just use Any as a fallback
            return "Any"

        schema_type = prop_schema.get("type", "string")
        schema_format = prop_schema.get("format", "")

        if schema_type == "string":
            if schema_format == "date-time":
                return "datetime"
            elif schema_format == "date":
                return "date"
            elif schema_format == "time":
                return "time"
            elif schema_format == "duration":
                return "timedelta"
            elif schema_format == "uuid":
                return "uuid.UUID"
            elif (schema_format == "uri" or schema_format == "url") and use_pydantic:
                return "AnyUrl"
            elif schema_format == "email" and use_pydantic:
                return "EmailStr"
            else:
                return "str"
        elif schema_type == "integer":
            return "int"
        elif schema_type == "number":
            return "float"
        elif schema_type == "boolean":
            return "bool"
        elif schema_type == "array":
            items = prop_schema.get("items", {})

            # Handle references in array items
            if "$ref" in items and ref_resolver:
                ref_path = items["$ref"]
                # If external reference, use the type from the import
                if not ref_path.startswith("#"):
                    schema_path = os.path.join(
                        os.path.dirname(ref_resolver.base_path), ref_path
                    )
                    if schema_path in ref_resolver.external_ref_types:
                        return f"List[{ref_resolver.external_ref_types[schema_path]}]"
                elif ref_path.startswith("#/definitions/"):
                    type_name = ref_path.split("/")[-1]
                    return f"List[{type_name}]"

            # If not a reference or couldn't resolve, use the default behavior
            item_type = PythonGenerator._get_python_type(
                items, f"{name}Item", use_pydantic, ref_resolver
            )
            return f"List[{item_type}]"
        elif schema_type == "object":
            if "properties" in prop_schema:
                # For nested objects with defined properties
                return "".join(x.capitalize() for x in name.split("_"))
            else:
                # For objects without defined properties
                # Check if additionalProperties is specified
                if "additionalProperties" in prop_schema:
                    add_props = prop_schema["additionalProperties"]
                    if isinstance(add_props, dict) and "type" in add_props:
                        # If additionalProperties specifies a type, use it
                        value_type = PythonGenerator._get_python_type(
                            add_props, "value", use_pydantic, ref_resolver
                        )
                        return f"Dict[str, {value_type}]"

                # Default for generic objects
                return "Dict[str, Any]"
        else:
            return "Any"

    @staticmethod
    def generate_model_init_exports(model_dir: str) -> None:
        """Generate __init__.py with type exports for all model classes in the directory.

        This function analyzes all Python model files in the specified directory
        and generates a proper __init__.py that exports all model classes for
        easy importing and IDE autocompletion.

        Args:
            model_dir: Directory containing the generated model files
        """
        print(f"Generating __init__.py with type exports for models in {model_dir}...")

        # Find all Python files (excluding __init__.py)
        py_files = []
        for file in os.listdir(model_dir):
            if file.endswith(".py") and file != "__init__.py":
                py_files.append(os.path.join(model_dir, file))

        # Create a dict to store all classes to export from each module
        exports = {}

        # Process each file to extract classes
        for py_file in py_files:
            module_name = os.path.basename(py_file).split(".")[0]
            exports[module_name] = set()

            try:
                # Read the file content
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Look for Pydantic class definitions
                pydantic_pattern = r"class\s+([a-zA-Z0-9_]+)\s*\(\s*BaseModel\s*\)"
                for cls_match in re.finditer(pydantic_pattern, content):
                    class_name = cls_match.group(1)
                    if not class_name.startswith("_"):  # Skip private classes
                        exports[module_name].add(class_name)

                # Look for dataclass definitions
                dataclass_pattern = r"@dataclass\s*\n\s*class\s+([a-zA-Z0-9_]+)"
                for cls_match in re.finditer(dataclass_pattern, content):
                    class_name = cls_match.group(1)
                    if not class_name.startswith("_"):  # Skip private classes
                        exports[module_name].add(class_name)

                # Look for enum definitions
                enum_pattern = r"class\s+([a-zA-Z0-9_]+)\s*\(\s*(str\s*,\s*)?Enum\s*\)"
                for cls_match in re.finditer(enum_pattern, content):
                    class_name = cls_match.group(1)
                    if not class_name.startswith("_"):  # Skip private classes
                        exports[module_name].add(class_name)

            except (OSError, IOError) as e:
                print(f"Error reading file {py_file}: {e}", file=sys.stderr)
            except re.error as e:
                print(
                    f"Error in regex pattern when processing {py_file}: {e}",
                    file=sys.stderr,
                )

        # Create the __init__.py content
        init_content = [
            "# Auto-generated model exports",
            "# This file was automatically generated to export all models for easy importing",
            "",
        ]

        # Add imports for all modules to make them available in the package
        init_content.append("# Import all model modules")
        init_content.append("try:")
        for module_name in sorted(exports.keys()):
            init_content.append(f"    from . import {module_name}")
        init_content.extend(
            [
                "except ImportError as e:",
                "    import sys",
                '    print(f"Warning: Some model modules could not be imported: {e}", file=sys.stderr)',
                "",
            ]
        )

        # Add __all__ to define what's exported
        init_content.append("# Define what gets imported with 'from models import *'")
        init_content.append("__all__ = [")

        # Include all module names
        for module_name in sorted(exports.keys()):
            init_content.append(f"    '{module_name}',")

        # Include all class names
        for module_name in sorted(exports.keys()):
            for class_name in sorted(exports[module_name]):
                init_content.append(f"    '{class_name}',")

        init_content.append("]")
        init_content.append("")

        # Add re-exports for convenience and IDE support
        init_content.append(
            "# Re-export all model classes for easy importing and IDE autocompletion"
        )
        for module_name in sorted(exports.keys()):
            if exports[module_name]:  # Only add imports for modules with classes
                init_content.append(f"from .{module_name} import (")
                for class_name in sorted(exports[module_name]):
                    init_content.append(f"    {class_name},")
                init_content.append(")")

        # Write the __init__.py file
        init_file = os.path.join(model_dir, "__init__.py")
        with open(init_file, "w", encoding="utf-8") as f:
            f.write("\n".join(init_content))

        print(f"Generated __init__.py with type exports: {init_file}")

    @staticmethod
    def generate_init_file(
        schema: Dict[str, Any], _: str, ref_resolver: SchemaRefResolver
    ) -> str:
        """Generate __init__.py file for the package"""
        imports = []

        # Collect all model classes from the schema definitions
        model_classes: Set[str] = set()

        def collect_model_classes(sch):
            if "definitions" in sch:
                for _, def_schema in sch["definitions"].items():
                    title = def_schema.get("title", "").replace(" ", "")
                    if not title:
                        title = "Root"
                    model_classes.add(title)

                    # Recurse into nested definitions
                    collect_model_classes(def_schema)

        collect_model_classes(schema)

        # Generate import statements for each model class
        for model_class in model_classes:
            # Convert to snake_case for the import statement
            model_class_snake = re.sub(
                "([a-z0-9])([A-Z])", r"\1_\2", model_class
            ).lower()
            imports.append(f"from .{model_class_snake} import {model_class}")

        # Add imports for external references
        for ref_path, schema_path in ref_resolver.external_refs.items():
            # Get the type name from the external schema
            type_name = ref_resolver.external_ref_types.get(schema_path, "")
            if not type_name:
                continue

            # Get basename without extension
            basename = os.path.splitext(os.path.basename(ref_path))[0]

            # Add import statement
            imports.append(f"from .{basename} import {type_name}")

        # Remove duplicates and sort imports
        imports = sorted(set(imports))

        # Generate __init__.py content
        init_content = [Writer.generate_header_comment("python")]
        init_content.append("\n".join(imports))
        return "\n".join(init_content)
