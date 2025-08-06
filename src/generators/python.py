import os
import sys
import re
from typing import Any, Dict, Optional, List, Set, Dict
from ..util.resolver import SchemaRefResolver
from ..util.writer import Writer
from ..util.schema_helpers import (
    to_pascal_case,
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
        referenced_by: Optional[str] = None,
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

        # Pre-scan the schema to find all used external references
        # This helps us ensure we generate all needed imports
        if ref_resolver:
            PythonGenerator._find_used_external_types(
                schema, ref_resolver, used_external_types
            )

        # Add imports for external references
        if is_main and ref_resolver and schema_file is not None:
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
                    "from pydantic import BaseModel, Field, AnyUrl, EmailStr"
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
        # Check for references in properties
        for _, prop_schema in schema.get("properties", {}).items():
            if "$ref" in prop_schema:
                ref_path = prop_schema["$ref"]
                if not ref_path.startswith("#"):
                    # This is an external reference, record the type
                    schema_path = os.path.join(
                        os.path.dirname(ref_resolver.base_path), ref_path
                    )
                    type_name = ref_resolver.external_ref_types.get(schema_path, "")
                    if type_name:
                        used_external_types.add(type_name)
                elif ref_path.startswith("#/definitions/"):
                    # This is an internal reference, check if it references an external type
                    def_name = ref_path.split("/")[-1]
                    if def_name in schema.get("definitions", {}):
                        def_schema = schema["definitions"][def_name]
                        if "$ref" in def_schema and not def_schema["$ref"].startswith(
                            "#"
                        ):
                            # This definition references an external type
                            ext_path = def_schema["$ref"]
                            schema_path = os.path.join(
                                os.path.dirname(ref_resolver.base_path), ext_path
                            )
                            type_name = ref_resolver.external_ref_types.get(
                                schema_path, ""
                            )
                            if type_name:
                                used_external_types.add(type_name)

            # Check for arrays that might contain references
            if prop_schema.get("type") == "array" and "items" in prop_schema:
                items = prop_schema["items"]
                if "$ref" in items:
                    ref_path = items["$ref"]
                    if not ref_path.startswith("#"):
                        # This is an external reference in an array
                        schema_path = os.path.join(
                            os.path.dirname(ref_resolver.base_path), ref_path
                        )
                        type_name = ref_resolver.external_ref_types.get(schema_path, "")
                        if type_name:
                            used_external_types.add(type_name)
                    elif ref_path.startswith("#/definitions/"):
                        # Check if this internal reference points to an external reference
                        def_name = ref_path.split("/")[-1]
                        if def_name in schema.get("definitions", {}):
                            def_schema = schema["definitions"][def_name]
                            if "$ref" in def_schema and not def_schema[
                                "$ref"
                            ].startswith("#"):
                                ext_path = def_schema["$ref"]
                                schema_path = os.path.join(
                                    os.path.dirname(ref_resolver.base_path), ext_path
                                )
                                type_name = ref_resolver.external_ref_types.get(
                                    schema_path, ""
                                )
                                if type_name:
                                    used_external_types.add(type_name)

        # Also check definitions section for references
        for def_name, def_schema in schema.get("definitions", {}).items():
            if "$ref" in def_schema and not def_schema["$ref"].startswith("#"):
                # This definition references an external type
                ref_path = def_schema["$ref"]
                schema_path = os.path.join(
                    os.path.dirname(ref_resolver.base_path), ref_path
                )
                type_name = ref_resolver.external_ref_types.get(schema_path, "")
                if type_name:
                    used_external_types.add(type_name)
            elif isinstance(def_schema, dict):
                # Recursively check this definition
                PythonGenerator._find_used_external_types(
                    def_schema, ref_resolver, used_external_types
                )

    @staticmethod
    def _generate_imports(
        ref_resolver: SchemaRefResolver,
        _: str,
        used_external_types: Optional[Set[str]] = None,
    ) -> List[str]:
        """Generate Python import statements for external references"""
        imports = []

        for ref_path, schema_path in ref_resolver.external_refs.items():
            # Get the type name from the external schema
            type_name = ref_resolver.external_ref_types.get(schema_path, "")
            if not type_name:
                continue

            # If we're tracking used types, only import what's actually used
            if used_external_types is not None and type_name not in used_external_types:
                continue

            # Get basename without extension
            basename = os.path.splitext(os.path.basename(ref_path))[0]

            # Add import statement
            imports.append(f"from .{basename} import {type_name}")

        return imports

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

            if description:
                output.append(f'"""{description}"""')

            # Use enumNames for member names for both string and integer enums
            if use_pydantic:
                if schema.get("type") == "string":
                    output.append(f"class {title}(str, Enum):")
                else:
                    output.append(f"class {title}(Enum):")
                if not enum_values:
                    output.append("    pass")
                    return "\n".join(output)
                for i, value in enumerate(enum_values):
                    enum_name = enum_member_name(enum_names, value, i, title)
                    desc = enum_member_desc(enum_descriptions, value, i)
                    desc_str = f"  # {desc}" if desc else ""
                    if isinstance(value, str):
                        output.append(f"    {enum_name} = '{value}'{desc_str}")
                    else:
                        output.append(f"    {enum_name} = {value}{desc_str}")
            else:
                output.append(f"class {title}(Enum):")
                if not enum_values:
                    output.append("    pass")
                    return "\n".join(output)
                for i, value in enumerate(enum_values):
                    enum_name = enum_member_name(enum_names, value, i, title)
                    desc = enum_member_desc(enum_descriptions, value, i)
                    desc_str = f"  # {desc}" if desc else ""
                    if isinstance(value, str):
                        output.append(f"    {enum_name} = '{value}'{desc_str}")
                    else:
                        output.append(f"    {enum_name} = {value}{desc_str}")
            return "\n".join(output)

        if use_pydantic:
            output = []
            if description:
                output.append(f'"""{description}"""')
            output.append(f"class {title}(BaseModel):")

            if not schema.get("properties"):
                output.append("    pass")
                return "\n".join(output)

            for prop_name, prop_schema in schema.get("properties", {}).items():
                field_type = PythonGenerator._get_python_type(
                    prop_schema, prop_name, use_pydantic, ref_resolver
                )

                field_desc = prop_schema.get("description", "")
                is_required = prop_name in required

                # Add field description as a comment for better readability in code
                if field_desc:
                    field_desc_formatted = field_desc.replace("\n", " ")
                    output.append(f"    # {field_desc_formatted}")

                    # Escape quotes in field descriptions to avoid syntax errors
                    field_desc = field_desc.replace('"', '\\"')

                # Use Pydantic's Field for optional fields with descriptions
                if not is_required:
                    if field_desc:
                        output.append(
                            f'    {prop_name}: Optional[{field_type}] = Field(default=None, description="{field_desc}")'
                        )
                    else:
                        output.append(f"    {prop_name}: Optional[{field_type}] = None")
                else:
                    if field_desc:
                        output.append(
                            f'    {prop_name}: {field_type} = Field(..., description="{field_desc}")'
                        )
                    else:
                        output.append(f"    {prop_name}: {field_type}")

            # Add Config class
            output.extend(["", "    class Config:", '        extra = "ignore"'])
        else:
            output = []
            if description:
                output.append(f'"""{description}"""')
            output.append("@dataclass")
            output.append(f"class {title}:")

            if not schema.get("properties"):
                output.append("    pass")
                return "\n".join(output)

            for prop_name, prop_schema in schema.get("properties", {}).items():
                field_type = PythonGenerator._get_python_type(
                    prop_schema, prop_name, use_pydantic
                )

                field_desc = prop_schema.get("description", "")
                is_required = prop_name in required

                if field_desc:
                    field_desc_formatted = field_desc.replace("\n", " ")
                    output.append(f"    # {field_desc_formatted}")

                if is_required:
                    output.append(f"    {prop_name}: {field_type}")
                else:
                    output.append(f"    {prop_name}: Optional[{field_type}] = None")

        return "\n".join(output)

    @staticmethod
    def _get_python_type(
        prop_schema: Dict[str, Any],
        name: str,
        use_pydantic: bool,
        ref_resolver: Optional[SchemaRefResolver] = None,
    ) -> str:
        """Convert JSON schema type to Python type"""
        # Handle external references specifically
        if "$ref" in prop_schema and ref_resolver:
            ref_path = prop_schema["$ref"]
            # If external reference, use the type from the import
            if not ref_path.startswith("#"):
                schema_path = os.path.join(
                    os.path.dirname(ref_resolver.base_path), ref_path
                )
                if schema_path in ref_resolver.external_ref_types:
                    return ref_resolver.external_ref_types[schema_path]

        # Handle references
        if "$ref" in prop_schema and ref_resolver:
            try:
                # Resolve the reference (needed for ref_resolver to track it)
                ref_resolver.resolve_ref(prop_schema["$ref"])

                # Extract type name from reference
                ref_path = prop_schema["$ref"]
                type_name = ""

                if ref_path.startswith("#/definitions/"):
                    type_name = ref_path.split("/")[-1]
                elif not ref_path.startswith("#"):
                    filename = os.path.basename(ref_path)
                    base_name = os.path.splitext(filename)[0]
                    type_name = "".join(x.capitalize() for x in base_name.split("_"))

                if type_name:
                    return type_name

                # If unable to extract name, fall back to property name
                return "".join(x.capitalize() for x in name.split("_"))

            except ValueError:
                print(
                    f"Warning: Unable to resolve reference {prop_schema['$ref']}",
                    file=sys.stderr,
                )

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
