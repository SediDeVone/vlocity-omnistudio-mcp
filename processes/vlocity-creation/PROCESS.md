# Vlocity Creation Process

Enable Claude to create OmniStudio components from validated schemas and good practices, not guesswork.

## Overview

The **vlocity-creation process** loads authoritative JSON schemas + good/bad practices guides, then presents them to Claude so it can create components from validated structure.

### Two Access Paths

#### Path A: MCP Tool (Claude Desktop)
```
User (Claude Desktop):
  "Create a DataRaptor Extract that fetches Account details by ID"
         ↓
MCP Tool (vlocity_schema):
  Calls flow.py --mode context-only
         ↓
flow.py:
  1. Loads schema: dataraptor_extract.schema.json
  2. Loads practices: generation-guide.md
  3. Merges into formatted markdown
         ↓
MCP Returns:
  Formatted schema + practices to Claude
         ↓
Claude (in session):
  Reviews schema + practices
  Creates component JSON following schema exactly
  Returns validated JSON
```

**Characteristics:**
- No separate API calls or LLM inference
- Schema + practices loaded once, returned to Claude
- Claude creates within existing session
- No ANTHROPIC_API_KEY required
- Works entirely within Claude's context

#### Path B: CLI (Developer)
```bash
python flow.py DataRaptor --subtype Extract --mode context-only
# Returns formatted markdown with schema + practices

python flow.py DataRaptor --subtype Extract --mode schema-only
# Returns raw JSON schema only
```

**Characteristics:**
- Direct Python invocation
- Useful for testing, validation, scripting
- Can pipe to other tools

## What Gets Loaded

### DataRaptor

**Files:**
- Schema: `skills/vlocity-generator/schemas/dataraptor_{extract|load|transform}.schema.json`
- Practices: `skills/vlocity-generator/references/generation-guide.md`

**Contents:**
- Required fields (DeveloperName, Label, Type, etc.)
- Optional fields (VlocityDataPackType, etc.)
- Field types and validation rules
- Naming conventions (CamelCase, no special chars)
- Good practices (pre/post transform bundles, etc.)
- Anti-patterns (circular references, etc.)

### Integration Procedure

**Files:**
- Schema: `skills/vlocity-generator/schemas/ip_element_types.schema.json`
- Practices: `skills/vlocity-generator/references/element-type-suffix-guide.md`

**Contents:**
- Element types and their properties
- PropertySetConfig structure for each element type
- Element naming conventions
- Execution order rules
- Input/output binding patterns

### FlexCard

**Files:**
- Schema: `skills/vlocity-generator/schemas/flexcard_definition.schema.json`
- Practices: `skills/vlocity-flexcard-helper/references/flexcard-schema-guide.md`

**Contents:**
- Card structure and properties
- State definitions and actions
- Data source configuration
- Layout and component properties
- Best practices for reusability

### OmniScript

**Files:**
- Schema: `skills/vlocity-generator/schemas/omniscript_element_types.schema.json`
- Practices: `skills/vlocity-flexcard-helper/references/omniscript-schema-guide.md`

**Contents:**
- Element types for OmniScript steps
- Block/step configuration
- Conditional logic patterns
- Data binding syntax
- Best practices for flow design

## How It Works

### 1. Request Schema

**User asks Claude:**
```
"Create a DataRaptor Extract that maps Account fields to JSON"
```

**Claude calls tool:**
```
vlocity_schema(component_type="DataRaptor", subtype="Extract")
```

### 2. Flow Loads Schema + Practices

```python
def get_schema(component_type, subtype=None):
    # Load dataraptor_extract.schema.json
    # Load generation-guide.md
    # Merge into context
    return {
        "schema": {...},
        "practices": "...",
        "component_type": "DataRaptor",
        "subtype": "Extract"
    }
```

### 3. Format for Claude

```python
def format_schema_context(component_type, schema_data):
    # Create markdown with:
    # - Title: "Component Creation Guide: DataRaptor"
    # - Schema JSON block
    # - Practices section (copied from guide)
    # - Instructions for Claude
    return formatted_markdown
```

### 4. Claude Creates Component

Claude sees the schema + practices and creates:
```json
{
  "name": "salesGetAccountByID",
  "label": "Get Account Details",
  "type": "Extract",
  "dataSourceType": "Account",
  "fields": [
    {"name": "Id", "type": "String", "required": true},
    {"name": "Name", "type": "String"},
    {"name": "BillingCity", "type": "String"}
  ]
}
```

