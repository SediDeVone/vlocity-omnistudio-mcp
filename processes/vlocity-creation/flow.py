#!/usr/bin/env python3
"""
Vlocity Creation Process — Provides schemas + good practices for creating OmniStudio components.

Workflow:
  1. Load JSON schema for the requested component type
  2. Load good/bad practices from reference guides
  3. Merge schema + practices into single context document
  4. Return to Claude for informed component creation

This enables Claude to create components from validated structure, not from memory/guesswork.
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

# Import example retrieval
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from vlocity_examples import find_examples, format_examples_as_markdown
except ImportError:
    find_examples = None
    format_examples_as_markdown = None


def get_skill_root() -> Path:
    """Get the skills directory root."""
    return Path(__file__).parent.parent.parent / "skills"


def load_json_file(file_path: Path) -> dict:
    """Load and parse a JSON file."""
    if not file_path.exists():
        return {}
    try:
        with open(file_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def load_text_file(file_path: Path) -> str:
    """Load text file content."""
    if not file_path.exists():
        return ""
    try:
        with open(file_path) as f:
            return f.read()
    except IOError:
        return ""


def get_schema(
    component_type: str,
    subtype: Optional[str] = None,
    vlocity_dir: Optional[str] = None,
    knowledge_base_dir: Optional[str] = None
) -> dict:
    """
    Load schema + practices + real-world examples for a component type.

    Args:
        component_type: 'DataRaptor' | 'IntegrationProcedure' | 'FlexCard' | 'OmniScript'
        subtype: For DataRaptor: 'Extract' | 'Load' | 'Transform'
        vlocity_dir: Optional path to local vlocity directory (for raw examples)
        knowledge_base_dir: Optional path to knowledge base (for anonymized examples)

    Returns:
        {
            "component_type": "...",
            "subtype": "..." (if applicable),
            "schema": {...},
            "practices": "...",
            "examples": "..." (if available)
        }
    """
    skill_root = get_skill_root()
    result = {
        "component_type": component_type,
        "schema": {},
        "practices": "",
        "examples": "",
        "_examples_raw": None  # Will be populated by find_examples if available
    }

    # DataRaptor
    if component_type == "DataRaptor":
        if not subtype:
            return {
                "status": "error",
                "error": "DataRaptor requires subtype: 'Extract' | 'Load' | 'Transform'"
            }

        subtype_lower = subtype.lower()
        schema_file = skill_root / "vlocity-generator" / "schemas" / f"dataraptor_{subtype_lower}.schema.json"
        result["subtype"] = subtype
        result["schema"] = load_json_file(schema_file)

        # Load generation guide for all DataRaptor types
        practices_file = skill_root / "vlocity-generator" / "references" / "generation-guide.md"
        practices = load_text_file(practices_file)
        result["practices"] = practices

    # Integration Procedure
    elif component_type == "IntegrationProcedure":
        schema_file = skill_root / "vlocity-generator" / "schemas" / "ip_element_types.schema.json"
        result["schema"] = load_json_file(schema_file)

        # Load element type suffix guide
        practices_file = skill_root / "vlocity-generator" / "references" / "element-type-suffix-guide.md"
        practices = load_text_file(practices_file)
        result["practices"] = practices

    # FlexCard
    elif component_type == "FlexCard":
        schema_file = skill_root / "vlocity-generator" / "schemas" / "flexcard_definition.schema.json"
        result["schema"] = load_json_file(schema_file)

        # Load FlexCard schema guide
        practices_file = skill_root / "vlocity-flexcard-helper" / "references" / "flexcard-schema-guide.md"
        practices = load_text_file(practices_file)
        result["practices"] = practices

    # OmniScript
    elif component_type == "OmniScript":
        schema_file = skill_root / "vlocity-generator" / "schemas" / "omniscript_element_types.schema.json"
        result["schema"] = load_json_file(schema_file)

        # Load OmniScript schema guide
        practices_file = skill_root / "vlocity-flexcard-helper" / "references" / "omniscript-schema-guide.md"
        practices = load_text_file(practices_file)
        result["practices"] = practices

    else:
        return {
            "status": "error",
            "error": f"Unknown component type: {component_type}. "
                    "Use: DataRaptor | IntegrationProcedure | FlexCard | OmniScript"
        }

    # Fetch real-world examples if sources provided
    if find_examples and (vlocity_dir or knowledge_base_dir):
        try:
            examples_result = find_examples(
                vlocity_dir=vlocity_dir,
                knowledge_base_dir=knowledge_base_dir,
                component_type=component_type,
                subtype=subtype,
                limit=3
            )
            if examples_result.get("status") == "success":
                result["_examples_raw"] = examples_result
        except Exception:
            pass  # Examples are optional; don't fail if unavailable

    return result


def format_schema_context(component_type: str, schema_data: dict) -> str:
    """
    Format loaded schema + practices as markdown for Claude.

    Args:
        component_type: The component type
        schema_data: Result from get_schema()

    Returns:
        Formatted markdown document
    """
    if schema_data.get("status") == "error":
        return f"Error: {schema_data.get('error')}"

    parts = [
        f"# Component Creation Guide: {component_type}\n\n"
    ]

    if schema_data.get("subtype"):
        parts.append(f"**Subtype:** {schema_data['subtype']}\n\n")

    # Schema section
    if schema_data.get("schema"):
        parts.append("## Schema\n\n")
        parts.append("```json\n")
        parts.append(json.dumps(schema_data["schema"], indent=2))
        parts.append("\n```\n\n")

    # Practices section
    if schema_data.get("practices"):
        parts.append("## Good Practices & Guidelines\n\n")
        parts.append(schema_data["practices"])
        parts.append("\n\n")

    # Examples section (if available)
    if schema_data.get("_examples_raw"):
        if format_examples_as_markdown:
            parts.append("## Real-World Examples\n\n")
            examples_md = format_examples_as_markdown(schema_data["_examples_raw"])
            parts.append(examples_md)
            parts.append("\n\n")

    # Instructions
    parts.append("## Instructions\n\n")
    parts.append("""1. Review the schema above for all required and optional fields
