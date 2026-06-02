#!/usr/bin/env python3
"""
MCP Server for OmniStudio

Exposes deterministic orchestration workflows as Claude tools:
- vlocity_analysis: Impact analysis for OmniStudio components (with field-level data flow)
- vlocity_schema: Load schemas + good practices for creating OmniStudio components
- vlocity_validate: Validate created component JSON against schema and naming conventions
- vlocity_search: Search the dependency index for components matching criteria
- omnistudio_plan: Solution planning for Jira tickets (future)

Configuration (claude_desktop_config.json):
  {
    "mcpServers": {
      "omnistudio": {
        "command": "python",
        "args": ["/path/to/omnistudio-skills/processes/mcp_server.py"]
      }
    }
  }

Usage (Claude Desktop):
  User: "Analyze the impact of sales_createOrderAPI in /workspace/vlocity"
  Claude: [calls vlocity_analysis tool automatically]

  User: "Load the schema for creating a DataRaptor Extract"
  Claude: [calls vlocity_schema tool, receives JSON schema + practices]

  User: "Validate this DataRaptor JSON I just created"
  Claude: [calls vlocity_validate tool, receives validation report]

  User: "Search for all DataRaptors in /workspace/vlocity"
  Claude: [calls vlocity_search tool, receives matching components]
"""

import json
import sys
import importlib.util
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print(
        "Error: mcp package not installed. Install with: pip install mcp",
        file=sys.stderr
    )
    sys.exit(1)

# Import process flow modules
processes_dir = Path(__file__).parent

# Load vlocity_analysis flow (handles hyphens in directory name)
analysis_flow_path = processes_dir / "vlocity-analysis" / "flow.py"
spec = importlib.util.spec_from_file_location("vlocity_analysis_flow", analysis_flow_path)
vlocity_analysis_flow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vlocity_analysis_flow)
vlocity_analysis_run = vlocity_analysis_flow.run

# Load vlocity_creation flow
creation_flow_path = processes_dir / "vlocity-creation" / "flow.py"
spec = importlib.util.spec_from_file_location("vlocity_creation_flow", creation_flow_path)
vlocity_creation_flow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vlocity_creation_flow)
vlocity_creation_run = vlocity_creation_flow.run
validate_component = vlocity_creation_flow.validate_component

# Load vlocity_search
search_path = processes_dir / "vlocity_search.py"
spec = importlib.util.spec_from_file_location("vlocity_search_module", search_path)
vlocity_search_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vlocity_search_module)
search = vlocity_search_module.search
format_search_results = vlocity_search_module.format_search_results

# Load vlocity_examples
examples_path = processes_dir / "vlocity_examples.py"
spec = importlib.util.spec_from_file_location("vlocity_examples_module", examples_path)
vlocity_examples_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vlocity_examples_module)
find_examples = vlocity_examples_module.find_examples
format_examples_as_markdown = vlocity_examples_module.format_examples_as_markdown

# Load vlocity_embeddings
embeddings_path = processes_dir / "vlocity_embeddings.py"
spec = importlib.util.spec_from_file_location("vlocity_embeddings_module", embeddings_path)
vlocity_embeddings_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vlocity_embeddings_module)
build_embeddings_index = vlocity_embeddings_module.build_embeddings_index
semantic_search = vlocity_embeddings_module.semantic_search
format_semantic_results = vlocity_embeddings_module.format_semantic_results

# Initialize MCP server
mcp = FastMCP("OmniStudio MCP Server")


@mcp.tool()
def vlocity_analysis(
    component_name: str,
    vlocity_dir: str,
    output_dir: str = "./output",
) -> str:
    """
    Fetch architecture and dependency documentation for an OmniStudio/Vlocity component.

    Runs deterministic steps: ensures dependency index exists, generates journey and flow
    documents, and loads all context. Returns formatted markdown documentation for the
    calling session to analyze.

    The returned documentation includes:
    - Architecture diagram and dependency table (journey document)
    - Execution flow sequence (if component is an Integration Procedure)
    - Dependency summary (total count, top 20 dependencies)

    After receiving this tool result, analyze it for:
    - Component purpose: What does it do at a high level?
    - Upstream impact: Components that call this (blast radius / what breaks on change)
    - Downstream impact: Components this depends on (what to regression test)
    - Risk level: HIGH/MEDIUM/LOW based on caller count and complexity
    - Test scope: All direct callers + critical dependencies

    Args:
        component_name: OmniStudio component name (e.g., sales_createOrderAPI)
        vlocity_dir: Path to vlocity metadata directory
        output_dir: Output directory for generated artifacts (default: ./output)

    Returns:
        Formatted markdown documentation for the component (no separate API calls)

    Examples:
        - "Analyze the impact of sales_createOrderAPI in /workspace/vlocity"
        - "What's the blast radius of OrderDataTransform?"
        - "Document the architecture of sales_createOrderAPI"
    """
    try:
        result = vlocity_analysis_run(
            component_name=component_name,
            vlocity_dir=vlocity_dir,
            output_dir=output_dir,
            mode="context-only"
        )

        if result.get("status") == "error":
            return f"Error: {result.get('error', 'Unknown error')}"

        return result.get("content", "No documentation generated")

    except Exception as e:
        return f"Error running vlocity_analysis: {str(e)}"


