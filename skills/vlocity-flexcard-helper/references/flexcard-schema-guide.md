# FlexCard JSON Schema & Definition Guide

This guide documents the JSON metadata format of Vlocity and OmniStudio FlexCards, explaining component structures, event-driven layouts, and conditional display filters.

---

## 1. Top-Level Structure

A FlexCard is defined in a main definition JSON file (typically the card's name, e.g. `salesProductCard.json`). The key top-level properties are:

| Field | Type | Description |
| :--- | :--- | :--- |
| **isFlex** | boolean | Set to `true` to declare it as a modern FlexCard rather than legacy Vlocity Card. |
| **isRepeatable** | boolean | Renders once for each item in the parsed data array if true. |
| **enableLwc** | boolean | True to compile the FlexCard as a native Lightning Web Component. |
| **dataSource** | object | Configuration block describing where the card retrieves its input data. |
| **states** | array | Interactive visual states. Standard layouts usually have at least one base state. |
| **events** | array | Pub/sub and custom listeners defined globally on the card. |
| **globalCSS** | boolean | Renders standard Vlocity stylesheet properties. |

---

## 2. DataSource Configuration

The `dataSource` block specifies how the card queries or receives data.

### Types of Data Sources:
- **Integration Procedure**: Triggers an IP during card rendering.
- **DataRaptor**: Triggers a DataRaptor Extract bundle.
- **SObject**: Triggers a direct SOQL query.
- **Custom**: Employs hardcoded static mock JSON data (useful for design).

### Example Configuration (Integration Procedure):
```json
"dataSource": {
  "type": "IntegrationProcedure",
  "value": {
    "ipMethod": "MyAccount_GetProducts",
    "inputMap": {
      "AccountId": "{recordId}"
    },
    "optionsMap": {
      "vlocityAsync": false
    }
  }
}
```
*Note*: `{recordId}` is an auto-populated context variable containing the parent page's active Salesforce Record ID.

---

## 3. States & Component Layout Tree

FlexCards support multiple visual states (e.g. active account vs suspended account).
Each state contains a **Component Tree** nested inside layout layers.

```json
"states": [
  {
    "name": "Active State",
    "filter": {
      "conditions": [
        {
          "field": "AccountStatus",
          "operator": "==",
          "value": "Active"
        }
      ]
    },
    "components": {
      "layer-0": {
        "children": [
          {
            "name": "ProductHeaderBlock",
            "element": "block",
            "children": [
              {
                "name": "ProductNameText",
                "element": "text",
                "property": {
                  "text": "<h3>{Name}</h3>"
                }
              }
            ]
          }
        ]
      }
    }
  }
]
```

---

## 4. Component Element Types

FlexCard UI nodes are defined by their `element` tag:

### A. `text` (HTML Content)
Supports rich text and merge fields (surrounded by `{}` braces).
```json
"property": {
  "text": "<p>Account Owner: <strong>{OwnerName}</strong></p>"
}
```

### B. `field` (Data field)
Renders a raw value from the data source with built-in formatters (Date, Currency, etc.).

### C. `button` (Action Trigger)
Renders a button that fires events, updates states, or triggers Apex/IP actions.

### D. `image`
Displays static or dynamic images.

### E. `childCard`
Embeds another FlexCard inside the current card, passing down the current row data.

### F. `datatable`
Renders standard tabular/grid layout columns.

---

## 5. Events & State Actions

Buttons and interactive triggers utilize `stateAction` collections to manage clicks.

### Action Types:
- **runIntegrationProcedure**: Triggers an IP.
- **updateOmniScript**: Updates variables if the card is embedded inside an OmniScript.
- **navigate**: Navigates to a community page, standard page, or custom URL.
- **openCard**: Renders a child card inside a Modal popup.

### Action JSON Example:
```json
"actionList": [
  {
    "type": "runIntegrationProcedure",
    "ipMethod": "MyAccount_UpdateStatus",
    "inputMap": {
      "Id": "{Id}",
      "NewStatus": "Suspended"
    }
  }
]
```

---

## 6. Conditional Visibility
- **State-level Filter**: The `filter` block evaluates conditions. If true, that state's component layout is loaded.
- **Element-level Show**: Individual components inside the layout can have a `"show"` formula property (e.g. `"{Price} > 500"`), hiding the element if the evaluation resolves to false.