2. Check the Good Practices section for naming conventions and patterns
3. Create the component JSON following the schema exactly
4. Validate that:
   - All required fields are present
   - Field names match the schema (case-sensitive)
   - Data types match (string, boolean, number, array, object)
   - Any field with enum values uses only allowed values
5. Return the complete component JSON

Do not add comments or explanations—just return valid JSON following the schema.
""")

    return "".join(parts)


def validate_component(
    component_json: str,
    component_type: str,
    subtype: Optional[str] = None
) -> dict:
    """
    Validate a component JSON against its schema and naming conventions.

    Args:
        component_json: JSON string of the component
        component_type: OmniStudio component type
        subtype: For DataRaptors: Extract | Load | Transform

    Returns:
        {
            "status": "valid" | "invalid",
            "errors": [...],
            "warnings": [...],
            "component_name": "..." (extracted from JSON)
        }
    """
    errors = []
    warnings = []
    component_name = None

    try:
        component = json.loads(component_json)
    except json.JSONDecodeError as e:
        return {
            "status": "invalid",
            "errors": [f"Invalid JSON: {str(e)}"],
            "warnings": [],
            "component_name": None
        }

    # Load schema for this component type
    schema_data = get_schema(component_type, subtype)
    if schema_data.get("status") == "error":
        return {
            "status": "invalid",
            "errors": [schema_data.get("error")],
            "warnings": [],
            "component_name": None
        }

    schema = schema_data.get("schema", {})
    practices = schema_data.get("practices", "")

    # Check required fields
    required_fields = schema.get("required", [])
    for field in required_fields:
        if field not in component:
            errors.append(f"Missing required field: {field}")

    # Extract component name for reporting
    name_field = None
    if component_type == "DataRaptor":
        name_field = "DeveloperName"
    elif component_type == "IntegrationProcedure":
        name_field = "DeveloperName"
    elif component_type == "FlexCard":
        name_field = "Name"
    elif component_type == "OmniScript":
        name_field = "DeveloperName"

    if name_field and name_field in component:
        component_name = component[name_field]

    # Validate field types (basic check against schema properties)
    properties = schema.get("properties", {})
    for field_name, field_value in component.items():
        if field_name not in properties:
            continue

        prop_schema = properties[field_name]
        expected_type = prop_schema.get("type")

        if expected_type == "string" and not isinstance(field_value, str):
            errors.append(f"Field '{field_name}': expected string, got {type(field_value).__name__}")
        elif expected_type == "number" and not isinstance(field_value, (int, float)):
            errors.append(f"Field '{field_name}': expected number, got {type(field_value).__name__}")
        elif expected_type == "boolean" and not isinstance(field_value, bool):
            errors.append(f"Field '{field_name}': expected boolean, got {type(field_value).__name__}")
        elif expected_type == "array" and not isinstance(field_value, list):
            errors.append(f"Field '{field_name}': expected array, got {type(field_value).__name__}")
        elif expected_type == "object" and not isinstance(field_value, dict):
            errors.append(f"Field '{field_name}': expected object, got {type(field_value).__name__}")

        # Check enum values
        enum_values = prop_schema.get("enum", [])
        if enum_values and field_value not in enum_values:
            errors.append(f"Field '{field_name}': invalid value '{field_value}'. Must be one of: {', '.join(map(str, enum_values))}")

    # Naming convention checks
    if component_type == "DataRaptor":
        dev_name = component.get("DeveloperName", "")
        if dev_name:
            # Check camelCase (starts lowercase, no spaces, no special chars except underscore)
            if not dev_name[0].islower():
                warnings.append(f"DeveloperName '{dev_name}' should start with lowercase (camelCase)")
            if " " in dev_name:
                errors.append(f"DeveloperName '{dev_name}' contains spaces")
            if not all(c.isalnum() or c == "_" for c in dev_name):
                errors.append(f"DeveloperName '{dev_name}' contains invalid characters (only alphanumeric and underscore allowed)")

        label = component.get("Label", "")
        if label and not label[0].isupper():
            warnings.append(f"Label '{label}' should start with uppercase")

        # Check Type field matches subtype if provided
        if subtype:
            dr_type = component.get("Type", "")
            if dr_type.lower() != subtype.lower():
                errors.append(f"DataRaptor Type '{dr_type}' does not match subtype '{subtype}'")

    elif component_type == "IntegrationProcedure":
        dev_name = component.get("DeveloperName", "")
        if dev_name and not dev_name[0].islower():
            warnings.append(f"DeveloperName '{dev_name}' should start with lowercase (camelCase)")

    elif component_type == "FlexCard":
        name = component.get("Name", "")
        if name and not name[0].isupper():
            warnings.append(f"FlexCard Name '{name}' should start with uppercase")

    return {
        "status": "valid" if not errors else "invalid",
        "errors": errors,
        "warnings": warnings,
        "component_name": component_name,
        "component_type": component_type,
        "subtype": subtype
    }


def run(
    component_type: str,
    subtype: Optional[str] = None,
    mode: str = "context-only",
    vlocity_dir: Optional[str] = None,
    knowledge_base_dir: Optional[str] = None
) -> dict:
    """
    Main orchestration function.

    Args:
        component_type: OmniStudio component type
        subtype: Subtype for DataRaptors
        mode: 'context-only' (return formatted schema + practices)
              'schema-only' (return raw schema JSON)
        vlocity_dir: Optional path to local vlocity directory
        knowledge_base_dir: Optional path to knowledge base

    Returns:
        dict with status and schema/context content
    """
    try:
        # Load schema + practices + examples
        schema_data = get_schema(
            component_type,
            subtype,
            vlocity_dir=vlocity_dir,
            knowledge_base_dir=knowledge_base_dir
        )

        if schema_data.get("status") == "error":
            return {
                "status": "error",
                "error": schema_data.get("error")
            }

        # Return formatted context for Claude
        if mode == "context-only":
            return {
                "status": "complete",
                "content": format_schema_context(component_type, schema_data),
                "component_type": component_type,
                "subtype": subtype,
                "has_schema": bool(schema_data.get("schema")),
                "has_practices": bool(schema_data.get("practices"))
            }

        # Return raw schema
        elif mode == "schema-only":
            return {
                "status": "complete",
                "schema": schema_data.get("schema"),
                "component_type": component_type,
                "subtype": subtype
            }

        else:
            return {
                "status": "error",
                "error": f"Unknown mode: {mode}"
            }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vlocity Creation Process")
    parser.add_argument(
        "component_type",
        help="Component type: DataRaptor | IntegrationProcedure | FlexCard | OmniScript"
    )
    parser.add_argument(
        "--subtype",
        help="For DataRaptor: Extract | Load | Transform"
    )
    parser.add_argument(
        "--mode",
        choices=["context-only", "schema-only"],
        default="context-only",
        help="Output mode"
    )
    parser.add_argument(
        "--vlocity-dir",
        help="Path to local vlocity directory (for raw examples)"
    )
    parser.add_argument(
        "--knowledge-base",
        help="Path to knowledge base directory (for anonymized examples)"
    )

    args = parser.parse_args()

    result = run(
        component_type=args.component_type,
        subtype=args.subtype,
        mode=args.mode,
        vlocity_dir=args.vlocity_dir,
        knowledge_base_dir=args.knowledge_base
    )

    if result["status"] == "error":
        print(f"❌ Error: {result['error']}")
        exit(1)

    print(json.dumps(result, indent=2))
