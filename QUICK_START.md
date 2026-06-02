# Quick Start: Knowledge Base System

## TL;DR

A system that teaches Claude to create better OmniStudio components by learning from your past projects—without leaking proprietary data.

## Installation (one-time)

```bash
# Install ChromaDB for semantic search (optional but recommended)
pip install chromadb

# Enable the MCP server in Claude Desktop:
# 1. Open Claude Desktop settings
# 2. Add to claude_desktop_config.json:
{
  "mcpServers": {
    "omnistudio": {
      "command": "python",
      "args": ["/full/path/to/omnistudio-skills/processes/mcp_server.py"]
    }
  }
}
# 3. Restart Claude Desktop
```

## Three Workflows

### Workflow 1: Learn from Your Current Project

You have a vlocity directory and want better component examples.

```bash
# Tell Claude about your project
# In Claude Desktop, after enabling MCP:

"Load the schema for creating a DataRaptor Extract"
# Claude calls: vlocity_schema(component_type="DataRaptor", subtype="Extract", vlocity_dir="/path/to/vlocity")
# Result: Schema + real examples from YOUR project
```

**When to use:** You have authorized access to a vlocity directory and want to see how YOUR team builds components.

### Workflow 2: Learn from Cross-Project Patterns

You're starting fresh or exploring patterns from multiple projects.

```bash
# First, harvest some completed projects
python processes/build_knowledge_base.py harvest /path/to/project1 --project project1
python processes/build_knowledge_base.py harvest /path/to/project2 --project project2

# Then, in Claude Desktop:
"Load the schema for creating a FlexCard"
# Claude calls: vlocity_schema(component_type="FlexCard", knowledge_base_dir="./knowledge-base")
# Result: Schema + anonymized examples from past projects
```

**When to use:** You're on a new project or want to see patterns from multiple projects without raw project access.

### Workflow 3: Find Similar Components

You want to understand how similar components are structured.

```bash
# Build the semantic search index (first time only)
python processes/vlocity_embeddings.py index

# Then, in Claude Desktop:
"Find Integration Procedures with complex conditional logic and error handling"
# Claude calls: vlocity_semantic_search(query="...", knowledge_base_dir="./knowledge-base")
# Result: Top 5 matching components (anonymized but structural pattern visible)
```

**When to use:** You need inspiration or want to see common patterns without knowing specific component names.

## 7 MCP Tools

| Tool | What It Does | When to Use |
|---|---|---|
| `vlocity_analysis` | Show impact of a specific component | Before modifying existing components |
| `vlocity_validate` | Check your component JSON against schema | After creating a component |
| `vlocity_search` | Find components by name/type/dependencies | Exploring the component graph |
| **`vlocity_schema`** | Get schema + practices + real examples | Before creating a component |
| **`vlocity_examples`** | Find real-world examples | When you want specific examples |
| **`vlocity_semantic_search`** | Natural language search ("complex IPs") | When you don't know what to search for |

\* New tools (in bold)

## Common Commands

### Harvest a Completed Project

```bash
python processes/build_knowledge_base.py harvest /path/to/vlocity \
  --project my_project_name \
  --kb knowledge-base/
```

This:
- Loads components with 2+ callers (configurable)
- Anonymizes them (no proprietary data leaks)
- Updates patterns.json with new statistics
- Saves mapping files locally (gitignored)

### Generate Updated Practices Guides

```bash
python processes/vlocity-creation/enrich_practices.py \
  --knowledge-base knowledge-base/
```

This generates:
- `generated-practices-dataraptor.md`
- `generated-practices-integrationprocedure.md`
- `generated-practices-flexcard.md`
- `generated-practices-omniscript.md`

### Build Semantic Search Index

```bash
python processes/vlocity_embeddings.py index --knowledge-base knowledge-base/
```

First query will be slow (~1-5s). Subsequent queries: <100ms.

## Security Guarantee

Nothing in the repo can identify your projects:
- ✅ Custom SObject names → DomainObject_A
- ✅ Custom field names → DomainField_1
- ✅ Component names → domain_getEntityDetails
- ✅ Business logic → Preserved (structural patterns only)

Mapping files (*.mapping.json) are **automatically gitignored**. Never committed.

## Troubleshooting

### "No index found"

```
Error: No dependency-index/index.json found

Solution: Build the index first
python skills/vlocity-dependency-indexer/build_index.py --init /path/to/vlocity
```

### "No examples found" when loading schema

```
Make sure you provide either:
vlocity_schema(component_type="DataRaptor", vlocity_dir="/path/to/vlocity")
or
vlocity_schema(component_type="DataRaptor", knowledge_base_dir="./knowledge-base")
```

### ChromaDB not installed for semantic search

```bash
pip install chromadb
# Then rebuild the index
python processes/vlocity_embeddings.py index --knowledge-base knowledge-base/ --force
```

## What Gets Committed vs Gitignored?

| File | Status | Reason |
|---|---|---|
| `knowledge-base/*/patterns.json` | ✅ Commit | Statistics only (safe) |
| `knowledge-base/*/examples/*.json` | ✅ Commit | Anonymized (safe) |
| `knowledge-base/*/examples/*.meta.json` | ✅ Commit | Metadata (safe) |
| `knowledge-base/*/examples/*.mapping.json` | ❌ Gitignore | Reverse-engineering only |
| `knowledge-base/embeddings/` | ❌ Gitignore | Raw text storage |

## Next Steps

1. ✅ System is ready to use
2. Harvest 3-5 completed projects to populate knowledge base
3. Test schema tool with examples
4. Explore semantic search
5. Share patterns across your team

## Getting Help

See `KNOWLEDGE_BASE_SYSTEM.md` for complete documentation:
- Anonymization algorithm details
- All MCP tool parameters
- Architecture overview
- Workflow examples
- Performance benchmarks

## Example Session

```
User: "I need to create a DataRaptor Extract to fetch customer accounts by status"

1. Claude: "Let me load the schema for DataRaptor Extract with examples"
   → vlocity_schema("DataRaptor", "Extract", knowledge_base_dir="./knowledge-base")
   → Returns: Schema + real examples from your knowledge base

2. Claude: "Based on the examples, here's the structure..."
   → Creates component JSON following patterns from real components

3. User: "Can you validate it?"
   → vlocity_validate(component_json, "DataRaptor", "Extract")
   → Returns: ✅ Valid, ready for deployment

4. User: "Show me how this compares to other components"
   → vlocity_search(vlocity_dir="/path/to/vlocity", calls="accountLookup")
   → Returns: Components that call accountLookup (to test together)
```

All of this without exposing any real project data—examples are anonymized, patterns are statistical, and your proprietary components stay yours.
