# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-23

### Changed
- Renamed package from `pgvector-context-engine` to `context-engine`
- Switched build backend from setuptools to hatchling
- Updated Python version requirement to >=3.11
- Added proper project metadata (author, classifiers, URLs)
- Added `Issues` URL to project links

### Added
- GitHub Actions CI pipeline (lint, test, build)
- GitHub Actions PyPI publish workflow (tag-based)
- GitHub Actions version check workflow
- `[dev]` extras now include black, ruff, mypy
- Tool configs for black, ruff, mypy in pyproject.toml

## [0.1.0] - 2025-01-01

### Added
- Initial release as `pgvector-context-engine`
- Core ContextEngine class with save, search, get_context
- CLI tool (`ctx-engine`)
- Ollama and OpenAI embedding providers
- Working memory (session-scoped storage)
- Relationship graph between memories
- Namespace isolation
- Embedding cache (LRU 128)
- Idempotent saves (content-hash based doc_id)

[0.2.0]: https://github.com/michaeldigiacomi/context-engine/releases/tag/v0.2.0
[0.1.0]: https://github.com/michaeldigiacomi/context-engine/releases/tag/v0.1.0