# Codeorite

A CLI tool to package repository code into a single text file, respecting .gitignore rules.

## Installation

```bash
pip install codeorite
```

## Usage

Basic usage:
```bash
codeorite --root /path/to/repo --output-file output.txt
```

### Options

- `--root`: Repository root directory (default: current directory)
- `--output-file`: Output file path
- `--config`: Path to config file (default: codeorite_config.yaml)
- `--languages-included`: Languages to include (e.g., python rust javascript)
- `--languages-excluded`: Languages to exclude
- `--includes`: Additional file extensions to include (e.g., .md .txt)
- `--excludes`: File extensions to exclude (e.g., .pyc .log)
- `--custom-instructions`: Lines to prepend as instructions

### Examples

Package only Python files:
```bash
codeorite --root . --output-file output.txt --languages-included python
```

Package multiple languages, exclude web assets:
```bash
codeorite --root . --output-file multi.txt \
    --languages-included python rust typescript javascript \
    --excludes .json .html .css
```

Include markdown files, exclude Python:
```bash
codeorite --root . --output-file docs.txt \
    --includes .md \
    --excludes .py .pyc
```

### Configuration File

Create `codeorite_config.yaml` in your repository:

```yaml
languages_included:
  - python
  - rust
languages_excluded:
  - javascript
includes:
  - .md
excludes:
  - .pyc
custom_instructions:
  - "# Project: MyRepo"
  - "# Author: Dev Team"
```

## Output Format

The output file contains:
1. Custom instructions (if provided)
2. Directory tree of included files
3. Contents of each included file

## Notes

- Respects .gitignore rules
- CLI arguments override config file settings
- Cannot include and exclude the same language/extension
