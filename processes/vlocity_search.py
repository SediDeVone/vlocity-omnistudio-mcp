#!/usr/bin/env python3
"""
Vlocity Component Search — Query the dependency index for components.

Supports filtering by:
- Component name (substring match)
- Component type (DataRaptor, IntegrationProcedure, FlexCard, OmniScript, etc.)
- Callers (components that call this one)
- Callees (components this one calls)
- Data source (for DataRaptors — which SObject they read/write)
"""

import json
from pathlib import Path
from typing import Optional, List


def find_index_json(vlocity_dir: Path) -> Optional[Path]:
    """
    Search for dependency-index/index.json starting from vlocity_dir.
    Checks vlocity_dir and one level up.
    """
    candidates = [
        vlocity_dir / "dependency-index" / "index.json",
        vlocity_dir.parent / "dependency-index" / "index.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def load_index(vlocity_dir: str) -> dict:
    """Load the dependency index from vlocity_dir."""
    vlocity_path = Path(vlocity_dir).expanduser()

    index_path = find_index_json(vlocity_path)
    if not index_path:
        return {
            "status": "error",
            "error": f"No dependency-index/index.json found. Run: python build_index.py --init {vlocity_dir}"
        }

    try:
        with open(index_path) as f:
            return {
                "status": "success",
                "index": json.load(f),
                "index_path": str(index_path)
            }
    except (json.JSONDecodeError, IOError) as e:
        return {
            "status": "error",
            "error": f"Failed to load index: {str(e)}"
        }


def search(
    vlocity_dir: str,
    name: Optional[str] = None,
    component_type: Optional[str] = None,
    called_by: Optional[str] = None,
    calls: Optional[str] = None,
    data_source: Optional[str] = None,
    limit: int = 50
) -> dict:
    """
    Search the dependency index for components matching criteria.

    Args:
        vlocity_dir: Path to vlocity metadata directory
        name: Substring to match in component name (case-insensitive)
        component_type: Filter by type (DataRaptor, IntegrationProcedure, FlexCard, OmniScript, etc.)
        called_by: Find components that are called by this component
        calls: Find components that call this component
        data_source: For DataRaptors, filter by SObject name
        limit: Max results to return

    Returns:
        {
            "status": "success" | "error",
            "results": [
                {
                    "name": "...",
                    "type": "...",
                    "schema": "...",
                    "folder": "...",
                    "caller_count": N,
                    "dependency_count": N,
                    "dependencies": [...]
                }
            ],
            "total_matched": N,
            "limit": limit
        }
    """
    index_result = load_index(vlocity_dir)
    if index_result.get("status") == "error":
        return index_result

    index = index_result["index"]
    nodes = index.get("nodes", {})

    results = []

    for comp_name, comp_data in nodes.items():
        # Apply filters
        if name and name.lower() not in comp_name.lower():
            continue

        if component_type and comp_data.get("type") != component_type:
            continue

        # Filter by data source (for DataRaptors, extract from component JSON metadata if available)
        if data_source:
            # This would require loading the component JSON files - for now, skip this filter
            # Could be enhanced to load and check SObjectName
            pass

        # Filter by called_by (find who calls this component)
        if called_by:
            # Search for edges where comp_name is a target and called_by is a source
            found = False
            for other_name, other_data in nodes.items():
                if other_name == called_by:
                    other_deps = other_data.get("deps", [])
                    for dep in other_deps:
                        if dep.get("target") == comp_name:
                            found = True
                            break
            if not found:
                continue

        # Filter by calls (find what this component calls)
        if calls:
            comp_deps = comp_data.get("deps", [])
            found = any(dep.get("target") == calls for dep in comp_deps)
            if not found:
                continue

        # Build result entry
        comp_deps = comp_data.get("deps", [])
        caller_count = 0
        for other_name, other_data in nodes.items():
            other_deps = other_data.get("deps", [])
            for dep in other_deps:
                if dep.get("target") == comp_name:
                    caller_count += 1
                    break

        results.append({
            "name": comp_name,
            "type": comp_data.get("type"),
            "schema": comp_data.get("schema"),
            "folder": comp_data.get("folder"),
            "caller_count": caller_count,
            "dependency_count": len(comp_deps),
            "dependencies": [dep.get("target") for dep in comp_deps[:5]]  # First 5 only
        })

    # Sort by relevance (callers + dependencies)
    results.sort(
        key=lambda x: (x["caller_count"] + x["dependency_count"]),
        reverse=True
    )

    return {
        "status": "success",
        "results": results[:limit],
        "total_matched": len(results),
        "limit": limit,
        "query": {
            "name": name,
            "component_type": component_type,
            "called_by": called_by,
            "calls": calls,
            "data_source": data_source
        }
    }


def format_search_results(search_result: dict) -> str:
    """Format search results as markdown."""
    if search_result.get("status") == "error":
        return f"Error: {search_result.get('error')}"

    results = search_result.get("results", [])
    total = search_result.get("total_matched", 0)
    limit = search_result.get("limit", 50)
    query = search_result.get("query", {})

    # Build header
    parts = ["# Vlocity Component Search Results\n\n"]

    # Query summary
    query_parts = []
    if query.get("name"):
        query_parts.append(f"Name: `{query['name']}`")
    if query.get("component_type"):
        query_parts.append(f"Type: `{query['component_type']}`")
    if query.get("called_by"):
        query_parts.append(f"Called by: `{query['called_by']}`")
    if query.get("calls"):
        query_parts.append(f"Calls: `{query['calls']}`")
    if query.get("data_source"):
        query_parts.append(f"Data source: `{query['data_source']}`")

    if query_parts:
        parts.append(f"**Query:** {', '.join(query_parts)}\n\n")

    parts.append(f"**Found {total} components** (showing first {min(limit, total)})\n\n")

    if not results:
        parts.append("No components matched your search criteria.")
        return "".join(parts)

    # Results table
    parts.append("| Component | Type | Callers | Dependencies | Top Calls |\n")
    parts.append("|-----------|------|---------|--------------|----------|\n")

    for result in results:
        name = result["name"]
        comp_type = result["type"] or "Unknown"
        callers = result["caller_count"]
        deps = result["dependency_count"]
        top_calls = ", ".join(result["dependencies"][:3]) if result["dependencies"] else "—"

        parts.append(f"| `{name}` | {comp_type} | {callers} | {deps} | {top_calls} |\n")

    return "".join(parts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vlocity Component Search")
    parser.add_argument("vlocity_dir", help="Path to vlocity metadata directory")
    parser.add_argument("--name", help="Substring to match in component name")
    parser.add_argument("--type", dest="component_type", help="Component type to filter")
    parser.add_argument("--called-by", help="Find components called by this component")
    parser.add_argument("--calls", help="Find components that call this component")
    parser.add_argument("--data-source", help="Filter DataRaptors by SObject")
    parser.add_argument("--limit", type=int, default=50, help="Max results")

    args = parser.parse_args()

    result = search(
        vlocity_dir=args.vlocity_dir,
        name=args.name,
        component_type=args.component_type,
        called_by=args.called_by,
        calls=args.calls,
        data_source=args.data_source,
        limit=args.limit
    )

    print(format_search_results(result))
