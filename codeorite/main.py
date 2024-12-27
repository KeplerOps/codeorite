import os
from pathlib import Path

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from codeorite.config import CodeoriteConfig


def load_gitignore(gitignore_path):
    """
    Parse .gitignore lines using 'pathspec' for more accurate gitignore matching.
    Returns a PathSpec object, or None if .gitignore doesn't exist.
    """
    if not os.path.exists(gitignore_path):
        return None
    with open(gitignore_path, "r", encoding="utf-8") as f:
        spec = PathSpec.from_lines(GitWildMatchPattern, f)
    return spec


def is_ignored_by_gitignore(file_path, spec, root_path):
    """
    Checks if file_path is ignored by the given PathSpec (i.e., .gitignore).
    """
    if spec is None:
        return False
    rel_path = os.path.relpath(file_path, root_path)
    return spec.match_file(rel_path)


def build_directory_tree(root_dir, included_files):
    """
    Build a directory tree string that only includes folders that contain included files.
    """
    tree_lines = []
    included_paths = {Path(f).resolve() for f in included_files}

    for current_root, dirs, files in os.walk(root_dir):
        current_path = Path(current_root).resolve()

        sub_included = False

        for f in files:
            if Path(current_root, f).resolve() in included_paths:
                sub_included = True
                break

        for d in dirs:
            subdir_path = Path(current_root, d).resolve()
            if any(str(p).startswith(str(subdir_path)) for p in included_paths):
                sub_included = True
                break

        if sub_included:
            level = len(current_path.relative_to(root_dir).parts)
            indent = "    " * level
            tree_lines.append(f"{indent}{current_path.name}/")

    return "\n".join(tree_lines)


def collect_files(root_dir, config: CodeoriteConfig):
    """
    Collect files from root_dir based on config, ignoring .gitignore,
    and return a list of file paths to include.
    """
    gitignore_spec = load_gitignore(os.path.join(root_dir, ".gitignore"))
    exts_included, exts_excluded = config.resolve_extensions()

    included_files = []

    for current_root, dirs, files in os.walk(root_dir):
        if ".git" in current_root:
            continue

        for file_name in files:
            file_path = os.path.join(current_root, file_name)

            if is_ignored_by_gitignore(file_path, gitignore_spec, root_dir):
                continue

            ext = os.path.splitext(file_name)[1].lower()

            if (not exts_included or ext in exts_included) and (
                ext not in exts_excluded
            ):
                included_files.append(file_path)

    return included_files


def pack_repository(root_dir, config: CodeoriteConfig):
    """
    Package the repository into a single text file based on the config.
    """
    included_files = collect_files(root_dir, config)
    dir_tree_str = build_directory_tree(root_dir, included_files)

    with open(config.output_file, "w", encoding="utf-8") as f:
        if config.custom_instructions:
            f.write("=== Custom Instructions ===\n")
            for instruction in config.custom_instructions:
                f.write(instruction + "\n")
            f.write("\n")

        f.write("=== DIRECTORY TREE (INCLUDED ONLY) ===\n")
        f.write(dir_tree_str + "\n\n")

        f.write("=== PACKED FILES ===\n")
        for file_path in included_files:
            f.write(f"\n--- START OF FILE: {file_path} ---\n")
            with open(file_path, "r", encoding="utf-8", errors="replace") as src:
                f.write(src.read())
            f.write(f"\n--- END OF FILE: {file_path} ---\n")
