# Helper functions for schema2code generators

def to_pascal_case(name: str) -> str:
    """Convert snake_case or lowerCamelCase to PascalCase."""
    if not name:
        return ""
    parts = name.replace('-', '_').replace('.', '_').replace(' ', '_').split('_')
    return ''.join(x[:1].upper() + x[1:] for x in parts if x)


def to_camel_case(name: str) -> str:
    """Convert snake_case or PascalCase to camelCase."""
    if not name:
        return ""
    # Convert PascalCase to snake_case first
    import re
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    parts = s2.split('_')
    return parts[0] + ''.join(x.capitalize() for x in parts[1:] if x)


def enum_member_name(enum_names, value, i, title=None):
    """Get the enum member name from enumNames or fallback."""
    str_value = str(value)
    if isinstance(enum_names, dict) and str_value in enum_names:
        name = enum_names[str_value]
    elif isinstance(enum_names, list) and i < len(enum_names):
        name = enum_names[i]
    else:
        if isinstance(value, int):
            name = f"VALUE_{value}"
        else:
            name = str(value).upper()
    if title and name.startswith(title):
        name = name[len(title):]
    
    # Replace dots and hyphens with underscores for valid Python identifiers
    name = name.replace(".", "_").replace("-", "_")
    
    # Prepend underscore if name starts with a digit
    if name and name[0].isdigit():
        name = "_" + name
    
    return name


def enum_member_desc(enum_descriptions, value, i):
    """Get the enum member description from enumDescriptions or fallback."""
    str_value = str(value)
    if isinstance(enum_descriptions, dict) and str_value in enum_descriptions:
        return enum_descriptions[str_value]
    elif isinstance(enum_descriptions, list) and i < len(enum_descriptions):
        return enum_descriptions[i]
    return None


