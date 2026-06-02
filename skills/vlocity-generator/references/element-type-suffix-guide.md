# Vlocity Element Type Suffix Guide

This reference documents the standard naming conventions, element type suffixes, and key configurations used when working with Vlocity and OmniStudio Integration Procedures (IPs), DataRaptors (DRs), and OmniScripts.

## Suffix Reference Table

In Vlocity development, elements are traditionally named with specific uppercase suffixes indicating their action type. This makes reading Integration Procedure actions and element hierarchies highly intuitive.

| Suffix | Element Type | Used In | Notes / Purpose |
| :--- | :--- | :--- | :--- |
| **\_SV** | Set Values | IP, OmniScript | Sets variables, context parameters, or default values in the JSON tree. |
| **\_DRT** | DataRaptor Transform Action | IP | Invokes a DataRaptor Transform to reshape hierarchical JSON structures. |
| **\_DRE** | DataRaptor Extract Action | IP, OmniScript | Standard DataRaptor Extract querying Salesforce SObjects into a JSON document. |
| **\_DREA** | DataRaptor Extract Action (Async) | OmniScript | Performs a non-blocking asynchronous extract in an OmniScript step. |
| **\_DREAT** | DataRaptor Extract Action (Turbo) | IP, OmniScript | High-performance cached query retrieving fields from a single SObject. |
| **\_DRTB** | DataRaptor Turbo Action | OmniScript | Similar to DREAT but optimized for OmniScript UI retrieval. |
| **\_DRPA** | DataRaptor Post Action (Load) | IP | Invokes a DataRaptor Load/Post bundle to write, update, or upsert Salesforce data. |
| **\_DRP** | DataRaptor Post Action (Load) | IP | Alternative abbreviation of DRPA for writing data. |
| **\_DRL** | DataRaptor Load Action | IP | Direct DataRaptor Load Action reference. |
| **\_RA** | Remote Action | IP | Invokes an Apex Controller class and method with JSON input. |
| **\_RSA** | Response Action | IP | Sends the final response JSON from an IP back to the caller/browser. |
| **\_IPA** | Integration Procedure Action | OmniScript | Invokes an external Integration Procedure from an OmniScript step. |
| **\_CB** | Conditional Block | IP, OmniScript | Groups multiple child elements to run only if a condition formula is met. |
| **\_LB** | Loop Block | IP | Iterates over a JSON list, running child actions for each list item. |
| **\_TCB** | Try Catch Block | IP | Catches errors occurring within nested steps, returning custom fallback data. |
| **\_NA** | Navigate Action | OmniScript | Navigates the user to a page, record page, URL, or console tab. |
| **\_CLWC** | Custom LWC (Button) | OmniScript | Renders a custom Salesforce Lightning Web Component as a button/interactive element. |
| **\_LWC** | LWC Element | OmniScript | Embeds a custom Lightning Web Component within a step. |
| **\_STEP** | Step container | OmniScript | A wizard page containing form inputs and display elements. |
| **\_Step** | Step container | OmniScript | Alternate casing for Step container. |
| **\_IP** | Integration Procedure | Type suffix | Used when referencing another IP or as an identifier. |
| **\_HTTP** | HTTP Action | IP | Makes REST or SOAP callouts to external APIs. |
| **\_TB** | Type Ahead Block | OmniScript | Renders a search input with autocomplete options (e.g. Google Address lookup). |
| **\_EB** | Edit Block | OmniScript | Allows inline editing, adding, or deleting a list of objects in a table-like view. |

---

## DataRaptor Naming Conventions

When generating or editing DataRaptor bundles, follow these standardized prefixes and suffix mappings to stay aligned with the architecture:
- **Prefix**: Prefix with project shortcode (e.g. `Prefix_` or `Custom_`) followed by functional area.
- **DREAT (DataRaptor Extract Action - Turbo)**: Use when querying fields from a single target object without complex sub-queries.
- **DRT (DataRaptor Transform)**: Use exclusively for reshaping JSON trees, converting string arrays to object lists, or applying formulas. Do not include SObject queries in a Transform.
- **DRPA / DRP (DataRaptor Post Action)**: Use for transactional writes. Always set upsert keys appropriately so matching accounts/contacts are updated rather than duplicated.

---

## IP Type/Subtype Key Formation

In Vlocity, an Integration Procedure is identified in code and REST APIs by its combined type and subtype key:
- **ProcedureKey** = `{Type}_{SubType}`
- **Salesforce Object Field Mapping**:
  - **Managed Package**: The object `%vlocity_namespace%__OmniScript__c` holds IPs (with `%vlocity_namespace%__IsProcedure__c` set to `true`). The lookup identifier is `%vlocity_namespace%__ProcedureKey__c` which equals `{Type}_{SubType}`.
  - **Native OmniStudio**: The object `OmniProcess` is used, and the system looks up by the combination of `Type` and `SubType` fields.

*Example*: If an IP has `Type` = `MyAccount` and `SubType` = `UpdateAddress`, its ProcedureKey is `MyAccount_UpdateAddress`. The REST endpoint path becomes `/services/apexrest/vlocity_cmt/v1/integrationprocedures/MyAccount_UpdateAddress`.

---

## OmniScript Key Formation

OmniScripts are defined by a triple key that accounts for language:
- **SourceKey** = `{Type}_{SubType}_{Language}`
- **Element Mapping**:
  - Elements in OmniScript are linked to their parent OmniScript record via the parent's ID (`%vlocity_namespace%__OmniScriptId__c` in managed or `OmniProcessId` in native).
  - The combination of Type, SubType, and Language uniquely identifies the wizard workflow.
