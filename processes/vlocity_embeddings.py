#!/usr/bin/env python3
"""
Vlocity Embeddings — Semantic search over anonymized component corpus.

This module:
1. Embeds anonymized components from knowledge-base/ using ChromaDB
2. Provides semantic search: "IPs with complex conditional logic"
3. Stores embeddings locally (gitignored) — never committed
4. Works entirely on safe anonymized data

Setup: python vlocity_embeddings.py index --knowledge-base knowledge-base/
Search: Called via vlocity_semantic_search MCP tool
"""

import json
from pathlib import Path
from typing import Optional, List, Dict

try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


def build_embeddings_index(
    knowledge_base_dir: str,
    force_rebuild: bool = False
) -> Optional[object]:
    """
    Build or load ChromaDB embedding index from knowledge-base/ examples.

    Returns:
        chromadb.Collection or None if ChromaDB not available
    """
    if not HAS_CHROMADB:
        return None

    kb_path = Path(knowledge_base_dir).expanduser()
    embeddings_dir = kb_path / "embeddings"

    # Check if index exists and is current
    if embeddings_dir.exists() and not force_rebuild:
        try:
            client = chromadb.PersistentClient(path=str(embeddings_dir))
            return client.get_or_create_collection(name="vlocity_components")
        except Exception:
            pass  # Fall through to rebuild

    # Build fresh index
    embeddings_dir.mkdir(parents=True, exist_ok=True)

    try:
        client = chromadb.PersistentClient(path=str(embeddings_dir))
        collection = client.get_or_create_collection(
            name="vlocity_components",
            metadata={"hnsw:space": "cosine"}
        )
    except Exception as e:
        print(f"Failed to initialize ChromaDB: {e}")
        return None

    # Load all anonymized examples and add to index
    component_types = ["DataRaptor", "IntegrationProcedure", "FlexCard", "OmniScript"]
    added_count = 0

    for comp_type in component_types:
        # Check for subtypes
        if comp_type == "DataRaptor":
            subtypes = ["Extract", "Load", "Transform"]
        else:
            subtypes = [None]

        for subtype in subtypes:
            if subtype:
                examples_dir = kb_path / comp_type / subtype / "examples"
            else:
                examples_dir = kb_path / comp_type / "examples"

            if not examples_dir.exists():
                continue

            # Load and embed all examples
            for example_file in sorted(examples_dir.glob("*.json")):
                if example_file.name.endswith(".meta.json") or example_file.name.endswith(".mapping.json"):
                    continue

                try:
                    with open(example_file) as f:
                        component_json = json.load(f)

                    # Create document: component name + type + anonymized structure
                    doc = create_embedding_document(component_json, comp_type, subtype)
                    component_id = f"{comp_type}/{subtype or 'default'}/{example_file.stem}"

                    # Add to collection
                    collection.add(
                        ids=[component_id],
                        documents=[doc],
                        metadatas=[{
                            "component_type": comp_type,
                            "subtype": subtype or "default",
                            "name": example_file.stem
                        }]
                    )
                    added_count += 1

                except (json.JSONDecodeError, IOError, Exception):
                    continue

    print(f"✅ Built embedding index with {added_count} components")
    return collection