def process_definitions_and_nested_types(schema, processed_types, ref_resolver, type_callback):
    """
    Shared utility to process definitions and nested types in a schema.
    - schema: the root schema dict
    - processed_types: set of already processed type names
    - ref_resolver: reference resolver (can be None)
    - type_callback: function(schema_dict, type_name) -> str or None (returns generated type code or None to skip)
    Returns: list of generated type code strings
    """
    output = []
    # Process definitions first
    if "definitions" in schema:
        for def_name, def_schema in schema["definitions"].items():
            if def_name not in processed_types:
                processed_types.add(def_name)

                # Skip if this definition references an external schema (TypeScript special case)
                if "$ref" in def_schema and ref_resolver and hasattr(ref_resolver, 'definition_to_external_map') and def_name in ref_resolver.definition_to_external_map:
                    continue

                # Resolve $ref if present
                if "$ref" in def_schema and ref_resolver:
                    try:
                        resolved_def = ref_resolver.resolve_ref(
                            def_schema["$ref"])
                        def_schema = resolved_def
                    except Exception:
                        pass
                def_schema_copy = def_schema.copy()
                def_schema_copy["title"] = def_name
                type_code = type_callback(def_schema_copy, def_name)
                if type_code is not None:  # Only add non-None returns
                    output.append(type_code)
    
    # Handle composition keywords at root level (allOf, anyOf, oneOf)
    # This processes properties from composed schemas even if the root has no direct properties
    for comp_key in ["allOf", "anyOf", "oneOf"]:
        if comp_key in schema:
            for comp_item in schema[comp_key]:
                if isinstance(comp_item, dict):
                    # Resolve $ref if present
                    resolved_item = comp_item
                    if "$ref" in comp_item and ref_resolver:
                        try:
                            resolved_item = ref_resolver.resolve_ref(comp_item["$ref"])
                        except Exception:
                            pass
                    
                    # Process properties within this composed item
                    for prop_name, prop_schema in resolved_item.get("properties", {}).items():
                        resolved_schema = prop_schema
                        type_name = ""
                        if "$ref" in prop_schema and ref_resolver:
                            try:
                                resolved_schema = ref_resolver.resolve_ref(prop_schema["$ref"])
                                ref_path = prop_schema["$ref"]
                                if ref_path.startswith("#/definitions/"):
                                    type_name = ref_path.split("/")[-1]
                                elif not ref_path.startswith("#"):
                                    import os
                                    filename = os.path.basename(ref_path)
                                    base_name = os.path.splitext(filename)[0]
                                    type_name = to_pascal_case(base_name)
                                if type_name in processed_types:
                                    continue
                            except Exception:
                                pass
                        
                        # Check if this is an inline object that needs type generation
                        if (resolved_schema.get("type") == "object" and "properties" in resolved_schema) or "properties" in resolved_schema:
                            if not type_name:
                                type_name = to_pascal_case(prop_name)
                            if type_name not in processed_types:
                                nested_schema = resolved_schema.copy()
                                # Always set title to the computed type_name to ensure consistency
                                nested_schema["title"] = type_name
                                processed_types.add(type_name)
                                type_code = type_callback(nested_schema, type_name)
                                if type_code is not None:
                                    output.append(type_code)
                                
                                # ALSO process nested inline objects within this inline object
                                # This handles cases like user_location within web_search_options
                                for nested_prop_name, nested_prop_schema in resolved_schema.get("properties", {}).items():
                                    if isinstance(nested_prop_schema, dict):
                                        # Check for nested inline objects
                                        if nested_prop_schema.get("type") == "object" and "properties" in nested_prop_schema:
                                            nested_nested_type_name = to_pascal_case(nested_prop_name)
                                            if nested_nested_type_name not in processed_types:
                                                nested_nested_schema = nested_prop_schema.copy()
                                                # Always set title to the computed type_name to ensure consistency
                                                nested_nested_schema["title"] = nested_nested_type_name
                                                processed_types.add(nested_nested_type_name)
                                                nested_nested_type_code = type_callback(nested_nested_schema, nested_nested_type_name)
                                                if nested_nested_type_code is not None:
                                                    output.append(nested_nested_type_code)
    
    # Process nested types in properties
    for prop_name, prop_schema in schema.get("properties", {}).items():
        resolved_schema = prop_schema
        type_name = ""
        if "$ref" in prop_schema and ref_resolver:
            try:
                resolved_schema = ref_resolver.resolve_ref(prop_schema["$ref"])
                ref_path = prop_schema["$ref"]
                if ref_path.startswith("#/definitions/"):
                    type_name = ref_path.split("/")[-1]
                elif not ref_path.startswith("#"):
                    import os
                    filename = os.path.basename(ref_path)
                    base_name = os.path.splitext(filename)[0]
                    type_name = to_pascal_case(base_name)
                if type_name in processed_types:
                    continue
            except Exception:
                pass
        if (resolved_schema.get("type") == "object" and "properties" in resolved_schema) or "properties" in resolved_schema:
            if not type_name:
                type_name = to_pascal_case(prop_name)
            if type_name in processed_types:
                continue
            nested_schema = resolved_schema.copy()
            # Always set title to the computed type_name to ensure consistency
            nested_schema["title"] = type_name
            processed_types.add(type_name)
            type_code = type_callback(nested_schema, type_name)
            if type_code is not None:  # Only add non-None returns
                output.append(type_code)
            
            # ALSO process nested inline objects within this inline object
            # This handles cases like data property within api_key.created
            for nested_prop_name, nested_prop_schema in resolved_schema.get("properties", {}).items():
                if isinstance(nested_prop_schema, dict):
                    # Check for nested inline objects
                    if nested_prop_schema.get("type") == "object" and "properties" in nested_prop_schema:
                        nested_nested_type_name = to_pascal_case(nested_prop_name)
                        if nested_nested_type_name not in processed_types:
                            nested_nested_schema = nested_prop_schema.copy()
                            # Always set title to the computed type_name to ensure consistency
                            nested_nested_schema["title"] = nested_nested_type_name
                            processed_types.add(nested_nested_type_name)
                            nested_nested_type_code = type_callback(nested_nested_schema, nested_nested_type_name)
                            if nested_nested_type_code is not None:
                                output.append(nested_nested_type_code)
                    
                    # ALSO check for array items with inline objects within nested properties
                    # This handles cases like certificates array within certificates.activated
                    if nested_prop_schema.get("type") == "array" and "items" in nested_prop_schema:
                        items = nested_prop_schema["items"]
                        if isinstance(items, dict) and items.get("type") == "object" and "properties" in items:
                            # Prefer title if available, otherwise use {PropertyName}Item pattern
                            if "title" in items:
                                item_type_name = to_pascal_case(items["title"])
                            else:
                                item_type_name = f"{to_pascal_case(nested_prop_name)}Item"
                            if item_type_name not in processed_types:
                                # First, process nested objects within this array item inline object
                                for item_prop_name, item_prop_schema in items.get("properties", {}).items():
                                    if isinstance(item_prop_schema, dict) and item_prop_schema.get("type") == "object" and "properties" in item_prop_schema:
                                        item_nested_type_name = to_pascal_case(item_prop_name)
                                        if item_nested_type_name not in processed_types:
                                            item_nested_schema = item_prop_schema.copy()
                                            if "title" not in item_nested_schema:
                                                item_nested_schema["title"] = item_nested_type_name
                                            processed_types.add(item_nested_type_name)
                                            item_nested_type_code = type_callback(item_nested_schema, item_nested_type_name)
                                            if item_nested_type_code is not None:
                                                output.append(item_nested_type_code)
                                
                                # Now add the array item inline object itself
                                item_schema = items.copy()
                                if "title" not in item_schema:
                                    item_schema["title"] = item_type_name
                                processed_types.add(item_type_name)
                                type_code = type_callback(item_schema, item_type_name)
                                if type_code is not None:
                                    output.append(type_code)
        
        # Process anyOf, oneOf, allOf for inline object definitions
        for comp_key in ["anyOf", "oneOf", "allOf"]:
            if comp_key in prop_schema:
                for i, schema_option in enumerate(prop_schema[comp_key]):
                    if not isinstance(schema_option, dict):
                        continue
                    
                    # Check if this option is an inline object definition
                    if schema_option.get("type") == "object" and "properties" in schema_option:
                        # Generate a class for this inline object
                        # Use just the property name + index, not the composition keyword (to avoid AudioanyOfOption0)
                        option_type_name = f"{to_pascal_case(prop_name)}Option{i}" if i > 0 else to_pascal_case(prop_name)
                        if option_type_name not in processed_types:
                            # First, process nested objects within this inline object
                            # and add them BEFORE the parent inline object
                            for nested_prop_name, nested_prop_schema in schema_option.get("properties", {}).items():
                                if isinstance(nested_prop_schema, dict) and nested_prop_schema.get("type") == "object" and "properties" in nested_prop_schema:
                                    nested_class_name = to_pascal_case(nested_prop_name)
                                    if nested_class_name not in processed_types:
                                        nested_class_schema = nested_prop_schema.copy()
                                        if "title" not in nested_class_schema:
                                            nested_class_schema["title"] = nested_class_name
                                        processed_types.add(nested_class_name)
                                        nested_type_code = type_callback(nested_class_schema, nested_class_name)
                                        if nested_type_code is not None:
                                            output.append(nested_type_code)
                            
                            # Now add the inline object itself
                            nested_schema = schema_option.copy()
                            if "title" not in nested_schema:
                                nested_schema["title"] = option_type_name
                            processed_types.add(option_type_name)
                            type_code = type_callback(nested_schema, option_type_name)
                            if type_code is not None:
                                output.append(type_code)
                    
                    # Also check if this option is an array with inline object items
                    elif schema_option.get("type") == "array" and "items" in schema_option:
                        items = schema_option["items"]
                        if isinstance(items, dict) and items.get("type") == "object" and "properties" in items:
                            # Generate a class for the array item inline object
                            option_type_name = f"{to_pascal_case(prop_name)}Option{i}Item"
                            if option_type_name not in processed_types:
                                # First, process nested objects within this inline object
                                # and add them BEFORE the parent inline object
                                for nested_prop_name, nested_prop_schema in items.get("properties", {}).items():
                                    if isinstance(nested_prop_schema, dict) and nested_prop_schema.get("type") == "object" and "properties" in nested_prop_schema:
                                        nested_class_name = to_pascal_case(nested_prop_name)
                                        if nested_class_name not in processed_types:
                                            nested_class_schema = nested_prop_schema.copy()
                                            if "title" not in nested_class_schema:
                                                nested_class_schema["title"] = nested_class_name
                                            processed_types.add(nested_class_name)
                                            nested_type_code = type_callback(nested_class_schema, nested_class_name)
                                            if nested_type_code is not None:
                                                output.append(nested_type_code)
                                
                                # Now add the inline object itself
                                nested_schema = items.copy()
                                if "title" not in nested_schema:
                                    nested_schema["title"] = option_type_name
                                processed_types.add(option_type_name)
                                type_code = type_callback(nested_schema, option_type_name)
                                if type_code is not None:
                                    output.append(type_code)
        
        # Process array items with anyOf/oneOf/allOf
        if prop_schema.get("type") == "array" and "items" in prop_schema:
            items = prop_schema["items"]
            if isinstance(items, dict):
                # First check for direct inline object in items (not in composition keywords)
                if items.get("type") == "object" and "properties" in items:
                    # Prefer title if available, otherwise use {PropertyName}Item pattern
                    if "title" in items:
                        item_type_name = to_pascal_case(items["title"])
                    else:
                        item_type_name = f"{to_pascal_case(prop_name)}Item"
                    if item_type_name not in processed_types:
                        # First, process nested objects within this array item inline object
                        # This handles cases like url_citation within annotations array items
                        for item_prop_name, item_prop_schema in items.get("properties", {}).items():
                            if isinstance(item_prop_schema, dict) and item_prop_schema.get("type") == "object" and "properties" in item_prop_schema:
                                item_nested_type_name = to_pascal_case(item_prop_name)
                                if item_nested_type_name not in processed_types:
                                    item_nested_schema = item_prop_schema.copy()
                                    if "title" not in item_nested_schema:
                                        item_nested_schema["title"] = item_nested_type_name
                                    processed_types.add(item_nested_type_name)
                                    item_nested_type_code = type_callback(item_nested_schema, item_nested_type_name)
                                    if item_nested_type_code is not None:
                                        output.append(item_nested_type_code)
                        
                        # Process composition keywords within array item inline object properties
                        # This handles cases like logprobs with anyOf in choices items
                        for item_prop_name, item_prop_schema in items.get("properties", {}).items():
                            if isinstance(item_prop_schema, dict):
                                for comp_key in ["anyOf", "oneOf", "allOf"]:
                                    if comp_key in item_prop_schema:
                                        for i, schema_option in enumerate(item_prop_schema[comp_key]):
                                            if isinstance(schema_option, dict) and schema_option.get("type") == "object" and "properties" in schema_option:
                                                # Generate a class for this inline object
                                                option_type_name = f"{to_pascal_case(item_prop_name)}Option{i}" if i > 0 else to_pascal_case(item_prop_name)
                                                if option_type_name not in processed_types:
                                                    # Process nested objects within this option
                                                    for nested_prop_name, nested_prop_schema in schema_option.get("properties", {}).items():
                                                        if isinstance(nested_prop_schema, dict) and nested_prop_schema.get("type") == "object" and "properties" in nested_prop_schema:
                                                            nested_class_name = to_pascal_case(nested_prop_name)
                                                            if nested_class_name not in processed_types:
                                                                nested_class_schema = nested_prop_schema.copy()
                                                                if "title" not in nested_class_schema:
                                                                    nested_class_schema["title"] = nested_class_name
                                                                processed_types.add(nested_class_name)
                                                                nested_type_code = type_callback(nested_class_schema, nested_class_name)
                                                                if nested_type_code is not None:
                                                                    output.append(nested_type_code)
                                                    
                                                    # Now add the inline object itself
                                                    nested_schema = schema_option.copy()
                                                    if "title" not in nested_schema:
                                                        nested_schema["title"] = option_type_name
                                                    processed_types.add(option_type_name)
                                                    type_code = type_callback(nested_schema, option_type_name)
                                                    if type_code is not None:
                                                        output.append(type_code)
                        
                        # Now add the array item inline object itself
                        item_schema = items.copy()
                        if "title" not in item_schema:
                            item_schema["title"] = item_type_name
                        processed_types.add(item_type_name)
                        type_code = type_callback(item_schema, item_type_name)
                        if type_code is not None:
                            output.append(type_code)
                
                for comp_key in ["anyOf", "oneOf", "allOf"]:
                    if comp_key in items:
                        # Special case: allOf with a reference and inline properties should merge them
                        if comp_key == "allOf":
                            # Check if we have a reference + inline object pattern
                            has_ref = any(isinstance(opt, dict) and "$ref" in opt for opt in items["allOf"])
                            has_inline_obj = any(isinstance(opt, dict) and "properties" in opt for opt in items["allOf"])
                            
                            if has_ref and has_inline_obj:
                                # This is a merged composition - generate a single class for the array item
                                item_type_name = f"{to_pascal_case(prop_name)}Item"
                                if item_type_name not in processed_types:
                                    # Pass the entire allOf schema to the callback so it generates the merged type
                                    item_schema = items.copy()  # includes the allOf
                                    if "title" not in item_schema:
                                        item_schema["title"] = item_type_name
                                    processed_types.add(item_type_name)
                                    type_code = type_callback(item_schema, item_type_name)
                                    if type_code is not None:
                                        output.append(type_code)
                                # Skip the individual option processing below for this case
                                continue
                        
                        for i, schema_option in enumerate(items[comp_key]):
                            # Check if this option is an inline object definition
                            if isinstance(schema_option, dict) and schema_option.get("type") == "object" and "properties" in schema_option:
                                # Generate a class for this inline object
                                # Use property name + Item + index, not the composition keyword
                                option_type_name = f"{to_pascal_case(prop_name)}Item{i}" if i > 0 else f"{to_pascal_case(prop_name)}Item"
                                if option_type_name not in processed_types:
                                    # First, process nested objects within this inline object
                                    # and add them BEFORE the parent inline object
                                    for nested_prop_name, nested_prop_schema in schema_option.get("properties", {}).items():
                                        if isinstance(nested_prop_schema, dict) and nested_prop_schema.get("type") == "object" and "properties" in nested_prop_schema:
                                            nested_class_name = to_pascal_case(nested_prop_name)
                                            if nested_class_name not in processed_types:
                                                nested_class_schema = nested_prop_schema.copy()
                                                if "title" not in nested_class_schema:
                                                    nested_class_schema["title"] = nested_class_name
                                                processed_types.add(nested_class_name)
                                                nested_type_code = type_callback(nested_class_schema, nested_class_name)
                                                if nested_type_code is not None:
                                                    output.append(nested_type_code)
                                    
                                    # Now add the inline object itself
                                    nested_schema = schema_option.copy()
                                    if "title" not in nested_schema:
                                        nested_schema["title"] = option_type_name
                                    processed_types.add(option_type_name)
                                    type_code = type_callback(nested_schema, option_type_name)
                                    if type_code is not None:
                                        output.append(type_code)
    return output
