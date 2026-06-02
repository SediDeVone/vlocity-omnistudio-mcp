# Knowledge Base

Anonymized corpus of OmniStudio components from past projects. Used to enhance component creation tools with real-world examples and patterns.

## Structure

```
knowledge-base/
├── DataRaptor/
│   ├── Extract/
│   │   ├── patterns.json              # Statistical patterns (safe to commit)
│   │   └── examples/
│   │       ├── domain_getEntityById.json              # Anonymized component
│   │       ├── domain_getEntityById.meta.json         # Metadata (safe to commit)
│   │       └── domain_getEntityById.mapping.json      # Gitignored: reverse-engineering only
│   ├── Load/
│   └── Transform/
├── IntegrationProcedure/
│   ├── patterns.json
│   └── examples/
├── FlexCard/
│   ├── patterns.json
│   └── examples/
├── OmniScript/
│   ├── patterns.json
│   └── examples/
└── embeddings/                        # Gitignored: local ChromaDB index
```

## What's Safe to Commit

- `*.json` example files — anonymized, no proprietary identifiers
- `*.meta.json` — metadata only (hashed project ID, caller count, field count)
- `patterns.json` — statistical aggregates (inherently safe)
- `*.md` documentation

## What's Gitignored (Local Only)

- `*.mapping.json` — maps anonymous identifiers back to real names
- `embeddings/` — ChromaDB index with full text (developers build locally from committed examples)

## Populating the Knowledge Base

```bash
# Harvest components from a single project
python processes/build_knowledge_base.py harvest /path/to/vlocity --project myproject

# Merge indexes from multiple projects (creates dependency cross-reference)
python processes/build_knowledge_base.py merge /proj1 proj1 /proj2 proj2 --output knowledge-base/dependency-index/index.json
```

## Anonymization Algorithm

| Input | Output | Preserved? |
|---|---|---|
| `vlocity_cmt__Bundle__c` (namespace prefix) | `<ns>__Bundle__c` | N |
| `Acme_ServiceCode__c` (custom SObject) | `DomainObject_A` | N |
| `acme__ServiceCode__c` (custom field) | `DomainField_1` | N |
| `acme_getCustomerDetails` (component name) | `domain_getEntityDetails` | N |
| `%input.acmeCustomerId%` (reference) | `%input.domainEntityId%` | N |
| `Account`, `Contact` (standard objects) | `Account`, `Contact` | ✓ |
| `Id`, `Name`, `BillingCity` (standard fields) | (same) | ✓ |
| Element types, filter operators, structure | (same) | ✓ |

**Key insight:** Custom identifiers change, but structural patterns are universal. The anonymization pipeline preserves everything Claude needs to create well-structured components.
