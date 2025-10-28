
# schema2code

A tool for converting JSON schema files to type definitions in various programming languages.

## Supported languages

- Go
- Python (with Pydantic or dataclasses)
- TypeScript
- C# (.NET)
- Protocol Buffers (proto3)

## Installation

### From PyPI (Recommended)

Install the latest stable release:

```bash
pip install schema2code
```

### Development Installation

For development or to get the latest features:

```bash
git clone https://github.com/LongStoryMedia/schema2code.git
cd schema2code
pip install -e ".[dev]"
```

### Quick Install Script

Alternatively, use the install script:

```bash
curl -sSL https://raw.githubusercontent.com/LongStoryMedia/schema2code/main/install.sh | bash
```

This will:
1. Create a `.schema2code` directory in your home folder
2. Clone the repository
3. Set up a virtual environment
4. Install the package and add it to your PATH

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

### Unit Test Suite

The project includes a pytest-based unit test suite covering:

- Generators (Python defaults & duplicate avoidance, TypeScript imports & index exports)
- CLI integration (multi-file generation, error cases)
- Schema loader validation (rejects non-object root documents)

#### Quick Start

```bash
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
pip install -r requirements.txt pytest
pytest -q
```

#### Notes

- Tests import implementation modules via the `src.` namespace (`from src.generators.python import PythonGenerator`).
- No editable install (`pip install -e .`) is required just to run tests, but you can still use it for development if preferred.
- Add new generator tests in `tests/` following existing patterns; prefer focused assertions on generated code snippets.

#### Coverage Testing

The project includes code coverage measurement to ensure test quality:

```bash
# Run tests with coverage report
pytest --cov=src --cov-report=term

# Generate HTML coverage report
pytest --cov=src --cov-report=html

# Generate XML coverage report (for CI/CD)
pytest --cov=src --cov-report=xml
```

Coverage reports help identify:

- **Untested code paths**: Functions or branches not executed during tests
- **Test effectiveness**: Areas where additional test cases might be valuable
- **Regression prevention**: Ensuring new code includes appropriate tests

The HTML report (in `coverage_html/index.html`) provides an interactive view showing:

- Overall coverage percentage by file and line
- Missing coverage highlighted in red
- Branch coverage for conditional logic

**Current coverage target**: Aim for >80% line coverage on generator modules, >60% overall.

#### Troubleshooting

- If imports fail, ensure `src/` is present and you launched pytest from the project root.
- Regenerate the virtual environment if dependency versions conflict: remove `.venv/` and repeat the quick start steps.

## Releases and Versioning

This project follows [Semantic Versioning](https://semver.org/). See [CHANGELOG.md](CHANGELOG.md) for release history.

### Version Information

Check the installed version:

```bash
schema2code --version
```

### Building from Source

To build the package yourself:

```bash
# Install build dependencies
pip install build twine

# Build the package
python -m build

# Check the build
twine check dist/*
```

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development and release instructions.

## Contributing

Contributions are welcome! To contribute:

1. Fork this repository and create a new branch for your feature or bugfix.
2. Make your changes and add tests as appropriate.
3. Run `./test_command_line.sh` to ensure all code generation works as expected.
4. Submit a pull request with a clear description of your changes.

Please follow PEP8 style for Python code and keep code generation logic modular and well-documented.
