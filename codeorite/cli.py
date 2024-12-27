"""CLI interface for Codeorite.

This module handles command-line argument parsing and validation for the repository packing tool.
Key features:
- Argument parsing with sane defaults
- Config file loading with YAML support
- Input validation for paths, languages, and extensions
- Error handling with appropriate exit codes

Exit codes:
    0: Success
    1: Validation/config error
    2: Permission error
"""

import argparse
import os
import sys
from typing import List, NoReturn, Optional, Union

import yaml

from codeorite.config import DEFAULT_CONFIG_FILE, SUPPORTED_LANGUAGES, CodeoriteConfig
from codeorite.main import pack_repository


class ValidationError(Exception):
    """Raised when input validation fails.

    Used to distinguish validation errors (bad input) from system errors (permissions, IO).
    These result in exit code 1 and a user-friendly error message.
    """

    pass


def exit_with_error(message: str, code: int = 1) -> NoReturn:
    """Exit with a formatted error message and code.

    Args:
        message: Error message to display to stderr
        code: Exit code (1 for validation, 2 for permissions)
    """
    sys.stderr.write(f"{message}\n")
    sys.exit(code)


def validate_directory(path: str) -> str:
    """Validate that a directory exists and is accessible.

    Args:
        path: Directory path to validate

    Returns:
        Validated path

    Raises:
        ValidationError: If directory doesn't exist
        PermissionError: If directory isn't accessible
    """
    if not os.path.isdir(path):
        raise ValidationError(f"Directory does not exist: {path}")
    return path


def validate_output_file(path: Optional[str]) -> Optional[str]:
    """Validate output file path.

    Args:
        path: Output file path to validate

    Returns:
        Validated path

    Raises:
        ValidationError: If path is empty or None
        PermissionError: If parent directory isn't writable
    """
    if path is None or not path:
        raise ValidationError("Output file path cannot be empty")
    return path


def validate_extension(ext: str) -> str:
    """Validate file extension format.

    Args:
        ext: File extension (e.g., '.py', '.rs')

    Returns:
        Validated extension

    Raises:
        ValidationError: If extension doesn't start with dot
    """
    if not ext.startswith("."):
        raise ValidationError(f"Invalid extension format (must start with dot): {ext}")
    return ext


def validate_extensions(exts: Optional[List[str]]) -> Optional[List[str]]:
    """Validate list of file extensions.

    Args:
        exts: List of extensions to validate

    Returns:
        List of validated extensions

    Raises:
        ValidationError: If any extension is invalid
    """
    if exts is not None:
        return [validate_extension(ext) for ext in exts]
    return exts


def validate_language(lang: str) -> str:
    """Validate that a language is supported.

    Args:
        lang: Language name to validate (case-insensitive)

    Returns:
        Validated language name

    Raises:
        ValidationError: If language isn't in SUPPORTED_LANGUAGES
    """
    if lang.lower() not in {k.lower() for k in SUPPORTED_LANGUAGES.keys()}:
        raise ValidationError(f"Unsupported language: {lang}")
    return lang


def validate_languages(langs: Optional[List[str]]) -> Optional[List[str]]:
    """Validate list of programming languages.

    Args:
        langs: List of languages to validate

    Returns:
        List of validated languages

    Raises:
        ValidationError: If any language is invalid
    """
    if langs is not None:
        return [validate_language(lang) for lang in langs]
    return langs


def validate_config(config: CodeoriteConfig) -> None:
    """Validate configuration consistency.

    Checks for:
    - Language conflicts (same language in include/exclude)
    - Extension conflicts (same extension in include/exclude)

    Args:
        config: Configuration to validate

    Raises:
        ValidationError: If configuration is inconsistent
    """
    # Check for language conflicts
    included_langs = set(lang.lower() for lang in config.languages_included)
    excluded_langs = set(lang.lower() for lang in config.languages_excluded)
    if included_langs & excluded_langs:
        raise ValidationError("Cannot include and exclude the same language")

    # Check for extension conflicts
    included_exts = set(ext.lower() for ext in config.includes)
    excluded_exts = set(ext.lower() for ext in config.excludes)
    if included_exts & excluded_exts:
        raise ValidationError("Cannot include and exclude the same extension")


