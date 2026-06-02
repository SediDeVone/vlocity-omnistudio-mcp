# Field-Level Data Extraction (Part A)

## Overview

Part A extends the vlocity-dependency-indexer to extract and document field-level mappings between components. This provides Claude with visibility into how data flows between DataRaptors and Integration Procedures.

## What Changed

### New Function: `extract_field_mappings()`

Located in `scripts/build_index.py`, this function reads component metadata and extracts:

**For DataRaptors:**
- Native schema: reads `_Items.json` files
  - InputFieldName, InputObjectName (source)
  - OutputFieldName, OutputObjectName (target)
- Managed schema: reads `_Mappings.json` files
  - Namespaced field names (DomainObjectFieldAPIName, InterfaceFieldAPIName)

**For Integration Procedures:**
- Reads element JSON files and PropertySetConfig
  - `additionalInput`: data sent to called component
  - `additionalOutput`: data exposed after element
  - `responseJSONPath`: where response is stored
  - `sendJSONPath`: subset of state sent to component

### Updated Function: `command_document()`

Now appends a "## Data Flow" section to journey.md that includes:

**For DataRaptors:**
```markdown
## Data Flow

**Field Mappings:**

| Input Field | Input Type | Output Field | Output Type |
|-------------|-----------|--------------|-------------|
| Account.Id | Account | customerId | JSON |
| Account.Name | Account | customerName | JSON |
```

**For Integration Procedures:**
```markdown
## Data Flow

**Element Bindings:**

| Element | Type | Sends | Receives At |
|---------|------|-------|-------------|
| FetchCustomer | DataRaptorAction | `customerId: %input.id%` | data.customer |
```

### Updated Function: `command_generate_all()`

Bulk journey generation now includes field-level data flow information for all components.

## How It Works

### Native DataRaptor Example

Given a DataRaptor with `_Items.json`:
```json
[
  {
    "InputFieldName": "Id",
    "InputObjectName": "Account",
    "OutputFieldName": "accountId",
    "OutputObjectName": "JSON"
  }
]
```

The journey.md includes:
```markdown
| Account.Id | Account | accountId | JSON |
```

### Managed DataRaptor Example

Given a managed DataRaptor with `_Mappings.json`:
```json
[
  {
    "%vlocity_namespace%__DomainObjectFieldAPIName__c": "Id",
    "%vlocity_namespace%__DomainObjectAPIName__c": "Account",
    "%vlocity_namespace%__InterfaceFieldAPIName__c": "accountId"
  }
]
```

The journey.md includes:
```markdown
| accountId | JSON | Id | Account |
```

### Integration Procedure Example

Given an IP element with PropertySetConfig:
```json
{
  "Name": "FetchCustomer",
  "Type": "DataRaptorAction",
  "PropertySetConfig": {
    "additionalInput": {"customerId": "%input.accountId%"},
    "responseJSONPath": "data.customer"
  }
}
```

The journey.md includes:
```markdown
| FetchCustomer | DataRaptorAction | `customerId: %input.accountId%` | data.customer |
```

## MCP Integration

When the MCP tool returns context in `context-only` mode, it now includes:

1. **Architecture diagram** (existing)
2. **REST endpoint reference** (existing)
3. **Data Flow information** (NEW - Part A)
4. **Dependencies list** (existing)

Claude receives field-level visibility to answer questions like:

- "If I change the Account.Phone field mapping, what downstream components need testing?"
- "What data flows from sales_createOrderAPI into sales_provideAPI?"
- "Which components depend on this DataRaptor output?"

## Testing

Part A has been validated with:

1. **DataRaptor field extraction** - Native and managed schemas
2. **Integration Procedure element bindings** - PropertySetConfig parsing
3. **Journey.md generation** - Field data tables included
4. **MCP context formatting** - Field data flows through to Claude

## Example Usage

### CLI

```bash
python build_index.py --document /path/to/index.json sales_createOrderAPI ./output
# Generates sales_createOrderAPI-journey.md with ## Data Flow section
```

### MCP

```
Claude: "Analyze sales_createOrderAPI in /path/to/vlocity"
↓
MCP tool calls flow.py
↓
flow.py calls build_index.py --document
↓
journey.md now includes "## Data Flow" with element bindings
↓
Claude receives enriched context and provides field-aware impact analysis
```

## Files Modified

- `skills/vlocity-dependency-indexer/scripts/build_index.py`
  - Added `extract_field_mappings()` function (~180 lines)
  - Updated `command_document()` to include field data (~40 lines)
  - Updated `command_generate_all()` to include field data (~50 lines)

## No Schema Changes

The index.json format is unchanged. Field data is included only in:
- Generated journey.md (human-readable)
- MCP context returned to Claude
- Flow visualization (when available)

## Next Steps

Part B (Component Creation Toolkit) will build on this by:
- Loading component schemas from existing files
- Providing Claude with creation templates
- Validating new components against extracted field patterns
