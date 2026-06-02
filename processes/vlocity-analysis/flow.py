#!/usr/bin/env python3
"""
Vlocity Analysis Process — Orchestrates deterministic index/docs generation + LLM impact analysis.

Workflow:
  1. Ensure dependency index exists (build_index.py --generate-all)
  2. Confirm component exists in index.json
  3. Generate journey + flow documentation
  4. Load all context files into memory
  5. LLM analysis (architecture + impact)

Deterministic steps (1-4) run without LLM. Step 5 is a single focused API call with pre-loaded context.
"""

import anthropic
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


def ensure_index(vlocity_dir: str, parent_dir: Optional[str] = None) -> str:
    """Ensure dependency-index/index.json exists. Generate if missing."""
    vlocity_path = Path(vlocity_dir).resolve()
    if parent_dir is None:
        parent_dir = str(vlocity_path.parent)
    else:
        parent_dir = str(Path(parent_dir).resolve())

    index_path = Path(parent_dir) / "dependency-index" / "index.json"
    if index_path.exists():
        return str(index_path)

    print(f"📚 Generating dependency index for {vlocity_path}...", file=sys.stderr)
    indexer_script = Path(__file__).parent.parent.parent / "skills" / "vlocity-dependency-indexer" / "scripts" / "build_index.py"

    result = subprocess.run(
        ["python3", str(indexer_script), "--generate-all", str(vlocity_path), str(parent_dir)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        raise RuntimeError(f"Index generation failed: {result.stderr}")

    if not index_path.exists():
        raise RuntimeError(f"Index file not created at {index_path}")

    return str(index_path)


def load_index(index_path: str) -> dict:
    """Load index.json into memory."""
    with open(index_path) as f:
        return json.load(f)


def assert_component_exists(component_name: str, index: dict) -> None:
    """Verify component is in the index."""
    if component_name not in index.get("nodes", {}):
        available = list(index.get("nodes", {}).keys())[:10]
        raise ValueError(
            f"Component '{component_name}' not found in index.\n"
            f"Available: {', '.join(available)}"
        )


def generate_docs(
    component_name: str,
    vlocity_dir: str,
    index_path: str,
    output_dir: str
) -> dict:
    """Generate journey + flow documentation for component."""
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    indexer_script = Path(__file__).parent.parent.parent / "skills" / "vlocity-dependency-indexer" / "scripts" / "build_index.py"

    # Journey document
    journey_result = subprocess.run(
        ["python3", str(indexer_script), "--document", index_path, component_name, str(output_path)],
        capture_output=True,
        text=True
    )
    if journey_result.returncode != 0:
        raise RuntimeError(f"Journey generation failed: {journey_result.stderr}")

    # Flow diagram
    flow_result = subprocess.run(
        ["python3", str(indexer_script), "--flow", vlocity_dir, component_name, str(output_path), index_path],
        capture_output=True,
        text=True
    )
    # Flow may not exist for non-IP components; that's OK

    journey_file = output_path / f"{component_name}-journey.md"
    flow_file = output_path / f"{component_name}-flow.md"

    if not journey_file.exists():
        raise RuntimeError(f"Journey document not generated: {journey_file}")

    return {
        "journey": journey_file,
        "flow": flow_file if flow_file.exists() else None
    }


def load_context(component_name: str, index_path: str, output_dir: str) -> dict:
    """Load all documentation files into memory for LLM context."""
    output_path = Path(output_dir)
    index_dir = Path(index_path).parent

    journey_file = output_path / f"{component_name}-journey.md"
    flow_file = output_path / f"{component_name}-flow.md"

    context = {"component": component_name}

    # Load journey
    if journey_file.exists():
        with open(journey_file) as f:
            context["journey"] = f.read()
    else:
        raise FileNotFoundError(f"Journey document not found: {journey_file}")

    # Load flow (optional)
    if flow_file.exists():
        with open(flow_file) as f:
            context["flow"] = f.read()
    else:
        context["flow"] = None

    # Load analysis bundle if available
    bundle_file = index_dir / f"{component_name}-analysis-bundle.json"
    if bundle_file.exists():
        with open(bundle_file) as f:
            context["bundle"] = json.load(f)
    else:
        context["bundle"] = None

    return context


def build_context_markdown(component_name: str, context: dict) -> str:
    """Format loaded context as markdown for return to calling LLM session."""
    parts = [
        f"# Component: {component_name}\n\n",
        "## Architecture\n",
        context.get("journey", ""),
    ]
    if context.get("flow"):
        parts += ["\n## Execution Flow\n\n", context["flow"]]
    if context.get("bundle"):
        bundle = context["bundle"]
        parts.append("\n## Dependency Summary\n\n")
        parts.append(f"Total dependencies: {bundle.get('total_dependencies', 'unknown')}\n")
        if bundle.get("dependency_list"):
            deps_str = ", ".join(bundle["dependency_list"][:20])
            if len(bundle.get("dependency_list", [])) > 20:
                deps_str += f", ... and {len(bundle['dependency_list']) - 20} more"
            parts.append(f"Top dependencies: {deps_str}\n")
    return "".join(parts)


def analyze_impact(component_name: str, context: dict, mode: str) -> str:
    """LLM analysis: architecture + impact."""
    # API key is read from ANTHROPIC_API_KEY environment variable or other credential sources
    try:
        client = anthropic.Anthropic()
    except Exception as e:
        raise RuntimeError(
            f"Failed to authenticate with Anthropic API. "
            f"Set ANTHROPIC_API_KEY environment variable or configure credentials. "
            f"Details: {str(e)}"
        )

    # Build the analysis prompt based on context
    prompt_parts = [
        f"Component: {component_name}\n",
        "# Architecture\n",
        context.get("journey", ""),
    ]

    if context.get("flow"):
        prompt_parts.append("\n# Execution Flow\n")
        prompt_parts.append(context["flow"])

    if context.get("bundle"):
        prompt_parts.append("\n# Dependency Analysis\n")
        bundle = context["bundle"]
        prompt_parts.append(f"Total dependencies: {bundle.get('total_dependencies', 'unknown')}\n")
        if bundle.get("dependency_list"):
            prompt_parts.append("Dependencies: " + ", ".join(bundle["dependency_list"][:20]) + "\n")

    full_context = "".join(prompt_parts)

    if mode == "blast-radius":
        system_prompt = """You are an impact analysis expert. Given component documentation,
provide a concise blast-radius assessment: How many components might be affected if this changes?
What is the risk level (HIGH/MEDIUM/LOW)? List the top 5 callers if available."""

    elif mode == "impact-report":
        system_prompt = """You are an impact analysis expert preparing a structured report for stakeholders.
Analyze the component thoroughly:
1. Architecture: What does this component do?
2. Blast Radius: How many other components depend on it?
3. Risk Level: HIGH/MEDIUM/LOW based on impact surface
4. Test Scope: What must be regression-tested if this changes?
5. Migration Notes: If this component were removed, what would break?
Format your response as structured sections with clear headings."""

    else:  # analyze (default)
        system_prompt = """You are a Vlocity/OmniStudio architecture and impact analysis expert.
Given component documentation (architecture diagram, flow, dependencies), provide:
1. Component Purpose: What does it do at a high level?
2. Architecture: Key elements and their roles
3. Upstream Impact: Components that call this (what breaks if you change it?)
4. Downstream Impact: Components this depends on (what to regression-test?)
5. Risk Assessment: HIGH/MEDIUM/LOW based on fan-in and complexity
6. Recommended Test Scope: All direct callers + critical dependencies
Be specific and actionable. Reference actual component names and types from the documentation."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": full_context,
            }
        ],
    )

    return message.content[0].text


def run(
    component_name: str,
    vlocity_dir: str,
    output_dir: str = "./output",
    mode: str = "analyze",
) -> dict:
    """Main orchestration function.

    Args:
        component_name: OmniStudio component to analyze (e.g., sales_createOrderAPI)
        vlocity_dir: Path to vlocity metadata directory
        output_dir: Where to write generated documentation
        mode: 'context-only' (MCP: return docs for calling session)
              'docs-only' (generate artifacts, no LLM)
              'analyze' (full impact analysis via Anthropic SDK)
              'blast-radius' (quick risk summary via Anthropic SDK)
              'impact-report' (structured report via Anthropic SDK)

    Returns:
        dict with status, optional 'content' (context-only mode),
        optional 'analysis' (LLM modes), and 'artifacts' (file paths)
    """

    try:
        # Step 1: Ensure index exists
        vlocity_path = Path(vlocity_dir).resolve()
        parent_dir = str(vlocity_path.parent)
        index_path = ensure_index(str(vlocity_path), parent_dir)
        print(f"✓ Index ready: {index_path}", file=sys.stderr)

        # Step 2: Confirm component exists
        index = load_index(index_path)
        assert_component_exists(component_name, index)
        component_type = index["nodes"][component_name].get("type", "Unknown")
        print(f"✓ Component found: {component_name} ({component_type})", file=sys.stderr)

        # Step 3: Generate documentation
        output_path = Path(output_dir).resolve()
        docs = generate_docs(component_name, str(vlocity_path), index_path, str(output_path))
        print(f"✓ Documentation generated: {output_path}", file=sys.stderr)

        # Step 4: Load context into memory
        context = load_context(component_name, index_path, str(output_path))
        print(f"✓ Context loaded ({len(context.get('journey', ''))} chars)", file=sys.stderr)

        # Exit early if docs-only mode
        if mode == "docs-only":
            return {
                "status": "complete",
                "artifacts": {
                    "journey": str(docs["journey"]),
                    "flow": str(docs["flow"]) if docs["flow"] else None,
                },
            }

        # Return formatted context for calling LLM session to analyze
        if mode == "context-only":
            return {
                "status": "complete",
                "content": build_context_markdown(component_name, context),
                "artifacts": {
                    "journey": str(docs["journey"]),
                    "flow": str(docs["flow"]) if docs["flow"] else None,
                },
            }

        # Step 5: LLM analysis (CLI modes only)
        print(f"🤖 Running impact analysis ({mode})...", file=sys.stderr)
        analysis = analyze_impact(component_name, context, mode)

        return {
            "status": "complete",
            "analysis": analysis,
            "artifacts": {
                "journey": str(docs["journey"]),
                "flow": str(docs["flow"]) if docs["flow"] else None,
            },
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vlocity Analysis Process")
    parser.add_argument("component_name", help="Component to analyze")
    parser.add_argument("vlocity_dir", help="Path to vlocity metadata directory")
    parser.add_argument("--output", default="./output", help="Output directory")
    parser.add_argument(
        "--mode",
        choices=["context-only", "docs-only", "analyze", "blast-radius", "impact-report"],
        default="analyze",
        help="Analysis mode",
    )

    args = parser.parse_args()

    result = run(
        component_name=args.component_name,
        vlocity_dir=args.vlocity_dir,
        output_dir=args.output,
        mode=args.mode,
    )

    if result["status"] == "error":
        print(f"❌ Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))
