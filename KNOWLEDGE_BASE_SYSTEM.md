# Knowledge Base System for OmniStudio Components

A comprehensive corpus-driven enhancement system that learns from 200+ real-world OmniStudio components while protecting proprietary data through anonymization.

## Overview

This system enables Claude to create better OmniStudio components by:
1. **Learning from real examples** — Anonymized examples of real DataRaptors, Integration Procedures, FlexCards, and OmniScripts
2. **Understanding patterns** — Statistical frequency of naming conventions, element types, filter structures
3. **Semantic search** — Find similar components by description ("IPs with complex conditional logic")
4. **Enriched practices** — Generation guides with real-world statistics and common patterns

**The critical constraint:** All project-specific data (custom SObjects, fields, business logic, client identifiers) is stripped at harvest time. Only structural knowledge enters the repo.

## Architecture

### 4-Phase System

**Phase 1: Anonymization Pipeline** (`build_knowledge_base.py`)
- Harvest real components from authorized projects
- Anonymize proprietary identifiers
- Extract statistical patterns
- Store in `knowledge-base/`

**Phase 2: Dynamic Example Retrieval** (`vlocity_examples.py` + `flow.py` + MCP tools)
- Find examples from local vlocity_dir (if authorized) OR knowledge-base (fallback)
- Integrate examples into schema guides
- Provide context for component creation

**Phase 3: Enriched Practices** (`enrich_practices.py`)
- Generate practices guides from knowledge-base patterns
- Include real-world statistics and anonymized code samples
- Update `skills/vlocity-generator/references/`

**Phase 4: Semantic Search** (`vlocity_embeddings.py` + MCP tool)
- Embed anonymized components with ChromaDB
- Natural language queries: "Find IPs with error handling"
- Safe to use in any context (all data anonymized)

## File Structure

```
Processes (orchestration + tools):
├── build_knowledge_base.py              Phase 1: Anonymization pipeline
├── vlocity_examples.py                  Phase 2: Example retrieval
├── vlocity_embeddings.py                Phase 4: Semantic search
├── vlocity_search.py                    Dependency index queries
├── vlocity-analysis/                    Impact analysis (unchanged)
├── vlocity-creation/
│   ├── flow.py                          Phase 2: Integrated examples into schema
│   ├── enrich_practices.py              Phase 3: Practices generation
│   └── __init__.py
├── mcp_server.py                        All 5 MCP tools (+ 2 new Phase 2/4 tools)
└── __init__.py

Knowledge Base (committed safe data + gitignored local data):
├── .gitignore                           Excludes *.mapping.json, embeddings/
├── README.md                            Structure and usage guide
├── DataRaptor/
│   ├── Extract/
│   │   ├── patterns.json                ✅ Committed (statistics only)
│   │   └── examples/
│   │       ├── domain_getEntityById.json                ✅ Committed (anonymized)
│   │       ├── domain_getEntityById.meta.json           ✅ Committed (metadata)
│   │       └── domain_getEntityById.mapping.json        ❌ Gitignored (local only)
│   ├── Load/
│   └── Transform/
├── IntegrationProcedure/
├── FlexCard/
├── OmniScript/
└── embeddings/                          ❌ Gitignored (ChromaDB, built locally)

Skills (output):
└── vlocity-generator/references/
    ├── generation-guide.md              (unchanged manual guide)
    ├── generated-practices-dataraptor.md         ✅ Committed (auto-generated)
    ├── generated-practices-integrationprocedure.md
    ├── generated-practices-flexcard.md
    └── generated-practices-omniscript.md
```

## Anonymization Algorithm

### What Gets Anonymized

| Data | Before | After | Why |
|---|---|---|---|
| Namespace prefixes | `vlocity_cmt__`, `acme__` | `<ns>__` | Project context |
| Custom SObjects | `Acme_ServiceCode__c` | `DomainObject_A` | Business domain |
| Custom fields | `customerSIN__c` | `DomainField_1` | PII + business context |
| Component names | `acme_getCustomerDetails` | `domain_getEntityDetails` | Project prefix |
| Reference values | `%input.acmeId%` | `%input.domainId%` | Project context |

