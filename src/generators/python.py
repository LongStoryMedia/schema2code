import os
import sys
import re
import tempfile
from typing import Any, Dict, Optional, List, Set
from ..util.resolver import SchemaRefResolver
from ..util.writer import Writer
from ..util.schema_helpers import (
    enum_member_name,
    enum_member_desc,
    process_definitions_and_nested_types,
    resolve_ref_type_name,
    to_pascal_case,
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
        # Reserved for future behavior differences between main and external schemas
        _unused_is_main = is_main
        # Initialize ref resolver if needed
        if ref_resolver is None and schema_file is not None:
            ref_resolver = SchemaRefResolver(schema_file, schema)

        # Track already processed types to avoid duplicates
        processed_types = set()
        
        # Track all external references found in the schema (for imports)
        external_refs = set()

        # Add header comment
        header = [Writer.generate_header_comment("python")]

        # Track required imports based on used types
        imports = [
            "from typing import List, Dict, Optional, Any, Union, Annotated, Literal",
            "from datetime import datetime, date, time, timedelta",
        ]

        # Collect all external references from the schema before generating
        def collect_refs(sch: Dict[str, Any], resolved_refs: Optional[set] = None) -> None:
            """Recursively collect all $ref fields from schema, including nested refs in resolved schemas"""
            if resolved_refs is None:
                resolved_refs = set()
            if not isinstance(sch, dict):
                return
            
            # Check direct $ref
            if "$ref" in sch and not sch["$ref"].startswith("#"):
                external_refs.add(sch["$ref"])
                # Also resolve this reference and collect refs from within it
                if ref_resolver and sch["$ref"] not in resolved_refs:
                    try:
                        resolved_refs.add(sch["$ref"])
                        resolved = ref_resolver.resolve_ref(sch["$ref"])
                        if isinstance(resolved, dict):
                            collect_refs(resolved, resolved_refs)
                    except Exception:
                        pass
            
            # Check properties
            for _, prop_schema in sch.get("properties", {}).items():
                collect_refs(prop_schema, resolved_refs)
            
            # Check array items
            if "items" in sch:
                collect_refs(sch["items"], resolved_refs)
            
            # Check composition keywords
            for comp_key in ["allOf", "anyOf", "oneOf"]:
                if comp_key in sch:
                    for item in sch[comp_key]:
                        collect_refs(item, resolved_refs)
            
            # Check definitions
            for _, def_schema in sch.get("definitions", {}).items():
                collect_refs(def_schema, resolved_refs)
        
        collect_refs(schema)
        
        # When schemas use allOf to merge properties from other schemas,
        # we need to import any nested types defined in those referenced modules
        # Get nested types by analyzing merged schemas from allOf
        nested_types_from_refs = {}  # module -> set of type names
        
        for comp_key in ["allOf", "anyOf", "oneOf"]:
            if comp_key in schema:
                for item in schema[comp_key]:
                    if isinstance(item, dict) and "$ref" in item:
                        ref_path = item["$ref"]
                        if not ref_path.startswith("#") and ref_resolver:
                            try:
                                module_name = ref_path.replace(".yaml", "").replace(".json", "").replace("-", "_")
                                resolved = ref_resolver.resolve_ref(ref_path)
                                
                                if isinstance(resolved, dict):
                                    # Get the main type name from the resolved schema's title
                                    # Use consistent to_pascal_case normalization
                                    main_type_title_raw = resolved.get("title", "")
                                    if main_type_title_raw:
                                        main_type_title = to_pascal_case(main_type_title_raw)
                                    else:
                                        import os
                                        main_type_title = to_pascal_case(os.path.splitext(os.path.basename(ref_path))[0])
                                    
                                    # Now collect nested types by looking at properties
                                    # Use property names (via to_pascal_case) like schema_helpers does, not titles
                                    nested_types = set()
                                    for prop_name, prop_schema in resolved.get("properties", {}).items():
                                        if isinstance(prop_schema, dict):
                                            # Check for inline objects with properties
                                            if prop_schema.get("type") == "object" and "properties" in prop_schema:
                                                # Always use property name, matching schema_helpers behavior
                                                type_name = to_pascal_case(prop_name)
                                                nested_types.add(type_name)
                                            
                                            # Check for array items
                                            elif prop_schema.get("type") == "array" and "items" in prop_schema:
                                                items = prop_schema["items"]
                                                if isinstance(items, dict) and items.get("type") == "object":
                                                    # Array items generate {PropName}Item type name
                                                    type_name = f"{to_pascal_case(prop_name)}Item"
                                                    nested_types.add(type_name)
                                                    # Also check nested objects within array items
                                                    for item_prop_name, item_prop_schema in items.get("properties", {}).items():
                                                        if isinstance(item_prop_schema, dict) and item_prop_schema.get("type") == "object" and "properties" in item_prop_schema:
                                                            # Use property name like schema_helpers does
                                                            nested_type_name = to_pascal_case(item_prop_name)
                                                            nested_types.add(nested_type_name)
                                    
                                    if nested_types:
                                        nested_types_from_refs[module_name] = nested_types
                            except Exception:
                                pass
        
        # Check properties for allOf patterns too (not just root-level)
        for prop_name, prop_schema in schema.get("properties", {}).items():
            if isinstance(prop_schema, dict):
                # Check array items with allOf
                if prop_schema.get("type") == "array" and "items" in prop_schema:
                    items = prop_schema["items"]
                    if isinstance(items, dict) and "allOf" in items:
                        for allof_item in items.get("allOf", []):
                            if isinstance(allof_item, dict) and "$ref" in allof_item:
                                ref_path = allof_item["$ref"]
                                if not ref_path.startswith("#") and ref_resolver:
                                    try:
                                        module_name = ref_path.replace(".yaml", "").replace(".json", "").replace("-", "_")
                                        resolved = ref_resolver.resolve_ref(ref_path)
                                        
                                        if isinstance(resolved, dict):
                                            # Collect nested types from this referenced schema
                                            nested_types = set()
                                            for ref_prop_name, ref_prop_schema in resolved.get("properties", {}).items():
                                                if isinstance(ref_prop_schema, dict):
                                                    if ref_prop_schema.get("type") == "object" and "properties" in ref_prop_schema:
                                                        # Use property name like schema_helpers does
                                                        type_name = to_pascal_case(ref_prop_name)
                                                        nested_types.add(type_name)
                                                    
                                                    elif ref_prop_schema.get("type") == "array" and "items" in ref_prop_schema:
                                                        ref_items = ref_prop_schema["items"]
                                                        if isinstance(ref_items, dict) and ref_items.get("type") == "object" and "properties" in ref_items:
                                                            # Array items are named {PropName}Item
                                                            type_name = f"{to_pascal_case(ref_prop_name)}Item"
                                                            nested_types.add(type_name)
                                                    
                                                    # Also check for composition keywords (anyOf, oneOf) with inline objects
                                                    for comp_key in ["anyOf", "oneOf"]:
                                                        if comp_key in ref_prop_schema:
                                                            for i, schema_option in enumerate(ref_prop_schema[comp_key]):
                                                                if isinstance(schema_option, dict) and schema_option.get("type") == "object" and "properties" in schema_option:
                                                                    # Use property name for inline objects in composition, like schema_helpers does
                                                                    type_name = to_pascal_case(ref_prop_name)
                                                                    nested_types.add(type_name)
                                            
                                            if nested_types:
                                                nested_types_from_refs[module_name] = nested_types
                                    except Exception:
                                        pass
        
        # Generate imports from collected external references
        # Only import the main type from each referenced schema
        # Nested types should be referenced within their parent module as needed
        for ref_path in sorted(external_refs):
            actual_type_name = resolve_ref_type_name(
                ref_path, ref_resolver
            )

            # Module name in snake_case
            module_name = ref_path.replace(".yaml", "").replace(".json", "").replace("-", "_")
            
            import_stmt = f"from .{module_name} import {actual_type_name}"
            imports.append(import_stmt)
            
            # Also import nested types from this module if we identified any
            if module_name in nested_types_from_refs:
                for nested_type in sorted(nested_types_from_refs[module_name]):
                    if nested_type != actual_type_name:  # Don't duplicate the main type
                        nested_import = f"from .{module_name} import {nested_type}"
                        if nested_import not in imports:
                            imports.append(nested_import)
                        # Mark this imported nested type as already processed so it won't be generated locally
                        processed_types.add(nested_type)

        # Scan for and generate imports from external references
        if ref_resolver and schema_file is not None:
            PythonGenerator._find_used_external_types(
                schema, ref_resolver, set()  # We already have external_refs, just for compatibility
            )

        # Add enum import if schema contains an enum
        if "enum" in schema:
            if use_pydantic:
                imports.append("from enum import Enum")
                imports.append(
                    "from pydantic import BaseModel, Field, AnyUrl, EmailStr, constr"
                )
            else:
                imports.append("from enum import Enum")
                imports.append("from dataclasses import dataclass, field")
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
                imports.append("from dataclasses import dataclass, field")

        # Don't build output with imports yet - we'll add them later after collecting all imports
        output = []

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

                # Also check if this name corresponds to an external reference in properties
                for prop_name, prop_schema in schema.get("properties", {}).items():
                    if "$ref" in prop_schema and not prop_schema["$ref"].startswith(
                        "#"
                    ):
                        # Convert property name to PascalCase to match potential type name
                        potential_type_name = to_pascal_case(prop_name)
                        if potential_type_name == name:
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
        # Get the root type title using consistent normalization
        root_title = schema.get("title", "")
        if root_title:
            root_title = to_pascal_case(root_title)
        else:
            root_title = "Root"
        
        root_type_is_model = False

        # Check if it's imported
        imported_types = [
            imp.split(" ")[-1]
            for imp in imports
            if imp.startswith("from .") and " import " in imp
        ]
        if root_title in imported_types or root_title in processed_types:
            # Skip generating the root type if it's imported or already processed as a nested type
            pass
        else:
            root_type = PythonGenerator._generate_type(
                schema, use_pydantic, ref_resolver, processed_types
            )
            if root_type:
                output.append(root_type)
                # Track if the root type is a BaseModel (not a Union alias or enum)
                if "BaseModel" in root_type:
                    root_type_is_model = True
        
        # Add model_rebuild() call for complex models with forward references
        # This is needed when using 'from __future__ import annotations'
        # Add it when the root type is a BaseModel and there are nested/definition types
        if use_pydantic and root_type_is_model and definition_outputs:
            output.append(f"{root_title}.model_rebuild()")

        # Add future annotations import at the very beginning for forward references
        imports.insert(0, "from __future__ import annotations")
        
        # Prepend header and imports to output
        final_output = header + ["\n".join(imports), ""] + output
        return "\n\n".join(final_output)

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
                                title = title.replace(" ", "").replace("-", "_")
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
                        # Check for anyOf, oneOf, allOf in array items
                        for schema_key in ["anyOf", "oneOf", "allOf"]:
                            if schema_key in items:
                                for sub_schema in items[schema_key]:
                                    if isinstance(sub_schema, dict):
                                        if "$ref" in sub_schema:
                                            process_ref(sub_schema["$ref"], external_refs)
                                        elif "properties" in sub_schema:
                                            process_schema(sub_schema, external_refs)

                # Check for nested objects that might have references
                if prop_schema.get("type") == "object" and "properties" in prop_schema:
                    process_schema(prop_schema, external_refs)

                # Check for anyOf, oneOf, allOf
                for schema_key in ["anyOf", "oneOf", "allOf"]:
                    if schema_key in prop_schema:
                        for sub_schema in prop_schema[schema_key]:
                            if isinstance(sub_schema, dict):
                                if "$ref" in sub_schema:
                                    process_ref(sub_schema["$ref"], external_refs)
                                elif "properties" in sub_schema:
                                    process_schema(sub_schema, external_refs)

            # Process any definitions
            for def_schema in current_schema.get("definitions", {}).values():
                if "$ref" in def_schema:
                    process_ref(def_schema["$ref"], external_refs)
                elif isinstance(def_schema, dict):
                    process_schema(def_schema, external_refs)

            # Handle composition keywords at root level (allOf, anyOf, oneOf)
            for comp_key in ["allOf", "anyOf", "oneOf"]:
                if comp_key in current_schema:
                    for item in current_schema[comp_key]:
                        if isinstance(item, dict):
                            if "$ref" in item:
                                process_ref(item["$ref"], external_refs)
                            elif "properties" in item:
                                process_schema(item, external_refs)

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
            # Sanitize basename to use underscores instead of hyphens (valid Python module names)
            basename = basename.replace("-", "_")
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
                        # First check if it has a title using consistent normalization
                        title_raw = ref_schema.get("title", "")
                        if title_raw:
                            title = to_pascal_case(title_raw)
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

            # Handle composition keywords (allOf, anyOf, oneOf) at any level
            for comp_key in ["allOf", "anyOf", "oneOf"]:
                if comp_key in schema:
                    for item in schema[comp_key]:
                        if isinstance(item, dict):
                            if "$ref" in item:
                                process_ref(item["$ref"])
                            elif "properties" in item:
                                process_schema(item)

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
            # Create a snapshot of loaded schemas to avoid "dictionary changed size" error
            # when resolve_ref() adds new schemas during iteration
            loaded_schemas_snapshot = list(ref_resolver.loaded_schemas.values())
            for schema in loaded_schemas_snapshot:
                process_schema(schema)

        return sorted(imports)

    @staticmethod
    def _extract_type_names_from_code(code: str) -> Set[str]:
        """Extract referenced type names (PascalCase identifiers) from generated code"""
        import re
        type_names = set()
        
        # Remove docstrings and comments from code before extracting type names
        # This avoids extracting words from documentation
        lines = code.split('\n')
        cleaned_lines = []
        in_docstring = False
        
        for line in lines:
            # Skip lines that are comments
            if line.strip().startswith('#'):
                continue
            
            # Track docstrings
            if '"""' in line or "'''" in line:
                in_docstring = not in_docstring
                continue
            
            # Skip lines inside docstrings
            if not in_docstring:
                cleaned_lines.append(line)
        
        cleaned_code = '\n'.join(cleaned_lines)
        
        # Now find PascalCase identifiers that appear after colons or commas or equals
        # to ensure they're type annotations, not regular words
        # Allow optional whitespace after the delimiter
        pascal_case_pattern = r'(?:[:\[\],=])\s*([A-Z][a-zA-Z0-9_]*)'
        
        # Built-in and common types to exclude
        builtins = {
            'Union', 'Optional', 'List', 'Dict', 'Any', 'Literal', 'Annotated',
            'Field', 'BaseModel', 'Enum', 'Config', 'Tuple', 'Set', 'AnyUrl',
            'EmailStr', 'Annotated', 'Json', 'IPv4Address', 'IPv6Address',
            'UUID', 'URL', 'HttpUrl', 'PostgresDsn', 'RedisDsn',
            'MongoDBDsn', 'ElasticsearchDsn', 'KafkaDsn', 'None'
        }
        
        for match in re.finditer(pascal_case_pattern, cleaned_code):
            name = match.group(1)
            if name not in builtins:
                type_names.add(name)
        
        return type_names

    @staticmethod
    def _add_imports_for_referenced_types(
        code: str, imports: List[str], ref_resolver: Optional[SchemaRefResolver] = None
    ) -> List[str]:
        """Add imports for any type references found in the generated code"""
        type_names = PythonGenerator._extract_type_names_from_code(code)
        
        # Get already imported types
        imported_types = set()
        for imp in imports:
            if " import " in imp:
                # Extract the type name from "from ... import TypeName"
                parts = imp.split(" import ")
                if len(parts) == 2:
                    imported_types.add(parts[1].strip())
        
        # Add imports for referenced types that aren't already imported
        for type_name in sorted(type_names):
            if type_name not in imported_types:
                # Convert type name to module name (PascalCase -> snake_case)
                module_name = re.sub(r'(?<!^)(?=[A-Z])', '_', type_name).lower()
                import_stmt = f"from .{module_name} import {type_name}"
                
                # Check if this import is already in the list (case-insensitive)
                if not any(imp.lower() == import_stmt.lower() for imp in imports):
                    imports.append(import_stmt)
                    imported_types.add(type_name)
        
        return imports

    @staticmethod
    def _merge_composed_schema_properties(
        schema: Dict[str, Any],
        ref_resolver: Optional[SchemaRefResolver] = None,
    ) -> tuple[Dict[str, Any], list]:
        """
        Merge properties from allOf at the root level only.
        anyOf/oneOf are discriminated unions and should NOT merge properties.
        Returns: (merged_properties_dict, required_list)
        """
        merged_properties = {}
        merged_required_set = set()
        
        # Only merge for allOf - anyOf/oneOf are discriminated unions
        if "allOf" in schema:
            for item in schema["allOf"]:
                # Resolve references if needed
                resolved_item = item
                if "$ref" in item and ref_resolver:
                    try:
                        resolved_item = ref_resolver.resolve_ref(item["$ref"])
                    except Exception:
                        continue
                
                # Merge properties from this item (make a copy to avoid modification issues)
                if "properties" in resolved_item:
                    for prop_name, prop_schema in resolved_item["properties"].items():
                        # Make a deep copy to avoid shared references
                        merged_properties[prop_name] = prop_schema.copy() if isinstance(prop_schema, dict) else prop_schema
                
                # Merge required fields (use set to deduplicate)
                if "required" in resolved_item:
                    merged_required_set.update(resolved_item["required"])
        
        return merged_properties, list(merged_required_set)

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

        from ..util.schema_helpers import to_pascal_case
        
        # Always normalize titles using to_pascal_case for consistency
        # This handles conversion of snake_case, spaces, hyphens, and dots uniformly
        title_str = schema.get("title", "")
        if title_str:
            # Always use to_pascal_case to ensure consistent normalization
            # regardless of whether title has spaces, hyphens, dots, etc.
            title = to_pascal_case(title_str)
        else:
            title = "Root"

        description = schema.get("description", "")
        required = schema.get("required", [])
        properties = dict(schema.get("properties", {})) if schema.get("properties") else {}

        # Merge properties from composed schemas (allOf, anyOf, oneOf)
        if (not properties or not required) and ("allOf" in schema or "anyOf" in schema or "oneOf" in schema):
            merged_props, merged_required = PythonGenerator._merge_composed_schema_properties(schema, ref_resolver)
            if merged_props:
                properties = dict(merged_props)  # Make a complete copy
            if merged_required:
                required = merged_required

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
                    # Sanitize enum name to ensure valid Python identifier: replace hyphens and dots with underscores
                    enum_name = enum_name.replace("-", "_").replace(".", "_")
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
                    # Sanitize enum name to ensure valid Python identifier: replace hyphens and dots with underscores
                    enum_name = enum_name.replace("-", "_").replace(".", "_")
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
            
            # Handle discriminated unions (anyOf/oneOf with no properties)
            if not properties and not required and ("anyOf" in schema or "oneOf" in schema):
                union_key = "anyOf" if "anyOf" in schema else "oneOf"
                union_items = schema.get(union_key, [])
                
                # Generate union types from all items (both $ref and inline)
                # Only generate Union if we have items to include
                if union_items:
                    union_types = []
                    for item in union_items:
                        if isinstance(item, dict):
                            if "$ref" in item:
                                ref_path = item["$ref"]
                                if not ref_path.startswith("#"):
                                    type_name = resolve_ref_type_name(
                                        ref_path, ref_resolver
                                    )
                                else:
                                    # Internal reference (#/definitions/...)
                                    type_name = ref_path.split("/")[-1]
                                union_types.append(type_name)
                            elif "enum" in item:
                                # Handle inline enum values
                                enum_values = item.get("enum", [])
                                if enum_values:
                                    if all(isinstance(val, str) for val in enum_values):
                                        # String enums: use Literal type
                                        literal_values = ", ".join(f'"{val}"' for val in enum_values)
                                        union_types.append(f"Literal[{literal_values}]")
                                    else:
                                        # Non-string enums: use Union of the values
                                        if len(enum_values) == 1:
                                            union_types.append(repr(enum_values[0]))
                                        else:
                                            union_vals = ", ".join(repr(val) for val in enum_values)
                                            union_types.append(f"Union[{union_vals}]")
                    
                    # Return a type alias instead of a class
                    if union_types:
                        return f"{title} = Union[{', '.join(union_types)}]"
            
            output.append(f"class {title}(BaseModel):")

            # Add class docstring under the class declaration with proper indentation
            if description:
                output.append(f'    """{description}"""')

            if not properties:
                output.append("    pass")
                return "\n".join(output)

            for prop_name, prop_schema in properties.items():
                # Sanitize property names that contain dots, hyphens, or slashes
                safe_prop_name = prop_name.replace(".", "_").replace("-", "_").replace("/", "_")
                
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
                    if isinstance(default_value, (list, dict)):
                        field_params.append(
                            f"default_factory=lambda: {repr(default_value)}"
                        )
                    elif isinstance(default_value, str):
                        field_params.append(f"default={repr(default_value)}")
                    else:
                        field_params.append(f"default={default_value}")
                elif not is_required:
                    field_params.append("default=None")
                else:
                    field_params.append("...")

                # Handle description
                if field_desc:
                    # Remove newlines and escape quotes in field descriptions to avoid syntax errors
                    # But avoid double-escaping already escaped quotes
                    field_desc = field_desc.replace("\n", " ")
                    # Only escape unescaped quotes (quotes not preceded by backslash)
                    field_desc = field_desc.replace('\\"', '\x00')  # Temporarily replace escaped quotes
                    field_desc = field_desc.replace('"', '\\"')      # Escape unescaped quotes
                    field_desc = field_desc.replace('\x00', '\\"')   # Restore the originally escaped quotes
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

                # Add alias if property name was sanitized
                if safe_prop_name != prop_name:
                    field_params.append(f"alias='{prop_name}'")

                # Combine field params
                field_param_str = ", ".join(field_params)

                # Create the field definition using Annotated with explicit default values
                if not is_required:
                    if default_value is not None:
                        if isinstance(default_value, (list, dict)):
                            # For mutable defaults, we don't set an explicit default on the field
                            # since we're using default_factory in Field()
                            output.append(
                                f"    {safe_prop_name}: Annotated[Optional[{field_type}], Field({field_param_str})]"
                            )
                        elif isinstance(default_value, str):
                            output.append(
                                f"    {safe_prop_name}: Annotated[Optional[{field_type}], Field({field_param_str})] = {repr(default_value)}"
                            )
                        else:
                            output.append(
                                f"    {safe_prop_name}: Annotated[Optional[{field_type}], Field({field_param_str})] = {default_value}"
                            )
                    else:
                        output.append(
                            f"    {safe_prop_name}: Annotated[Optional[{field_type}], Field({field_param_str})] = None"
                        )
                else:
                    output.append(
                        f"    {safe_prop_name}: Annotated[{field_type}, Field({field_param_str})]"
                    )

                # Add field docstring with proper indentation
                if field_desc:
                    field_desc_formatted = field_desc.replace("\n", " ")
                    output.append(f'    """{field_desc_formatted}"""')

            # Add Config class
            output.extend(["", "    class Config:", '        extra = "ignore"'])
        else:
            output = []
            
            # Handle pure discriminated unions (anyOf/oneOf with only $ref items and no properties)
            if not properties and not required and ("anyOf" in schema or "oneOf" in schema):
                union_key = "anyOf" if "anyOf" in schema else "oneOf"
                union_items = schema.get(union_key, [])
                
                # Check if all items are $ref (pure discriminated union)
                if all(isinstance(item, dict) and "$ref" in item for item in union_items):
                    # Generate a Union type alias
                    union_types = []
                    for item in union_items:
                        if "$ref" in item:
                            ref_path = item["$ref"]
                            if not ref_path.startswith("#"):
                                type_name = resolve_ref_type_name(
                                    ref_path, ref_resolver
                                )
                            else:
                                # Internal reference (#/definitions/...)
                                type_name = ref_path.split("/")[-1]
                            union_types.append(type_name)

                    # Return a type alias instead of a class
                    if union_types:
                        return f"{title} = Union[{', '.join(union_types)}]"
            
            output.append("@dataclass")
            output.append(f"class {title}:")

            # Add class docstring under the class declaration with proper indentation
            if description:
                output.append(f'    """{description}"""')

            if not properties:
                output.append("    pass")
                return "\n".join(output)

            for prop_name, prop_schema in properties.items():
                # Sanitize property names that contain dots, hyphens, or slashes
                safe_prop_name = prop_name.replace(".", "_").replace("-", "_").replace("/", "_")
                
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
                    output.append(f"    {safe_prop_name}: {field_type}")
                else:
                    if default_value is not None:
                        if isinstance(default_value, (list, dict)):
                            output.append(
                                f"    {safe_prop_name}: {field_type} = field(default_factory=lambda: {repr(default_value)})"
                            )
                        elif isinstance(default_value, str):
                            output.append(
                                f"    {safe_prop_name}: {field_type} = {repr(default_value)}"
                            )
                        else:
                            output.append(
                                f"    {safe_prop_name}: {field_type} = {default_value}"
                            )
                    else:
                        output.append(f"    {safe_prop_name}: Optional[{field_type}] = None")

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
        from ..util.schema_helpers import to_pascal_case
        
        # Handle inline objects first - if this property is an inline object with properties
        if prop_schema.get("type") == "object" and "properties" in prop_schema:
            # For inline objects, always use the property name for the type name.
            # This ensures consistency with how schema_helpers.process_definitions_and_nested_types
            # generates the class name. The schema's title field is just documentation.
            inline_type_name = to_pascal_case(name)
            return inline_type_name
        
        # Handle references
        if "$ref" in prop_schema and ref_resolver:
            ref_path = prop_schema["$ref"]
            try:
                if not ref_path.startswith("#"):
                    return resolve_ref_type_name(
                        ref_path, ref_resolver
                    )
                elif ref_path.startswith("#/definitions/"):
                    return ref_path.split("/")[-1]

                # As a last resort, use the property name
                return to_pascal_case(name)

            except ValueError:
                print(
                    f"Warning: Unable to resolve reference {prop_schema['$ref']}",
                    file=sys.stderr,
                )

        # Handle oneOf, anyOf, allOf, and not
        if "oneOf" in prop_schema:
            # For oneOf, create a Union type of all possible types
            types = []
            for i, schema in enumerate(prop_schema["oneOf"]):
                # Check if this is an inline object definition
                if isinstance(schema, dict) and schema.get("type") == "object" and "properties" in schema:
                    from ..util.schema_helpers import to_pascal_case
                    # Use schema title if available (matches _generate_type which reads title);
                    # fall back to {PropertyName}Option{i} pattern (matches schema_helpers fallback)
                    if "title" in schema:
                        inline_type_name = to_pascal_case(schema["title"])
                    else:
                        inline_type_name = f"{to_pascal_case(name)}Option{i}" if i > 0 else to_pascal_case(name)
                    types.append(inline_type_name)
                else:
                    types.append(
                        PythonGenerator._get_python_type(
                            schema, f"{name}Option{i}", use_pydantic, ref_resolver
                        )
                    )
            return f"Union[{', '.join(types)}]"

        if "anyOf" in prop_schema:
            # For anyOf, similar to oneOf but semantically different (can match multiple schemas)
            types = []
            for i, schema in enumerate(prop_schema["anyOf"]):
                # Check if this is an inline object definition
                if isinstance(schema, dict) and schema.get("type") == "object" and "properties" in schema:
                    from ..util.schema_helpers import to_pascal_case
                    # Use schema title if available (matches _generate_type which reads title);
                    # fall back to {PropertyName}Option{i} pattern (matches schema_helpers fallback)
                    if "title" in schema:
                        inline_type_name = to_pascal_case(schema["title"])
                    else:
                        inline_type_name = f"{to_pascal_case(name)}Option{i}" if i > 0 else to_pascal_case(name)
                    types.append(inline_type_name)
                else:
                    types.append(
                        PythonGenerator._get_python_type(
                            schema, f"{name}Option{i}", use_pydantic, ref_resolver
                        )
                    )
            return f"Union[{', '.join(types)}]"

        if "allOf" in prop_schema:
            # For allOf, we'd ideally create an intersection type, but Python doesn't have that
            # Check if the last schema is an inline object definition
            last_schema = prop_schema["allOf"][-1]
            if isinstance(last_schema, dict) and last_schema.get("type") == "object" and "properties" in last_schema:
                # Use the generated class name for this inline object (must match schema_helpers naming)
                from ..util.schema_helpers import to_pascal_case
                # Match the naming in schema_helpers.py: {PropertyName}Option0, {PropertyName}Option1, etc.
                # But NOT with "allOf" in the name - allOf merges into a single type
                inline_type_name = to_pascal_case(name)
                return inline_type_name
            else:
                return PythonGenerator._get_python_type(
                    last_schema, name, use_pydantic, ref_resolver
                )

        if "not" in prop_schema:
            # Python doesn't have a direct way to represent "not" schemas
            # We'll just use Any as a fallback
            return "Any"

        schema_type = prop_schema.get("type", "string")
        schema_format = prop_schema.get("format", "")

        # Handle inline enums - check for enum field in the property schema
        if "enum" in prop_schema:
            enum_values = prop_schema["enum"]
            if enum_values:
                # Generate string literal union for enum values
                if all(isinstance(val, str) for val in enum_values):
                    # String enums: use Literal type
                    literal_values = ", ".join(f'"{val}"' for val in enum_values)
                    return f"Literal[{literal_values}]"
                else:
                    # Mixed or non-string enums: use Union type
                    enum_types = []
                    for val in enum_values:
                        if isinstance(val, str):
                            enum_types.append(f'"{val}"')
                        elif isinstance(val, int):
                            enum_types.append(str(val))
                        elif isinstance(val, float):
                            enum_types.append(str(val))
                        elif isinstance(val, bool):
                            enum_types.append(str(val))
                        else:
                            enum_types.append(f'"{val}"')
                    return f"Literal[{', '.join(enum_types)}]"

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
            # For inline objects with titles, prefer the title; otherwise use {PropertyName}Item
            item_name = name + "Item"
            if isinstance(items, dict) and "title" in items:
                item_name = to_pascal_case(items["title"])
            
            item_type = PythonGenerator._get_python_type(
                items, item_name, use_pydantic, ref_resolver
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
            # Convert hyphens to underscores to match the actual filename
            module_name = module_name.replace("-", "_")
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
            "from __future__ import annotations",
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

        # Write the __init__.py file atomically to prevent corruption from parallel writes
        init_file = os.path.join(model_dir, "__init__.py")
        init_dir = os.path.dirname(init_file)
        fd, tmp_path = tempfile.mkstemp(dir=init_dir, suffix=".tmp", prefix="__init__")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(init_content))
            os.replace(tmp_path, init_file)
        except BaseException:
            os.unlink(tmp_path)
            raise

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
                    title_raw = def_schema.get("title", "")
                    if title_raw:
                        title = to_pascal_case(title_raw)
                    else:
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
