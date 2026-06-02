#!/usr/bin/env python3
"""
Knowledge Base Build System — Harvest and anonymize OmniStudio components.

This tool:
1. Harvests real components from authorized vlocity_dir
2. Anonymizes proprietary identifiers (custom SObjects, fields, namespaces)
3. Extracts statistical patterns (usage frequency, common structures)
4. Writes safe anonymized examples + patterns.json to knowledge-base/

Anonymization ensures the repo never contains:
- Custom SObject names (Acme_ServiceCode__c → DomainObject_A)
- Custom field names (customerSIN__c → DomainField_1)
- Project identifiers / namespace prefixes
- Real component names with project context
- Any business logic that could identify the project

But PRESERVES:
- Standard Salesforce objects (Account, Order, Asset)
- Standard Salesforce fields (Id, Name, BillingCity)
- Element types (DataRaptorExtractAction, SetValues, ConditionalBlock)
- Filter operators, structural nesting, execution patterns
- Field reference patterns like %input.X% (with values anonymized)

Mapping tables (*.mapping.json) are gitignored and kept locally for reversal only.
"""

import json
import hashlib
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from collections import defaultdict, Counter


# Standard Salesforce objects and fields (never anonymize these)
STANDARD_SOBJECTS = {
    "Account", "Contact", "Opportunity", "Lead", "Case",
    "Order", "OrderItem", "Quote", "Asset", "Contract",
    "Product2", "PricebookEntry", "User", "Organization",
    "RecordType", "Profile", "PermissionSet", "CustomObject",
    "Attachment", "ContentDocument", "Task", "Event",
    "WorkOrder", "WorkOrderLineItem", "ServiceResource",
    "OperatingHours", "ServiceTerritory"
}

STANDARD_FIELDS = {
    "Id", "Name", "DeveloperName", "Label", "Description",
    "CreatedDate", "CreatedById", "LastModifiedDate", "LastModifiedById",
    "BillingStreet", "BillingCity", "BillingState", "BillingPostalCode",
    "BillingCountry", "ShippingStreet", "ShippingCity", "ShippingState",
    "ShippingPostalCode", "ShippingCountry", "Phone", "Email",
    "Website", "Industry", "Type", "Status", "OwnerId",
    "AccountNumber", "CustomerPriority", "SLA", "SLAExpirationDate",
    "Amount", "Probability", "ExpectedRevenue", "LeadSource",
    "Reason", "StageName", "CloseDate", "NextStep",
    "IsClosed", "IsWon", "RecordTypeId", "SystemModstamp"
}


def is_standard_sobject(name: str) -> bool:
    """Check if this is a standard Salesforce object."""
    if "__c" in name or "__" in name.replace("_", ""):
        return False
    return name in STANDARD_SOBJECTS or name.endswith("_Event") or name.endswith("_History")


def is_standard_field(name: str) -> bool:
    """Check if this is a standard Salesforce field."""
    if "__c" not in name and "__r" not in name:
        return name in STANDARD_FIELDS
    return False


def extract_namespace(name: str) -> Optional[str]:
    """Extract namespace prefix from a name (e.g., vlocity_cmt, custom_ns)."""
    if "__" in name:
        parts = name.split("__")
        if len(parts) > 1:
            return parts[0]
    return None