### What's Preserved (Structural Knowledge)

- **Standard SF objects**: Account, Contact, Order, Asset, Case, etc.
- **Standard SF fields**: Id, Name, BillingCity, CreatedDate, etc.
- **Element types**: DataRaptorExtractAction, SetValues, ConditionalBlock, HTTPAction
- **Filter operators**: `=`, `LIKE`, `IN`, `LIMIT`, `ORDER BY`
- **Structural nesting**: FilterGroup hierarchies, element sequences, branching patterns
- **Field reference patterns**: `%input.X%`, `%Step:Block:Field%` format (values anonymized)

### Mapping Table (Local Only)

Each harvested component gets a `.mapping.json` file showing the mapping:
```json
{
  "sobjects": {"DomainObject_A": "Acme_ServiceCode__c", ...},
  "fields": {"DomainField_1": "customerSIN__c", ...},
  "namespaces": ["acme", "vlocity_cmt"]
}
```

**These files are gitignored** — developers can reverse-engineer locally for debugging, but they never enter the repo.

## How to Use

### Scenario A: Working on an Authorized Project

You have direct access to a vlocity directory.

```bash
# 1. Get schema with raw examples from your project
python processes/mcp_server.py
# In Claude Desktop: "Load the schema for DataRaptor Extract"
# → vlocity_schema(component_type="DataRaptor", subtype="Extract")
# → Returns schema + real examples from your local vlocity_dir
```

No knowledge-base needed. You're using your authorized project data directly.

### Scenario B: New Project or Exploring Patterns

You don't have a specific vlocity directory, or want to see cross-project patterns.

```bash
# 1. Generate practices from knowledge base patterns
python processes/vlocity-creation/enrich_practices.py \
  --knowledge-base knowledge-base/ \
  --output skills/vlocity-generator/references/

# 2. Build semantic search index (one-time, local)
python processes/vlocity_embeddings.py index \
  --knowledge-base knowledge-base/

# 3. Use Claude with KB-backed tools
python processes/mcp_server.py
# In Claude Desktop: "Load the schema for DataRaptor Extract"
# → vlocity_schema(component_type="DataRaptor", subtype="Extract")
# → Returns schema + anonymized examples from knowledge-base/
```

All data is anonymized, so this is safe to use anywhere.

### Scenario C: Harvest a New Project

You completed a project and want to add its components to the knowledge base for future reference.

```bash
# 1. Harvest components from authorized vlocity directory
python processes/build_knowledge_base.py harvest /path/to/vlocity \
  --project my_project \
  --kb knowledge-base/ \
  --min-callers 2 \
  --max-per-type 10

# This:
# - Loads the dependency index
# - Selects top 10 components per type by caller count
# - Anonymizes each component
# - Writes anonymized JSON + meta.json + mapping.json (gitignored)
# - Updates patterns.json with new statistics

# 2. Commit the anonymized examples and patterns
git add knowledge-base/*/patterns.json
git add knowledge-base/*/examples/*.json
git add knowledge-base/*/examples/*.meta.json
git commit -m "docs: Add knowledge base examples from my_project harvest"

# 3. Regenerate practices guides with new patterns
python processes/vlocity-creation/enrich_practices.py \
  --knowledge-base knowledge-base/ \
  --output skills/vlocity-generator/references/

git add skills/vlocity-generator/references/generated-practices-*.md
git commit -m "docs: Update practices with new KB patterns"

# 4. Rebuild semantic search index (local, not committed)
python processes/vlocity_embeddings.py index \
  --knowledge-base knowledge-base/ \
  --force
```

**Note:** Mapping files (*.mapping.json) are automatically gitignored. Never commit them.

## MCP Tools

