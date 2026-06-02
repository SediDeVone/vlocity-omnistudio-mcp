# Changelog: Vlocity Creation Process

All notable changes to the vlocity-creation process are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-28

### Added

- **Schema Loading:** `get_schema()` function to load authoritative JSON schemas + practices for all OmniStudio component types
  - DataRaptor (Extract, Load, Transform): loads from `skills/vlocity-generator/schemas/dataraptor_*.schema.json`
  - Integration Procedure: loads from `skills/vlocity-generator/schemas/ip_element_types.schema.json`
  - FlexCard: loads from `skills/vlocity-generator/schemas/flexcard_definition.schema.json`
  - OmniScript: loads from `skills/vlocity-generator/schemas/omniscript_element_types.schema.json`

- **Practices Integration:** Loads good/bad practices from reference guides
  - DataRaptor practices: `skills/vlocity-generator/references/generation-guide.md`
  - Integration Procedure practices: `skills/vlocity-generator/references/element-type-suffix-guide.md`
  - FlexCard practices: `skills/vlocity-flexcard-helper/references/flexcard-schema-guide.md`
  - OmniScript practices: `skills/vlocity-flexcard-helper/references/omniscript-schema-guide.md`

- **Context Formatting:** `format_schema_context()` function to merge schema + practices into markdown
  - Presents JSON schema in readable format
  - Includes good practices and naming conventions
  - Provides creation instructions for Claude
  - Optimized for in-session analysis (no API calls)

- **MCP Tool:** `vlocity_schema` tool exposed via MCP server
  - Available in Claude Desktop without CLI/developer setup
  - Accepts: component_type + optional subtype
  - Returns: Formatted markdown with schema + practices
  - Use before creating any component to ensure validated structure

- **CLI Support:** `flow.py` script for developer/testing use
  - `--mode context-only`: formatted markdown (for Claude analysis)
  - `--mode schema-only`: raw JSON schema (for programmatic use)
  - Useful for testing, validation, and automation

- **Documentation:** Comprehensive PROCESS.md explaining both MCP and CLI paths
  - How schemas are loaded and formatted
  - Integration with Part A (field extraction)
  - Workflow examples for each component type
  - Limitations and next steps

### Architecture

**Two Access Paths:**

1. **MCP Path** (Claude Desktop)
   - User → MCP tool → flow.py (context-only) → Markdown returned to Claude
   - Claude analyzes and creates component in session
   - No ANTHROPIC_API_KEY required

2. **CLI Path** (Developer/Testing)
   - `python flow.py DataRaptor --subtype Extract --mode context-only`
   - Direct Python execution, useful for scripting and validation

**No API Calls:**
- Schemas are local JSON files (no remote fetch)
- Practices are local markdown files (no remote fetch)
- Formatting is deterministic (no LLM inference)
- All work is synchronous and local to the process

### Design Decisions

- **Schema as Source of Truth:** JSON schemas in `skills/vlocity-generator/schemas/` are authoritative for all component structure
- **Practices as Guidance:** Reference guides provide naming conventions, best practices, and anti-patterns
- **Context-Formatted Output:** Markdown format is human-readable for Claude and includes instructions
- **No Validation in Process:** This process returns schemas; actual validation happens in Claude or downstream tools
- **Reuse Existing Files:** No new schema/guide files created; process loads what already exists in generator skills

### Testing

- Validated schema loading for all component types
- Tested markdown formatting with realistic schema data
- Verified MCP tool integration with existing server
- Tested CLI modes with sample invocations

### Files

- `flow.py` (~240 lines) — Main orchestration
- `PROCESS.md` — Complete documentation
- `CHANGELOG.md` — This file

### Not Included (Future)

- Validation of created components (requires Salesforce metadata validation)
- Deployment of created components (separate vlocity-generator integration)
- Migration of existing components (separate tool)
- Performance optimization (out of scope for creation)
- Custom schema extensions (use existing schemas as-is)
