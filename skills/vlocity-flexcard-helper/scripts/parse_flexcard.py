#!/usr/bin/env python3
"""
parse_flexcard.py — Vlocity FlexCard JSON parser

Parses a FlexCard .json file (DataPack export format) and outputs a
human-readable summary of its structure: data source, states, components,
events, and CSS.

Usage:
    python parse_flexcard.py <flexcard_json_path> [--format text|json] [--state <index>]

Examples:
    python parse_flexcard.py salesProductCard.json
    python parse_flexcard.py salesProductCard.json --state 0
    python parse_flexcard.py salesProductCard.json --format json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get(obj: dict, *keys, default=None):
    """Safely traverse nested dict keys."""
    for key in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(key, default)
        if obj is None:
            return default
    return obj


def _truncate(text: str, max_len: int = 80) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


# ---------------------------------------------------------------------------
# Top-level metadata
# ---------------------------------------------------------------------------

def extract_metadata(data: dict) -> dict:
    """Extract top-level card metadata."""
    return {
        "name": data.get("Name", data.get("name", "<unknown>")),
        "version": data.get("Version__c", data.get("version", None)),
        "isFlex": data.get("IsFlex__c", data.get("isFlex", False)),
        "isRepeatable": data.get("IsRepeatable__c", data.get("isRepeatable", False)),
        "enableLwc": data.get("EnableLWC__c", data.get("enableLwc", False)),
        "author": data.get("Author__c", data.get("author", None)),
        "description": data.get("Description__c", data.get("description", None)),
        "active": data.get("Active__c", data.get("active", None)),
    }


# ---------------------------------------------------------------------------
# Data source
# ---------------------------------------------------------------------------

def extract_data_source(data: dict) -> dict:
    """Extract data source configuration."""
    # DataPack exports may nest the card definition under 'records' or directly
    card_def_raw = (
        data.get("Definition__c")
        or data.get("definition")
        or data.get("cardJson")
        or "{}"
    )
    if isinstance(card_def_raw, str):
        try:
            card_def = json.loads(card_def_raw)
        except json.JSONDecodeError:
            card_def = {}
    else:
        card_def = card_def_raw

    ds = card_def.get("dataSource", {})
    if not ds:
        # Try top-level for already-expanded exports
        ds = data.get("dataSource", {})

    result = {
        "type": ds.get("type", "<none>"),
    }

    ds_type = result["type"]
    if ds_type == "IntegrationProcedure":
        result["integrationProcedureKey"] = ds.get("integrationProcedureKey") or ds.get("ipKey")
        result["integrationProcedureType"] = ds.get("integrationProcedureType")
    elif ds_type == "DataRaptor":
        result["dataRaptorName"] = ds.get("name") or ds.get("dataRaptorName")
        result["dataRaptorBundleType"] = ds.get("dataRaptorBundleType")
        result["objectName"] = ds.get("objectName")
    elif ds_type == "SObject":
        result["query"] = ds.get("query") or ds.get("soqlQuery")
        result["objectName"] = ds.get("objectName")
    elif ds_type == "Custom":
        result["customJS"] = _truncate(str(ds.get("customJS", "")), 120)

    result["refreshMode"] = ds.get("refreshMode")
    result["contextAware"] = ds.get("contextAware")

    # Store full card definition for later use
    result["_card_def"] = card_def
    return result


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def extract_events(card_def: dict) -> list:
    """Extract pub/sub and click events."""
    events_raw = card_def.get("events", [])
    events = []
    for ev in events_raw:
        entry = {
            "name": ev.get("name"),
            "type": ev.get("type"),
            "action": ev.get("action"),
            "actionType": ev.get("actionType"),
        }
        if ev.get("stateAction"):
            entry["stateAction"] = ev["stateAction"]
        events.append(entry)
    return events


# ---------------------------------------------------------------------------
# Component tree
# ---------------------------------------------------------------------------

def _parse_element(el: Any, indent: int = 0) -> list:
    """Recursively parse component tree elements."""
    lines = []
    prefix = "  " * indent

    if isinstance(el, dict):
        el_type = el.get("element") or el.get("type") or "unknown"
        el_name = el.get("name") or el.get("key") or ""
        label = el.get("property", {}).get("label") if isinstance(el.get("property"), dict) else el.get("label", "")
        merge_field = el.get("property", {}).get("mergeField") if isinstance(el.get("property"), dict) else ""
        size = el.get("size")
        actions = el.get("actions", [])
        conditional = el.get("show") or el.get("conditionalVisibility") or el.get("filter")

        summary = f"{prefix}[{el_type}]"
        if el_name:
            summary += f" name='{el_name}'"
        if label:
            summary += f" label='{_truncate(str(label), 40)}'"
        if merge_field:
            summary += f" mergeField='{_truncate(str(merge_field), 50)}'"
        if size:
            summary += f" size={size}"
        if conditional:
            summary += f" ⚠ conditional"
        if actions:
            summary += f" [actions: {len(actions)}]"
        lines.append(summary)

        # Recurse into children
        children = el.get("children") or el.get("components") or []
        if isinstance(children, list):
            for child in children:
                lines.extend(_parse_element(child, indent + 1))
        elif isinstance(children, dict):
            # layer-0 structure
            for layer_key, layer_val in children.items():
                lines.append(f"{prefix}  <{layer_key}>")
                layer_children = layer_val.get("children", []) if isinstance(layer_val, dict) else layer_val
                for child in (layer_children if isinstance(layer_children, list) else []):
                    lines.extend(_parse_element(child, indent + 2))

    elif isinstance(el, list):
        for item in el:
            lines.extend(_parse_element(item, indent))

    return lines


def extract_states(card_def: dict, state_filter: int = None) -> list:
    """Extract and summarize card states."""
    states_raw = card_def.get("states", [])
    states = []

    for i, state in enumerate(states_raw):
        if state_filter is not None and i != state_filter:
            continue

        state_name = state.get("name") or state.get("label") or f"State {i}"
        state_filter_cond = state.get("filter") or state.get("conditionalFilter")
        actions = state.get("actions", [])
        child_cards = state.get("childCards", []) or []

        # Component tree — may be under 'components' dict with layer keys
        components_raw = state.get("components", {})
        component_lines = []
        if isinstance(components_raw, dict):
            for layer_key, layer_val in components_raw.items():
                component_lines.append(f"  <{layer_key}>")
                layer_children = (
                    layer_val.get("children", [])
                    if isinstance(layer_val, dict)
                    else layer_val
                )
                for child in (layer_children if isinstance(layer_children, list) else []):
                    component_lines.extend(_parse_element(child, indent=2))
        elif isinstance(components_raw, list):
            for comp in components_raw:
                component_lines.extend(_parse_element(comp, indent=1))

        state_summary = {
            "index": i,
            "name": state_name,
            "filter": state_filter_cond,
            "componentTree": component_lines,
            "actions": [
                {
                    "type": a.get("actionType") or a.get("type"),
                    "name": a.get("name"),
                }
                for a in (actions if isinstance(actions, list) else [])
            ],
            "childCards": child_cards,
        }
        states.append(state_summary)

    return states


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

def extract_css(card_def: dict, data: dict) -> dict:
    """Summarize CSS information."""
    css_text = (
        card_def.get("customCSS")
        or card_def.get("css")
        or data.get("CSS__c")
        or ""
    )
    if not css_text:
        return {"hasCustomCSS": False}

    lines = css_text.strip().split("\n")
    selectors = [l.strip() for l in lines if "{" in l and not l.strip().startswith("//")]
    return {
        "hasCustomCSS": True,
        "lineCount": len(lines),
        "selectorCount": len(selectors),
        "selectors": selectors[:10],  # first 10 selectors
        "globalCSS": card_def.get("globalCSS", False),
    }


# ---------------------------------------------------------------------------
# Full parse
# ---------------------------------------------------------------------------

def parse_flexcard(path: str, state_filter: int = None) -> dict:
    """Main parse function. Returns a structured summary dict."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(p, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # DataPack exports sometimes wrap data under 'VlocityCard__c' records
    # Try to unwrap if needed
    data = raw
    if "VlocityDataPackData" in raw:
        records = _safe_get(raw, "VlocityDataPackData", "VlocityCard__c", default=[])
        if records:
            data = records[0]
    elif isinstance(raw, list) and len(raw) > 0:
        data = raw[0]

    metadata = extract_metadata(data)
    ds_info = extract_data_source(data)
    card_def = ds_info.pop("_card_def", {})

    # If card definition was not nested, try to parse the whole data as the card def
    if not card_def:
        card_def = data

    events = extract_events(card_def)
    states = extract_states(card_def, state_filter=state_filter)
    css = extract_css(card_def, data)

    return {
        "metadata": metadata,
        "dataSource": ds_info,
        "events": events,
        "states": states,
        "css": css,
        "stateCount": len(card_def.get("states", [])),
        "filePath": str(p.resolve()),
    }


