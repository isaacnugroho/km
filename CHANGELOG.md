# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-06-17

### Added

- Addendum 2: LO repository `catalog.json`, package `dependencies`, workspace `rootPath`, dependency graph validation (cycle detection), and transitive `effective_cache_set` LO cache sync.
- Extended `validate_bindings` and `status` with `implicit_dependencies`, `binding_kind`, and structured dependency error codes.
- `km://schemas/learning-ontologies` includes `binding_kind` and `dependencies` per cached LO.
- Semantic MR approve re-validates catalog dependency graph when `{lo-root}/catalog.json` is present.

### Changed

- When `rootPath` and catalog are configured, binding only an extension LO auto-caches transitive prerequisites in `.km/lo-cache/`.
- Workspaces without `rootPath` or empty `dependencies` retain pre-0.6.0 binding behavior.

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
