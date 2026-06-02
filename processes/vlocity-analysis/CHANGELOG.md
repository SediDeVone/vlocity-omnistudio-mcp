# Changelog

All notable changes to the vlocity-analysis process will be documented in this file.

---

## [1.1.0] — 2026-05-28

### Changed

- **MCP path now uses calling LLM session for analysis (breaking change for MCP users)**
  - `vlocity_analysis` MCP tool no longer requires `ANTHROPIC_API_KEY`
  - Removed `mode` parameter from MCP tool
  - Tool now returns markdown documentation; Claude Desktop/Code does the analysis in existing session
  - Eliminates redundant nested Anthropic API calls
  - More natural conversation flow: user can ask follow-ups, refine analysis, iterate
  
- **CLI path unchanged**
  - Direct CLI invocation (`--mode analyze/blast-radius/impact-report`) still calls Anthropic SDK
  - Behavior identical to v1.0.0 for command-line users
  - Requires `ANTHROPIC_API_KEY` only for CLI modes (`analyze`, `blast-radius`, `impact-report`)

### Added

- **New `context-only` mode** — internal mode used by MCP tool, returns journey + flow + dependencies as formatted markdown
- **Two-path architecture** clearly documented:
  - **MCP Path:** tool returns docs → Claude analyzes in session (no API key)
  - **CLI Path:** tool calls Anthropic SDK directly (requires API key)

### Details

- MCP tool docstring now instructs Claude on analysis: "After receiving this tool result, analyze it for: component purpose, upstream impact, downstream impact, risk level, test scope"
- CLI modes unchanged; can still run `python flow.py <component> <vlocity_dir> --mode analyze`
- `analyze_impact()` function retained for CLI usage

---

## [1.0.0] — 2026-05-28

### Added

- **Initial release:** Process layer for Vlocity component impact analysis
- **5-step orchestration:**
  1. Ensure dependency index (`build_index.py --generate-all`)
  2. Load and validate component exists in index
  3. Generate journey + flow documentation
  4. Load all context into memory
  5. Perform LLM analysis via Anthropic SDK
  
- **4 analysis modes:**
  - `analyze` — full impact assessment with architecture, upstream/downstream impact, risk level, test scope
  - `blast-radius` — quick risk summary + top callers
  - `impact-report` — structured 5-section report for stakeholders
  - `docs-only` — generate artifacts without LLM call
  
- **MCP exposure:** Tool registered in `mcp_server.py` for Claude Desktop access
  
- **Direct Python import:** `from processes.vlocity_analysis.flow import run`
  
- **CLI invocation:** `python flow.py <component> <vlocity_dir> --mode <mode>`

### Details

- **Deterministic steps (1–4):** Subprocess calls + file I/O, no LLM tokens consumed
- **LLM step (5):** Single focused Anthropic API call with pre-loaded context
- **Index caching:** Reuses pre-computed `dependency-index/index.json` across calls (~30s savings per run)
- **Error handling:** Clear messages for missing components, API key issues, generation failures
- **Backward compatibility:** `vlocity-impact-analyzer` SKILL.md unchanged; process is *additional* access path

### Requirements

- `ANTHROPIC_API_KEY` environment variable (for LLM analysis modes)
- Vlocity dependency indexer skill (called via subprocess)

### Testing

- Validated against real component: `sales_createOrderAPI` (35+ dependencies, complex flow)
- All modes working: docs-only ✓, blast-radius (pending API key setup), impact-report (pending API key setup), analyze (pending API key setup)
- Performance: 5–15s with index cache, ~35–45s first run

---

## Future (Planned)

- [ ] Support streaming LLM output for large dependency graphs
- [ ] Parallel doc generation for transitive dependencies
- [ ] Caching of LLM responses per component (configurable TTL)
- [ ] Extended modes: `refactor-scope`, `migration-impact`
