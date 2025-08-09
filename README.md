
# schema2code

A tool for converting JSON schema files to type definitions in various programming languages.

## Supported languages

- Go
- Python (with Pydantic or dataclasses)
- TypeScript
- C# (.NET)
- Protocol Buffers (proto3)

## Installation

This project is a Python package. You can install it in editable mode for development:

```bash
pip install -e .
```

Or, to use the CLI directly:

```bash
python -m src.main [schema_file] --language [language] --output [output_file] [options]
```

## Usage

```bash
python -m src.main [schema_file] --language [language] --output [output_file] [options]
```

### Required arguments

- `schema_file`: Path to the JSON or YAML schema file
- `--language`, `-l`: Target language (`go`, `python`, `typescript`, `csharp`, `dotnet`, `proto`, `protobuf`)
- `--output`, `-o`: Output file path

### Optional arguments

- `--mode`: `create` (default) or `append` - Whether to create a new file or append to existing
- `--no-create`: Don't create the file if it doesn't exist
- `--package`: Go package name or Protocol Buffer package name (default: "main")
- `--namespace`: C# namespace (default: "SchemaTypes")
- `--no-pydantic`: Use dataclasses instead of Pydantic for Python
- `--no-overwrite`: Prevents overwriting of existing files
- `--go-package`: Go package option for Protocol Buffer files

## Examples

Generate Go types:

```bash
python -m src.main schema.json --language go --output models.go --package models
```

Generate Python types with Pydantic:

```bash
python -m src.main schema.json --language python --output models.py
```

Generate Python types with dataclasses:

```bash
python -m src.main schema.json --language python --output models.py --no-pydantic
```

Generate TypeScript interfaces:

```bash
python -m src.main schema.json --language typescript --output models.ts
```

Generate C# classes:

```bash
python -m src.main schema.json --language csharp --output Models.cs --namespace MyApp.Models
```

Generate Protocol Buffer message definitions:

```bash
python -m src.main schema.json --language proto --output message.proto --package mypackage --go-package "example/mypackage"
```

Append to existing file:

```bash
python -m src.main schema.json --language go --output models.go --mode append
```

## Testing

To test the command line tool across all sample schemas and supported languages, run:

```bash
./test_command_line.sh
```

This script will generate code for all schemas in `sample_schemas/` and output to `sample_code/`, reporting any errors or issues.

## Contributing

Contributions are welcome! To contribute:

1. Fork this repository and create a new branch for your feature or bugfix.
2. Make your changes and add tests as appropriate.
3. Run `./test_command_line.sh` to ensure all code generation works as expected.
4. Submit a pull request with a clear description of your changes.

Please follow PEP8 style for Python code and keep code generation logic modular and well-documented.