def create_embedding_document(component_json: dict, component_type: str, subtype: Optional[str] = None) -> str:
    """
    Create a text document suitable for embedding from a component.

    Includes: name, type, field references, element types, structural patterns.
    """
    parts = []

    # Component name and type
    if "DeveloperName" in component_json:
        parts.append(f"name: {component_json['DeveloperName']}")
    if "Name" in component_json:
        parts.append(f"name: {component_json['Name']}")

    parts.append(f"component_type: {component_type}")
    if subtype:
        parts.append(f"subtype: {subtype}")

    # Extract element types (for IP/OmniScript)
    element_types = []
    for key, value in component_json.items():
        if "Element" in key and isinstance(value, dict):
            if "Type" in value:
                element_types.append(value["Type"])

    if element_types:
        parts.append(f"elements: {', '.join(set(element_types))}")

    # Extract filter patterns (for DataRaptor)
    if component_type == "DataRaptor":
        if "FilterGroup" in component_json and isinstance(component_json["FilterGroup"], list):
            parts.append(f"uses_filters: true")
            parts.append(f"filter_count: {len(component_json['FilterGroup'])}")

        if "ProcessType" in component_json:
            parts.append(f"process_type: {component_json['ProcessType']}")

    # Extract field references (anonymized but still useful for patterns)
    field_refs = []
    def collect_refs(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.endswith("__c") or "Field" in key:
                    if isinstance(value, str) and "__" in value:
                        field_refs.append(value)
                collect_refs(value)
        elif isinstance(obj, list):
            for item in obj:
                collect_refs(item)

    collect_refs(component_json)
    if field_refs:
        parts.append(f"fields: {', '.join(set(field_refs)[:10])}")

    # Add structural keywords based on content
    json_str = json.dumps(component_json)
    keywords = []
    if "Conditional" in json_str:
        keywords.append("conditional_logic")
    if "TryCatch" in json_str:
        keywords.append("error_handling")
    if "HTTPAction" in json_str:
        keywords.append("http_integration")
    if "DataRaptorExtract" in json_str or "DataRaptorLoad" in json_str:
        keywords.append("dataraptor_action")
    if "SetValues" in json_str:
        keywords.append("value_mapping")

    if keywords:
        parts.append(f"keywords: {', '.join(keywords)}")

    return " ".join(parts)


def semantic_search(
    query: str,
    collection: object,
    component_type: Optional[str] = None,
    limit: int = 5
) -> Dict:
    """
    Semantic search over embedded components.

    Args:
        query: Natural language query (e.g., "IPs with complex conditional logic")
        collection: ChromaDB collection (from build_embeddings_index)
        component_type: Optional filter by type
        limit: Max results

    Returns:
        {
            "status": "success" | "error",
            "results": [
                {
                    "id": "...",
                    "component_type": "...",
                    "name": "...",
                    "distance": 0.123  # Lower is better
                }
            ]
        }
    """
    if not collection:
        return {
            "status": "error",
            "error": "Embedding index not initialized"
        }

    try:
        # Build where filter if component_type specified
        where = None
        if component_type:
            where = {"component_type": component_type}

        results = collection.query(
            query_texts=[query],
            n_results=limit,
            where=where
        )

        if not results or not results.get("ids") or not results["ids"][0]:
            return {
                "status": "success",
                "results": [],
                "message": "No matching components"
            }

        # Format results
        formatted = []
        ids = results["ids"][0]
        distances = results["distances"][0] if results.get("distances") else [0] * len(ids)
        metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(ids)

        for comp_id, distance, metadata in zip(ids, distances, metadatas):
            formatted.append({
                "id": comp_id,
                "component_type": metadata.get("component_type", "Unknown"),
                "subtype": metadata.get("subtype", ""),
                "name": metadata.get("name", "Unknown"),
                "distance": round(distance, 3)  # Lower is better
            })

        return {
            "status": "success",
            "results": formatted,
            "count": len(formatted),
            "query": query
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }


def format_semantic_results(search_result: Dict) -> str:
    """Format semantic search results as markdown."""
    if search_result.get("status") == "error":
        return f"❌ Error: {search_result.get('error')}"

    results = search_result.get("results", [])
    query = search_result.get("query", "")

    parts = ["# Semantic Search Results\n\n"]
    parts.append(f"**Query:** {query}\n\n")

    if not results:
        parts.append(search_result.get("message", "No results found"))
        return "".join(parts)

    parts.append(f"Found {len(results)} matching components:\n\n")

    for result in results:
        name = result.get("name", "Unknown")
        comp_type = result.get("component_type", "Unknown")
        subtype = result.get("subtype", "")
        distance = result.get("distance", 0)
        relevance = max(0, 100 - int(distance * 100))  # Convert distance to relevance %

        parts.append(f"**{name}** ({comp_type}")
        if subtype and subtype != "default":
            parts.append(f" - {subtype}")
        parts.append(f")\n")
        parts.append(f"- Relevance: {relevance}%\n\n")

    return "".join(parts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Vlocity Embeddings Manager")
    subparsers = parser.add_subparsers(dest="command")

    # Index command
    index_parser = subparsers.add_parser("index", help="Build or rebuild embedding index")
    index_parser.add_argument("--knowledge-base", default="./knowledge-base", help="Knowledge base directory")
    index_parser.add_argument("--force", action="store_true", help="Force rebuild")

    # Search command
    search_parser = subparsers.add_parser("search", help="Semantic search")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--knowledge-base", default="./knowledge-base", help="Knowledge base directory")
    search_parser.add_argument("--type", help="Filter by component type")
    search_parser.add_argument("--limit", type=int, default=5, help="Max results")

    args = parser.parse_args()

    if args.command == "index":
        if not HAS_CHROMADB:
            print("❌ ChromaDB not installed. Install with: pip install chromadb")
            exit(1)

        build_embeddings_index(args.knowledge_base, force_rebuild=args.force)

    elif args.command == "search":
        if not HAS_CHROMADB:
            print("❌ ChromaDB not installed. Install with: pip install chromadb")
            exit(1)

        collection = build_embeddings_index(args.knowledge_base)
        result = semantic_search(args.query, collection, args.type, args.limit)
        print(format_semantic_results(result))

    else:
        parser.print_help()