# ---------------------------------------------------------------------------
# Text formatter
# ---------------------------------------------------------------------------

def format_text(summary: dict, state_filter: int = None) -> str:
    lines = []
    sep = "=" * 70
    thin = "-" * 50

    # Header
    lines.append(sep)
    lines.append("FLEXCARD SUMMARY")
    lines.append(sep)

    meta = summary["metadata"]
    lines.append(f"  Name        : {meta['name']}")
    lines.append(f"  Version     : {meta.get('version', 'N/A')}")
    lines.append(f"  Type        : {'Flex' if meta['isFlex'] else 'Legacy Vlocity Card'}")
    lines.append(f"  Repeatable  : {meta['isRepeatable']}")
    lines.append(f"  LWC Mode    : {meta['enableLwc']}")
    lines.append(f"  Active      : {meta.get('active', 'N/A')}")
    if meta.get("description"):
        lines.append(f"  Description : {_truncate(meta['description'], 80)}")
    lines.append("")

    # Data source
    lines.append(thin)
    lines.append("DATA SOURCE")
    lines.append(thin)
    ds = summary["dataSource"]
    for k, v in ds.items():
        if v is not None:
            lines.append(f"  {k:30s}: {v}")
    lines.append("")

    # Events
    lines.append(thin)
    lines.append(f"EVENTS ({len(summary['events'])})")
    lines.append(thin)
    if summary["events"]:
        for ev in summary["events"]:
            lines.append(
                f"  [{ev.get('type', '?')}] {ev.get('name', '')} → action={ev.get('actionType') or ev.get('action', '')}"
            )
    else:
        lines.append("  (none)")
    lines.append("")

    # States
    total_states = summary["stateCount"]
    shown_states = len(summary["states"])
    heading = f"STATES (showing {shown_states}/{total_states})"
    if state_filter is not None:
        heading += f"  [filter: state {state_filter}]"
    lines.append(thin)
    lines.append(heading)
    lines.append(thin)

    for state in summary["states"]:
        lines.append(f"\n  ► State {state['index']}: {state['name']}")
        if state["filter"]:
            lines.append(f"    Condition : {_truncate(str(state['filter']), 70)}")
        if state["componentTree"]:
            lines.append("    Components:")
            for cl in state["componentTree"]:
                lines.append(f"      {cl}")
        else:
            lines.append("    Components: (empty)")
        if state["actions"]:
            lines.append("    Actions:")
            for a in state["actions"]:
                lines.append(f"      - [{a.get('type', '?')}] {a.get('name', '')}")
        if state["childCards"]:
            lines.append(f"    Child Cards: {state['childCards']}")
    lines.append("")

    # CSS
    lines.append(thin)
    lines.append("CSS")
    lines.append(thin)
    css = summary["css"]
    if css["hasCustomCSS"]:
        lines.append(f"  Custom CSS  : Yes ({css['lineCount']} lines, {css['selectorCount']} selectors)")
        lines.append(f"  Global CSS  : {css.get('globalCSS', False)}")
        if css.get("selectors"):
            lines.append("  Top selectors:")
            for sel in css["selectors"]:
                lines.append(f"    {sel}")
    else:
        lines.append("  Custom CSS  : None")
    lines.append("")
    lines.append(sep)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Parse a Vlocity FlexCard JSON file and print a human-readable summary."
    )
    parser.add_argument("flexcard_json_path", help="Path to the FlexCard .json file")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--state",
        type=int,
        default=None,
        metavar="INDEX",
        help="Show only the specified state by index (0-based)",
    )

    args = parser.parse_args()

    try:
        summary = parse_flexcard(args.flexcard_json_path, state_filter=args.state)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON — {e}", file=sys.stderr)
        sys.exit(1)

    if args.format == "json":
        # Remove internal helpers before printing
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(format_text(summary, state_filter=args.state))


if __name__ == "__main__":
    main()
