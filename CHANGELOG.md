# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive test coverage reporting with pytest-cov
- CI/CD pipeline with GitHub Actions
- Support for coverage reports in XML and HTML formats
- Enhanced test suite for all generators (Go, C#, Python, TypeScript, Protocol Buffers)

### Changed
- Improved package structure with proper src/ layout
- Enhanced pyproject.toml with better metadata and dependencies
- Updated Python version requirement to >=3.8

### Fixed
- Import path issues in test suite
- External reference handling in generators
- Field numbering in Protocol Buffer generation

## [0.2.0] - 2025-10-03

### Added
- Unit test suite with pytest framework
- Code coverage reporting
- GitHub Actions CI/CD pipeline
- Support for default values in Python generators
- External reference deduplication
- TypeScript import generation and index.ts exports
- Comprehensive tests for all language generators

### Changed
- Improved error handling and validation
- Better external schema reference resolution
- Enhanced generator output formatting

### Fixed
- Duplicate type generation issues
- Missing imports in generated TypeScript code
- Default value handling in various generators

## [0.1.0] - Initial Release

### Added
- Basic JSON/YAML schema to code generation
- Support for Go, Python, TypeScript, C#, and Protocol Buffer output
- Command-line interface
- External schema reference support
- Basic validation and error handling