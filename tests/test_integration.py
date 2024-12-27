import os
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

from codeorite.cli import run_cli
from codeorite.config import DEFAULT_CONFIG_FILE


@pytest.fixture
def integration_workspace():
    """Create a temporary workspace with a sample project structure."""
    temp_dir = tempfile.mkdtemp()

    # Create a sample project structure
    project = {
        "src/main.py": "def main():\n    print('Hello, World!')\n\nif __name__ == '__main__':\n    main()",
        "src/utils/helpers.py": "def helper():\n    return 'helper'",
        "tests/test_main.py": "def test_main():\n    assert True",
        "docs/README.md": "# Project Documentation\n\nThis is a test project.",
        ".gitignore": "*.pyc\n__pycache__/\n.env\n",
        "requirements.txt": "pytest>=7.0.0\nyaml>=6.0",
        "setup.py": "from setuptools import setup\n\nsetup(\n    name='test-project',\n    version='0.1.0'\n)",
        "src/data/config.json": '{"key": "value"}',
        "src/web/index.html": "<html><body>Hello</body></html>",
        "src/web/styles.css": "body { color: black; }",
        "src/lib/module.js": "console.log('Hello');",
        "src/lib/types.ts": "interface Test { prop: string; }",
        "src/backend/server.rs": 'fn main() { println!("Server"); }',
        "src/backend/lib.rs": "pub fn add(a: i32, b: i32) -> i32 { a + b }",
    }

    for file_path, content in project.items():
        full_path = os.path.join(temp_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    yield temp_dir
    shutil.rmtree(temp_dir)


def test_basic_python_project_packing(integration_workspace):
    """Test packing a basic Python project with default settings."""
    output_file = os.path.join(integration_workspace, "output.txt")

    # Run CLI with minimal arguments
    args = [
        "--root",
        integration_workspace,
        "--output-file",
        output_file,
        "--languages-included",
        "python",
    ]
    exit_code = run_cli(args)
    assert exit_code == 0

    # Verify output file exists and contains expected content
    assert os.path.exists(output_file)
    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()
        # Check structure
        assert "=== DIRECTORY TREE (INCLUDED ONLY) ===" in content
        assert "=== PACKED FILES ===" in content
        # Check Python files are included
        assert "src/main.py" in content
        assert "src/utils/helpers.py" in content
        assert "tests/test_main.py" in content
        # Check non-Python files are excluded
        assert "docs/README.md" not in content
        assert "setup.py" in content  # setup.py should be included
        # Check file contents
        assert "def main():" in content
        assert "def helper():" in content
        assert "def test_main():" in content


def test_multi_language_project(integration_workspace):
    """Test packing a project with multiple programming languages."""
    output_file = os.path.join(integration_workspace, "multi_lang.txt")

    # Run CLI using explicit arguments instead of config file
    args = [
        "--root",
        integration_workspace,
        "--output-file",
        output_file,
        "--languages-included",
        "python",
        "rust",
        "typescript",
        "javascript",
        "--excludes",
        ".json",
        ".html",
        ".css",  # Exclude web assets
    ]
    exit_code = run_cli(args)
    assert exit_code == 0

    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()
        # Check included languages
        assert "src/main.py" in content
        assert "src/backend/server.rs" in content
        assert "src/lib/types.ts" in content
        assert "src/lib/module.js" in content
        # Check excluded files
        assert "src/web/index.html" not in content
        assert "src/web/styles.css" not in content
        assert "src/data/config.json" not in content


def test_gitignore_respect(integration_workspace):
    """Test that .gitignore patterns are respected."""
    # Create some files that should be ignored
    ignored_files = {
        "src/__pycache__/main.cpython-39.pyc": "binary content",
        "src/.env": "SECRET_KEY=test",
        "src/temp.pyc": "binary content",
    }
    for file_path, content in ignored_files.items():
        full_path = os.path.join(integration_workspace, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)

    output_file = os.path.join(integration_workspace, "gitignore_test.txt")
    args = [
        "--root",
        integration_workspace,
        "--output-file",
        output_file,
        "--languages-included",
        "python",
    ]

    exit_code = run_cli(args)
    assert exit_code == 0

    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()
        # Check that ignored files are not included
        assert "main.cpython-39.pyc" not in content
        assert "SECRET_KEY=test" not in content
        assert "temp.pyc" not in content
        # But regular Python files are included
        assert "src/main.py" in content


def test_custom_instructions(integration_workspace):
    """Test adding custom instructions to the output."""
    output_file = os.path.join(integration_workspace, "with_instructions.txt")

    instructions = [
        "# Project: Test Integration",
        "# Author: Test User",
        "# Instructions:",
        "# 1. Run setup.py",
        "# 2. Execute main.py",
    ]

    args = [
        "--root",
        integration_workspace,
        "--output-file",
        output_file,
        "--languages-included",
        "python",
        "--custom-instructions",
    ] + instructions

    exit_code = run_cli(args)
    assert exit_code == 0

    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()
        # Check custom instructions section
        assert "=== Custom Instructions ===" in content
        for instruction in instructions:
            assert instruction in content
        # Check that rest of the content is still there
        assert "=== DIRECTORY TREE (INCLUDED ONLY) ===" in content
        assert "=== PACKED FILES ===" in content


def test_complex_file_filtering(integration_workspace):
    """Test complex file filtering scenarios."""
    output_file = os.path.join(integration_workspace, "filtered.txt")

    # Add some additional test files
    extra_files = {
        "src/module.pyc": "binary",
        "docs/guide.md": "# User Guide\n\nThis is a guide.",
        "src/test_utils.py": "def test_util(): pass",
        "src/production.py": "def prod(): pass",
    }
    for file_path, content in extra_files.items():
        full_path = os.path.join(integration_workspace, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)

    # Run CLI with explicit arguments - only include .md files
    args = [
        "--root",
        integration_workspace,
        "--output-file",
        output_file,
        "--includes",
        ".md",  # Only include markdown files
        "--excludes",
        ".pyc",
        ".py",  # Exclude all Python files
    ]
    exit_code = run_cli(args)
    assert exit_code == 0

    with open(output_file, "r", encoding="utf-8") as f:
        content = f.read()
        # Check included files
        assert "docs/guide.md" in content  # Only .md files should be included
        # Check excluded files
        assert "src/main.py" not in content  # .py excluded
        assert "src/production.py" not in content  # .py excluded
        assert "src/module.pyc" not in content  # .pyc excluded
        assert "src/test_utils.py" not in content  # .py excluded
        assert "tests/test_main.py" not in content  # .py excluded


def test_error_conditions(integration_workspace):
    """Test various error conditions in an end-to-end scenario."""
    output_file = os.path.join(integration_workspace, "error_test.txt")

    # Test 1: Invalid language
    args = [
        "--root",
        integration_workspace,
        "--output-file",
        output_file,
        "--languages-included",
        "invalid_lang",
    ]
    assert run_cli(args) != 0

    # Test 2: Invalid root directory
    args = [
        "--root",
        os.path.join(integration_workspace, "nonexistent"),
        "--output-file",
        output_file,
    ]
    assert run_cli(args) != 0

    # Test 3: Invalid config file
    config_path = os.path.join(integration_workspace, DEFAULT_CONFIG_FILE)
    with open(config_path, "w") as f:
        f.write("invalid_yaml_content: [missing_bracket")  # Malformed YAML
    args = [
        "--root",
        integration_workspace,
        "--config",
        config_path,
        "--output-file",
        output_file,
    ]
    assert run_cli(args) != 0

    # Test 4: Permission error simulation
    if os.name != "nt":  # Skip on Windows
        os.chmod(integration_workspace, 0o444)  # Read-only
        try:
            args = [
                "--root",
                integration_workspace,
                "--output-file",
                os.path.join(integration_workspace, "no_permission.txt"),
            ]
            assert run_cli(args) != 0
        finally:
            os.chmod(integration_workspace, 0o755)  # Restore permissions