def anonymize_component(raw_json: dict, component_type: str) -> Tuple[dict, dict]:
    """
    Anonymize a component JSON, replacing proprietary identifiers.

    Returns:
        (anonymized_json, mapping_table)
        mapping_table: {
            "sobjects": {"DomainObject_A": "realname", ...},
            "fields": {"DomainField_1": "realname", ...},
            "components": {"domain_getX": "realname", ...},
            "namespaces": ["original_ns", ...] → all map to <ns>__
        }
    """
    mapping = {"sobjects": {}, "fields": {}, "components": {}, "namespaces": set()}

    def build_mapping_pass(obj, path=""):
        """First pass: collect all custom identifiers and assign stable aliases."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                build_mapping_pass(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for item in obj:
                build_mapping_pass(item, path)
        elif isinstance(obj, str):
            # Check for SObject names in common locations
            if path.endswith("InterfaceObject") or path.endswith("sobject") or "sobject" in path.lower():
                if obj and not is_standard_sobject(obj) and "__c" in obj:
                    if obj not in mapping["sobjects"]:
                        idx = len(mapping["sobjects"]) + 1
                        mapping["sobjects"][obj] = f"DomainObject_{chr(64 + idx)}"  # A, B, C...

            # Check for field names
            if ("field" in path.lower() or "name" in path.lower()) and "__c" in obj:
                if obj not in mapping["fields"]:
                    idx = len(mapping["fields"]) + 1
                    mapping["fields"][obj] = f"DomainField_{idx}"

            # Extract namespace prefixes
            ns = extract_namespace(obj)
            if ns and ns not in ["vlocity", "sfdc"]:
                mapping["namespaces"].add(ns)

    build_mapping_pass(raw_json)

    # Create reverse mapping for substitution
    reverse_sobjects = {v: k for k, v in mapping["sobjects"].items()}
    reverse_fields = {v: k for k, v in mapping["fields"].items()}

    def anonymize_value(value, path=""):
        """Recursively anonymize a value."""
        if isinstance(value, dict):
            return {k: anonymize_value(v, f"{path}.{k}") for k, v in value.items()}
        elif isinstance(value, list):
            return [anonymize_value(item, path) for item in value]
        elif isinstance(value, str):
            if not value:
                return value

            # Replace namespace prefixes
            for ns in mapping["namespaces"]:
                if value.startswith(f"{ns}__"):
                    value = value.replace(f"{ns}__", "<ns>__", 1)

            # Replace custom SObjects
            for real, anon in mapping["sobjects"].items():
                if real in value:
                    value = value.replace(real, anon)

            # Replace custom fields
            for real, anon in mapping["fields"].items():
                if real in value:
                    value = value.replace(real, anon)

            return value
        else:
            return value

    anonymized = anonymize_value(raw_json)

    # Convert set to list for JSON serialization
    mapping["namespaces"] = list(mapping["namespaces"])

    # Invert for the mapping file (real → anon)
    final_mapping = {
        "sobjects": {v: k for k, v in mapping["sobjects"].items()},
        "fields": {v: k for k, v in mapping["fields"].items()},
        "namespaces": mapping["namespaces"]
    }

    return anonymized, final_mapping


def extract_patterns(components: List[dict], component_type: str, subtype: Optional[str] = None) -> dict:
    """
    Extract statistical patterns from anonymized components.

    Returns patterns.json content with usage statistics and common structures.
    """
    if not components:
        return {
            "sample_count": 0,
            "component_type": component_type,
            "subtype": subtype,
            "note": "No components to analyze"
        }

    patterns = {
        "sample_count": len(components),
        "component_type": component_type,
        "subtype": subtype,
    }

    # Collect statistics
    sobject_freq = Counter()
    filter_patterns = defaultdict(int)
    naming_patterns = defaultdict(int)
    bundle_placement = {"pre_transform": 0, "post_transform": 0}

    for comp in components:
        # Count custom vs standard SObjects used
        def count_sobjects(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if "object" in key.lower() and isinstance(value, str):
                        if value and not is_standard_sobject(value):
                            sobject_freq[value] += 1
                    count_sobjects(value)
            elif isinstance(obj, list):
                for item in obj:
                    count_sobjects(item)

        count_sobjects(comp)

        # Analyze naming patterns
        if "DeveloperName" in comp:
            name = comp["DeveloperName"]
            # Classify by pattern
            if "_verb" in name.lower():
                naming_patterns["domain_verbObject"] += 1
            elif name[0].isupper():
                naming_patterns["Domain_VerbObject"] += 1
            else:
                naming_patterns["domain_other"] += 1

        # Check for bundle placement
        if component_type == "DataRaptor" and "ProcessType" in comp:
            if comp.get("ProcessType") == "Pre-Transform":
                bundle_placement["pre_transform"] += 1
            elif comp.get("ProcessType") == "Post-Transform":
                bundle_placement["post_transform"] += 1

    # Compute percentages
    total = sum(bundle_placement.values())
    if total > 0:
        patterns["pre_transform_bundle_pct"] = round(100 * bundle_placement["pre_transform"] / total)
        patterns["post_transform_bundle_pct"] = round(100 * bundle_placement["post_transform"] / total)

    # Top objects
    if sobject_freq:
        patterns["common_sobjects"] = [obj for obj, _ in sobject_freq.most_common(5)]

    # Naming conventions
    if naming_patterns:
        total_named = sum(naming_patterns.values())
        patterns["naming_conventions"] = [
            {
                "pattern": pattern,
                "frequency": round(count / total_named, 2)
            }
            for pattern, count in sorted(naming_patterns.items(), key=lambda x: -x[1])
        ]

    return patterns


def load_vlocity_index(vlocity_dir: Path) -> dict:
    """Load the dependency index from vlocity_dir."""
    index_path = vlocity_dir / "dependency-index" / "index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"No index at {index_path}. Run build_index.py first.")

    with open(index_path) as f:
        return json.load(f)


def harvest(
    vlocity_dir: str,
    project_id: str,
    knowledge_base_dir: str,
    min_caller_count: int = 2,
    max_per_type: int = 10
) -> None:
    """
    Harvest components from vlocity_dir and store anonymized versions in knowledge_base_dir.

    1. Load dependency index
    2. For each component type: select top N by caller_count
    3. Load raw _DataPack.json
    4. Anonymize → write JSON + meta.json + mapping.json (gitignored)
    5. Recompute patterns.json
    """
    vlocity_path = Path(vlocity_dir).expanduser()
    kb_path = Path(knowledge_base_dir).expanduser()

    if not vlocity_path.exists():
        print(f"❌ Vlocity directory not found: {vlocity_path}")
        return

    # Load index
    try:
        index = load_vlocity_index(vlocity_path)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return

    nodes = index.get("nodes", {})
    project_hash = hashlib.md5(project_id.encode()).hexdigest()[:6]

    # Group by type
    by_type = defaultdict(list)
    for comp_name, comp_data in nodes.items():
        comp_type = comp_data.get("type")
        caller_count = 0

        # Count callers
        for other_name, other_data in nodes.items():
            other_deps = other_data.get("deps", [])
            for dep in other_deps:
                if dep.get("target") == comp_name:
                    caller_count += 1
                    break

        if caller_count >= min_caller_count:
            by_type[comp_type].append({
                "name": comp_name,
                "caller_count": caller_count,
                "folder": comp_data.get("folder"),
                "data": comp_data
            })

    # Harvest each type
    harvested = {}

    for comp_type, comps in by_type.items():
        # Sort by caller count, take top N
        comps.sort(key=lambda x: -x["caller_count"])
        selected = comps[:max_per_type]

        if not selected:
            print(f"⊘ {comp_type}: no components with {min_caller_count}+ callers")
            continue

        # Determine subtype if applicable
        subtype = None
        if comp_type == "DataRaptor":
            # Group by subtype (Extract, Load, Transform)
            by_subtype = defaultdict(list)
            for comp in selected:
                subtype_val = comp["data"].get("subtype", "Extract")
                by_subtype[subtype_val].append(comp)

            # Process each subtype separately
            for st, st_comps in by_subtype.items():
                harvested_subtype = process_harvest_batch(
                    comp_type, st, st_comps, kb_path, vlocity_path, project_hash
                )
                if harvested_subtype:
                    key = f"{comp_type}/{st}"
                    harvested[key] = harvested_subtype
        else:
            harvested_type = process_harvest_batch(
                comp_type, subtype, selected, kb_path, vlocity_path, project_hash
            )
            if harvested_type:
                harvested[comp_type] = harvested_type

    # Print summary
    print(f"✅ Harvested {len(harvested)} component types/subtypes")
    for key, count in harvested.items():
        print(f"   {key}: {count} components")


def process_harvest_batch(
    comp_type: str,
    subtype: Optional[str],
    components: List[dict],
    kb_path: Path,
    vlocity_path: Path,
    project_hash: str
) -> int:
    """Process a batch of components for harvest."""

    # Create output directory
    if subtype:
        out_dir = kb_path / comp_type / subtype / "examples"
    else:
        out_dir = kb_path / comp_type / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)

    harvested_count = 0
    anonymized_batch = []

    for comp_info in components:
        comp_name = comp_info["name"]
        comp_folder = comp_info["folder"]

        # Load raw component JSON from _DataPack.json
        datapack_path = vlocity_path / comp_folder / "_DataPack.json"
        if not datapack_path.exists():
            continue

        try:
            with open(datapack_path) as f:
                raw_json = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        # Anonymize
        anon_json, mapping = anonymize_component(raw_json, comp_type)

        # Write anonymized component
        safe_name = comp_name.replace(" ", "_").replace("/", "_")
        anon_path = out_dir / f"{safe_name}.json"
        with open(anon_path, "w") as f:
            json.dump(anon_json, f, indent=2)

        # Write metadata (safe to commit)
        meta = {
            "project_hash": project_hash,
            "caller_count": comp_info["caller_count"],
            "sobject_count": len(mapping.get("sobjects", {})),
            "mapping_count": len(mapping.get("fields", {})),
            "component_type": comp_type,
            "subtype": subtype
        }
        meta_path = out_dir / f"{safe_name}.meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        # Write mapping (gitignored, local only)
        mapping_path = out_dir / f"{safe_name}.mapping.json"
        with open(mapping_path, "w") as f:
            json.dump(mapping, f, indent=2)

        anonymized_batch.append(anon_json)
        harvested_count += 1

    # Recompute patterns.json
    if anonymized_batch:
        patterns = extract_patterns(anonymized_batch, comp_type, subtype)
        patterns_path = kb_path / comp_type / (subtype or "patterns.json")
        if subtype:
            patterns_path = patterns_path.parent / "patterns.json"

        patterns_path.parent.mkdir(parents=True, exist_ok=True)
        with open(patterns_path, "w") as f:
            json.dump(patterns, f, indent=2)

    return harvested_count


def merge_indexes(project_dirs: List[Tuple[str, str]], output_path: str) -> None:
    """
    Merge anonymized dependency indexes from multiple projects.

    Args:
        project_dirs: List of (vlocity_dir, project_id) tuples
        output_path: Where to write merged index.json
    """
    merged_nodes = {}
    seen_components = {}  # Track which project contributed each component

    for vlocity_dir, project_id in project_dirs:
        vlocity_path = Path(vlocity_dir).expanduser()

        try:
            index = load_vlocity_index(vlocity_path)
        except FileNotFoundError:
            print(f"⊘ Skipping {project_id}: no index found")
            continue

        project_hash = hashlib.md5(project_id.encode()).hexdigest()[:6]
        nodes = index.get("nodes", {})

        for comp_name, comp_data in nodes.items():
            # Create stable hash-based alias for component (same component = same alias across projects)
            comp_hash = hashlib.md5(comp_name.encode()).hexdigest()[:8]
            alias = f"{comp_data.get('type', 'Unknown')[:3]}_{comp_hash}"

            if alias not in merged_nodes:
                # First time seeing this component
                merged_nodes[alias] = {
                    "original_name": comp_name,
                    "type": comp_data.get("type"),
                    "schema": comp_data.get("schema"),
                    "projects": [project_hash],
                    "deps": []
                }
                seen_components[comp_name] = alias
            else:
                # Component seen before, track project
                if project_hash not in merged_nodes[alias].get("projects", []):
                    merged_nodes[alias]["projects"].append(project_hash)

    # Write merged index
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    merged_index = {
        "nodes": merged_nodes,
        "merged_from_projects": len(project_dirs),
        "component_count": len(merged_nodes)
    }

    with open(output_path, "w") as f:
        json.dump(merged_index, f, indent=2)

    print(f"✅ Merged {len(merged_nodes)} components from {len(project_dirs)} projects")
    print(f"   Wrote: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Knowledge Base Builder")
    subparsers = parser.add_subparsers(dest="command")

    # Harvest command
    harvest_parser = subparsers.add_parser("harvest", help="Harvest components from vlocity_dir")
    harvest_parser.add_argument("vlocity_dir", help="Path to vlocity metadata directory")
    harvest_parser.add_argument("--project", required=True, help="Project identifier")
    harvest_parser.add_argument("--kb", default="./knowledge-base", help="Knowledge base directory")
    harvest_parser.add_argument("--min-callers", type=int, default=2, help="Minimum caller count")
    harvest_parser.add_argument("--max-per-type", type=int, default=10, help="Max components per type")

    # Merge command
    merge_parser = subparsers.add_parser("merge", help="Merge indexes from multiple projects")
    merge_parser.add_argument("projects", nargs="+", help="Project directories (vlocity_dir project_id pairs)")
    merge_parser.add_argument("--output", required=True, help="Output path for merged index")

    args = parser.parse_args()

    if args.command == "harvest":
        harvest(
            vlocity_dir=args.vlocity_dir,
            project_id=args.project,
            knowledge_base_dir=args.kb,
            min_caller_count=args.min_callers,
            max_per_type=args.max_per_type
        )
    elif args.command == "merge":
        # Parse project pairs
        projects = []
        for i in range(0, len(args.projects), 2):
            if i + 1 < len(args.projects):
                projects.append((args.projects[i], args.projects[i + 1]))

        if not projects:
            print("❌ Must provide vlocity_dir project_id pairs")
            sys.exit(1)

        merge_indexes(projects, args.output)
    else:
        parser.print_help()
