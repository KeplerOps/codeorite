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

from codeorite.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIG_FILE = "codeorite_config.yaml"
DEFAULT_OUTPUT_FILE = "output.txt"

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

        logger.debug(
            "Created configuration: output=%s, langs_in=%s, langs_ex=%s, includes=%s, excludes=%s",
            output_file,
            languages_included,
            languages_excluded,
            includes,
            excludes,
        )

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
        logger.debug("Loading configuration from %s", config_path)

        try:
            if not os.path.exists(config_path):
                logger.info("Config file not found at %s, using defaults", config_path)
                return cls()

            with open(config_path, "r", encoding="utf-8") as f:
                try:
                    data = yaml.safe_load(f) or {}
                    if not isinstance(data, dict):
                        logger.warning(
                            "Invalid config format in %s (not a dictionary), using defaults",
                            config_path,
                        )
                        return cls()
                    logger.info("Successfully loaded config from %s", config_path)
                    logger.debug("Config data: %s", data)
                    return cls(**data)
                except yaml.YAMLError as e:
                    logger.warning("YAML parsing error in %s: %s", config_path, e)
                    return cls()
        except (IOError, UnicodeError) as e:
            logger.warning("Error reading config file %s: %s", config_path, e)
            return cls()

    @classmethod
    def from_dict(cls, data: dict) -> "CodeoriteConfig":
        """Create configuration from a dictionary.

        Args:
            data: Dictionary containing configuration values

        Returns:
            CodeoriteConfig instance
        """
        logger.debug("Creating configuration from dictionary: %s", data)
        return cls(**data)

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
                lang_key = next(
                    k for k in SUPPORTED_LANGUAGES if k.lower() == lang_lower
                )
                exts = SUPPORTED_LANGUAGES[lang_key]
                includes.update(exts)
                logger.debug("Added extensions for language %s: %s", lang, exts)

        # Add extensions from excluded languages
        for lang in self.languages_excluded:
            lang_lower = lang.lower()
            if lang_lower in {k.lower() for k in SUPPORTED_LANGUAGES}:
                lang_key = next(
                    k for k in SUPPORTED_LANGUAGES if k.lower() == lang_lower
                )
                exts = SUPPORTED_LANGUAGES[lang_key]
                excludes.update(exts)
                logger.debug(
                    "Added excluded extensions for language %s: %s", lang, exts
                )

        # Add explicit includes/excludes
        if self.includes:
            logger.debug("Adding explicit includes: %s", self.includes)
            includes.update(self.includes)
        if self.excludes:
            logger.debug("Adding explicit excludes: %s", self.excludes)
            excludes.update(self.excludes)

        # Excludes take precedence over includes
        includes -= excludes

        logger.debug(
            "Final resolved extensions - includes: %s, excludes: %s", includes, excludes
        )
        return includes, excludes
