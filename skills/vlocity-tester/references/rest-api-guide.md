# Vlocity & OmniStudio REST API Guide

This guide documents the Salesforce REST API endpoints used to invoke deployed Vlocity Integration Procedures (IPs) and DataRaptors (DRs), detailing authentication, request formats, and handling common error responses.

---

## 1. Managed Package Endpoints

When using the legacy managed package flavor (`vlocity_cmt` or `vlocity_ps`), the Vlocity Custom Apex REST endpoint handles invocations.

### A. Integration Procedure Endpoint
Invoke an Integration Procedure by its Type and SubType key (`{Type}_{SubType}`):
```http
POST /services/apexrest/vlocity_cmt/v1/integrationprocedures/{Type}_{SubType}
```
**Request Body**:
```json
{
  "AccountId": "0018000000abcde",
  "Status": "Active"
}
```

### B. Alternate CustomSplit Endpoint
Sometimes, depending on namespace configuration, the system routes requests via the `CustomSplit` Apex class:
```http
POST /services/apexrest/vlocity_cmt/v1/CustomSplit
```
**Request Body**:
```json
{
  "sClassName": "vlocity_cmt.IntegrationProcedureService",
  "sMethodName": "runIntegrationService",
  "input": {
    "ipMethod": "Type_SubType",
    "AccountId": "0018000000abcde"
  },
  "options": {}
}
```

### C. DataRaptor Endpoint
Invoke a DataRaptor directly:
```http
POST /services/apexrest/vlocity_cmt/v1/DataRaptor/{DataRaptorName}
```
**Request Body**:
```json
{
  "input": {
    "AccountId": "0018000000abcde"
  },
  "options": {
    "type": "Extract"
  }
}
```

---

## 2. Native OmniStudio Endpoints

With the new native Salesforce OmniStudio architecture (OmniProcess and OmniDataTransform), endpoints use standard Salesforce namespaces.

### A. Integration Procedure Endpoint
```http
POST /services/apexrest/omnistudio/v1/integrationprocedures/{Type}_{SubType}
```

### B. DataRaptor Endpoint
```http
POST /services/apexrest/omnistudio/v1/DataRaptor/{DataRaptorName}
```

---

## 3. Authentication via Salesforce CLI

To authorize REST API requests, retrieve the access token and API instance URL from the `sf` CLI (previously `sfdx`).

### Command
```bash
sf org display --json --target-org <org_alias>
```

### Response JSON Extract
```json
{
  "status": 0,
  "result": {
    "accessToken": "00D80000000xxxx!ARQA...",
    "instanceUrl": "https://mycompany-dev.develop.my.salesforce.com",
    "username": "developer@mycompany.com"
  }
}
```

### Applying Authorization Header
Merge the instance URL and access token in HTTP calls:
```http
Host: mycompany-dev.develop.my.salesforce.com
Authorization: Bearer 00D80000000xxxx!ARQA...
Content-Type: application/json
```

---

## 4. Example Curl Commands

### Invoking an Integration Procedure (Managed)
```bash
curl -X POST \
  https://mycompany-dev.develop.my.salesforce.com/services/apexrest/vlocity_cmt/v1/integrationprocedures/MyAccount_UpdateAddress \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "AccountId": "0018000000abcdeAAA",
    "Street": "123 Main Street"
  }'
```

### Invoking a DataRaptor (Native)
```bash
curl -X POST \
  https://mycompany-dev.develop.my.salesforce.com/services/apexrest/omnistudio/v1/DataRaptor/My_GetAccountDetails \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "AccountId": "0018000000abcdeAAA"
    },
    "options": {
      "type": "Extract"
    }
  }'
```

---

## 5. Error Response Format & Troubleshooting

### Scenario A: Unauthorized (401)
- **Cause**: Session expired or incorrect Org Alias.
- **Fix**: Re-authenticate using `sf org login web` or check target org value.

### Scenario B: Endpoint Not Found (404)
- **Cause**: Wrong schema flavor (e.g. attempting native path on managed org).
- **Fix**: Check `invoke_ip.py --schema managed` or `native` flag to force correct routing.

### Scenario C: Vlocity Engine Failure (200 but error in body)
Sometimes errors return 200 HTTP codes but report failures inside:
```json
{
  "error": "IP MyAccount_UpdateAddress not found or inactive.",
  "success": false
}
```
- **Cause**: Deployed IP is deactivated.
- **Fix**: Ensure the element has `Active = true` in its Salesforce record (check `elem_active_field`).
