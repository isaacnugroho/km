# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.1] - 2026-06-05

### Fixed

- SHACL prefix-binding: warn and skip unusable SPARQL prefixes (including empty default `:`) instead of failing validation.

### Changed

- Removed bundled `hexagonal-architecture` Learning Ontology from this repository; bind LOs from the external [ontologies](https://github.com/isaacnugroho/ontologies) repo.
- `km init` without `--lo-source` creates a workspace with empty `learning_ontologies`.

### Added

- GitHub Actions CI (`pytest` on push/PR) and tagged release builds for Linux, Windows, and macOS.
- `--version` CLI flag and semver-validated release tags (`scripts/validate_release_tag.py`).
- GitHub Sponsors configuration (`.github/FUNDING.yml`).
- Expanded unit and integration tests (prefix filter, empty LO workspace, version metadata, MCP smoke flows).

### Release

Tag a release after updating this file and `pyproject.toml`:

```bash
git tag v0.5.1
git push origin v0.5.1
```

[Unreleased]: https://github.com/isaacnugroho/km/compare/v0.5.1...HEAD
[0.5.1]: https://github.com/isaacnugroho/km/releases/tag/v0.5.1
