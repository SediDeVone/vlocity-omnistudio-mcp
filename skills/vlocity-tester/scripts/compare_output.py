#!/usr/bin/env python3
"""
compare_output.py — Compare actual vs. expected JSON output from a Vlocity DR or IP invocation.

Reports field-level differences: added keys, removed keys, and changed values.
Supports ignoring specific JSON paths (for timestamps, volatile IDs, etc.)

Usage:
  python compare_output.py --actual <file> --expected <file>
  python compare_output.py --actual <file> --expected <file> --ignore-paths result.CreatedDate --fuzzy-ids
"""
import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

# Salesforce ID pattern (15 or 18 chars)
SF_ID_PATTERN = re.compile(r'\b([a-zA-Z0-9]{15}|[a-zA-Z0-9]{18})\b')

# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def normalize_ids(value: str) -> str:
    """Replace Salesforce IDs with a placeholder for fuzzy comparison."""
    return SF_ID_PATTERN.sub("<SF_ID>", value)

def get_at_path(data: Any, path: str) -> Any:
    """Navigate a dot-separated path in nested dicts/lists."""
    parts = path.split(".")
    current = data
    for part in parts:
        if current is None:
            return None
        if part.isdigit() and isinstance(current, list):
            idx = int(part)
            current = current[idx] if idx < len(current) else None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current

def should_ignore(path: str, ignore_paths: List[str]) -> bool:
    """Check if this path should be ignored."""
    for ignore in ignore_paths:
        if path == ignore or path.startswith(ignore + ".") or path.startswith(ignore + "["):
            return True
    return False

# ─────────────────────────────────────────────────────────────────────────────
# DIFF ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def diff_values(actual: Any, expected: Any, path: str, ignore_paths: List[str],
                fuzzy_ids: bool, diffs: List[Dict]):
    """Recursively compare two values and collect differences."""
    if should_ignore(path, ignore_paths):
        return

    if type(actual) != type(expected):
        # Allow None vs missing
        if actual is None and expected is None:
            return
        diffs.append({
            "path": path,
            "type": "type_mismatch",
            "actual": type(actual).__name__,
            "expected": type(expected).__name__,
            "actual_value": actual,
            "expected_value": expected,
        })
        return

    if isinstance(actual, dict):
        all_keys = set(actual.keys()) | set(expected.keys())
        for key in sorted(all_keys):
            child_path = f"{path}.{key}" if path else key
            if key not in actual:
                if not should_ignore(child_path, ignore_paths):
                    diffs.append({"path": child_path, "type": "removed", "expected_value": expected[key]})
            elif key not in expected:
                if not should_ignore(child_path, ignore_paths):
                    diffs.append({"path": child_path, "type": "added", "actual_value": actual[key]})
            else:
                diff_values(actual[key], expected[key], child_path, ignore_paths, fuzzy_ids, diffs)

    elif isinstance(actual, list):
        if len(actual) != len(expected):
            if not should_ignore(path, ignore_paths):
                diffs.append({
                    "path": path,
                    "type": "length_mismatch",
                    "actual_length": len(actual),
                    "expected_length": len(expected),
                })
        for i, (a, e) in enumerate(zip(actual, expected)):
            diff_values(a, e, f"{path}[{i}]", ignore_paths, fuzzy_ids, diffs)

    elif isinstance(actual, str):
        a_val = normalize_ids(actual) if fuzzy_ids else actual
        e_val = normalize_ids(expected) if fuzzy_ids else expected
        if a_val != e_val:
            diffs.append({
                "path": path,
                "type": "changed",
                "actual_value": actual,
                "expected_value": expected,
            })

    else:
        if actual != expected:
            diffs.append({
                "path": path,
                "type": "changed",
                "actual_value": actual,
                "expected_value": expected,
            })

# ─────────────────────────────────────────────────────────────────────────────
# REPORTING
# ─────────────────────────────────────────────────────────────────────────────

def format_text_report(diffs: List[Dict], actual_file: str, expected_file: str) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append(f"Vlocity Output Comparison")
    lines.append(f"  Actual:   {actual_file}")
    lines.append(f"  Expected: {expected_file}")
    lines.append("=" * 60)

    if not diffs:
        lines.append("\n✓ MATCH — No differences found.")
        return "\n".join(lines)

    lines.append(f"\n✗ DIFFERENCES FOUND: {len(diffs)}\n")

    added = [d for d in diffs if d["type"] == "added"]
    removed = [d for d in diffs if d["type"] == "removed"]
    changed = [d for d in diffs if d["type"] == "changed"]
    other = [d for d in diffs if d["type"] not in ("added", "removed", "changed")]

    if added:
        lines.append(f"--- ADDED in actual ({len(added)}) ---")
        for d in added:
            val = json.dumps(d.get("actual_value"), default=str)
            lines.append(f"  + {d['path']}: {val[:120]}")

    if removed:
        lines.append(f"\n--- REMOVED from actual ({len(removed)}) ---")
        for d in removed:
            val = json.dumps(d.get("expected_value"), default=str)
            lines.append(f"  - {d['path']}: {val[:120]}")

    if changed:
        lines.append(f"\n--- CHANGED ({len(changed)}) ---")
        for d in changed:
            actual_val = json.dumps(d.get("actual_value"), default=str)
            expected_val = json.dumps(d.get("expected_value"), default=str)
            lines.append(f"  ~ {d['path']}")
            lines.append(f"    actual:   {actual_val[:100]}")
            lines.append(f"    expected: {expected_val[:100]}")

    if other:
        lines.append(f"\n--- OTHER ISSUES ({len(other)}) ---")
        for d in other:
            lines.append(f"  ! {d['path']} [{d['type']}]: {d}")

    return "\n".join(lines)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Compare actual vs expected Vlocity output JSON")
    parser.add_argument("--actual", required=True, help="Path to actual output JSON file")
    parser.add_argument("--expected", required=True, help="Path to expected/baseline JSON file")
    parser.add_argument("--ignore-paths", nargs="+", default=[],
                        help="Dot-separated JSON paths to ignore e.g. result.CreatedDate result.Id")
    parser.add_argument("--fuzzy-ids", action="store_true",
                        help="Normalize Salesforce IDs before comparing")
    parser.add_argument("--output-format", choices=["text", "json"], default="text")
    parser.add_argument("--output", help="Save report to file instead of stdout")
    args = parser.parse_args()

    # Load files
    for label, path in [("actual", args.actual), ("expected", args.expected)]:
        if not os.path.exists(path):
            print(f"ERROR: {label} file not found: {path}")
            sys.exit(2)

    with open(args.actual, encoding="utf-8") as f:
        actual = json.load(f)
    with open(args.expected, encoding="utf-8") as f:
        expected = json.load(f)

    # Run diff
    diffs = []
    diff_values(actual, expected, "", args.ignore_paths, args.fuzzy_ids, diffs)

    # Format report
    if args.output_format == "json":
        report = json.dumps({"match": len(diffs) == 0, "differences": diffs}, indent=2)
    else:
        report = format_text_report(diffs, args.actual, args.expected)

    # Output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[Report saved to: {args.output}]")
    else:
        print(report)

    # Exit code
    sys.exit(0 if not diffs else 1)

if __name__ == "__main__":
    main()
