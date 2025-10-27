import subprocess
import sys
from pathlib import Path
import yaml
import pytest

ROOT = Path(__file__).parent.parent
SCHEMAS = ROOT / "sample_schemas"


def run_cli(args):
    # Execute via src.main module path
    cmd = [sys.executable, "-m", "src.main"] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def test_cli_generates_multiple_files(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    schema = SCHEMAS / "user_config.yaml"
    result = run_cli(
        [
            str(schema),
            "--language",
            "python",
            "--output",
            str(out_dir / "user_config.py"),
        ]
    )
    assert result.returncode == 0, result.stderr
    # Should produce multiple related files (imports)
    assert (out_dir / "__init__.py").exists()
    # Ensure GPUConfig file exists separately when referenced indirectly
    # Regenerate GPUConfig explicitly and check content
    gpu_result = run_cli(
        [
            str(SCHEMAS / "gpu_config.yaml"),
            "--language",
            "python",
            "--output",
            str(out_dir / "gpu_config.py"),
        ]
    )
    assert gpu_result.returncode == 0
    content = (out_dir / "gpu_config.py").read_text(encoding="utf-8")
    assert "class GPUConfig(" in content


def test_missing_schema_file_error():
    result = run_cli(
        ["non_existent_schema.yaml", "--language", "python", "--output", "dummy.py"]
    )
    assert result.returncode != 0
    assert "Error:" in result.stderr or "No such file" in (
        result.stderr + result.stdout
    )


def test_schema_loader_error(tmp_path):
    # Create a yaml file that parses but is not an object (list)
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("- just\n- a\n- list\n", encoding="utf-8")
    result = run_cli(
        [
            str(bad_file),
            "--language",
            "python",
            "--output",
            str(tmp_path / "bad_out.py"),
        ]
    )
    assert result.returncode != 0
