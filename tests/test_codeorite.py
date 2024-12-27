import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest
import yaml

from codeorite.config import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_OUTPUT_FILE,
    SUPPORTED_LANGUAGES,
    CodeoriteConfig,
)
from codeorite.main import (
    build_directory_tree,
    collect_files,
    is_ignored_by_gitignore,
    load_gitignore,
    pack_repository,
)


@pytest.fixture
def temp_workspace():
    """Fixture providing a temporary workspace for tests."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_files(temp_workspace):
    """Fixture creating a set of sample files for testing."""
    files = {
        "src/main.py": "print('Hello from Python')\n",
        "src/lib.rs": 'fn main() { println!("Hello from Rust"); }\n',
        "docs/README.md": "# Documentation\n",
        "tests/test.py": "def test_something(): pass\n",
        ".gitignore": "*.pyc\n__pycache__/\n*.o\n",
        "build/temp.o": "binary content\n",
        "src/nested/deep/code.py": "# Deeply nested file\n",
    }

    for file_path, content in files.items():
        full_path = os.path.join(temp_workspace, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

    return temp_workspace


@pytest.fixture
def cleanup_output_files():
    """Fixture to clean up output files after tests."""
    yield
    # Clean up any output files that might have been created
    output_patterns = [
        "output.txt",
        "from_config.txt",
        "cli_override.txt",
        "test.txt",
        "original.txt",
        "modified.txt",
    ]
    for pattern in output_patterns:
        for file in Path().glob(f"**/{pattern}"):
            try:
                file.unlink()
            except (FileNotFoundError, PermissionError):
                pass


class TestCodeoriteConfig:
    """Test suite for CodeoriteConfig class."""

    def test_default_initialization(self):
        """Test default configuration initialization."""
        config = CodeoriteConfig()
        assert config.output_file == DEFAULT_OUTPUT_FILE
        assert config.languages_included == []
        assert config.languages_excluded == []
        assert config.includes == []
        assert config.excludes == []
        assert config.custom_instructions == []

    def test_custom_initialization(self):
        """Test custom configuration initialization."""
        config = CodeoriteConfig(
            output_file="custom.txt",
            languages_included=["python"],
            languages_excluded=["rust"],
            includes=[".txt"],
            excludes=[".md"],
            custom_instructions=["# Custom header"],
        )
        assert config.output_file == "custom.txt"
        assert config.languages_included == ["python"]
        assert config.languages_excluded == ["rust"]
        assert config.includes == [".txt"]
        assert config.excludes == [".md"]
        assert config.custom_instructions == ["# Custom header"]

    def test_from_file_nonexistent(self, temp_workspace):
        """Test loading from non-existent config file."""
        config_path = os.path.join(temp_workspace, "nonexistent.yaml")
        config = CodeoriteConfig.from_file(config_path)
        assert config.output_file == DEFAULT_OUTPUT_FILE

    def test_from_file_valid(self, temp_workspace):
        """Test loading from valid config file."""
        config_path = os.path.join(temp_workspace, "config.yaml")
        config_data = {
            "output_file": "output.txt",
            "languages_included": ["python", "rust"],
            "languages_excluded": ["javascript"],
            "includes": [".txt"],
            "excludes": [".md"],
            "custom_instructions": ["# Header"],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        config = CodeoriteConfig.from_file(config_path)
        assert config.output_file == "output.txt"
        assert set(config.languages_included) == {"python", "rust"}
        assert config.languages_excluded == ["javascript"]

    def test_resolve_extensions(self):
        """Test extension resolution from language specifications."""
        config = CodeoriteConfig(
            languages_included=["python", "rust"],
            languages_excluded=["javascript"],
            includes=[".txt"],
            excludes=[".md"],
        )
        includes, excludes = config.resolve_extensions()
        assert ".py" in includes
        assert ".rs" in includes
        assert ".txt" in includes
        assert ".js" in excludes
        assert ".md" in excludes

    def test_case_insensitive_languages(self):
        """Test case-insensitive language handling."""
        config = CodeoriteConfig(languages_included=["PYTHON", "Rust"])
        includes, _ = config.resolve_extensions()
        assert ".py" in includes
        assert ".rs" in includes

    def test_invalid_language(self):
        """Test handling of unsupported language specifications."""
        config = CodeoriteConfig(languages_included=["nonexistent_lang"])
        includes, _ = config.resolve_extensions()
        assert len(includes) == 0

    def test_duplicate_extensions(self):
        """Test handling of duplicate extensions in includes/excludes."""
        config = CodeoriteConfig(
            languages_included=["python"],
            includes=[".py"],  # Duplicate with python's extension
            excludes=[".py"],  # Conflict between include and exclude
        )
        includes, excludes = config.resolve_extensions()
        # Extension should not be in includes if it's in excludes
        assert ".py" not in includes
        # Exclude should take precedence over include
        assert ".py" in excludes

    def test_from_file_encoding_error(self, temp_workspace):
        """Test handling of encoding errors in config file."""
        config_path = os.path.join(temp_workspace, "invalid_encoding.yaml")

        # Create a file with invalid UTF-8 encoding
        with open(config_path, "wb") as f:
            f.write(b"\xff\xfe" + b"invalid utf-8 content")

        config = CodeoriteConfig.from_file(config_path)
        # Should fall back to defaults on encoding error
        assert config.output_file == DEFAULT_OUTPUT_FILE

    def test_resolve_extensions_empty_languages(self):
        """Test resolve_extensions with empty language lists."""
        config = CodeoriteConfig(
            languages_included=[],
            languages_excluded=[],
            includes=[".txt"],
            excludes=[".md"],
        )
        includes, excludes = config.resolve_extensions()
        assert ".txt" in includes
        assert ".md" in excludes
        assert len(includes) == 1  # Only explicit include
        assert len(excludes) == 1  # Only explicit exclude


class TestGitignoreHandling:
    """Test suite for .gitignore handling functionality."""

    def test_load_gitignore_nonexistent(self, temp_workspace):
        """Test loading non-existent .gitignore."""
        spec = load_gitignore(os.path.join(temp_workspace, ".gitignore"))
        assert spec is None

    def test_load_gitignore_valid(self, temp_workspace):
        """Test loading valid .gitignore patterns."""
        gitignore_path = os.path.join(temp_workspace, ".gitignore")
        with open(gitignore_path, "w") as f:
            f.write("*.pyc\n__pycache__/\n")

        spec = load_gitignore(gitignore_path)
        assert spec is not None
        assert spec.match_file("test.pyc")
        assert spec.match_file("__pycache__/cache.py")
        assert not spec.match_file("test.py")

    def test_is_ignored_by_gitignore(self, sample_files):
        """Test .gitignore pattern matching."""
        spec = load_gitignore(os.path.join(sample_files, ".gitignore"))
        assert is_ignored_by_gitignore(
            os.path.join(sample_files, "test.pyc"), spec, sample_files
        )
        assert is_ignored_by_gitignore(
            os.path.join(sample_files, "build/temp.o"), spec, sample_files
        )
        assert not is_ignored_by_gitignore(
            os.path.join(sample_files, "src/main.py"), spec, sample_files
        )

    def test_complex_gitignore_patterns(self, temp_workspace):
        """Test complex gitignore patterns including negation and directories."""
        gitignore_content = """
        # Ignore all .txt files
        *.txt
        # But not important.txt
        !important.txt
        # Ignore all files in any target directory
        target/
        # Ignore files with spaces and special chars
        **/*[0-9]*.md
        **/test space/*
        """
        gitignore_path = os.path.join(temp_workspace, ".gitignore")
        with open(gitignore_path, "w") as f:
            f.write(gitignore_content)

        spec = load_gitignore(gitignore_path)
        assert spec.match_file("file.txt")
        assert not spec.match_file("important.txt")
        assert spec.match_file("target/file.txt")
        assert spec.match_file("src/target/file.txt")
        assert spec.match_file("test123.md")
        assert spec.match_file("test space/file.txt")


class TestDirectoryTree:
    """Test suite for directory tree building functionality."""

    def test_build_directory_tree_empty(self, temp_workspace):
        """Test building tree with no included files."""
        tree = build_directory_tree(temp_workspace, [])
        assert tree == ""

    def test_build_directory_tree_with_files(self, sample_files):
        """Test building tree with included files."""
        included_files = [
            os.path.join(sample_files, "src/main.py"),
            os.path.join(sample_files, "src/nested/deep/code.py"),
        ]
        tree = build_directory_tree(sample_files, included_files)
        assert "src/" in tree
        assert "nested/" in tree
        assert "deep/" in tree


class TestFileCollection:
    """Test suite for file collection functionality."""

    def test_collect_files_all_languages(self, sample_files):
        """Test collecting files with no language restrictions."""
        config = CodeoriteConfig()
        files = collect_files(sample_files, config)
        assert any(f.endswith("main.py") for f in files)
        assert any(f.endswith("lib.rs") for f in files)
        assert any(f.endswith("README.md") for f in files)

    def test_collect_files_filtered(self, sample_files):
        """Test collecting files with language and extension filters."""
        config = CodeoriteConfig(languages_included=["python"], excludes=[".md"])
        files = collect_files(sample_files, config)
        assert any(f.endswith("main.py") for f in files)
        assert any(f.endswith("test.py") for f in files)
        assert not any(f.endswith("lib.rs") for f in files)
        assert not any(f.endswith("README.md") for f in files)

    def test_collect_files_gitignore(self, sample_files):
        """Test collecting files respecting .gitignore."""
        # Create some files that should be ignored
        ignored_files = {"ignored.pyc": "binary", "__pycache__/cache.py": "cache"}
        for file_path, content in ignored_files.items():
            full_path = os.path.join(sample_files, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)

        config = CodeoriteConfig()
        files = collect_files(sample_files, config)
        assert not any(f.endswith(".pyc") for f in files)
        assert not any("__pycache__" in f for f in files)


@pytest.mark.usefixtures("cleanup_output_files")
class TestPackRepository:
    """Test suite for main repository packing functionality."""

    def test_pack_repository_basic(self, sample_files):
        """Test basic repository packing."""
        output_file = os.path.join(sample_files, "output.txt")
        config = CodeoriteConfig(output_file=output_file)

        pack_repository(sample_files, config)

        assert os.path.exists(output_file)
        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "=== DIRECTORY TREE" in content
            assert "=== PACKED FILES ===" in content
            assert "main.py" in content
            assert "Hello from Python" in content

    def test_pack_repository_with_custom_instructions(self, sample_files):
        """Test packing with custom instructions."""
        output_file = os.path.join(sample_files, "output.txt")
        config = CodeoriteConfig(
            output_file=output_file,
            custom_instructions=["# Custom Header", "Instructions here"],
        )

        pack_repository(sample_files, config)

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "=== Custom Instructions ===" in content
            assert "# Custom Header" in content
            assert "Instructions here" in content

    def test_pack_repository_empty(self, temp_workspace):
        """Test packing an empty repository."""
        output_file = os.path.join(temp_workspace, "output.txt")
        config = CodeoriteConfig(output_file=output_file)

        pack_repository(temp_workspace, config)

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()
            # Check for the exact section headers
            assert "=== DIRECTORY TREE (INCLUDED ONLY) ===" in content
            assert "=== PACKED FILES ===" in content
            # Verify that there's no content between the headers (just whitespace)
            sections = content.split("===")
            # Remove empty strings from split
            sections = [s.strip() for s in sections if s.strip()]
            assert len(sections) == 2
            assert sections[0] == "DIRECTORY TREE (INCLUDED ONLY)"
            assert sections[1] == "PACKED FILES"
            # Verify no actual content
            assert not any(
                line.strip() for line in content.splitlines() if "===" not in line
            )

    @pytest.mark.parametrize(
        "file_content",
        [
            "Hello\x00World",  # Null bytes
            "Hello\uFFFFWorld",  # Invalid Unicode
            "Hello\x1AWorld",  # Control characters
        ],
    )
    def test_pack_repository_invalid_content(self, temp_workspace, file_content):
        """Test packing files with invalid content."""
        test_file = os.path.join(temp_workspace, "test.txt")
        with open(test_file, "w", encoding="utf-8", errors="replace") as f:
            f.write(file_content)

        output_file = os.path.join(temp_workspace, "output.txt")
        config = CodeoriteConfig(output_file=output_file)

        pack_repository(temp_workspace, config)

        # Should complete without errors and create output file
        assert os.path.exists(output_file)

    def test_pack_repository_large_files(self, temp_workspace):
        """Test packing large files."""
        large_file = os.path.join(temp_workspace, "large.txt")
        with open(large_file, "w") as f:
            f.write("x" * 1024 * 1024)  # 1MB file

        output_file = os.path.join(temp_workspace, "output.txt")
        config = CodeoriteConfig(output_file=output_file)

        pack_repository(temp_workspace, config)

        assert os.path.exists(output_file)
        assert os.path.getsize(output_file) > 1024 * 1024

    def test_pack_repository_permission_denied(self, temp_workspace):
        """Test handling of permission denied errors."""
        if os.name != "nt":  # Skip on Windows
            output_dir = os.path.join(temp_workspace, "restricted")
            os.makedirs(output_dir)
            os.chmod(output_dir, 0o000)  # Remove all permissions

            try:
                output_file = os.path.join(output_dir, "output.txt")
                config = CodeoriteConfig(output_file=output_file)

                with pytest.raises(PermissionError):
                    pack_repository(temp_workspace, config)
            finally:
                os.chmod(output_dir, 0o755)  # Restore permissions

    def test_pack_repository_symlink_handling(self, temp_workspace):
        """Test handling of symbolic links in repository."""
        if os.name != "nt":  # Skip on Windows
            # Create a file and a symlink to it
            real_file = os.path.join(temp_workspace, "real_file.py")
            symlink = os.path.join(temp_workspace, "link_file.py")
            with open(real_file, "w") as f:
                f.write("print('real file')")
            os.symlink(real_file, symlink)

            config = CodeoriteConfig(
                output_file=os.path.join(temp_workspace, "output.txt")
            )
            pack_repository(temp_workspace, config)

            with open(config.output_file, "r") as f:
                content = f.read()
                # Verify both real file and symlink are handled appropriately
                assert "real_file.py" in content
                # Implementation-dependent: decide if symlinks should be included
                # assert "link_file.py" in content

    def test_pack_repository_max_file_size(self, temp_workspace):
        """Test handling of very large files with size limits."""
        large_file = os.path.join(temp_workspace, "huge.txt")
        with open(large_file, "w") as f:
            f.write("x" * (10 * 1024 * 1024))  # 10MB file

        config = CodeoriteConfig(output_file=os.path.join(temp_workspace, "output.txt"))
        # Depending on implementation, should either:
        # 1. Skip files above certain size
        # 2. Truncate files
        # 3. Handle them normally
        pack_repository(temp_workspace, config)
        assert os.path.exists(config.output_file)

    def test_pack_repository_special_filenames(self, temp_workspace):
        """Test handling of special filenames and characters."""
        special_files = {
            "file with spaces.py": "print('spaces')",
            "file_with_émoji🐍.py": "print('emoji')",
            "file.with.dots.py": "print('dots')",
            "-file-with-dashes-.py": "print('dashes')",
            "!special!chars#.py": "print('special')",
            "नेपाली_फाइल.py": "print('unicode')",
        }

        for filename, content in special_files.items():
            try:
                filepath = os.path.join(temp_workspace, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
            except OSError:
                continue  # Skip if OS doesn't support the filename

        config = CodeoriteConfig(output_file=os.path.join(temp_workspace, "output.txt"))
        pack_repository(temp_workspace, config)

        with open(config.output_file, "r", encoding="utf-8") as f:
            content = f.read()
            for filename in special_files.keys():
                if os.path.exists(os.path.join(temp_workspace, filename)):
                    assert filename in content

    def test_pack_repository_concurrent_modification(self, temp_workspace):
        """Test handling of files being modified during packing."""
        import threading
        import time

        test_file = os.path.join(temp_workspace, "changing.py")
        with open(test_file, "w") as f:
            f.write("initial content")

        def modify_file():
            time.sleep(0.1)  # Small delay to ensure packing has started
            with open(test_file, "w") as f:
                f.write("modified content")

        config = CodeoriteConfig(output_file=os.path.join(temp_workspace, "output.txt"))

        # Start file modification in background
        thread = threading.Thread(target=modify_file)
        thread.start()

        # Pack repository while file is being modified
        pack_repository(temp_workspace, config)

        thread.join()
        assert os.path.exists(config.output_file)

    def test_pack_repository_error_recovery(self, temp_workspace):
        """Test recovery from errors during packing."""
        # Create a file that will cause an error when read
        error_file = os.path.join(temp_workspace, "error.py")
        with open(error_file, "w") as f:
            f.write("good content")

        # Create some valid files too
        valid_file = os.path.join(temp_workspace, "valid.py")
        with open(valid_file, "w") as f:
            f.write("print('valid')")

        # Mock os.path.getsize to raise error for specific file
        original_getsize = os.path.getsize

        def mock_getsize(path):
            if "error.py" in path:
                raise OSError("Simulated error")
            return original_getsize(path)

        # Patch getsize temporarily
        import unittest.mock

        with unittest.mock.patch("os.path.getsize", side_effect=mock_getsize):
            config = CodeoriteConfig(
                output_file=os.path.join(temp_workspace, "output.txt")
            )
            pack_repository(temp_workspace, config)

        # Should still create output with valid files
        with open(config.output_file, "r") as f:
            content = f.read()
            assert "valid.py" in content

    @pytest.mark.parametrize(
        "scenario",
        [
            "empty_file",
            "binary_file",
            "long_lines",
            "mixed_line_endings",
        ],
    )
    def test_pack_repository_file_content_variations(self, temp_workspace, scenario):
        """Test handling of various file content scenarios."""
        test_file = os.path.join(temp_workspace, f"{scenario}.txt")

        if scenario == "empty_file":
            open(test_file, "w").close()
        elif scenario == "binary_file":
            with open(test_file, "wb") as f:
                f.write(bytes(range(256)))
        elif scenario == "long_lines":
            with open(test_file, "w") as f:
                f.write("x" * 10000 + "\n")  # Very long line
        elif scenario == "mixed_line_endings":
            with open(test_file, "w", newline="") as f:
                f.write("line1\r\nline2\nline3\rline4")

        config = CodeoriteConfig(output_file=os.path.join(temp_workspace, "output.txt"))
        pack_repository(temp_workspace, config)

        assert os.path.exists(config.output_file)
        with open(config.output_file, "r") as f:
            content = f.read()
            assert f"{scenario}.txt" in content

    def test_permission_errors(self, temp_workspace):
        """Test handling of various permission error scenarios."""
        if os.name != "nt":  # Skip on Windows
            # Test output directory permission
            output_dir = os.path.join(temp_workspace, "restricted")
            os.makedirs(output_dir)
            os.chmod(output_dir, 0o000)  # Remove all permissions

            try:
                output_file = os.path.join(output_dir, "output.txt")
                config = CodeoriteConfig(output_file=output_file)

                with pytest.raises(PermissionError):
                    pack_repository(temp_workspace, config)
            finally:
                os.chmod(output_dir, 0o755)  # Restore permissions

            # Test source directory permission
            src_dir = os.path.join(temp_workspace, "src")
            os.makedirs(src_dir)
            test_file = os.path.join(src_dir, "test.py")
            with open(test_file, "w") as f:
                f.write("print('test')")

            # First make the file readable to ensure it's collected
            os.chmod(test_file, 0o644)

            # Create config that will try to read the Python file
            config = CodeoriteConfig(
                output_file=os.path.join(temp_workspace, "output.txt"),
                languages_included=["python"],
            )

            # Now remove read permissions from the file
            os.chmod(test_file, 0o000)

            try:
                with pytest.raises(PermissionError):
                    pack_repository(temp_workspace, config)
            finally:
                # Restore permissions to clean up
                os.chmod(test_file, 0o644)


@pytest.mark.usefixtures("cleanup_output_files")
class TestCLI:
    """Test suite for command-line interface functionality."""

    @pytest.fixture
    def mock_pack_repository(self):
        """Fixture to mock pack_repository function."""
        with unittest.mock.patch("codeorite.cli.pack_repository") as mock:
            yield mock

    @pytest.fixture
    def config_file(self, temp_workspace):
        """Fixture to create a sample config file."""
        config_path = os.path.join(temp_workspace, "codeorite_config.yaml")
        config_data = {
            "output_file": "from_config.txt",
            "languages_included": ["python"],
            "languages_excluded": ["javascript"],
            "includes": [".txt"],
            "excludes": [".md"],
            "custom_instructions": ["# From Config"],
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
        return config_path

    def test_default_arguments(self, temp_workspace, mock_pack_repository):
        """Test CLI with default arguments."""
        from codeorite.cli import run_cli

        with unittest.mock.patch.object(sys, "argv", ["codeorite"]):
            exit_code = run_cli([])

        mock_pack_repository.assert_called_once()
        args, kwargs = mock_pack_repository.call_args
        assert args[0] == os.path.abspath(".")  # Default root directory
        assert isinstance(args[1], CodeoriteConfig)
        assert args[1].output_file == DEFAULT_OUTPUT_FILE
        assert exit_code == 0

    def test_all_arguments_specified(self, temp_workspace, mock_pack_repository):
        """Test CLI with all arguments explicitly specified."""
        from codeorite.cli import run_cli

        # Create a config file
        config_path = os.path.join(temp_workspace, "custom_config.yaml")
        config_data = {
            "output_file": "from_config.txt",
            "languages_included": ["python"],
            "languages_excluded": [],
            "includes": [],
            "excludes": [],
            "custom_instructions": [],
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        test_args = [
            "--root",
            temp_workspace,
            "--config",
            config_path,
            "--output-file",
            "output.txt",
            "--languages-included",
            "python",
            "rust",
            "--languages-excluded",
            "javascript",
            "--includes",
            ".txt",
            ".log",
            "--excludes",
            ".md",
            ".yaml",
            "--custom-instructions",
            "Instruction 1",
            "Instruction 2",
        ]

        exit_code = run_cli(test_args)
        assert exit_code == 0

        mock_pack_repository.assert_called_once()
        args, kwargs = mock_pack_repository.call_args
        assert args[0] == os.path.abspath(temp_workspace)
        config = args[1]
        assert config.output_file == "output.txt"
        assert set(config.languages_included) == {"python", "rust"}
        assert config.languages_excluded == ["javascript"]
        assert set(config.includes) == {".txt", ".log"}
        assert set(config.excludes) == {".md", ".yaml"}
        assert config.custom_instructions == ["Instruction 1", "Instruction 2"]

    def test_config_file_override(
        self, temp_workspace, config_file, mock_pack_repository
    ):
        """Test that CLI arguments properly override config file settings."""
        from codeorite.cli import run_cli

        test_args = [
            "--root",
            temp_workspace,
            "--config",
            config_file,
            "--output-file",
            "cli_override.txt",
            "--languages-included",
            "rust",  # Override config's python
        ]

        exit_code = run_cli(test_args)
        assert exit_code == 0

        mock_pack_repository.assert_called_once()
        args, kwargs = mock_pack_repository.call_args
        config = args[1]
        assert config.output_file == "cli_override.txt"  # CLI value
        assert config.languages_included == ["rust"]  # CLI value
        assert config.languages_excluded == ["javascript"]  # From config file
        assert config.includes == [".txt"]  # From config file

    def test_help_message(self, capsys):
        """Test that help message is displayed correctly."""
        from codeorite.cli import run_cli

        with pytest.raises(SystemExit) as exc_info:
            run_cli(["--help"])

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        help_text = captured.out

        # Verify help message contains all argument descriptions
        assert "--root" in help_text
        assert "--config" in help_text
        assert "--output-file" in help_text
        assert "--languages-included" in help_text
        assert "--languages-excluded" in help_text
        assert "--includes" in help_text
        assert "--excludes" in help_text
        assert "--custom-instructions" in help_text
        assert "Package a repository into a single text file" in help_text

    @pytest.mark.parametrize(
        "invalid_args,expected_error",
        [
            (["--root", "/nonexistent/path"], "Directory does not exist"),
            (
                ["--languages-included", "python", "--languages-excluded", "python"],
                "Cannot include and exclude the same language",
            ),
            (["--output-file", ""], "Output file path cannot be empty"),
            (
                ["--includes", ".py", "--excludes", ".py"],
                "Cannot include and exclude the same extension",
            ),
        ],
    )
    def test_invalid_arguments(self, invalid_args, expected_error, capsys):
        """Test handling of invalid command-line arguments."""
        from codeorite.cli import run_cli

        exit_code = run_cli(invalid_args)
        assert exit_code != 0

        captured = capsys.readouterr()
        assert expected_error in captured.err

    def test_nonexistent_config_file(self, temp_workspace, mock_pack_repository):
        """Test behavior with non-existent config file."""
        from codeorite.cli import run_cli

        nonexistent_config = os.path.join(temp_workspace, "nonexistent.yaml")
        test_args = ["--root", temp_workspace, "--config", nonexistent_config]

        exit_code = run_cli(test_args)
        assert exit_code == 1

        mock_pack_repository.assert_not_called()

    def test_exit_codes(self, temp_workspace):
        """Test various exit codes based on different scenarios."""
        from codeorite.cli import run_cli

        # Test successful execution
        with unittest.mock.patch("codeorite.cli.pack_repository"):
            exit_code = run_cli(["--root", temp_workspace])
            assert exit_code == 0

        # Test file permission error
        with unittest.mock.patch("codeorite.cli.pack_repository") as mock:
            mock.side_effect = PermissionError("Access denied")
            exit_code = run_cli(["--root", temp_workspace])
            assert exit_code == 2

        # Test general error
        with unittest.mock.patch("codeorite.cli.pack_repository") as mock:
            mock.side_effect = Exception("Unknown error")
            exit_code = run_cli(["--root", temp_workspace])
            assert exit_code == 1

    def test_argument_type_validation(self, mock_pack_repository):
        """Test validation of argument types."""
        from codeorite.cli import run_cli

        # Test invalid type for --languages-included
        exit_code = run_cli(["--languages-included", "123"])
        assert exit_code != 0

        # Test invalid extension format
        exit_code = run_cli(["--includes", "py"])  # Missing dot
        assert exit_code != 0

    def test_main_function(self):
        """Test the main() function that wraps run_cli()."""
        from codeorite.cli import main

        with mock.patch("codeorite.cli.run_cli", return_value=42) as mock_run_cli:
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 42
            mock_run_cli.assert_called_once_with()

    def test_cli_with_no_args(self):
        """Test CLI behavior when no args are provided (using None)."""
        from codeorite.cli import run_cli

        with mock.patch("sys.argv", ["codeorite"]):
            exit_code = run_cli(None)  # Should use sys.argv[1:]
            assert exit_code == 0

    def test_validate_extensions_none(self):
        """Test validate_extensions with None input."""
        from codeorite.cli import validate_extensions

        result = validate_extensions(None)
        assert result is None

    def test_validate_languages_none(self):
        """Test validate_languages with None input."""
        from codeorite.cli import validate_languages

        result = validate_languages(None)
        assert result is None

    def test_exit_with_error(self, capsys):
        """Test exit_with_error function."""
        from codeorite.cli import exit_with_error

        test_message = "Test error message"
        test_code = 42

        with pytest.raises(SystemExit) as exc_info:
            exit_with_error(test_message, test_code)

        assert exc_info.value.code == test_code
        captured = capsys.readouterr()
        assert test_message in captured.err

    def test_config_file_encoding(self, temp_workspace, mock_pack_repository):
        """Test handling of config files with different encodings."""
        from codeorite.cli import run_cli

        # Test UTF-16 encoded config
        config_path = os.path.join(temp_workspace, "utf16.yaml")
        config_data = {
            "output_file": "test.txt",
            "languages_included": ["python"],
            "custom_instructions": ["# UTF-16 Test", "测试", "テスト", "🐍"],
        }

        with open(config_path, "w", encoding="utf-16") as f:
            yaml.dump(config_data, f, allow_unicode=True)

        test_args = ["--root", temp_workspace, "--config", config_path]
        exit_code = run_cli(test_args)
        assert exit_code == 1  # Should fail gracefully

        # Test UTF-8 with BOM
        config_path = os.path.join(temp_workspace, "utf8bom.yaml")
        with open(config_path, "wb") as f:
            f.write(b"\xef\xbb\xbf")  # UTF-8 BOM
            f.write(yaml.dump(config_data).encode("utf-8"))

        test_args = ["--root", temp_workspace, "--config", config_path]
        exit_code = run_cli(test_args)
        assert exit_code == 0
        mock_pack_repository.assert_called_once()

    def test_large_config_file(self, temp_workspace, mock_pack_repository):
        """Test handling of very large config files."""
        from codeorite.cli import run_cli

        config_path = os.path.join(temp_workspace, "large.yaml")
        config_data = {
            "output_file": "test.txt",
            "languages_included": ["python"],
            # Create a large custom_instructions list
            "custom_instructions": [f"Line {i}" for i in range(10000)],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        test_args = ["--root", temp_workspace, "--config", config_path]
        exit_code = run_cli(test_args)
        assert exit_code == 0
        mock_pack_repository.assert_called_once()

    def test_relative_paths_in_config(self, temp_workspace, mock_pack_repository):
        """Test handling of relative paths in config values."""
        from codeorite.cli import run_cli

        # Create a nested config structure
        os.makedirs(os.path.join(temp_workspace, "configs/nested"))
        config_path = os.path.join(temp_workspace, "configs/nested/config.yaml")

        config_data = {
            "output_file": "../../output.txt",  # Relative path going up
            "languages_included": ["python"],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        test_args = ["--root", temp_workspace, "--config", config_path]
        exit_code = run_cli(test_args)
        assert exit_code == 0
        mock_pack_repository.assert_called_once()

        # Verify the output path was resolved correctly
        args, _ = mock_pack_repository.call_args
        assert args[1].output_file == "../../output.txt"

    def test_concurrent_config_modification(self, temp_workspace, mock_pack_repository):
        """Test handling of config file being modified during execution."""
        import threading
        import time

        from codeorite.cli import run_cli

        config_path = os.path.join(temp_workspace, "changing.yaml")
        original_config = {
            "output_file": "original.txt",
            "languages_included": ["python"],
        }

        with open(config_path, "w") as f:
            yaml.dump(original_config, f)

        def modify_config():
            time.sleep(0.1)  # Small delay
            modified_config = {
                "output_file": "modified.txt",
                "languages_included": ["rust"],
            }
            with open(config_path, "w") as f:
                yaml.dump(modified_config, f)

        thread = threading.Thread(target=modify_config)
        thread.start()

        test_args = ["--root", temp_workspace, "--config", config_path]
        exit_code = run_cli(test_args)

        thread.join()
        assert exit_code == 0  # Should use the config as it was when first read
        mock_pack_repository.assert_called_once()

    def test_validate_config_args_usage(self, temp_workspace, mock_pack_repository):
        """Test that validate_config properly uses the args parameter."""
        from codeorite.cli import ValidationError, run_cli, validate_config

        # Create a config where validation might depend on args
        config_path = os.path.join(temp_workspace, "config.yaml")
        config_data = {
            "output_file": "test.txt",
            "languages_included": ["python"],
            "languages_excluded": ["python"],  # Conflict with includes
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        # The args should affect validation
        test_args = ["--root", temp_workspace, "--config", config_path]
        exit_code = run_cli(test_args)
        assert exit_code == 1  # Should fail due to language conflict
        mock_pack_repository.assert_not_called()

    @pytest.mark.parametrize(
        "scenario,config_content,expected_code",
        [
            ("empty", "", 0),  # Empty file
            ("malformed", "malformed: yaml: content: :", 1),  # Malformed YAML
            (
                "invalid_format",
                "['not', 'a', 'dict']",
                1,
            ),  # Valid YAML but wrong format
            ("valid", {"output_file": "test.txt"}, 0),  # Valid config
            (
                "utf8_bom",
                b"\xef\xbb\xbf"
                + yaml.dump({"output_file": "test.txt"}).encode("utf-8"),
                0,
            ),  # UTF-8 with BOM
        ],
    )
    def test_config_file_loading(
        self,
        temp_workspace,
        mock_pack_repository,
        scenario,
        config_content,
        expected_code,
    ):
        """Test various config file loading scenarios."""
        from codeorite.cli import run_cli

        config_path = os.path.join(temp_workspace, f"{scenario}.yaml")

        if isinstance(config_content, bytes):
            with open(config_path, "wb") as f:
                f.write(config_content)
        elif isinstance(config_content, dict):
            with open(config_path, "w") as f:
                yaml.dump(config_content, f)
        else:
            with open(config_path, "w") as f:
                f.write(config_content)

        test_args = ["--root", temp_workspace, "--config", config_path]
        exit_code = run_cli(test_args)
        assert exit_code == expected_code

        if expected_code == 0:
            mock_pack_repository.assert_called_once()
        else:
            mock_pack_repository.assert_not_called()

    def test_config_file_io_error(self, temp_workspace, mock_pack_repository):
        """Test handling of IO errors when reading config file."""
        import errno

        from codeorite.cli import run_cli

        def mock_open(*args, **kwargs):
            raise IOError(errno.EIO, "I/O error")

        with mock.patch("builtins.open", side_effect=mock_open):
            test_args = ["--root", temp_workspace, "--config", "config.yaml"]
            exit_code = run_cli(test_args)
            assert exit_code == 1
            mock_pack_repository.assert_not_called()

    def test_config_file_permission_error(self, temp_workspace, mock_pack_repository):
        """Test handling of permission errors when reading config file."""
        from codeorite.cli import run_cli

        config_path = os.path.join(temp_workspace, "noperm.yaml")
        with open(config_path, "w") as f:
            yaml.dump({}, f)

        def mock_open(*args, **kwargs):
            raise PermissionError("Permission denied")

        with mock.patch("builtins.open", side_effect=mock_open):
            test_args = ["--root", temp_workspace, "--config", config_path]
            exit_code = run_cli(test_args)
            assert exit_code == 1
            mock_pack_repository.assert_not_called()

    def test_validate_config_with_none_values(
        self, temp_workspace, mock_pack_repository
    ):
        """Test validate_config with None values in config."""
        from codeorite.cli import run_cli

        # Test with None output_file
        config_path = os.path.join(temp_workspace, "config.yaml")
        config_data = {
            "output_file": None,  # Invalid value
            "languages_included": ["python"],
            "languages_excluded": ["rust"],
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        test_args = [
            "--root",
            temp_workspace,
            "--config",
            config_path,
            "--output-file",
            "",
        ]
        exit_code = run_cli(test_args)
        assert exit_code == 1  # Should fail due to empty output_file
        mock_pack_repository.assert_not_called()

        # Test with None language lists (should use defaults)
        config_data = {
            "output_file": "output.txt",
            "languages_included": None,
            "languages_excluded": None,
        }

        with open(config_path, "w") as f:
            yaml.dump(config_data, f)

        test_args = ["--root", temp_workspace, "--config", config_path]
        exit_code = run_cli(test_args)
        assert exit_code == 0  # Should succeed with default empty lists
        mock_pack_repository.assert_called_once()

    def test_non_default_config_file_missing(
        self, temp_workspace, mock_pack_repository
    ):
        """Test handling of missing non-default config file."""
        from codeorite.cli import DEFAULT_CONFIG_FILE, run_cli

        # Use a non-default config file path that doesn't exist
        test_args = ["--root", temp_workspace, "--config", "non_default_config.yaml"]
        exit_code = run_cli(test_args)
        assert exit_code == 1  # Should fail for non-default missing config
        mock_pack_repository.assert_not_called()

    def test_unexpected_error_handling(self, temp_workspace, mock_pack_repository):
        """Test handling of unexpected errors in run_cli."""
        from codeorite.cli import run_cli

        def mock_validate_directory(*args):
            raise RuntimeError("Unexpected runtime error")

        with mock.patch(
            "codeorite.cli.validate_directory", side_effect=mock_validate_directory
        ):
            test_args = ["--root", temp_workspace]
            exit_code = run_cli(test_args)
            assert exit_code == 1
            mock_pack_repository.assert_not_called()
