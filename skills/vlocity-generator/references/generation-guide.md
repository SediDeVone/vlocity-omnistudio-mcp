# Vlocity Component Generation Guide

This guide provides annotated examples and best practices for creating and modifying Vlocity and OmniStudio DataPacks (DataRaptors and Integration Procedures) using LLMs.

---

## 1. DataRaptor Extract Walkthrough (Query Account by Id)

A DataRaptor Extract queries Salesforce data. In managed package format, it is saved under the `%vlocity_namespace%__DRBundle__c` SObject, while the mappings are under `%vlocity_namespace%__DRMapItem__c`.

Here is a full `_DataPack.json` sample for a simple Account extract:

```json
{
  "Name": "My_GetAccountDetails",
  "Type": "Extract",
  "InputType": "JSON",
  "OutputType": "JSON",
  "InterfaceObject": "Account",
  "CheckFieldLevelSecurity": false,
  "IgnoreErrors": false,
  "OverwriteAllNullValues": false,
  "Mappings": [
    {
      "InterfaceObjectName": "Account",
      "InterfaceFieldAPIName": "Id",
      "FilterOperator": "=",
      "FilterValue": "AccountId",
      "FilterGroup": 0,
      "DomainObjectAPIName": "Account",
      "DomainObjectFieldAPIName": "Id"
    },
    {
      "InterfaceObjectName": "Account",
      "InterfaceFieldAPIName": "Name",
      "DomainObjectAPIName": "Account:Name"
    },
    {
      "InterfaceObjectName": "Account",
      "InterfaceFieldAPIName": "Phone",
      "DomainObjectAPIName": "Account:Phone"
    }
  ]
}
```

### Explanation:
- The first mapping queries `Account` where `Id` equals the input parameter `AccountId`.
- The subsequent mappings specify that from the retrieved `Account` record, retrieve `Name` and `Phone` and nest them in the output JSON under `{"Account": {"Name": "...", "Phone": "..."}}`.

---

## 2. Integration Procedure Walkthrough (SetValues → DataRaptor → Response)

An Integration Procedure coordinates steps. The main component is saved in `%vlocity_namespace%__OmniScript__c` (managed) or `OmniProcess` (native), with its steps inside `%vlocity_namespace%__Element__c` or `OmniProcessElement`.

Here is a full structured representation:

```json
{
  "Name": "My_GetAndEnrichAccount",
  "Type": "MyAccount",
  "SubType": "GetAndEnrich",
  "Language": "Procedure",
  "IsProcedure": true,
  "Elements": [
    {
      "Name": "InitParams_SV",
      "Type": "Set Values",
      "Active": true,
      "PropertySetConfig": {
        "elementValueMap": {
          "DefaultStatus": "Active"
        },
        "label": "Initialize Parameters"
      }
    },
    {
      "Name": "FetchAccount_DRE",
      "Type": "DataRaptor Extract Action",
      "Active": true,
      "PropertySetConfig": {
        "bundle": "My_GetAccountDetails",
        "dataRaptor Input Parameters": [
          {
            "name": "AccountId",
            "source": "%AccountId%"
          }
        ],
        "label": "Fetch Account Details"
      }
    },
    {
      "Name": "ReturnResponse_RSA",
      "Type": "Response Action",
      "Active": true,
      "PropertySetConfig": {
        "responseJSONNode": "AccountData",
        "responseJSONPath": "FetchAccount_DRE:Account",
        "additionalOutput": {
          "Status": "%InitParams_SV:DefaultStatus%",
          "Timestamp": "NOW()"
        },
        "label": "Return Final Response"
      }
    }
  ]
}
```

---

## 3. Adding an Element to an Existing IP

To add an element to an existing IP folder structure:
1. Identify the list of elements under the IP directory (they are named `_Element_<ElementName>.json`).
2. Add a new `_Element_<ElementName>.json` file.
3. Update `_DataPack.json` in the IP's root directory to include the element in the parent's children tracking lists.
4. Ensure the `Order` field in the new element JSON matches its sequence position.