## Workflow: Create a Component

### Example 1: DataRaptor Extract

**User:** "Create a DataRaptor Extract called accountLookup that fetches Account.Id, Name, and Phone"

**Claude:**
1. Calls `vlocity_schema(component_type="DataRaptor", subtype="Extract")`
2. Receives schema + practices
3. Reviews schema for required fields:
   - DeveloperName (required)
   - Label (required)
   - Type (required = "Extract")
   - Columns (required, array of field definitions)
4. Reviews practices for naming conventions:
   - DeveloperName: camelCase, no spaces
   - Column names: match SObject field names exactly
5. Creates component JSON following schema
6. Returns component JSON

**Result:**
```json
{
  "VlocityDataPackType": "DataRaptor",
  "DeveloperName": "accountLookup",
  "Label": "Account Lookup",
  "Type": "Extract",
  "SObjectName": "Account",
  "Columns": [
    {
      "FieldName": "Id",
      "ColumnName": "Id",
      "ColumnLabel": "Account ID"
    },
    {
      "FieldName": "Name",
      "ColumnName": "Name",
      "ColumnLabel": "Account Name"
    },
    {
      "FieldName": "Phone",
      "ColumnName": "Phone",
      "ColumnLabel": "Phone Number"
    }
  ]
}
```

### Example 2: Integration Procedure

**User:** "Create an Integration Procedure that calls the accountLookup DataRaptor and orders the result by Name"

**Claude:**
1. Calls `vlocity_schema(component_type="IntegrationProcedure")`
2. Receives schema + practices for IP elements
3. Reviews element types (DataRaptorAction, HTTPAction, etc.)
4. Reviews PropertySetConfig structure for each element type
5. Creates IP with elements
6. Returns IP JSON

## Integration with Part A (Field Extraction)

The vlocity-creation process complements Part A:

**Part A (Analysis):**
- Extracts existing field mappings from deployed components
- Shows Claude how data flows through existing system
- Enables impact analysis by field

**Part B (Creation):**
- Provides schemas for creating new components
- Ensures new components follow same structural rules
- Validates field names match naming conventions

**Combined:** Claude can now analyze existing components AND create new components that fit the existing architecture.

## File Structure

```
processes/vlocity-creation/
├── flow.py              # Main orchestration (get_schema, format_schema_context, run)
├── PROCESS.md           # This file
└── CHANGELOG.md         # Version history
```

## CLI Usage

### Get DataRaptor Extract Schema

```bash
python flow.py DataRaptor --subtype Extract --mode context-only
# Returns formatted markdown with schema + practices
```

### Get Raw Schema JSON

```bash
python flow.py DataRaptor --subtype Extract --mode schema-only
# Returns { "schema": {...}, "component_type": "DataRaptor", "subtype": "Extract" }
```

### Get FlexCard Schema

```bash
python flow.py FlexCard --mode context-only
```

### Get Integration Procedure Schema

```bash
python flow.py IntegrationProcedure --mode context-only
```

## MCP Tool Usage

The tool is automatically registered when MCP server starts. In Claude Desktop:

```
User: "Load the schema for creating a DataRaptor Extract"
Claude: [calls vlocity_schema tool]
Tool returns: Formatted schema + practices
Claude: [reviews and summarizes for user]
```

## What Gets Validated

Claude creates components that satisfy:

1. **Schema compliance** — All required fields present, correct types
2. **Naming conventions** — Field names match expected patterns
3. **Structural rules** — Relationships between fields are valid
4. **Best practices** — Follows documented good practices
5. **Integration readiness** — Component can be deployed and used

## Limitations

**What this process does NOT do:**

❌ Validate component names are unique (requires metadata access)
❌ Check if dependencies exist (requires full vlocity scan)
❌ Deploy components (requires Salesforce connection)
❌ Migrate or transform existing components (Part A is read-only analysis)
❌ Optimize performance (schema validation, not profiling)

**What this process DOES do:**

✅ Provide authoritative schemas for all component types
✅ Load good/bad practices from reference guides
✅ Format context for Claude to create valid components
✅ Ensure structural compliance before creation
✅ Enable consistent component design

## Next Steps

1. **Test with real schemas** — Try creating a component using the MCP tool
2. **Integrate with deployment** — Connect created components to vlocity-generator SKILL for deployment
3. **Add validation rules** — Layer additional checks (name uniqueness, dependency verification)
4. **Batch creation** — Enable creating multiple components in sequence
