#!/usr/bin/env python3
"""
Vlocity Example Retrieval — Find real-world component examples.

Two sources:
1. Local vlocity_dir: Raw (un-anonymized) components from authorized project
2. Central knowledge_base: Anonymized examples safe for any context

Fallback chain: local first (if vlocity_dir available) → KB fallback
"""

import json
from pathlib import Path
from typing import Optional, List, Dict


def find_examples_local(
    vlocity_dir: str,
    component_type: str,
    subtype: Optional[str] = None,
    name_hint: Optional[str] = None,
    limit: int = 3
) -> Dict:
    """
    Find raw (un-anonymized) component examples from authorized vlocity_dir.

    Args:
        vlocity_dir: Path to vlocity metadata directory
        component_type: 'DataRaptor' | 'IntegrationProcedure' | 'FlexCard' | 'OmniScript'
        subtype: For DataRaptor: 'Extract' | 'Load' | 'Transform'
        name_hint: Filter by name substring (case-insensitive)
        limit: Max examples to return

    Returns:
        {
            "status": "success" | "error",
            "source": "local",
            "examples": [
                {
                    "name": "...",
                    "component": {...},  # Raw JSON (may be large, trimmed for context)
                    "caller_count": N
                }
            ]
        }
    """
    vlocity_path = Path(vlocity_dir).expanduser()

    # Load dependency index to find components by type and caller count
    index_path = vlocity_path / "dependency-index" / "index.json"
    if not index_path.exists():
        return {
            "status": "error",
            "error": f"No index found at {index_path}"
        }

    try:
        with open(index_path) as f:
            index = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return {
            "status": "error",
            "error": f"Failed to load index: {str(e)}"
        }

    nodes = index.get("nodes", {})

    # Filter by type
    candidates = []
    for comp_name, comp_data in nodes.items():
        if comp_data.get("type") != component_type:
            continue

        if subtype and comp_data.get("subtype") != subtype:
            continue

        if name_hint and name_hint.lower() not in comp_name.lower():
            continue

        # Count callers
        caller_count = 0
        for other_name, other_data in nodes.items():
            other_deps = other_data.get("deps", [])
            for dep in other_deps:
                if dep.get("target") == comp_name:
                    caller_count += 1
                    break

        candidates.append({
            "name": comp_name,
            "folder": comp_data.get("folder"),
            "caller_count": caller_count
        })

    if not candidates:
        return {
            "status": "success",
            "source": "local",
            "examples": [],
            "message": "No matching components in local vlocity_dir"
        }

    # Sort by caller count (most used first)
    candidates.sort(key=lambda x: -x["caller_count"])

    # Load actual component JSON
    examples = []
    for cand in candidates[:limit]:
        datapack_path = vlocity_path / cand["folder"] / "_DataPack.json"
        if not datapack_path.exists():
            continue

        try:
            with open(datapack_path) as f:
                raw_json = json.load(f)
            examples.append({
                "name": cand["name"],
                "component": trim_component_for_context(raw_json, component_type),
                "caller_count": cand["caller_count"]
            })
        except (json.JSONDecodeError, IOError):
            continue

    return {
        "status": "success",
        "source": "local",
        "examples": examples,
        "count": len(examples)
    }


def find_examples_central(
    knowledge_base_dir: str,
    component_type: str,
    subtype: Optional[str] = None,
    name_hint: Optional[str] = None,
    limit: int = 3
) -> Dict:
    """
    Find anonymized component examples from central knowledge base.

    Args:
        knowledge_base_dir: Path to knowledge-base/
        component_type: 'DataRaptor' | 'IntegrationProcedure' | 'FlexCard' | 'OmniScript'
        subtype: For DataRaptor: 'Extract' | 'Load' | 'Transform'
        name_hint: Filter by name substring (case-insensitive)
        limit: Max examples to return

    Returns:
        {
            "status": "success" | "error",
            "source": "central",
            "examples": [
                {
                    "name": "...",
                    "component": {...},  # Anonymized JSON
                    "metadata": {
                        "caller_count": N,
                        "sobject_count": N,
                        "field_count": N
                    }
                }
            ]
        }
    """
    kb_path = Path(knowledge_base_dir).expanduser()

    if not kb_path.exists():
        return {
            "status": "error",
            "error": f"Knowledge base not found at {kb_path}"
        }

    # Determine examples directory
    if subtype:
        examples_dir = kb_path / component_type / subtype / "examples"
    else:
        examples_dir = kb_path / component_type / "examples"

    if not examples_dir.exists():
        return {
            "status": "success",
            "source": "central",
            "examples": [],
            "message": f"No examples found for {component_type}" + (f" {subtype}" if subtype else "")
        }

    # Load all example files
    example_files = sorted(examples_dir.glob("*.json"))

    # Filter by name hint
    if name_hint:
        example_files = [
            f for f in example_files
            if name_hint.lower() in f.stem.lower() and not f.name.endswith(".meta.json")
        ]

    # Load and sort by caller count
    loaded = []
    for example_file in example_files:
        if example_file.name.endswith(".meta.json") or example_file.name.endswith(".mapping.json"):
            continue

        try:
            with open(example_file) as f:
                component_json = json.load(f)

            # Load metadata if available
            meta_file = example_file.parent / f"{example_file.stem}.meta.json"
            metadata = {}
            if meta_file.exists():
                with open(meta_file) as f:
                    metadata = json.load(f)

            loaded.append({
                "name": example_file.stem,
                "component": component_json,
                "metadata": metadata,
                "caller_count": metadata.get("caller_count", 0)
            })
        except (json.JSONDecodeError, IOError):
            continue

    loaded.sort(key=lambda x: -x["caller_count"])

    examples = [
        {
            "name": item["name"],
            "component": trim_component_for_context(item["component"], component_type),
            "metadata": item["metadata"]
        }
        for item in loaded[:limit]
    ]

    return {
        "status": "success",
        "source": "central",
        "examples": examples,
        "count": len(examples)
    }


