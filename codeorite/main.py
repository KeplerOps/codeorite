"""Main functionality for Codeorite repository packing.

This module handles the core functionality of collecting and packaging repository files
according to the specified configuration and .gitignore rules.
"""

import os
from pathlib import Path

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from codeorite.config import CodeoriteConfig
from codeorite.logging import get_logger

logger = get_logger(__name__)


def load_gitignore(gitignore_path):
    """Parse .gitignore lines using 'pathspec' for more accurate gitignore matching.

    Args:
        gitignore_path: Path to .gitignore file

    Returns:
        PathSpec object, or None if .gitignore doesn't exist
    """
    if not os.path.exists(gitignore_path):
        logger.debug("No .gitignore found at %s", gitignore_path)
        return None

    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            spec = PathSpec.from_lines(GitWildMatchPattern, f)
            logger.debug("Loaded .gitignore from %s", gitignore_path)
            return spec
    except Exception as e:
        logger.warning("Error reading .gitignore at %s: %s", gitignore_path, e)
        return None


def is_ignored_by_gitignore(file_path, spec, root_path):
    """Check if file_path is ignored by the given PathSpec.

    Args:
        file_path: Path to check
        spec: PathSpec object from .gitignore
        root_path: Repository root path

    Returns:
        bool: True if file should be ignored
    """
    if spec is None:
        return False
    rel_path = os.path.relpath(file_path, root_path)
    is_ignored = spec.match_file(rel_path)
    if is_ignored:
        logger.debug("File ignored by .gitignore: %s", rel_path)
    return is_ignored


def _is_path_included(path: Path, included_paths: set[Path]) -> bool:
    """Check if a path or any of its subdirectories are included.

    Args:
        path: Path to check
        included_paths: Set of paths that are included

    Returns:
        bool: True if path or any subdirectory is included
    """
    return path in included_paths or any(
        str(p).startswith(str(path)) for p in included_paths
    )


def _format_tree_line(current_path: Path, root_path: Path) -> str:
    """Format a single line in the directory tree.

    Args:
        current_path: Current directory path
        root_path: Root directory path

    Returns:
        str: Formatted tree line with proper indentation
    """
    try:
        rel_path = current_path.relative_to(root_path)
        level = len(rel_path.parts) if str(rel_path) != "." else 0
        indent = "    " * level
        dir_name = current_path.name or root_path.name
        return f"{indent}{dir_name}/"
    except ValueError as e:
        logger.warning("Could not determine relative path for %s: %s", current_path, e)
        return ""


def _check_directory_inclusion(
    current_path: Path, files: list[str], dirs: list[str], included_paths: set[Path]
) -> bool:
    """Check if a directory should be included in the tree.

    Args:
        current_path: Current directory path
        files: List of files in the directory
        dirs: List of subdirectories
        included_paths: Set of included file paths

    Returns:
        bool: True if directory should be included
    """
    # Check if any files in this directory are included
    if any(
        _is_path_included(Path(current_path, f).resolve(), included_paths)
        for f in files
    ):
        return True

    # Check if any subdirectories contain included files
    return any(
        _is_path_included(Path(current_path, d).resolve(), included_paths) for d in dirs
    )


def build_directory_tree(root_dir: str, included_files: list[str]) -> str:
    """Build a directory tree string that only includes folders containing included files.

    This function creates a visual representation of the directory structure,
    showing only directories that contain files that were selected for inclusion.

    Args:
        root_dir: Repository root directory
        included_files: List of files to include

    Returns:
        str: Formatted directory tree
    """
    logger.debug("Building directory tree for %d included files", len(included_files))
    tree_lines = []
    root_path = Path(root_dir).resolve()
    included_paths = {Path(f).resolve() for f in included_files}

    for current_root, dirs, files in os.walk(root_dir):
        current_path = Path(current_root).resolve()

        if _check_directory_inclusion(current_path, files, dirs, included_paths):
            tree_line = _format_tree_line(current_path, root_path)
            if tree_line:
                tree_lines.append(tree_line)
                logger.debug("Added directory to tree: %s", current_path.name)

    return "\n".join(tree_lines)


def collect_files(root_dir, config: CodeoriteConfig):
    """Collect files from root_dir based on config and .gitignore rules.

    Args:
        root_dir: Repository root directory
        config: Configuration object

    Returns:
        list: List of file paths to include
    """
    logger.info("Collecting files from %s", root_dir)
    gitignore_spec = load_gitignore(os.path.join(root_dir, ".gitignore"))
    exts_included, exts_excluded = config.resolve_extensions()

    logger.debug("Extensions included: %s", exts_included or "all")
    logger.debug("Extensions excluded: %s", exts_excluded)

    included_files = []
    skipped_files = 0

    for current_root, dirs, files in os.walk(root_dir):
        if ".git" in current_root:
            logger.debug("Skipping .git directory: %s", current_root)
            continue

        for file_name in files:
            file_path = os.path.join(current_root, file_name)

            if is_ignored_by_gitignore(file_path, gitignore_spec, root_dir):
                skipped_files += 1
                continue

            ext = os.path.splitext(file_name)[1].lower()

            if (not exts_included or ext in exts_included) and (
                ext not in exts_excluded
            ):
                included_files.append(file_path)
                logger.debug("Including file: %s", file_path)
            else:
                skipped_files += 1
                logger.debug("Skipping file due to extension rules: %s", file_path)

    logger.info(
        "Found %d files to include (%d files skipped)",
        len(included_files),
        skipped_files,
    )
    return included_files


def pack_repository(root_dir, config: CodeoriteConfig):
    """Package the repository into a single text file based on the config.

    Args:
        root_dir: Repository root directory
        config: Configuration object
    """
    logger.info("Starting repository packing")
    logger.info("Output file: %s", config.output_file)

    included_files = collect_files(root_dir, config)
    dir_tree_str = build_directory_tree(root_dir, included_files)

    try:
        with open(config.output_file, "w", encoding="utf-8") as f:
            if config.custom_instructions:
                logger.debug(
                    "Writing %d custom instructions", len(config.custom_instructions)
                )
                f.write("=== Custom Instructions ===\n")
                for instruction in config.custom_instructions:
                    f.write(instruction + "\n")
                f.write("\n")

            logger.debug("Writing directory tree")
            f.write("=== DIRECTORY TREE (INCLUDED ONLY) ===\n")
            f.write(dir_tree_str + "\n\n")

            logger.info("Writing %d files to output", len(included_files))
            f.write("=== PACKED FILES ===\n")

            for file_path in included_files:
                logger.debug("Processing file: %s", file_path)
                f.write(f"\n--- START OF FILE: {file_path} ---\n")
                try:
                    with open(
                        file_path, "r", encoding="utf-8", errors="replace"
                    ) as src:
                        f.write(src.read())
                    f.write(f"\n--- END OF FILE: {file_path} ---\n")
                except Exception as e:
                    logger.error("Error processing file %s: %s", file_path, e)
                    raise

        logger.info("Repository successfully packed to %s", config.output_file)

    except Exception as e:
        logger.error("Failed to pack repository: %s", e)
        raise
