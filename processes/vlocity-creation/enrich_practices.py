#!/usr/bin/env python3
"""
Enrich Practices — Generate guides from knowledge base patterns and examples.

This script:
1. Reads patterns.json from knowledge-base/<Type>/
2. Reads anonymized examples
3. Generates enriched practices markdown with real statistics
4. Writes to skills/vlocity-generator/references/generated-practices-*.md

All input is from anonymized KB, so output is safe to commit.
"""

import json
from pathlib import Path
from typing import Optional, Dict, List
from collections import Counter


def load_patterns(knowledge_base_dir: Path, component_type: str, subtype: Optional[str] = None) -> Optional[dict]:
    """Load patterns.json for a component type."""
    if subtype:
        patterns_file = knowledge_base_dir / component_type / subtype / "patterns.json"
    else:
        patterns_file = knowledge_base_dir / component_type / "patterns.json"

    if not patterns_file.exists():
        return None

    try:
        with open(patterns_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def load_examples(knowledge_base_dir: Path, component_type: str, subtype: Optional[str] = None) -> List[dict]:
    """Load all anonymized example components."""
    if subtype:
        examples_dir = knowledge_base_dir / component_type / subtype / "examples"
    else:
        examples_dir = knowledge_base_dir / component_type / "examples"

    examples = []
    if not examples_dir.exists():
        return examples

    for example_file in sorted(examples_dir.glob("*.json")):
        if example_file.name.endswith(".meta.json") or example_file.name.endswith(".mapping.json"):
            continue

        try:
            with open(example_file) as f:
                examples.append(json.load(f))
        except (json.JSONDecodeError, IOError):
            continue

    return examples


def generate_dataraptor_practices(knowledge_base_dir: Path) -> str:
    """Generate enriched practices for DataRaptor types."""
    parts = ["# DataRaptor Generation Guide\n\n"]
    parts.append("*Generated from corpus analysis of real-world DataRaptors*\n\n")

    for subtype in ["Extract", "Load", "Transform"]:
        patterns = load_patterns(knowledge_base_dir, "DataRaptor", subtype)
        examples = load_examples(knowledge_base_dir, "DataRaptor", subtype)

        if not patterns and not examples:
            continue

        parts.append(f"## {subtype} DataRaptors\n\n")

        if patterns:
            sample_count = patterns.get("sample_count", 0)
            parts.append(f"**Analyzed {sample_count} real {subtype} DataRaptors**\n\n")

            # Naming patterns
            naming = patterns.get("naming_conventions", [])
            if naming:
                parts.append("### Naming Conventions\n\n")
                for pattern_info in naming:
                    pattern = pattern_info.get("pattern", "unknown")
                    freq = pattern_info.get("frequency", 0)
                    parts.append(f"- `{pattern}`: used in {int(freq*100)}% of components\n")
                parts.append("\n")

            # Common SObjects
            sobjects = patterns.get("common_sobjects", [])
            if sobjects:
                parts.append("### Common Data Sources\n\n")
                parts.append("Most frequently used SObjects:\n")
                for sobject in sobjects[:5]:
                    parts.append(f"- {sobject}\n")
                parts.append("\n")

        if examples:
            parts.append(f"### Real Examples ({len(examples)} sampled)\n\n")
            for example in examples[:2]:
                if "DeveloperName" in example:
                    name = example["DeveloperName"]
                    parts.append(f"**{name}**\n")
                    if "InterfaceObject" in example:
                        parts.append(f"- Object: `{example['InterfaceObject']}`\n")
                    if "Type" in example:
                        parts.append(f"- Type: {example['Type']}\n")
                    parts.append("\n")

    parts.append("## Best Practices\n\n")
    parts.append("- Use camelCase for DeveloperName (e.g., `domain_getEntityById`)\n")
    parts.append("- Use Title Case for Label (e.g., `Get Entity By ID`)\n")
    parts.append("- Keep InterfaceObject consistent across related DataRaptors\n")
    parts.append("- Document field mappings in the Label for maintainability\n")

    return "".join(parts)


def generate_ip_practices(knowledge_base_dir: Path) -> str:
    """Generate enriched practices for Integration Procedures."""
    patterns = load_patterns(knowledge_base_dir, "IntegrationProcedure")
    examples = load_examples(knowledge_base_dir, "IntegrationProcedure")

    parts = ["# Integration Procedure Generation Guide\n\n"]
    parts.append("*Generated from corpus analysis of real-world Integration Procedures*\n\n")

    if patterns:
        sample_count = patterns.get("sample_count", 0)
        parts.append(f"**Analyzed {sample_count} real Integration Procedures**\n\n")

        # Naming patterns
        naming = patterns.get("naming_conventions", [])
        if naming:
            parts.append("## Naming Conventions\n\n")
            for pattern_info in naming:
                pattern = pattern_info.get("pattern", "unknown")
                freq = pattern_info.get("frequency", 0)
                parts.append(f"- `{pattern}`: used in {int(freq*100)}% of components\n")
            parts.append("\n")

    if examples:
        parts.append(f"## Real Examples ({len(examples)} sampled)\n\n")
        for example in examples[:2]:
            if "DeveloperName" in example:
                name = example["DeveloperName"]
                parts.append(f"**{name}**\n")

                # Count element types
                elements = {}
                for key, value in example.items():
                    if "Element" in key and isinstance(value, dict):
                        elem_type = value.get("Type", "Unknown")
                        elements[elem_type] = elements.get(elem_type, 0) + 1

                if elements:
                    parts.append("- Element composition:\n")
                    for elem_type, count in sorted(elements.items(), key=lambda x: -x[1]):
                        parts.append(f"  - {elem_type}: {count}\n")
                parts.append("\n")

    parts.append("## Best Practices\n\n")
    parts.append("- Use camelCase for DeveloperName (e.g., `domain_createOrder`)\n")
    parts.append("- Break complex logic into TryCatchBlock for error handling\n")
    parts.append("- Use ConditionalBlock for branching based on input data\n")
    parts.append("- Order elements logically: inputs → transforms → outputs\n")
    parts.append("- Document element flow in comments for maintenance\n")

    return "".join(parts)


def generate_flexcard_practices(knowledge_base_dir: Path) -> str:
    """Generate enriched practices for FlexCards."""
    patterns = load_patterns(knowledge_base_dir, "FlexCard")
    examples = load_examples(knowledge_base_dir, "FlexCard")

    parts = ["# FlexCard Generation Guide\n\n"]
    parts.append("*Generated from corpus analysis of real-world FlexCards*\n\n")

    if patterns:
        sample_count = patterns.get("sample_count", 0)
        parts.append(f"**Analyzed {sample_count} real FlexCards**\n\n")

    if examples:
        parts.append(f"## Real Examples ({len(examples)} sampled)\n\n")
        for example in examples[:2]:
            if "Name" in example:
                name = example["Name"]
                parts.append(f"**{name}**\n")
                if "Definition" in example:
                    parts.append("- Includes custom state definitions\n")
                parts.append("\n")

    parts.append("## Best Practices\n\n")
    parts.append("- Use Title Case for FlexCard Name\n")
    parts.append("- Define clear state conditions in Definition\n")
    parts.append("- Use data-driven field mappings for maintainability\n")
    parts.append("- Test responsive behavior on mobile viewports\n")

    return "".join(parts)


def generate_omniscript_practices(knowledge_base_dir: Path) -> str:
    """Generate enriched practices for OmniScripts."""
    patterns = load_patterns(knowledge_base_dir, "OmniScript")
    examples = load_examples(knowledge_base_dir, "OmniScript")

    parts = ["# OmniScript Generation Guide\n\n"]
    parts.append("*Generated from corpus analysis of real-world OmniScripts*\n\n")

    if patterns:
        sample_count = patterns.get("sample_count", 0)
        parts.append(f"**Analyzed {sample_count} real OmniScripts**\n\n")

    if examples:
        parts.append(f"## Real Examples ({len(examples)} sampled)\n\n")
        for example in examples[:2]:
            if "DeveloperName" in example:
                name = example["DeveloperName"]
                parts.append(f"**{name}**\n")
                parts.append("\n")

    parts.append("## Best Practices\n\n")
    parts.append("- Use camelCase for DeveloperName\n")
    parts.append("- Organize steps into logical blocks for user experience\n")
    parts.append("- Validate user input at each step\n")
    parts.append("- Use error handling for integration failures\n")

    return "".join(parts)


def generate_all(knowledge_base_dir: str, output_dir: str) -> None:
    """Generate all enriched practices files."""
    kb_path = Path(knowledge_base_dir).expanduser()
    out_path = Path(output_dir).expanduser()

    if not kb_path.exists():
        print(f"❌ Knowledge base not found: {kb_path}")
        return

    out_path.mkdir(parents=True, exist_ok=True)

    generators = [
        ("DataRaptor", generate_dataraptor_practices),
        ("IntegrationProcedure", generate_ip_practices),
        ("FlexCard", generate_flexcard_practices),
        ("OmniScript", generate_omniscript_practices)
    ]

    for name, generator in generators:
        try:
            content = generator(kb_path)
            if content:
                output_file = out_path / f"generated-practices-{name.lower()}.md"
                with open(output_file, "w") as f:
                    f.write(content)
                print(f"✅ Generated: {output_file}")
            else:
                print(f"⊘ {name}: no data available")
        except Exception as e:
            print(f"❌ {name} error: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Enrich Practices from Knowledge Base")
    parser.add_argument("--knowledge-base", default="./knowledge-base", help="Knowledge base directory")
    parser.add_argument("--output", default="./skills/vlocity-generator/references", help="Output directory")

    args = parser.parse_args()

    generate_all(args.knowledge_base, args.output)