@mcp.tool()
def vlocity_schema(
    component_type: str,
    subtype: str = None,
    vlocity_dir: str = None,
    knowledge_base_dir: str = None
) -> str:
    """
    Load the authoritative schema, practices, and real-world examples for creating an OmniStudio component.

    Use this BEFORE creating any component to ensure you follow validated structure,
    naming conventions, and best practices.

    The returned context includes:
    - JSON schema with all required and optional fields
    - Field types and validation rules
    - Good practices and anti-patterns
    - Naming conventions and patterns
    - Real-world examples (if vlocity_dir or knowledge_base_dir provided)

    After receiving the schema:
    1. Review all required fields and their types
    2. Check naming conventions from practices section
    3. Study real-world examples (if provided) for structural patterns
    4. Create the component JSON following the schema exactly
    5. Validate that all required fields are present
    6. Return the complete JSON (no comments, pure JSON only)

    Args:
        component_type: 'DataRaptor' | 'IntegrationProcedure' | 'FlexCard' | 'OmniScript'
        subtype: For DataRaptor only: 'Extract' | 'Load' | 'Transform'
                 For others: omit
        vlocity_dir: Optional path to authorized vlocity directory (for raw examples)
        knowledge_base_dir: Optional path to knowledge base (for anonymized examples)

    Returns:
        Formatted markdown with JSON schema + practices + examples

    Examples:
        - "Load the schema for creating a DataRaptor Extract"
        - "What's the schema for an Integration Procedure?"
        - "Show me the FlexCard definition structure with examples"
    """
    try:
        result = vlocity_creation_run(
            component_type=component_type,
            subtype=subtype,
            mode="context-only",
            vlocity_dir=vlocity_dir,
            knowledge_base_dir=knowledge_base_dir
        )

        if result.get("status") == "error":
            return f"Error: {result.get('error', 'Unknown error')}"

        return result.get("content", "No schema available")

    except Exception as e:
        return f"Error running vlocity_schema: {str(e)}"


@mcp.tool()
def vlocity_validate(
    component_json: str,
    component_type: str,
    subtype: str = None
) -> str:
    """
    Validate a created component JSON against its schema and naming conventions.

    Use this AFTER creating a component with vlocity_schema to catch structural issues
    before deployment. Checks required fields, field types, enum values, and naming
    conventions from the schema's good practices guide.

    The returned validation report includes:
    - Errors: Must-fix issues (missing required fields, wrong types, invalid enum values)
    - Warnings: Best-practice violations (naming conventions, capitalization)
    - Component metadata: Extracted name, type, subtype

    Args:
        component_json: The component JSON as a string (must be valid JSON)
        component_type: 'DataRaptor' | 'IntegrationProcedure' | 'FlexCard' | 'OmniScript'
        subtype: For DataRaptor only: 'Extract' | 'Load' | 'Transform'
                 For others: omit

    Returns:
        Formatted validation report

    Examples:
        - "Validate this DataRaptor Extract JSON"
        - "Check if this component follows the schema rules"
    """
    try:
        result = validate_component(
            component_json=component_json,
            component_type=component_type,
            subtype=subtype
        )

        # Format result as markdown
        parts = []
        parts.append(f"# Validation Report\n\n")

        if result.get("component_name"):
            parts.append(f"**Component:** {result['component_name']} ({result['component_type']}")
            if result.get("subtype"):
                parts.append(f" - {result['subtype']}")
            parts.append(")\n\n")

        status = result.get("status")
        if status == "valid":
            parts.append("✅ **Status: VALID**\n\n")
        else:
            parts.append("❌ **Status: INVALID**\n\n")

        errors = result.get("errors", [])
        if errors:
            parts.append("## Errors (must fix)\n\n")
            for error in errors:
                parts.append(f"- {error}\n")
            parts.append("\n")

        warnings = result.get("warnings", [])
        if warnings:
            parts.append("## Warnings (best practices)\n\n")
            for warning in warnings:
                parts.append(f"- {warning}\n")
            parts.append("\n")

        if status == "valid" and not warnings:
            parts.append("This component is ready for deployment.")

        return "".join(parts)

    except Exception as e:
        return f"Error validating component: {str(e)}"


