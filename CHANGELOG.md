# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] - 2024-12-27

### Changed
- Testing automated release workflow with GitHub Actions

## [0.2.3] - 2024-12-27

### Fixed
- Added missing project URLs in PyPI package metadata

## [0.2.2] - 2024-12-27

### Added
- Project URLs for homepage, repository, and documentation

### Changed
- Refactored `build_directory_tree` into smaller, more focused functions
- Improved code organization following Clean Code principles
- Enhanced type hints and documentation

## [0.2.1] - 2024-12-27

### Changed
- Updated default logging level to WARNING to reduce verbosity
- Modified console handler to consistently use WARNING level
- Updated test cases to reflect new logging behavior

## [0.2.0] - 2024-12-27

### Changed
- Reduced logging verbosity by setting default log level to WARNING
- Improved console output by filtering out DEBUG and INFO messages

## [0.1.0] - 2024-12-27

### Added
- Initial release
- Core functionality to package repository into a single text file
- Support for .gitignore patterns
- Command-line interface with configurable options
- Basic logging system
- Test suite for core functionality 