def load_config_file(config_path: str) -> Union[dict, None]:
    """Load and parse YAML configuration file.

    Args:
        config_path: Path to YAML config file

    Returns:
        Parsed config dict or None if file doesn't exist

    Raises:
        ValidationError: If config file is invalid
    """
    if not os.path.exists(config_path):
        if config_path == DEFAULT_CONFIG_FILE:
            return None
        raise ValidationError(f"Config file not found: {config_path}")

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if data is not None and not isinstance(data, dict):
                raise ValidationError(f"Invalid config file format: {config_path}")
            return data
    except yaml.YAMLError as e:
        raise ValidationError(f"Error parsing config file: {e}")


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="Package a repository into a single text file respecting .gitignore.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--root",
        type=str,
        default=".",
        help="Root directory of the repository (default: current directory).",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=DEFAULT_CONFIG_FILE,
        help="Path to the YAML configuration file (default: codeorite_config.yaml).",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Override the output file name specified in config.",
    )
    parser.add_argument(
        "--languages-included",
        nargs="*",
        help=f"List of languages to include (overrides config). Supported: {', '.join(SUPPORTED_LANGUAGES.keys())}",
    )
    parser.add_argument(
        "--languages-excluded",
        nargs="*",
        help="List of languages to exclude (overrides config).",
    )
    parser.add_argument(
        "--includes",
        nargs="*",
        help="List of explicit file extensions to include (e.g. .py, .rs).",
    )
    parser.add_argument(
        "--excludes",
        nargs="*",
        help="List of explicit file extensions to exclude (e.g. .md, .yaml).",
    )
    parser.add_argument(
        "--custom-instructions",
        nargs="*",
        help="List of lines to prepend as custom instructions.",
    )
    return parser


def update_config_from_args(config: CodeoriteConfig, args: argparse.Namespace) -> None:
    """Update configuration with command line arguments.

    Args:
        config: Configuration object to update
        args: Parsed command line arguments
    """
    if args.output_file is not None:
        config.output_file = validate_output_file(args.output_file)
    if args.languages_included is not None:
        config.languages_included = validate_languages(args.languages_included)
    if args.languages_excluded is not None:
        config.languages_excluded = validate_languages(args.languages_excluded)
    if args.includes is not None:
        config.includes = validate_extensions(args.includes)
    if args.excludes is not None:
        config.excludes = validate_extensions(args.excludes)
    if args.custom_instructions is not None:
        config.custom_instructions = args.custom_instructions


def run_cli(args_list: Optional[List[str]] = None) -> int:
    """Run the CLI with the given arguments.

    This is the main entry point for programmatic CLI usage.
    Handles argument parsing, validation, and repository packing.

    Args:
        args_list: Command line arguments (uses sys.argv[1:] if None)

    Returns:
        Exit code:
            0: Success
            1: Validation/config error (including config file permission errors)
            2: Repository packing permission error

    Example:
        >>> run_cli(['--root', '.', '--languages-included', 'python'])
        0
    """
    try:
        parser = create_argument_parser()
        args = parser.parse_args(args_list)

        # Validate root directory early
        validate_directory(args.root)

        try:
            # Load and validate configuration
            config_data = load_config_file(args.config)
            config = (
                CodeoriteConfig.from_file(args.config)
                if config_data
                else CodeoriteConfig()
            )

            # Update config with CLI arguments
            update_config_from_args(config, args)

            # Validate final configuration
            validate_config(config)

            try:
                # Pack repository - only repository packing permission errors get code 2
                pack_repository(os.path.abspath(args.root), config)
                return 0
            except PermissionError as e:
                sys.stderr.write(f"Permission denied: {e}\n")
                return 2
            except Exception as e:
                sys.stderr.write(f"Error: {str(e)}\n")
                return 1

        except (PermissionError, OSError) as e:
            # Config file permission errors get code 1
            sys.stderr.write(f"Configuration error: {str(e)}\n")
            return 1

    except ValidationError as e:
        sys.stderr.write(f"Validation error: {str(e)}\n")
        return 1
    except Exception as e:
        sys.stderr.write(f"Unexpected error: {str(e)}\n")
        return 1


def main() -> NoReturn:
    """Main entry point for the CLI.

    Wraps run_cli() to handle system exit.
    This is the function called when running `codeorite` from the command line.
    """
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
