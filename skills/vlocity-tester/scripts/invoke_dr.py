#!/usr/bin/env python3
"""
invoke_dr.py — Invoke a Vlocity/OmniStudio DataRaptor via Salesforce REST API.

Supports:
  - Managed package: POST /services/apexrest/vlocity_cmt/v1/DataRaptor/<DRName>
  - Native OmniStudio: POST /services/apexrest/omnistudio/v1/DataRaptor/<DRName>

Usage:
  python invoke_dr.py --dr-name <name> --dr-type Extract [--input <file>] [--org <alias>]
  python invoke_dr.py --dr-name <name> --dr-dir <path> [--org <alias>]  # auto-reads SampleInput
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

# ─────────────────────────────────────────────────────────────────────────────
# AUTH (shared with invoke_ip.py logic)
# ─────────────────────────────────────────────────────────────────────────────

def get_org_info(org_alias=None):
    cmd = ["sf", "org", "display", "--json"]
    if org_alias:
        cmd += ["--target-org", org_alias]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        info = data.get("result", {})
        instance_url = info.get("instanceUrl", "")
        access_token = info.get("accessToken", "")
        if not instance_url or not access_token:
            print("ERROR: Could not get org info. Run: sf org login web --alias <alias>")
            sys.exit(1)
        return instance_url.rstrip("/"), access_token
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"ERROR: {e}")
        print("Ensure Salesforce CLI is installed and authenticated.")
        sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_schema_from_dir(dr_dir):
    """Detect schema flavor from DataPack.json in the DR directory."""
    if not dr_dir or not os.path.isdir(dr_dir):
        return None
    for f in os.listdir(dr_dir):
        if f.endswith("_DataPack.json"):
            try:
                with open(os.path.join(dr_dir, f), encoding="utf-8") as fh:
                    data = json.load(fh)
                sobj = data.get("VlocityRecordSObjectType", "")
                if sobj == "OmniDataTransform":
                    return "native"
                if "DRBundle" in sobj or "%vlocity_namespace%" in sobj:
                    return "managed"
                # Also check Type field
                dr_type = data.get("Type") or data.get("%vlocity_namespace%__Type__c")
                return "managed"  # if we found a DataPack, assume managed unless we see OmniDataTransform
            except Exception:
                pass
    return None

def detect_dr_type_from_dir(dr_dir):
    """Auto-detect DataRaptor type (Extract/Load/Transform) from DataPack.json."""
    if not dr_dir or not os.path.isdir(dr_dir):
        return "Extract"
    for f in os.listdir(dr_dir):
        if f.endswith("_DataPack.json"):
            try:
                with open(os.path.join(dr_dir, f), encoding="utf-8") as fh:
                    data = json.load(fh)
                # Try both schema flavors
                dr_type = (data.get("Type") or
                           data.get("%vlocity_namespace%__Type__c") or
                           "Extract")
                return dr_type
            except Exception:
                pass
    return "Extract"

def load_sample_input_from_dir(dr_dir, dr_name):
    """Load SampleInput from the DR directory."""
    if not dr_dir or not os.path.isdir(dr_dir):
        return {}
    candidates = [
        f"{dr_name}_SampleInputJson.json",
        f"{dr_name}_SampleInput.json",
        "SampleInputJson.json",
    ]
    for candidate in candidates:
        path = os.path.join(dr_dir, candidate)
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                print(f"  [Auto-loaded SampleInput from: {path}]")
                return data
            except Exception:
                pass
    return {}

# ─────────────────────────────────────────────────────────────────────────────
# REST INVOCATION
# ─────────────────────────────────────────────────────────────────────────────

def invoke_dr(instance_url, access_token, dr_name, dr_type, input_data, schema="managed", verbose=False):
    """Invoke a DataRaptor via REST API."""
    if schema == "native":
        url = f"{instance_url}/services/apexrest/omnistudio/v1/DataRaptor/{dr_name}"
    else:
        url = f"{instance_url}/services/apexrest/vlocity_cmt/v1/DataRaptor/{dr_name}"

    payload = {
        "input": input_data,
        "options": {"type": dr_type},
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    if verbose:
        print(f"  POST {url}")
        print(f"  Body: {json.dumps(payload)[:500]}")

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            elapsed_ms = int((time.time() - start) * 1000)
            raw = resp.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {"rawResponse": raw}
            return data, resp.status, elapsed_ms
    except urllib.error.HTTPError as e:
        elapsed_ms = int((time.time() - start) * 1000)
        try:
            error_data = json.loads(e.read().decode("utf-8"))
        except Exception:
            error_data = {"error": str(e), "code": e.code}
        return error_data, e.code, elapsed_ms

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Invoke a Vlocity/OmniStudio DataRaptor via REST API")
    parser.add_argument("--dr-name", required=True, help="DataRaptor name e.g. salesGetAssetByPremiseId")
    parser.add_argument("--dr-type", choices=["Extract", "Load", "Transform"],
                        help="DataRaptor type (auto-detected if --dr-dir is provided)")
    parser.add_argument("--org", help="Salesforce org alias")
    parser.add_argument("--input", help="Path to JSON input file")
    parser.add_argument("--input-json", help="Inline JSON string for input")
    parser.add_argument("--dr-dir", help="Path to the DR component directory (auto-reads SampleInput and type)")
    parser.add_argument("--schema", choices=["managed", "native", "auto"], default="auto")
    parser.add_argument("--output", help="Save response to this file")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Detect schema
    schema = args.schema
    if schema == "auto":
        detected = detect_schema_from_dir(args.dr_dir)
        schema = detected or "managed"
        print(f"Schema: {schema} (auto-detected{' from DataPack' if detected else ', defaulting to managed'})")
    else:
        print(f"Schema: {schema}")

    # Detect DR type
    dr_type = args.dr_type
    if not dr_type:
        dr_type = detect_dr_type_from_dir(args.dr_dir) if args.dr_dir else "Extract"
        print(f"DR Type: {dr_type} (auto-detected)")
    else:
        print(f"DR Type: {dr_type}")

    # Load input
    input_data = {}
    if args.input:
        with open(args.input, encoding="utf-8") as f:
            loaded = json.load(f)
            input_data = loaded.get("input", loaded) if isinstance(loaded, dict) else loaded
    elif args.input_json:
        input_data = json.loads(args.input_json)
    elif args.dr_dir:
        input_data = load_sample_input_from_dir(args.dr_dir, args.dr_name)
    else:
        print("WARNING: No input provided. Using empty input.")

    # Authenticate
    print(f"\nAuthenticating...")
    instance_url, access_token = get_org_info(args.org)
    print(f"  Instance: {instance_url}")

    # Invoke
    print(f"\nInvoking DataRaptor: {args.dr_name} ({dr_type})")
    response, status, elapsed = invoke_dr(instance_url, access_token, args.dr_name, dr_type, input_data, schema, args.verbose)

    status_icon = "✓" if status in (200, 201) else "✗"
    print(f"\n  [{status_icon}] HTTP {status} — {elapsed}ms")
    print("\n--- Response ---")
    print(json.dumps(response, indent=2, default=str))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(response, f, indent=2, default=str)
        print(f"\n[Saved to: {args.output}]")

    if status not in (200, 201):
        sys.exit(1)

if __name__ == "__main__":
    main()
