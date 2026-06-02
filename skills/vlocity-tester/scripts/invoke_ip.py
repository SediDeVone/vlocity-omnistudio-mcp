#!/usr/bin/env python3
"""
invoke_ip.py — Invoke a Vlocity/OmniStudio Integration Procedure via Salesforce REST API.

Supports:
  - Managed package: POST /services/apexrest/vlocity_cmt/v1/integrationprocedures/<TypeKey>
  - Managed (alternate): POST /services/apexrest/vlocity_cmt/v1/CustomSplit via IntegrationProcedureService
  - Native OmniStudio: POST /services/apexrest/omnistudio/v1/integrationprocedures/<TypeKey>

Usage:
  python invoke_ip.py --ip-key <key> [--input <file>] [--input-json <json>] [--org <alias>] [--schema managed|native|auto]
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

def get_org_info(org_alias=None):
    """Get instance URL and access token from Salesforce CLI."""
    cmd = ["sf", "org", "display", "--json"]
    if org_alias:
        cmd += ["--target-org", org_alias]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        info = data.get("result", {})
        instance_url = info.get("instanceUrl") or info.get("instanceUrl", "")
        access_token = info.get("accessToken") or info.get("accessToken", "")
        if not instance_url or not access_token:
            print("ERROR: Could not retrieve instanceUrl or accessToken from sf org display")
            print("Run: sf org login web --alias <alias>")
            sys.exit(1)
        return instance_url.rstrip("/"), access_token
    except subprocess.CalledProcessError as e:
        print(f"ERROR: sf org display failed: {e.stderr}")
        print("Ensure Salesforce CLI is installed and you are authenticated.")
        print("Run: sf org login web --alias <alias>")
        sys.exit(1)
    except FileNotFoundError:
        print("ERROR: 'sf' command not found. Install Salesforce CLI from https://developer.salesforce.com/tools/salesforcecli")
        sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_schema_from_datapack(ip_key, search_dirs=None):
    """Try to find the DataPack.json for the IP and detect schema from it."""
    if search_dirs is None:
        search_dirs = ["."]
    for base in search_dirs:
        for root, _, files in os.walk(base):
            for f in files:
                if f.endswith("_DataPack.json") and ip_key.replace("_", "") in f.replace("_", ""):
                    try:
                        with open(os.path.join(root, f), encoding="utf-8") as fh:
                            data = json.load(fh)
                        sobj = data.get("VlocityRecordSObjectType", "")
                        if sobj == "OmniProcess":
                            return "native"
                        if "%vlocity_namespace%" in sobj:
                            return "managed"
                    except Exception:
                        pass
    return None

# ─────────────────────────────────────────────────────────────────────────────
# REST INVOCATION
# ─────────────────────────────────────────────────────────────────────────────

def invoke_ip_managed_direct(instance_url, access_token, ip_key, input_data, verbose=False):
    """Invoke via the direct managed-package REST endpoint."""
    url = f"{instance_url}/services/apexrest/vlocity_cmt/v1/integrationprocedures/{ip_key}"
    body = json.dumps({"input": input_data, "options": {}}).encode("utf-8")
    return _post_request(url, access_token, body, verbose)

def invoke_ip_managed_split(instance_url, access_token, ip_key, input_data, verbose=False):
    """Invoke via the CustomSplit / IntegrationProcedureService endpoint (alternative)."""
    url = f"{instance_url}/services/apexrest/vlocity_cmt/v1/CustomSplit"
    payload = {
        "sClassName": "vlocity_cmt.IntegrationProcedureService",
        "sMethodName": "runIntegrationService",
        "input": {
            "ipMethod": ip_key,
            **input_data,
        },
        "options": {},
    }
    body = json.dumps(payload).encode("utf-8")
    return _post_request(url, access_token, body, verbose)

def invoke_ip_native(instance_url, access_token, ip_key, input_data, verbose=False):
    """Invoke via the native OmniStudio REST endpoint."""
    url = f"{instance_url}/services/apexrest/omnistudio/v1/integrationprocedures/{ip_key}"
    body = json.dumps({"input": input_data, "options": {}}).encode("utf-8")
    return _post_request(url, access_token, body, verbose)

def _post_request(url, access_token, body, verbose=False):
    """Execute HTTP POST and return (response_data, status_code, elapsed_ms)."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    if verbose:
        print(f"  POST {url}")
        print(f"  Body: {body.decode('utf-8')[:500]}...")

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            elapsed_ms = int((time.time() - start) * 1000)
            status = resp.status
            raw = resp.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"rawResponse": raw}
            return data, status, elapsed_ms
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start) * 1000)
        try:
            error_body = e.read().decode("utf-8")
            error_data = json.loads(error_body)
        except Exception:
            error_data = {"error": str(e), "code": e.code}
        return error_data, e.code, elapsed_ms

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Invoke a Vlocity/OmniStudio Integration Procedure via REST API")
    parser.add_argument("--ip-key", required=True, help="IP key e.g. sales_CreateOrder or myGuidedSelling_CreateCartIP")
    parser.add_argument("--org", help="Salesforce org alias (defaults to defaultusername)")
    parser.add_argument("--input", help="Path to JSON input file")
    parser.add_argument("--input-json", help="Inline JSON string for input")
    parser.add_argument("--schema", choices=["managed", "native", "auto"], default="auto",
                        help="Schema flavor (default: auto-detect)")
    parser.add_argument("--output", help="Save response JSON to this file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show request details")
    parser.add_argument("--use-split", action="store_true",
                        help="Use CustomSplit endpoint instead of direct endpoint (managed only)")
    args = parser.parse_args()

    # Load input data
    input_data = {}
    if args.input:
        if not os.path.exists(args.input):
            print(f"ERROR: Input file not found: {args.input}")
            sys.exit(1)
        with open(args.input, encoding="utf-8") as f:
            loaded = json.load(f)
            # Handle both {"input": {...}} and raw input formats
            if isinstance(loaded, dict) and "input" in loaded:
                input_data = loaded["input"]
            else:
                input_data = loaded
    elif args.input_json:
        try:
            input_data = json.loads(args.input_json)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in --input-json: {e}")
            sys.exit(1)
    else:
        print("WARNING: No input provided. Invoking with empty input. Use --input or --input-json.")

    # Get org auth info
    print(f"Authenticating with Salesforce org{'  (' + args.org + ')' if args.org else ''}...")
    instance_url, access_token = get_org_info(args.org)
    print(f"  Instance: {instance_url}")

    # Determine schema
    schema = args.schema
    if schema == "auto":
        detected = detect_schema_from_datapack(args.ip_key)
        schema = detected or "managed"
        print(f"  Schema: {schema} (auto-detected{' from DataPack' if detected else ', defaulting to managed'})")
    else:
        print(f"  Schema: {schema}")

    # Invoke the IP
    print(f"\nInvoking Integration Procedure: {args.ip_key}")
    if schema == "native":
        response, status, elapsed = invoke_ip_native(instance_url, access_token, args.ip_key, input_data, args.verbose)
    elif args.use_split:
        response, status, elapsed = invoke_ip_managed_split(instance_url, access_token, args.ip_key, input_data, args.verbose)
    else:
        response, status, elapsed = invoke_ip_managed_direct(instance_url, access_token, args.ip_key, input_data, args.verbose)
        # If direct endpoint returns 404, try CustomSplit as fallback
        if status == 404:
            print("  Direct endpoint returned 404, trying CustomSplit fallback...")
            response, status, elapsed = invoke_ip_managed_split(instance_url, access_token, args.ip_key, input_data, args.verbose)

    # Display result
    status_icon = "✓" if status in (200, 201) else "✗"
    print(f"\n  [{status_icon}] HTTP {status} — {elapsed}ms")
    print("\n--- Response ---")
    formatted = json.dumps(response, indent=2, default=str)
    print(formatted)

    # Save output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(response, f, indent=2, default=str)
        print(f"\n[Saved to: {args.output}]")

    # Exit with error code on failure
    if status not in (200, 201):
        sys.exit(1)

if __name__ == "__main__":
    main()
