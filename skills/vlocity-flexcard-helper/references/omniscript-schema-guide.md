# OmniScript JSON Schema & Element Reference Guide

This reference documents the multi-file directory structure and PropertySet options that define a Vlocity OmniScript form wizard workflow.

---

## 1. Directory & File Organization

Vlocity OmniScripts are divided into separate files within a directory, representing individual elements. This prevents massive file diff issues in version control.

### Files inside an OmniScript directory:
- **`{Type}_{SubType}_{Language}_DataPack.json`**: The root configuration file storing high-level metadata (e.g. Type, SubType, language) and tracking the collection of child elements.
- **`{Type}_{SubType}_{Language}_PropertySet.json`**: Contains global runtime settings for the wizard.
- **`_Element_{ElementName}.json`**: One JSON file per step, input element, formula, or action.
- **`_ParentKeys.json`**: Tracks external dependencies (DataRaptors, IPs, Apex classes) to ensure correct migration ordering.

---

## 2. Global PropertySet Fields

The root OmniScript contains global configurations in its property set block:

| Field | Type | Description |
| :--- | :--- | :--- |
| **allowCancel** | boolean | Shows a Cancel button allowing the user to abort the wizard. |
| **allowSaveForLater** | boolean | Enables state persistence so a user can pause and return to the form later. |
| **hideStepChart** | boolean | Hides the horizontal step navigation indicators at the top of the UI. |
| **autoFocus** | boolean | Automatically shifts focus to the first input field on step changes. |
| **persistentComponent** | array | Renders static sidebar components or layouts throughout the wizard. |
| **saveObjectId** | string | The SObject ID used to map standard Salesforce attachment saves. |

---

## 3. Element Types Reference

Every child element has a `"Type"` mapping to a specific rendering engine or action handler:

### A. Container Elements

- **Step**: The primary layout page. Everything inside a Step is rendered on a single wizard screen.
- **Block**: A layout group within a Step. Used for grid positioning or conditional section show/hide.
- **Conditional Block**: An active block that evaluates a formula before displaying its nested children.
- **Loop Block**: Iterates over a JSON list, repeating all child input elements.

### B. Input Elements

- **Text**: Renders a standard single-line text input field.
- **Number**: Enforces numeric input validation.
- **Select**: Renders a picklist. Options can be static key-value pairs or dynamic (populated from an Apex class).
- **Date / DateTime**: Displays a calendar input widget.
- **Checkbox / Radio**: Option toggles.
- **Type Ahead Block**: An autocomplete text field mapping to SOQL or external API lookups.

### C. Action Elements

- **Integration Procedure Action (IPA)**: Executes an IP in the background.
  - *Key Property*: `integrationProcedureKey`: "MyAccount_UpdateStatus"
- **DataRaptor Extract Action (DREA)**: Invokes a DR Extract.
  - *Key Property*: `bundle`: "My_GetAccountDetails"
- **Remote Action**: Invokes a custom Apex Controller method.
  - *Key Properties*: `remoteClass`, `remoteMethod`
- **Navigate Action**: Redirects the user on completion.

---

## 4. Variable Referencing (`%` Syntax)

OmniScript maps fields dynamically using parent-child paths:

- **Simple variable**: `%AccountId%` retrieves the root value.
- **Nested Step Path**: `%VerifyStep:ContactBlock:LastName%` digs into the step structure.
- **List/Array Index**: `%AccountList|0:Name%` retrieves the `Name` field of the first item in the `AccountList` array.
- **Formulas**: In conditional visibility, use standard logical evaluations:
  ```json
  "show": {
    "group": {
      "operator": "AND",
      "rules": [
        {
          "field": "VerifyStep:AgreedToTerms",
          "operator": "==",
          "value": "true"
        }
      ]
    }
  }
  ```

---

## 5. Validation Patterns
- **Required Fields**: Set `required: true` on inputs.
- **Pattern Match (Regex)**: Define dynamic constraints (e.g. email regex validation) inside the element's PropertySet.
- **Custom Error Messages**: Define key-value pairs mapping validator triggers to user-facing strings (e.g. `{"required": "Please provide a valid account number."}`).