*Example Element JSON (`_Element_LogEvent_RA.json`)*:
```json
{
  "Name": "LogEvent_RA",
  "Type": "Remote Action",
  "Active": true,
  "Order": 3,
  "PropertySetConfig": {
    "remoteClass": "MyLogger",
    "remoteMethod": "logIPExecution",
    "additionalInput": {
      "ipName": "MyAccount_GetAndEnrich",
      "payload": "%FetchAccount_DRE%"
    }
  }
}
```

---

## 4. DataRaptor Load Walkthrough (Upsert Account)

A DataRaptor Load writes to Salesforce objects. It maps an incoming JSON payload to target Salesforce SObjects and fields.

```json
{
  "Name": "My_UpsertAccount",
  "Type": "Load",
  "InputType": "JSON",
  "OutputType": "CustomSObject",
  "RollbackOnError": true,
  "Mappings": [
    {
      "InterfaceFieldAPIName": "AccId",
      "DomainObjectAPIName": "Account:Id",
      "IsUpsertKey": true
    },
    {
      "InterfaceFieldAPIName": "AccName",
      "DomainObjectAPIName": "Account:Name",
      "IsRequiredForUpsert": true
    },
    {
      "InterfaceFieldAPIName": "AccPhone",
      "DomainObjectAPIName": "Account:Phone"
    }
  ]
}
```

### Explanation:
- `IsUpsertKey: true` tells the engine to check if an Account exists with `Id = AccId` and perform an UPDATE. If not found, it inserts a new account.
- `IsRequiredForUpsert` guarantees that validation fails early if no Name is present.

---

## 5. DataRaptor Transform Walkthrough (Reshape a List)

DataRaptor Transforms convert an incoming JSON array or tree into a different structure.

```json
{
  "Name": "My_ReshapeProductList",
  "Type": "Transform",
  "InputType": "JSON",
  "OutputType": "JSON",
  "Mappings": [
    {
      "InterfaceFieldAPIName": "RawProducts:Name",
      "DomainObjectAPIName": "CleanProducts:ProductName"
    },
    {
      "InterfaceFieldAPIName": "RawProducts:Price__c",
      "DomainObjectAPIName": "CleanProducts:Cost"
    }
  ]
}
```

If input is `{"RawProducts": [{"Name": "Fiber 100", "Price__c": 500}]}`, output will be `{"CleanProducts": [{"ProductName": "Fiber 100", "Cost": 500}]}`.

---

## 6. Common Variable Patterns

### Variable Referencing (`%varName%`)
- **Root-level Reference**: `%AccountId%` refers to the root-level variable in the input payload.
- **Step-level Reference**: `%FetchAccount_DRE:Account%` refers to the `Account` node inside the output of the step `FetchAccount_DRE`.
- **Deep Reference**: `%StepA:BlockB:InputC%` accesses nested nodes inside wizard steps.

### Execution Conditional Formulas
Use to conditionally run steps.
- **Example**: `%FetchAccount_DRE:Account:Active% == true`
- **Checking Null/Empty**: `%AccountId% != NULL` or `ISBLANK(%AccountId%) == false`

### Extra Payload Passing
In DataRaptor Actions and Remote Actions:
- **Send Only Additional Input**: Set to `true` to discard the main incoming JSON tree and only pass the key-value pairs specified under `additionalInput`.
- **Default Behavior**: If `false`, the entire JSON payload is passed down, with `additionalInput` merged on top.

---

## 7. Troubleshooting & Common Pitfalls

- **Wrong SObject Type / Namespace**: When switching between Managed Package and Native OmniStudio, using the wrong field names (e.g. using `expectedInputJson` on a managed package DataRaptor instead of `InputJson`) will cause silent or cryptic deployment failures.
- **Missing Response Action**: If an Integration Procedure doesn't have a `Response Action` (`_RSA` element), the REST API will return `200 OK` but an empty JSON body `{}`, making it look like a bug in the earlier actions. Always add a response step.
- **Malformed Suffixes**: Incorrectly named suffixes (e.g. named `FetchData_Action` instead of `FetchData_DRE`) won't crash the engine, but breaks standard reviews and clean architecture tracking. Always end with the proper suffixes.
