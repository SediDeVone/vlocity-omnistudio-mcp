# Changelog

All notable changes to the Vlocity/OmniStudio Dependency Indexer skill are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-05-28

### Added

- **Field-Level Data Extraction (Part A):** New `extract_field_mappings()` function for detailed data flow visualization
  - DataRaptor field mappings: reads `_Items.json` (native) and `_Mappings.json` (managed)
    - Extracts InputFieldName → OutputFieldName transformations
    - Captures source (SObject) and target (JSON) types
    - Supports both native (`OmniDataTransform`) and managed (`vlocity_cmt`) schemas
  - Integration Procedure element bindings: extracts PropertySetConfig data flow
    - Captures `additionalInput`: data sent to called components
    - Captures `responseJSONPath`: where responses are stored in state
    - Shows which IP state paths feed into dependent component calls

- **Data Flow Documentation:** `## Data Flow` section added to all journey.md files
  - DataRaptors: "Field Mappings" table showing input → output field transformations
  - Integration Procedures: "Element Bindings" table showing data flow through elements
  - Both tables included in journey documentation at `--document` and `--generate-all` modes

- **Richer Impact Analysis:** MCP tool now returns field-level context to Claude
  - Claude can analyze "If I change field X, which downstream components need testing?"
  - Shows exact data paths through components (e.g., `data.customer.name` → consumers)
  - Enables data-aware impact radius assessment beyond component-level dependencies

### Changed

- `command_document()` now extracts field data and includes "## Data Flow" section
- `command_generate_all()` now includes field data in bulk journey generation
- Index format unchanged; field data flows through journey.md and MCP context only

### Technical Details

- New function: `extract_field_mappings(component_name, component_path, component_type, schema_type)`
  - Returns `{"type": "...", "mappings": [...], "elements": [...]}`
  - Handles DataRaptor native/managed schemas, IP element bindings
  - Graceful fallback if field files don't exist
- No breaking changes; index.json schema unchanged
- No new dependencies; uses existing json, os, pathlib imports

See [FIELD_EXTRACTION.md](./FIELD_EXTRACTION.md) for detailed documentation.

## [1.0.0] - 2026-05-27

### Added

- **Core Indexing:** `--init <vlocity_dir>` mode to scan and index all OmniStudio/Vlocity components in a single pass
  - Discovers OmniScripts, Integration Procedures, DataRaptors, FlexCards, and Calculation Procedures
  - Generates `dependency-index/index.json` with full component graph and 1-level dependencies
  - Generates `dependency-index/summary.md` with human-readable statistics

- **Dependency Extraction:** Full 1-level dependency capture for all component types
  - Integration Procedure Actions (IPA)
  - DataRaptor actions (Extract, Load, Transform, Turbo)
  - Remote Actions (Apex/LWC callouts)
  - HTTP/REST Actions
  - OmniScript embeds
  - FlexCard nesting and data sources

- **Hidden Dependency Detection:** Automatic capture of implicit dependencies often missed by simpler tools
  - `preTransformBundle` on DataRaptor steps
  - `postTransformBundle` on DataRaptor steps
  - FlexCard `dataSource.ipMethod` Integration Procedure calls
  - FlexCard `actionList[].integrationProcedureKey` runIP actions
  - FlexCard `childCards[]` nested card references

- **Element Traversal:** `--element <index.json> <ComponentName> [--depth N|--all]` mode for deep recursive dependency analysis
  - BFS/DFS traversal from any named component
  - Configurable depth limit or unlimited transitive closure
  - Circular reference detection with `[CIRCULAR → ComponentName]` markers
  - Indented tree output and Mermaid diagram generation

- **Journey Documentation:** `--document <index.json> <ComponentName> <output_dir>` mode for stakeholder-friendly documentation
  - Full transitive dependency traversal
  - Mermaid diagram with subgraph layering (UI → Orchestration → Data → Apex)
  - Level-by-level dependency breakdown tables
  - Saves to `<ComponentName>-journey.md`

- **Schema Support:** Dual-schema compatibility (managed `vlocity_cmt` and native `OmniProcess`)
  - Automatic schema detection via `VlocityRecordSObjectType` field
  - Namespace cleaning for readable output

- **Index Format:** Machine-readable JSON index for programmatic querying
  - `meta` section with generation timestamp and component count
  - `nodes` section mapping component names to type, schema, folder, and dependency edges
  - Each dependency edge includes target, type, and via element reference

### Dependencies

- **Scripts:** Reuses `extract_dependencies.py` from `vlocity-architecture-mapper` for core JSON parsing logic
- **Python:** Standard library only (json, os, re, subprocess, pathlib, collections, datetime)
- **Tools:** python3, git (for future delta mode)

### Limitations

- Delta mode (`--delta`) not yet implemented; all `--init` runs are full scans
- No version or active/inactive status tracking
- No Apex class indexing (captured as Remote dependencies only)
- No environment-specific metadata segregation

---

## [Unreleased]

### Planned

- [ ] Delta mode: `--delta <vlocity_dir> [--since <ref>]` for git-based incremental updates
- [ ] Delta log: `dependency-index/delta-log.md` tracking changes over time
- [ ] Reverse queries: Find all callers of a given component
- [ ] Impact analysis: "If I change component X, what breaks downstream?"
- [ ] Visualization export: Generate visual diagrams in other formats (SVG, PNG)
- [ ] Apex class discovery: Index and link custom Apex classes
- [ ] Configuration export: CI/CD-friendly formats (CSV, YAML)
