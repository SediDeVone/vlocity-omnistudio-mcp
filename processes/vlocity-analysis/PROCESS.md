---
name: vlocity-analysis
description: Process layer for deterministic Vlocity component documentation + impact analysis. Orchestrates dependency indexing, doc generation, and LLM analysis via Anthropic SDK.
type: process
mcp_tool: vlocity_analysis
---

# Vlocity Analysis Process

## Overview

**Purpose:** Analyze the impact and architecture of an OmniStudio/Vlocity component with a single function call, replacing multi-step SKILL.md workflows with explicit Python orchestration.

**Use cases:**
- BAs on Claude Desktop: Ask naturally, Claude auto-calls the MCP tool
- Developers on Claude Code: Use `/vlocity-impact-analyzer` skill (unchanged)
- Programmatic access: Import `flow.run()` directly into other Python scripts

**Design:** 4 deterministic steps (subprocess + file I/O) + 1 optional LLM analysis step. No user interaction needed.

---

## Two Access Paths

This process supports two distinct execution paths:

### Path A: MCP (Claude Desktop)

User asks naturally → Claude auto-calls tool → tool runs steps 1–4 → returns documentation markdown → Claude analyzes in conversation.

```
User: "Analyze the impact of sales_createOrderAPI in /workspace/vlocity"
Claude: calls vlocity_analysis tool
Tool: runs steps 1–4, returns journey + flow + dependencies as markdown
Claude: <receives markdown, analyzes in existing session, no secondary API call>
```

**Advantage:** No `ANTHROPIC_API_KEY` needed. Analysis happens in the user's Claude session. User can ask follow-ups, refine analysis, iterate.

### Path B: CLI (Direct Invocation)

User runs script directly with `--mode analyze/blast-radius/impact-report` → tool runs steps 1–4 + step 5 (Anthropic SDK call) → returns JSON with analysis.

```bash
python processes/vlocity-analysis/flow.py sales_createOrderAPI /path/to/vlocity --mode analyze
```

**Requirement:** `ANTHROPIC_API_KEY` environment variable must be set.

---

## Workflow

### Step 1: Ensure Dependency Index

**Function:** `ensure_index(vlocity_dir, parent_dir) → index_path`

Checks if `{parent_dir}/dependency-index/index.json` exists.

**If missing:**
- Runs: `python build_index.py --generate-all <vlocity_dir> <parent_dir>`
- Waits for completion
- Returns path to generated index.json

**If present:**
- Returns path immediately

**Why:** The dependency index is expensive to compute (~30 seconds) but stable once generated. Reuse it across all analysis calls.

---

### Step 2: Load Index and Verify Component

**Function:** `load_index(index_path) → dict`

Loads `index.json` into memory.

**Function:** `assert_component_exists(component_name, index) → None`

Confirms `component_name` is in `index["nodes"]`.

**If missing:**
- Lists available components (first 10)
- Raises `ValueError` with suggestions

---

### Step 3: Generate Documentation

**Function:** `generate_docs(component_name, vlocity_dir, index_path, output_dir) → dict`

Generates fresh journey and flow documents:

```bash
python build_index.py --document <index_path> <component_name> <output_dir>
python build_index.py --flow <vlocity_dir> <component_name> <output_dir> <index_path>
```

**Outputs:**
- `{component_name}-journey.md` — architecture diagram + dependency table
- `{component_name}-flow.md` — execution flow (optional for non-IP components)

---

### Step 4: Load Context

**Function:** `load_context(component_name, index_path, output_dir) → dict`

Reads all artifacts into memory:
- Journey document (required)
- Flow document (optional)
- Analysis bundle (optional) — `{component_name}-analysis-bundle.json` from `dependency-index/`

**Returns:** Dict with keys: `component`, `journey`, `flow`, `bundle`

---

### Step 5: LLM Analysis (CLI-only, Optional)

**Function:** `analyze_impact(component_name, context, mode) → str`

For CLI-only modes: calls Anthropic API with pre-loaded context and mode-specific system prompt.

**Requires:** `ANTHROPIC_API_KEY` environment variable (CLI path only)

**Modes:**

| Mode | Path | LLM Call | Output |
|------|------|----------|--------|
| `context-only` | MCP | None | Returns journey + flow + dependencies as formatted markdown |
| `docs-only` | CLI | None | Returns artifact file paths (journey.md, flow.md) |
| `analyze` | CLI | Anthropic SDK | Component purpose, architecture, upstream/downstream impact, risk level, test scope |
| `blast-radius` | CLI | Anthropic SDK | Blast radius count, risk level (HIGH/MEDIUM/LOW), top 5 callers |
| `impact-report` | CLI | Anthropic SDK | 5-section markdown: architecture, blast radius, risk, test scope, migration notes |

