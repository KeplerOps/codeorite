"""Configuration handling for Codeorite.

This module handles configuration loading and validation, supporting both YAML files
and programmatic configuration. It defines the supported languages and their file extensions.

Example:
    >>> config = CodeoriteConfig(languages_included=['python'])
    >>> includes, excludes = config.resolve_extensions()
    >>> '.py' in includes
    True
"""

import os
from typing import List, Optional, Set, Tuple

import yaml

# Default configuration values
DEFAULT_CONFIG_FILE = "codeorite_config.yaml"
DEFAULT_OUTPUT_FILE = "output.txt"

# Mapping of supported languages to their file extensions
SUPPORTED_LANGUAGES = {
    "python": [".py"],
    "rust": [".rs"],
    "javascript": [".js"],
    "typescript": [".ts"],
    "go": [".go"],
    "java": [".java"],
    "cpp": [".cpp", ".hpp", ".h"],
    "c": [".c", ".h"],
}


class CodeoriteConfig:
    """Configuration for repository packing.

    Handles both file-based and programmatic configuration with validation.
    All fields are optional and have sensible defaults.

    Attributes:
        output_file (str): Path to write packed output (default: output.txt)
        languages_included (List[str]): Languages to include (default: all)
        languages_excluded (List[str]): Languages to exclude (default: none)
        includes (List[str]): Additional extensions to include (default: none)
        excludes (List[str]): Extensions to exclude (default: none)
        custom_instructions (List[str]): Lines to prepend to output (default: none)
    """

    def __init__(
        self,
        output_file: str = DEFAULT_OUTPUT_FILE,
        languages_included: Optional[List[str]] = None,
        languages_excluded: Optional[List[str]] = None,
        includes: Optional[List[str]] = None,
        excludes: Optional[List[str]] = None,
        custom_instructions: Optional[List[str]] = None,
    ):
        """Initialize configuration with optional overrides.

        Args:
            output_file: Path to write packed output
            languages_included: Languages to include (case-insensitive)
            languages_excluded: Languages to exclude (case-insensitive)
            includes: Additional file extensions to include (e.g., '.md')
            excludes: File extensions to exclude (e.g., '.pyc')
            custom_instructions: Lines to prepend to output
        """
        self.output_file = output_file
        self.languages_included = languages_included or []
        self.languages_excluded = languages_excluded or []
        self.includes = includes or []
        self.excludes = excludes or []
        self.custom_instructions = custom_instructions or []

    @classmethod
    def from_file(cls, config_path: str) -> "CodeoriteConfig":
        """Create configuration from YAML file.

        Loads configuration from a YAML file, falling back to defaults for
        missing or invalid values. File encoding issues are handled gracefully.

        Args:
            config_path: Path to YAML config file

        Returns:
            CodeoriteConfig with values from file or defaults

        Example:
            >>> config = CodeoriteConfig.from_file('codeorite_config.yaml')
        """
        try:
            if not os.path.exists(config_path):
                return cls()

            with open(config_path, "r", encoding="utf-8") as f:
                try:
                    data = yaml.safe_load(f) or {}
                    if not isinstance(data, dict):
                        return cls()
                    return cls(**data)
                except yaml.YAMLError:
                    return cls()
        except (IOError, UnicodeError):
            return cls()

    def resolve_extensions(self) -> Tuple[Set[str], Set[str]]:
        """Resolve included and excluded file extensions.

        Combines language-based extensions with explicitly included/excluded extensions.
        Handles case-sensitivity and duplicates.

        Returns:
            Tuple of (included_extensions, excluded_extensions)

        Example:
            >>> config = CodeoriteConfig(languages_included=['python'], includes=['.txt'])
            >>> includes, excludes = config.resolve_extensions()
            >>> sorted(includes)
            ['.py', '.txt']
        """
        includes = set()
        excludes = set()

        # Add extensions from included languages
        for lang in self.languages_included:
            lang_lower = lang.lower()
            if lang_lower in {k.lower() for k in SUPPORTED_LANGUAGES}:
                includes.update(
                    SUPPORTED_LANGUAGES[
                        next(k for k in SUPPORTED_LANGUAGES if k.lower() == lang_lower)
                    ]
                )

        # Add extensions from excluded languages
        for lang in self.languages_excluded:
            lang_lower = lang.lower()
            if lang_lower in {k.lower() for k in SUPPORTED_LANGUAGES}:
                excludes.update(
                    SUPPORTED_LANGUAGES[
                        next(k for k in SUPPORTED_LANGUAGES if k.lower() == lang_lower)
                    ]
                )

        # Add explicit includes/excludes
        includes.update(self.includes)
        excludes.update(self.excludes)

        # Excludes take precedence over includes
        includes -= excludes

        return includes, excludes