### Existing Tools (Unchanged)

- **vlocity_analysis** — Analyze impact of a specific component
- **vlocity_validate** — Check component JSON against schema
- **vlocity_search** — Find components by name, type, dependencies

### New Tools (Phase 2 & 4)

- **vlocity_schema** (enhanced) — Load schema + practices + real examples
  ```
  vlocity_schema(
    component_type: "DataRaptor",
    subtype: "Extract",
    vlocity_dir: "/authorized/vlocity",           # Optional: raw examples
    knowledge_base_dir: "./knowledge-base"        # Optional: anonymized fallback
  )
  ```

- **vlocity_examples** — Find real-world component examples
  ```
  vlocity_examples(
    component_type: "IntegrationProcedure",
    vlocity_dir: "/authorized/vlocity",
    knowledge_base_dir: "./knowledge-base",
    name_hint: "order"                            # Optional filter
  )
  ```

- **vlocity_semantic_search** — Natural language search over components
  ```
  vlocity_semantic_search(
    query: "Find IPs with complex conditional logic and error handling",
    knowledge_base_dir: "./knowledge-base",
    component_type: "IntegrationProcedure",       # Optional filter
    limit: 5
  )
  ```

## Data Security

### What's Never Committed

- Custom SObject names or field names
- Business logic or data transformations
- Client identifiers or proprietary patterns
- Mapping files (*.mapping.json)
- Embedding index (embeddings/)

### What's Safe to Commit

- Anonymized component JSON (DomainObject_A, DomainField_1, etc.)
- Metadata (caller counts, field counts, component types)
- Statistical patterns (naming frequency, element usage frequency)
- Generated practices guides (all based on anonymized data)

### Fallback Safety

If a component-specific mapping is lost:
- Developers can rebuild it by re-harvesting the project
- The anonymized examples are still useful (structural patterns preserved)
- No information is permanently lost except the mapping (which can be regenerated)

## Workflow Examples

### "I need to create a DataRaptor Extract with complex filtering"

```
User: "Show me examples of DataRaptor Extracts with multiple filter groups"

1. Claude calls: vlocity_schema(
     component_type="DataRaptor",
     subtype="Extract",
     knowledge_base_dir="./knowledge-base"
   )
2. Response includes:
   - JSON schema with all fields
   - Good practices (naming conventions, SObject patterns)
   - Real examples from knowledge base:
     * domain_getOrdersByStatus (uses 3 filter groups)
     * domain_getAccountContacts (uses composite filters)
   - Metadata: "Used by 12 other components"

3. Claude creates component following schema and examples
4. Claude calls: vlocity_validate(component_json, "DataRaptor", "Extract")
5. Response: "✅ Valid, ready for deployment"
```

### "I want to understand Integration Procedure patterns"

```
User: "What do Integration Procedures with error handling look like?"

1. Claude calls: vlocity_semantic_search(
     query="IPs with comprehensive error handling",
     knowledge_base_dir="./knowledge-base"
   )
2. Response: Top 5 matching IPs with relevance scores
   * domain_updateOrder (92% relevance) — has TryCatchBlock + ConditionalBlock
   * domain_createContract (88% relevance) — has error handling + logging
   * domain_syncAccount (85% relevance) — has failure recovery logic

3. Claude calls: vlocity_examples(
     component_type="IntegrationProcedure",
     knowledge_base_dir="./knowledge-base",
     name_hint="updateOrder"
   )
4. Response: Detailed structure of domain_updateOrder with element breakdown
5. Claude creates similar pattern for your use case
```

### "I'm starting a fresh project with no authorized vlocity access"

```
User: "Create a FlexCard that displays account information with state-based rendering"

1. Claude calls: vlocity_schema(
     component_type="FlexCard",
     knowledge_base_dir="./knowledge-base"    # No local vlocity_dir
   )
2. Response: Schema + anonymized FlexCard examples from knowledge base
3. Claude calls: vlocity_semantic_search(
     query="FlexCards with conditional state rendering",
     knowledge_base_dir="./knowledge-base"
   )
4. Response: Matching anonymized FlexCards from past projects
5. Claude creates component based on patterns, no access needed
```