---

## Tool Schema (MCP)

```python
def vlocity_analysis(
    component_name: str,
    vlocity_dir: str,
    output_dir: str = "./output"
) -> str:
    """
    Fetch documentation for an OmniStudio component.
    
    Returns formatted markdown with architecture, flow, and dependencies.
    The calling Claude session analyzes this documentation in context.
    
    Args:
        component_name: OmniStudio component (e.g., sales_createOrderAPI)
        vlocity_dir: Path to vlocity metadata directory
        output_dir: Where to write generated docs (default: ./output)
    
    Returns:
        Markdown documentation (journey + flow + dependency summary)
    
    No API keys required — analysis happens in the calling session.
    """
```

---

## Return Value

### MCP (context-only mode)

**Tool returns:** Formatted markdown string with all documentation
```
# Component: sales_createOrderAPI

## Architecture
[journey diagram and dependency table...]

## Execution Flow
[flow diagram...]

## Dependency Summary
Total dependencies: 35
Top dependencies: DataRaptor1, DataRaptor2, ...
```

### CLI (analyze/blast-radius/impact-report modes)

**Function returns:** JSON dict
```json
{
  "status": "complete",
  "analysis": "LLM response",
  "artifacts": {
    "journey": "/path/to/component-journey.md",
    "flow": "/path/to/component-flow.md"
  }
}
```

### CLI (docs-only mode)

**Function returns:** JSON dict with artifact paths only
```json
{
  "status": "complete",
  "artifacts": {
    "journey": "/path/to/component-journey.md",
    "flow": "/path/to/component-flow.md"
  }
}
```

**On error (any mode/path):**
```json
{
  "status": "error",
  "error": "Human-readable error message"
}
```

---

## Error Handling

| Condition | Behavior |
|-----------|----------|
| Index generation fails | Raise `RuntimeError` with stderr |
| Component not found | Raise `ValueError` with available components list |
| Documentation not generated | Raise `RuntimeError` with missing file path |
| API key not set | Raise `RuntimeError` with credential instructions |
| LLM API error | Raise exception; caller handles retry |

---

## Configuration

### Environment Variables

```bash
export ANTHROPIC_API_KEY="sk-..."  # Required for LLM analysis modes
```

### Optional: Pre-computed Index

If `dependency-index/index.json` already exists at `{vlocity_dir}/../dependency-index/`, it will be reused. No regeneration needed.

---

## Integration Points

### Called Scripts

- `skills/vlocity-dependency-indexer/scripts/build_index.py` — generates index, documents components, flows
  
### MCP Server

- Exposed by `processes/mcp_server.py` as tool `vlocity_analysis`
- Claude Desktop discovers it automatically

### SKILL.md Compatibility

- `skills/vlocity-impact-analyzer/SKILL.md` remains unchanged
- Users can still invoke via `/vlocity-impact-analyzer` on Claude Code
- Process layer is an *additional* access path, not a replacement

---

## Typical Usage

### Via MCP (Claude Desktop)

```
User: "Analyze the impact of sales_createOrderAPI in /workspace/vlocity"
Claude: [automatically calls vlocity_analysis tool]
```

### Programmatic (Python)

```python
from processes.vlocity_analysis.flow import run

result = run(
    component_name="sales_createOrderAPI",
    vlocity_dir="/path/to/vlocity",
    output_dir="./output",
    mode="impact-report"
)
print(result["analysis"])
```

### CLI (Direct)

```bash
python processes/vlocity-analysis/flow.py sales_createOrderAPI /path/to/vlocity --mode blast-radius
```

---

## Performance

| Step | Time | Cacheable |
|------|------|-----------|
| Index generation (`--generate-all`) | ~30s | Yes (reused across calls) |
| Doc generation (`--document`, `--flow`) | ~2–5s | No (regenerated per component) |
| Context loading | <100ms | N/A |
| LLM analysis | 2–10s | No |
| **Total (first run)** | ~35–45s | — |
| **Total (with index cache)** | ~5–15s | — |

---

## Related

- **vlocity-dependency-indexer** — underlying skill that generates index and docs
- **vlocity-impact-analyzer** — SKILL.md frontend (unchanged)
- **mcp_server.py** — MCP server that exposes this process as a tool
