import re
from pathlib import Path
import yaml
from src.generators.python import PythonGenerator
from src.util.resolver import SchemaRefResolver

SAMPLE_DIR = Path(__file__).parent.parent / "sample_schemas"


def load_schema(name: str):
    path = SAMPLE_DIR / name
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), str(path)


def test_dataclass_generation_with_default_factory():
    schema, schema_path = load_schema("dataclass_example.yaml")
    resolver = SchemaRefResolver(schema_path, schema)
    code = PythonGenerator.generate(
        schema, use_pydantic=False, schema_file=schema_path, ref_resolver=resolver
    )
    # Expect dataclass decorator
    assert "@dataclass" in code
    # tags should use default_factory=list
    assert re.search(
        r"tags: Optional\[List\[str\]\] = field\(default_factory=list\)", code
    )
    # metadata should use default_factory=dict
    assert re.search(
        r"metadata: Optional\[Dict\[str, str\]\] = field\(default_factory=dict\)", code
    )
    # name required so no Optional wrapper removal test; just ensure field exists
    assert re.search(r"name: str", code)