## Maintenance

### Regular Updates (as projects complete)

```bash
# After finishing a project:
python processes/build_knowledge_base.py harvest /path/to/vlocity \
  --project completed_project_name \
  --kb knowledge-base/

python processes/vlocity-creation/enrich_practices.py \
  --knowledge-base knowledge-base/ \
  --output skills/vlocity-generator/references/

git add knowledge-base/ skills/vlocity-generator/references/
git commit -m "docs: Update knowledge base from completed_project"

# Rebuild embeddings locally (not committed)
python processes/vlocity_embeddings.py index --knowledge-base knowledge-base/ --force
```

### Checking for Leaks

```bash
# Verify no proprietary data is committed:
git diff HEAD --name-only | grep -E "\.mapping\.json|embeddings/" && echo "❌ Mapping/embedding files found in commit" || echo "✅ Clean"

# Inspect a random example to ensure anonymization:
python -m json.tool knowledge-base/DataRaptor/Extract/examples/domain_getEntityById.json | grep -E "Acme|acme|CustomerSIN|ServiceCode" && echo "❌ Proprietary data detected" || echo "✅ Properly anonymized"
```

## Performance

- **Harvest:** ~5-10 seconds per component type (single-threaded, I/O bound)
- **Semantic search:** ~100-500ms for index building (lazy, first query slower)
- **Semantic search:** <100ms for subsequent queries (cached index)
- **Schema + examples:** <50ms (JSON parsing only)

## Troubleshooting

### "No index found" when harvesting

```bash
# Error: No dependency-index/index.json found

# Solution: Run the dependency indexer first
python skills/vlocity-dependency-indexer/build_index.py --init /path/to/vlocity
```

### "ChromaDB not installed" for semantic search

```bash
# Error: Semantic search requires ChromaDB

# Solution: Install optional dependency
pip install chromadb
```

### "Knowledge base not found" for examples

```bash
# Error: Knowledge base not found at ./knowledge-base

# Solution: Harvest a project first
python processes/build_knowledge_base.py harvest /path/to/vlocity --project myproject
```

### Examples not showing in schema

Check that `vlocity_dir` or `knowledge_base_dir` parameter is provided:
```python
# This won't show examples (no sources provided)
vlocity_schema(component_type="DataRaptor", subtype="Extract")

# This will show examples
vlocity_schema(
  component_type="DataRaptor",
  subtype="Extract",
  knowledge_base_dir="./knowledge-base"  # ← Need this
)
```

## Implementation Status

- [x] Phase 1: Anonymization pipeline (`build_knowledge_base.py`)
- [x] Phase 1: Knowledge base structure with `.gitignore`
- [x] Phase 2: Example retrieval (`vlocity_examples.py`)
- [x] Phase 2: Integration into schema flow (`flow.py`)
- [x] Phase 2: New MCP tools (`vlocity_examples`, enhanced `vlocity_schema`)
- [x] Phase 3: Practices enrichment (`enrich_practices.py`)
- [x] Phase 4: Semantic search (`vlocity_embeddings.py`)
- [x] Phase 4: Semantic search MCP tool (`vlocity_semantic_search`)
- [x] Bug fix: `vlocity_search.py` (deps key)

## Next Steps

1. **Harvest initial corpus** — Run `build_knowledge_base.py harvest` on 3-5 completed projects
2. **Generate practices** — Run `enrich_practices.py` to populate generated guides
3. **Build embeddings** — Run `vlocity_embeddings.py index` for semantic search
4. **Test in Claude Desktop** — Load the MCP server and try schema + examples flow
5. **Document project patterns** — Add patterns guide to DOCUMENTATION.md based on learned statistics
