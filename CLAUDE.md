# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

schema2code converts JSON Schema files (JSON/YAML) into typed code definitions for Go, Python (Pydantic or dataclasses), TypeScript, C#/.NET, and Protocol Buffers (proto3). It resolves `$ref` references including cross-file external schemas, and handles `allOf`/`anyOf`/`oneOf` composition, enums, nested objects, arrays, and maps.

## Commands

```bash
# Run all unit tests
pytest -q

# Run a single test file
pytest tests/test_python_generator.py -q

# Run a single test function
pytest tests/test_python_generator.py::test_inline_enum_generation -v

# Tests with coverage
pytest --cov=src --cov-report=term-missing

# Integration test: runs all 132 sample schemas through all 5 languages
./test_command_line.sh

# Lint/format (dev dependencies)
black src/ tests/
flake8 src/ tests/

# Build package
python -m build && twine check dist/*

# Run the tool
python -m src.main schema.json --language python --output models.py
```

## Architecture

### Data Flow

```
Schema file (.json/.yaml)
  → SchemaLoader (src/util/loader.py) reads and validates
  → generate_types() in src/main.py orchestrates:
      → SchemaRefResolver (src/util/resolver.py) resolves all $ref (internal + external)
      → _preprocess_schema_references() eagerly resolves chained refs
      → Language Generator produces code string
      → Separate files generated for external referenced schemas
  → Writer (src/util/writer.py) writes output files
```

### Generator Pattern

Each language generator (`src/generators/{python,go,typescript,dotnet,proto}.py`) is a class with only `@staticmethod` methods. The main entry is `Generator.generate(schema, ..., ref_resolver, ...) -> str`.

Generators share logic through `schema_helpers.process_definitions_and_nested_types()` which walks the schema tree (definitions, properties, compositions, arrays, nested objects) and calls a `type_callback(schema_dict, type_name)` provided by each generator. Each generator maintains a `processed_types: set` to deduplicate types.

### Key Modules

- **src/main.py**: CLI entry point (`main()`) and orchestrator (`generate_types()`)
- **src/util/resolver.py**: `SchemaRefResolver` — resolves `$ref`, tracks external schemas, caches loaded files, derives type names from titles/filenames
- **src/util/schema_helpers.py**: Shared helpers — `to_pascal_case()`, `enum_member_name()`, `process_definitions_and_nested_types()` (the central schema-walking function)
- **src/util/loader.py**: `SchemaLoader` — reads JSON/YAML, validates root is a dict
- **src/util/writer.py**: `Writer` — file output with "DO NOT EDIT" headers, create/append modes

### Import Paths

Tests and code use the `src.` namespace: `from src.generators.python import PythonGenerator`. The `schema2code/` top-level directory is a thin shim that adds `src/` to `sys.path` and delegates to `src.main`.

### Test Conventions

Tests load sample schemas from `sample_schemas/` via `yaml.safe_load`, create a `SchemaRefResolver`, call `Generator.generate()`, and assert on the generated code string with `assert "..." in code` or `re.search()`. Shared fixtures are in `tests/conftest.py` (`temp_output_dir`, `load_schema`).