@mcp.tool()
def vlocity_examples(
    component_type: str,
    subtype: str = None,
    vlocity_dir: str = None,
    knowledge_base_dir: str = None,
    name_hint: str = None
) -> str:
    """
    Find real-world OmniStudio component examples for reference and learning.

    Use this to study how components are structured in practice. Examples come from:
    1. Local vlocity_dir (if provided) — raw components from authorized project
    2. Central knowledge_base (if provided) — anonymized examples safe for any context

    Examples include metadata like caller count and field usage to show complexity.

    Args:
        component_type: 'DataRaptor' | 'IntegrationProcedure' | 'FlexCard' | 'OmniScript'
        subtype: For DataRaptor only: 'Extract' | 'Load' | 'Transform'
        vlocity_dir: Optional path to local vlocity directory
        knowledge_base_dir: Optional path to knowledge base
        name_hint: Optional substring to filter component names

    Returns:
        Formatted markdown with real-world examples

    Examples:
        - "Show me examples of DataRaptor Extracts"
        - "Find examples of complex Integration Procedures"
        - "What do real FlexCards look like?"
    """
    try:
        result = find_examples(
            vlocity_dir=vlocity_dir,
            knowledge_base_dir=knowledge_base_dir,
            component_type=component_type,
            subtype=subtype,
            name_hint=name_hint,
            limit=3
        )

        if result.get("status") == "error":
            return f"Error: {result.get('error', 'Unknown error')}"

        return format_examples_as_markdown(result)

    except Exception as e:
        return f"Error running vlocity_examples: {str(e)}"


@mcp.tool()
def vlocity_search(
    vlocity_dir: str,
    name: str = None,
    component_type: str = None,
    called_by: str = None,
    calls: str = None,
    data_source: str = None,
    limit: int = 50
) -> str:
    """
    Search the dependency index for OmniStudio components matching your criteria.

    Use this to explore the component ecosystem before deep analysis. Finds components by name,
    type, or dependency patterns. Requires that vlocity_dir has been indexed via
    vlocity-dependency-indexer.

    The returned results include component metadata, caller count, dependency count, and top
    dependencies. Components are ranked by relevance (most callers + dependencies first).

    Args:
        vlocity_dir: Path to vlocity metadata directory
        name: Substring to match in component name (case-insensitive)
        component_type: Filter by type: 'DataRaptor' | 'IntegrationProcedure' | 'FlexCard' | 'OmniScript'
        called_by: Find components that are called by this component
        calls: Find components that call this component
        data_source: Filter DataRaptors by SObject name (e.g., Account, Order)
        limit: Maximum results to return (default: 50)

    Returns:
        Formatted table with matching components

    Examples:
        - "Search for all components named Account in /workspace/vlocity"
        - "Find all DataRaptors in /workspace/vlocity"
        - "Show me all components called by sales_createOrderAPI"
        - "What calls the accountLookup DataRaptor?"
    """
    try:
        result = search(
            vlocity_dir=vlocity_dir,
            name=name,
            component_type=component_type,
            called_by=called_by,
            calls=calls,
            data_source=data_source,
            limit=limit
        )

        return format_search_results(result)

    except Exception as e:
        return f"Error searching index: {str(e)}"


@mcp.tool()
def vlocity_semantic_search(
    query: str,
    knowledge_base_dir: str = "./knowledge-base",
    component_type: str = None,
    limit: int = 5
) -> str:
    """
    Semantic search over the knowledge base of anonymized OmniStudio components.

    Use this to find components matching natural language descriptions, without knowing
    exact names. Works on structural patterns, element types, and component characteristics.

    The search index is built from anonymized examples in knowledge-base/, so results
    contain no proprietary data — just component names and types that match your query.

    First run: Building the embedding index takes a few seconds. Subsequent searches are instant.

    Args:
        query: Natural language description of what you're looking for
        knowledge_base_dir: Path to knowledge-base/ directory
        component_type: Optional filter by type ('DataRaptor' | 'IntegrationProcedure' | 'FlexCard' | 'OmniScript')
        limit: Max results to return (default: 5)

    Returns:
        Formatted markdown with matching components

    Examples:
        - "Find IPs with complex conditional logic"
        - "Show me DataRaptors that use multiple filter conditions"
        - "What FlexCards have state-based behavior?"
        - "Find components that integrate with external APIs"
    """
    try:
        # Build or load index (lazy initialization)
        collection = build_embeddings_index(knowledge_base_dir)

        if not collection:
            return "⚠️ Semantic search requires ChromaDB. Install with: pip install chromadb"

        # Search
        result = semantic_search(query, collection, component_type, limit)

        if result.get("status") == "error":
            return f"Error: {result.get('error', 'Unknown error')}"

        return format_semantic_results(result)

    except Exception as e:
        return f"Error running semantic search: {str(e)}"


if __name__ == "__main__":
    # Run the MCP server
    mcp.run(transport="stdio")