def find_examples(
    vlocity_dir: Optional[str] = None,
    knowledge_base_dir: Optional[str] = None,
    component_type: Optional[str] = None,
    subtype: Optional[str] = None,
    name_hint: Optional[str] = None,
    limit: int = 3
) -> Dict:
    """
    Find examples with fallback: local first → KB second.

    Priority:
    1. If vlocity_dir is provided and index exists, use local (authorized access)
    2. Otherwise, fall back to central knowledge base
    """
    # Try local first
    if vlocity_dir:
        result = find_examples_local(vlocity_dir, component_type, subtype, name_hint, limit)
        if result.get("status") == "success" and result.get("examples"):
            return result

    # Fall back to central KB
    if knowledge_base_dir:
        return find_examples_central(knowledge_base_dir, component_type, subtype, name_hint, limit)

    return {
        "status": "error",
        "error": "No vlocity_dir or knowledge_base_dir provided"
    }


def trim_component_for_context(component_json: dict, component_type: str) -> dict:
    """
    Trim a component JSON to context-relevant fields for schema examples.

    Includes: structure, element types, field references, naming
    Excludes: large arrays, inline documentation, metadata bloat
    """
    trimmed = {}

    # Copy essential structure fields
    keep_keys = {
        # Universal
        "DeveloperName", "Name", "Label", "Type",

        # DataRaptor
        "InputType", "OutputType", "InterfaceObject", "SObjectName",
        "ProcessType", "IsActive", "DRVersion",

        # IP
        "IntegrationProcedureElement", "InteractionMode", "ChainOnStep",

        # FlexCard
        "States", "Namespace", "Definition",

        # OmniScript
        "DomainObject", "OmniScript_Element_1", "DomniScript_Element"
    }

    for key, value in component_json.items():
        if key in keep_keys:
            trimmed[key] = value

    # For IP/OmniScript, include element structure (first 5 elements max)
    if component_type in ["IntegrationProcedure", "OmniScript"]:
        elements = []
        for key in sorted(component_json.keys()):
            if "Element" in key and isinstance(component_json[key], dict):
                elements.append(component_json[key])
                if len(elements) >= 5:
                    break
        if elements:
            trimmed["_sample_elements"] = elements

    # For FlexCard, include state definitions (first 2)
    if component_type == "FlexCard":
        if "States" in component_json:
            trimmed["States"] = component_json["States"][:2] if isinstance(component_json["States"], list) else component_json["States"]

    return trimmed


def format_examples_as_markdown(examples_result: Dict) -> str:
    """Format example retrieval result as markdown for Claude."""
    if examples_result.get("status") == "error":
        return f"❌ Error: {examples_result.get('error')}"

    examples = examples_result.get("examples", [])
    source = examples_result.get("source", "unknown")

    parts = [f"# Real-World Examples ({source})\n\n"]

    if not examples:
        parts.append(examples_result.get("message", "No examples found"))
        return "".join(parts)

    for i, example in enumerate(examples, 1):
        parts.append(f"## Example {i}: {example.get('name')}\n\n")

        # Metadata
        metadata = example.get("metadata", {})
        if metadata:
            parts.append("**Metadata:**\n")
            if metadata.get("caller_count"):
                parts.append(f"- Used by {metadata['caller_count']} other components\n")
            if metadata.get("sobject_count"):
                parts.append(f"- Operates on {metadata['sobject_count']} custom objects\n")
            if metadata.get("field_count"):
                parts.append(f"- Uses {metadata['field_count']} custom fields\n")
            parts.append("\n")

        # Component structure
        component = example.get("component", {})
        if component:
            parts.append("**Structure:**\n")
            parts.append("```json\n")
            parts.append(json.dumps(component, indent=2)[:1500])  # Truncate to 1500 chars
            if len(json.dumps(component)) > 1500:
                parts.append("\n... (truncated)")
            parts.append("\n```\n\n")

    return "".join(parts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Find OmniStudio component examples")
    parser.add_argument("component_type", help="DataRaptor | IntegrationProcedure | FlexCard | OmniScript")
    parser.add_argument("--vlocity-dir", help="Local vlocity directory (for authorized access)")
    parser.add_argument("--knowledge-base", help="Central knowledge base directory")
    parser.add_argument("--subtype", help="For DataRaptor: Extract | Load | Transform")
    parser.add_argument("--name", help="Filter by name substring")
    parser.add_argument("--limit", type=int, default=3, help="Max examples")

    args = parser.parse_args()

    result = find_examples(
        vlocity_dir=args.vlocity_dir,
        knowledge_base_dir=args.knowledge_base,
        component_type=args.component_type,
        subtype=args.subtype,
        name_hint=args.name,
        limit=args.limit
    )

    print(format_examples_as_markdown(result))
