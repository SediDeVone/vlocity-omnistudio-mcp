# OmniStudio Skills

Open-source collection of **7 Vlocity/OmniStudio agentic skills**, an **MCP server** with 6 semantic tools, and a **corpus-driven knowledge base system** for Claude Code.

This repository contains everything needed to build, test, and analyze Salesforce OmniStudio components (DataRaptors, Integration Procedures, FlexCards, OmniScripts) with AI-driven code generation, impact analysis, and intelligent dependency tracking.

## Quick Start

### 1. Clone this repository

```bash
git clone <repo-url>
cd omnistudio-skills
```

### 2. Set up your Claude Code environment

Copy the MCP server configuration to Claude Code's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "omnistudio": {
      "command": "python",
      "args": ["/path/to/omnistudio-skills/processes/mcp_server.py"]
    }
  }
}
```

Replace `/path/to/omnistudio-skills` with the actual path to your cloned repository.

### 3. Activate the Python environment (optional, for local testing)

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# or
.venv\Scripts\activate      # Windows

pip install -r requirements.txt
```

## Skills Library

| Skill | Description | Category | Foundation |
|-------|-------------|----------|-----------|
| **Vlocity Dependency Indexer** | Builds pre-computed dependency indices for offline graph analysis and journey documentation. *Foundation skill — used by all others.* | development | — |
| **Vlocity Architecture Mapper** | Traces OmniStudio dependency chains and generates architecture documentation. | development | Indexer |
| **Vlocity DataPack Reviewer** | Static analysis on DataPacks to identify architectural risks and performance bottlenecks. | development | Indexer |
| **Vlocity Generator** | Schema-aware generation and modification of Vlocity/OmniStudio DataPack JSON files. | development | Indexer |
| **Vlocity Tester** | Tests deployed DataRaptors and Integration Procedures via Salesforce REST API. | development | Indexer |
| **Vlocity FlexCard Helper** | Parses and validates FlexCard and OmniScript visual component metadata. | development | Indexer |
| **OmniStudio Impact Analyzer** | Intelligent change impact analysis with blast radius and upstream/downstream dependency chains. | development | Indexer |

## MCP Server Tools

The embedded MCP server (`processes/mcp_server.py`) exposes 6 tools for Claude Desktop:

- **`vlocity_analysis`** — Impact analysis orchestration (v1.1.0)
- **`vlocity_schema`** — Schema loading and validation
- **`vlocity_validate`** — Component validation against best practices
- **`vlocity_search`** — Dependency index queries (powered by built indices)
- **`vlocity_examples`** — Retrieve component examples from the knowledge base
- **`vlocity_semantic_search`** — ChromaDB-powered semantic search over the corpus (requires ChromaDB setup)

## Knowledge Base System

The embedded **4-phase corpus-driven knowledge base** provides semantic search and example retrieval:

- **Phase 1:** Anonymization pipeline — strips PII and sensitive metadata from real DataPacks
- **Phase 2:** Example extraction — catalogues component patterns and best practices
- **Phase 3:** Schema enrichment — maps component types to their Salesforce metadata definitions
- **Phase 4:** Semantic indexing — ChromaDB embeddings for natural-language component search

See [`knowledge-base/README.md`](knowledge-base/README.md) for detailed architecture and usage.

## Folder Structure

```
omnistudio-skills/
├── skills/                          # 7 Vlocity skill definitions
│   ├── vlocity-architecture-mapper/
│   ├── vlocity-dependency-indexer/  (foundation)
│   ├── vlocity-datapack-reviewer/
│   ├── vlocity-generator/
│   ├── vlocity-tester/
│   ├── vlocity-flexcard-helper/
│   └── vlocity-impact-analyzer/
├── processes/                       # MCP server and process layer
│   ├── mcp_server.py               # Entry point for Claude Code MCP configuration
│   ├── vlocity-analysis/           # Impact analysis orchestration
│   ├── vlocity-creation/           # Schema loading and generation
│   ├── build_knowledge_base.py      # Phase 1: Anonymization
│   ├── vlocity_examples.py          # Phase 2: Example retrieval
│   ├── vlocity_embeddings.py        # Phase 4: Semantic search
│   ├── vlocity_search.py            # Dependency index queries
│   └── __init__.py
├── knowledge-base/                  # Component corpus
│   ├── DataRaptor/                 # Extract, Load, Transform examples
│   ├── IntegrationProcedure/        # All Integration Procedure examples
│   ├── FlexCard/                    # FlexCard visual components
│   ├── OmniScript/                  # OmniScript flow examples
│   ├── embeddings/                  # ChromaDB semantic indices (built locally)
│   ├── *.mapping.json               # Generated schema mappings
│   └── README.md
├── guardrails/                      # Security and validation standards
│   └── GUARDRAILS_SPEC.md           # Guardrails framework specification
├── scripts/
│   ├── document_vlocity_component.sh # Vlocity component documentation helper
│   └── dev/
│       └── lint_skills.py            # SKILL.md linter for development
├── KNOWLEDGE_BASE_SYSTEM.md         # Comprehensive knowledge base architecture docs
├── QUICK_START.md                   # Knowledge base quick-start
├── skills.json                      # Machine-readable skill registry (7 vlocity entries)
├── manifest.json                    # Deployment manifest (7 vlocity entries)
└── LICENSE                          # MIT License
```

## Requirements

- **Python:** 3.11+
- **Optional:** ChromaDB for semantic search (`pip install chromadb`)
- **Optional:** Salesforce CLI (`sf`) for deployment integration

## Usage Examples

### Example 1: Build a dependency index

```bash
cd skills/vlocity-dependency-indexer
python scripts/build_index.py --datapack /path/to/vlocity/datapacks
```

### Example 2: Analyze component impact

Use Claude Code with the MCP server configured:

```
@omnistudio I want to understand the impact of changing the DataRaptor "GetCustomerAccount". 
Show me all Integration Procedures that call it, and what downstream DataRaptors they use.
```

The `vlocity_analysis` tool will:
1. Load the dependency index
2. Build an impact graph
3. Trace upstream callers (Integration Procedures)
4. Document downstream dependencies
5. Return a blast-radius analysis

### Example 3: Generate a new component with validation

```
@omnistudio Create a new Integration Procedure that validates phone numbers and returns 
a standardized format. Validate the JSON against OmniStudio IP schema.
```

The `vlocity_schema` and `vlocity_validate` tools will:
1. Load the IP schema
2. Generate a valid schema-compliant JSON template
3. Validate the generated component
4. Return the IP ready for deployment

## MCP Configuration (Claude Desktop)

Place this in `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or the equivalent on Windows/Linux:

```json
{
  "mcpServers": {
    "omnistudio": {
      "command": "python",
      "args": ["/absolute/path/to/omnistudio-skills/processes/mcp_server.py"]
    }
  }
}
```

Restart Claude Code. The `vlocity_*` tools will be available in all conversations.

## Documentation

- **[`KNOWLEDGE_BASE_SYSTEM.md`](KNOWLEDGE_BASE_SYSTEM.md)** — Architecture and 4-phase system design
- **[`QUICK_START.md`](QUICK_START.md)** — Knowledge base setup and usage
- **[`knowledge-base/README.md`](knowledge-base/README.md)** — Corpus structure and best practices
- **Individual Skill READMEs** — Each skill in `skills/*/` has `SKILL.md` and `DOCUMENTATION.md`

## License

MIT License — free for personal and commercial use. See [LICENSE](LICENSE) for details.

## Support

For issues, questions, or contributions:
- File an issue on GitHub or open a pull request

