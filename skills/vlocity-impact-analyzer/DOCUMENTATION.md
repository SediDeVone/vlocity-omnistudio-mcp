# OmniStudio Impact Analyzer — Full Documentation

## Overview

The Impact Analyzer transforms impact analysis from manual guesswork into a structured, data-driven process. By combining the pre-computed dependency index from `vlocity-dependency-indexer` with Claude's reasoning, it answers critical questions about change scope and risk.

## Use Cases

### Use Case 1: Pre-Change Impact Assessment

**Scenario:** "I need to modify the `GetCustomerDetails` DataRaptor. What's the blast radius?"

**Workflow:**
```
User: "What's the impact of changing GetCustomerDetails?"
  ↓
Impact Analyzer runs --analyze
  ↓
Discovers: 12 Integration Procedures call this DR
  ↓
Lists them with caller counts (direct + transitive)
  ↓
Risk Level: HIGH (12+ callers)
  ↓
Recommends: Full regression testing for all 12 IPs + their callers
```

### Use Case 2: Dependency Chain Analysis

**Scenario:** "This FlexCard uses an IP that calls a DataRaptor. What breaks if I remove the DataRaptor?"

**Workflow:**
```
User: "What happens if I remove GetCatalogDetails_DR?"
  ↓
Impact Analyzer loads full transitive chain
  ↓
Shows: FlexCard A → IP B → IP C → GetCatalogDetails_DR
  ↓
Identifies: 3 direct callers + 8 transitive callers
  ↓
Recommends: 11 components need retesting
```

### Use Case 3: Refactoring Scope

**Scenario:** "I want to consolidate 5 similar DataRaptors into one. How many places will be affected?"

**Workflow:**
```
User: "Can I consolidate GetProductDetails_v1, GetProductDetails_v2, etc.?"
  ↓
Impact Analyzer runs --analyze for each
  ↓
Shows cumulative impact: 23 total callers across all 5 DRs
  ↓
Recommends: Create consolidated DR, update all 23 callers, test scope: 23+transitives
```

## Modes

### Mode: `analyze` (default)

Full 5-step analysis: check docs → identify component → generate docs → load context → analyze.

**Example:**
```bash
# Run interactively:
User: "Analyze the impact of changing sales_ProductInCatalogCheck"

# Or explicitly:
python build_index.py --analyze vlocity sales_ProductInCatalogCheck
```

**Output:**
- Upstream callers (components that will break)
- Downstream dependencies (components affected)
- Risk level assessment
- Recommended test scope
- Migration notes if applicable

### Mode: `blast-radius`

Quick risk assessment without detailed documentation.

Shows:
- Number of upstream callers
- Risk level (HIGH/MEDIUM/LOW)
- Caller list by type

Useful for quick decisions: "Is this a safe change?"

### Mode: `impact-report`

Detailed impact report formatted for stakeholder review.

Includes:
- Executive summary (risk level, blast radius)
- Change impact table
- Testing recommendations
- Mitigation strategies

## Integration Points

### With vlocity-dependency-indexer

Impact Analyzer **requires** a pre-computed `index.json`. It will automatically generate one if missing.

Workflow:
```
1. Analyze is triggered
2. Check for index.json
3. If missing: "May I run --generate-all?" (asks permission)
4. If yes: generates index (one-time cost, ~30 seconds for 651 components)
5. Then proceeds with impact analysis using the index
```

### In Pipelines

The skill fits naturally into two orchestration pipelines:

**Vlocity Discovery & Architecture:**
```
indexer (init) → architecture-mapper → datapack-reviewer → impact-analyzer
```

Purpose: Understand an org's Vlocity setup and identify high-risk components.

**Vlocity Development Lifecycle:**
```
indexer (init) → generator → datapack-reviewer → tester → impact-analyzer
```

Purpose: Build and ship new Vlocity components with full impact awareness.

## Examples

### Example 1: Sales Order IP Analysis

**Question:** "What's the impact of optimizing sales_createOrderAPI?"

**Analysis Output:**
```
Primary Element:    sales_createOrderAPI
Component Type:     IntegrationProcedure
Total Dependencies: 105
Child IPs:          22

Upstream Impact (Callers):
  • sales_submitOrder (OmniScript)
  • CreateOrder_FlexCard (FlexCard)
  • order_processing_batch (Integration Procedure)
  [+2 more]

Downstream Impact (Called Components):
  • GetProductDetails (DataRaptor Extract)
  • CalculateDiscount (Calculation Procedure)
  • ValidateInventory (Integration Procedure)
  [+10 more]

Risk Level: HIGH
  Reason: Called by 5+ components; optimization changes behavior

Recommended Test Scope:
  • Retesting: 5 direct callers + 22 child IPs = 27 components
  • Scope: Create test cases for each order scenario (standard, discount, backorder)
  • Automation: Run full order pipeline integration tests
  • Timing: Regression testing estimated 4–6 hours manual + 2 CI runs

Migration Notes:
  • If changing IP signature: update 5 callers + 27 transitive callers
  • If removing step: validate 10 downstream DRs still receive input
  • If renaming: 32 total components need code updates
```

### Example 2: DataRaptor Consolidation

**Question:** "Can I consolidate GetCustomerInfo_v1, GetCustomerInfo_v2, GetCustomerInfo_v3?"

**Analysis for each:**
```
GetCustomerInfo_v1:  Callers: 8,  Risk: MEDIUM
GetCustomerInfo_v2:  Callers: 12, Risk: HIGH
GetCustomerInfo_v3:  Callers: 3,  Risk: LOW
────────────────────────────────────
Cumulative Impact:   23 direct callers
                     42 transitive callers
                     65 total components affected

Consolidated Recommendation:
  • Create GetCustomerInfo_unified
  • Update 23 direct callers (3-day effort)
  • Test 65 total components (regression scope)
  • Cleanup: archive old v1/v2/v3 after 1 release cycle
```

## Best Practices

1. **Analyze before you code** — Run impact analysis in planning phase, not after changes
2. **Understand your callers** — Know who depends on your component before modifying it
3. **Plan regression testing** — Use recommended test scope to size QA effort
4. **Document breaking changes** — If signature changes, list all affected callers
5. **Use for dependency updates** — When updating a library component, see downstream impact

## Limitations

1. **Index freshness** — Analysis is only as accurate as the index. Re-index after major metadata changes.
2. **Indirect dependencies** — The index captures direct Vlocity/OmniStudio dependencies. It does NOT include:
   - Custom Apex class dependencies (Remote Actions are noted but not fully traced)
   - LWC component dependencies (tracked as Remote but not expanded)
   - External API calls (noted as REST endpoints but not resolved)
3. **Design-time vs runtime** — The index reflects component structure, not actual runtime behavior (e.g., conditional branching in IP steps is not analyzed)
4. **Permissions** — Impact analysis assumes all listed components are deployed to the target org. It does not check user permissions.

## FAQ

**Q: How often should I rebuild the index?**

A: Once per project setup, then after major metadata syncs or quarterly refreshes. For CI/CD, rebuild on every deployment branch.

**Q: What if a component isn't in the index?**

A: The impact analyzer will note "Component not found in index" and suggest regenerating the index if metadata has changed since the last build.

**Q: Can I analyze multiple components at once?**

A: Not in a single analysis run, but you can run sequential analyses and manually synthesize. For bulk analysis, use the `vlocity-dependency-indexer --element` command with `--all` flag to see full transitive trees.

**Q: Does this work for OmniScripts and FlexCards?**

A: Yes. The index includes all component types. OmniScripts and FlexCards are analyzed for upstream callers and downstream dependencies.
