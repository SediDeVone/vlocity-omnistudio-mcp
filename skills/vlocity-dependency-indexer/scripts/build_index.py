#!/usr/bin/env python3
import json
import sys
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict, deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'vlocity-architecture-mapper'))
from scripts.extract_dependencies import load_json, clean_namespace, get_target as orig_get_target, NAMESPACE_PLACEHOLDERS

def get_target(data):
    """Enhanced get_target that handles managed schema fields."""
    ele_type = data.get("Type") or data.get("type") or data.get("%vlocity_namespace%__Type__c")
    # Handle different property set names across Vlocity versions (native and managed)
    props = (data.get("PropertySetConfig") or data.get("propertySetConfig") or
             data.get("PropertySetMap") or data.get("%vlocity_namespace%__PropertySet__c") or {})

    if not ele_type:
        return None

    if "Integration Procedure" in ele_type:
        target = props.get("integrationProcedureKey") or data.get("integrationProcedureKey")
        return clean_namespace(target)
    elif "DataRaptor" in ele_type:
        target = props.get("bundle") or props.get("bundleName") or data.get("bundle")
        return clean_namespace(target)
    elif "Remote" in ele_type:
        remote_class = props.get("remoteClass") or data.get("remoteClass") or "Unknown"
        remote_method = props.get("remoteMethod") or data.get("remoteMethod") or "Unknown"
        return f"{clean_namespace(remote_class)}.{remote_method}"
    elif "HTTP" in ele_type or "Rest" in ele_type:
        return props.get("restPath") or props.get("restUrl") or data.get("restPath")
    elif ele_type == "OmniScript":
        target = data.get("EmbeddedOmniScriptKey") or props.get("EmbeddedOmniScriptKey") or props.get("omniScriptKey")
        return clean_namespace(target)
    elif "Calculation Procedure" in ele_type:
        target = props.get("calculationProcedureKey") or data.get("calculationProcedureKey")
        return clean_namespace(target)
    elif "Matrix" in ele_type:
        target = props.get("matrixName") or props.get("matrixKey") or data.get("matrixKey")
        return clean_namespace(target)
    return None

COMPONENT_TYPES = {
    'OmniScript': 'vlocity/OmniScript',
    'IntegrationProcedure': 'vlocity/IntegrationProcedure',
    'DataRaptor': 'vlocity/DataRaptor',
    'FlexCard': 'vlocity/FlexCard',
    'CalculationProcedure': 'vlocity/CalculationProcedure',
}

def detect_schema(folder_path):
    """Detect if metadata is managed or native schema."""
    datapack_file = None
    for f in os.listdir(folder_path):
        if f.endswith('_DataPack.json') or f.endswith('DataPack.json'):
            datapack_file = os.path.join(folder_path, f)
            break

    if not datapack_file:
        return 'unknown'

    data = load_json(datapack_file)
    if not data:
        return 'unknown'

    sobj_type = data.get('VlocityRecordSObjectType', '')
    if 'OmniProcess' in sobj_type or 'OmniDataTransform' in sobj_type:
        return 'native'
    elif '%vlocity_namespace%' in sobj_type or 'vlocity_cmt' in sobj_type or 'vlocity_ins' in sobj_type:
        return 'managed'
    return 'unknown'

def get_hidden_dr_deps(data):
    """Extract pre/post transform bundle dependencies."""
    deps = []
    props = (data.get('PropertySetConfig') or data.get('propertySetConfig') or
             data.get('PropertySetMap') or data.get('%vlocity_namespace%__PropertySet__c') or {})

    if props.get('preTransformBundle'):
        deps.append({
            'target': clean_namespace(props.get('preTransformBundle')),
            'dep_type': 'DataRaptorTransform',
            'via_field': 'preTransformBundle'
        })
    if props.get('postTransformBundle'):
        deps.append({
            'target': clean_namespace(props.get('postTransformBundle')),
            'dep_type': 'DataRaptorTransform',
            'via_field': 'postTransformBundle'
        })
    return deps

def parse_flexcard(file_path):
    """Extract dependencies from a FlexCard definition file."""
    deps = []
    data = load_json(file_path)
    if not data:
        return deps

    data_source = data.get('dataSource') or {}
    if data_source.get('type') == 'IntegrationProcedure':
        value = data_source.get('value') or {}
        ip_method = value.get('ipMethod')
        if ip_method:
            deps.append({
                'target': clean_namespace(ip_method),
                'dep_type': 'IntegrationProcedure',
                'via_element': 'dataSource.ipMethod'
            })
    elif data_source.get('type') == 'DataRaptor':
        value = data_source.get('value') or {}
        bundle = value.get('bundleName') or value.get('bundle')
        if bundle:
            deps.append({
                'target': clean_namespace(bundle),
                'dep_type': 'DataRaptorExtract',
                'via_element': 'dataSource.bundle'
            })

    states = data.get('states') or []
    for state in states:
        actions = state.get('actions') or []
        for action in actions:
            action_list = action.get('actionList') or []
            for act in action_list:
                if act.get('type') == 'runIP':
                    ip_key = act.get('integrationProcedureKey')
                    if ip_key:
                        deps.append({
                            'target': clean_namespace(ip_key),
                            'dep_type': 'IntegrationProcedure',
                            'via_element': f"state.{state.get('name', 'Unknown')}.runIP"
                        })
                elif act.get('type') == 'openCard':
                    card_name = act.get('cardName')
                    if card_name:
                        deps.append({
                            'target': clean_namespace(card_name),
                            'dep_type': 'FlexCard',
                            'via_element': f"state.{state.get('name', 'Unknown')}.openCard"
                        })

    child_cards = data.get('childCards') or []
    for child in child_cards:
        card_name = child.get('name')
        if card_name:
            deps.append({
                'target': clean_namespace(card_name),
                'dep_type': 'FlexCard',
                'via_element': 'childCards'
            })

    return deps

def extract_component_deps(comp_type, comp_folder):
    """Extract all 1-level dependencies for a component."""
    deps = []

    if comp_type == 'FlexCard':
        for f in os.listdir(comp_folder):
            if f.endswith('.json') and not f.endswith('_DataPack.json'):
                card_path = os.path.join(comp_folder, f)
                deps.extend(parse_flexcard(card_path))
                break
    else:
        for root, dirs, files in os.walk(comp_folder):
            for file in files:
                if ('_Element_' in file or 'OmniProcessElement' in file) and file.endswith('.json'):
                    elem_path = os.path.join(root, file)
                    data = load_json(elem_path)
                    if data:
                        # Get type from various possible field names
                        ele_type = (data.get('Type') or data.get('type') or
                                   data.get('%vlocity_namespace%__Type__c') or 'Unknown')
                        ele_name = data.get('Name') or data.get('name', 'Unknown')

                        # Only process if it's an action type (has dependencies)
                        if any(keyword in str(ele_type) for keyword in
                               ['Action', 'Integration', 'DataRaptor', 'Remote', 'HTTP', 'Rest', 'OmniScript', 'Calculation', 'Matrix']):
                            target = get_target(data)
                            if target:
                                deps.append({
                                    'target': target,
                                    'dep_type': ele_type,
                                    'via_element': ele_name
                                })
                            hidden = get_hidden_dr_deps(data)
                            deps.extend(hidden)

    return deps

def extract_field_mappings(component_name, component_path, component_type, schema_type):
    """Extract field-level mappings from DataRaptor or Integration Procedure metadata.

    Returns a dict with field mapping information:
    {
        'type': 'DataRaptorExtract' | 'DataRaptorLoad' | 'DataRaptorTransform' | 'IntegrationProcedure',
        'mappings': [
            {'input': 'Field1', 'output': 'Field2', 'source': 'SObject', 'target': 'JSON'},
            ...
        ],
        'elements': [  # For Integration Procedures
            {'name': 'ElementName', 'type': 'DataRaptorAction', 'sends': {...}, 'receives_at': '...'},
            ...
        ]
    }
    """
    if component_type != 'DataRaptor' and component_type != 'IntegrationProcedure':
        return None

    result = {
        'type': component_type,
        'mappings': [],
        'elements': []
    }

    if component_type == 'DataRaptor':
        # Try native schema first (_Items.json)
        items_file = None
        for f in os.listdir(component_path):
            if f.endswith('_Items.json') or f.endswith('Items.json'):
                items_file = os.path.join(component_path, f)
                break

        if items_file and os.path.isfile(items_file):
            data = load_json(items_file)
            if data and isinstance(data, list):
                for item in data:
                    mapping = {}
                    # Native schema fields
                    if 'InputFieldName' in item and 'OutputFieldName' in item:
                        mapping['input'] = item.get('InputFieldName', '')
                        mapping['output'] = item.get('OutputFieldName', '')
                        mapping['source'] = item.get('InputObjectName', 'JSON')
                        mapping['target'] = item.get('OutputObjectName', 'JSON')
                        if mapping['input'] and mapping['output']:
                            result['mappings'].append(mapping)

        # Try managed schema (_Mappings.json) if no items found
        if not result['mappings']:
            mappings_file = None
            for f in os.listdir(component_path):
                if f.endswith('_Mappings.json') or f.endswith('Mappings.json'):
                    mappings_file = os.path.join(component_path, f)
                    break

            if mappings_file and os.path.isfile(mappings_file):
                data = load_json(mappings_file)
                if data and isinstance(data, list):
                    for item in data:
                        mapping = {}
                        # Managed schema fields (namespaced)
                        input_field = (item.get('%vlocity_namespace%__InterfaceFieldAPIName__c') or
                                      item.get('InterfaceFieldAPIName'))
                        output_field = (item.get('%vlocity_namespace%__DomainObjectFieldAPIName__c') or
                                       item.get('DomainObjectFieldAPIName'))
                        output_obj = (item.get('%vlocity_namespace%__DomainObjectAPIName__c') or
                                     item.get('DomainObjectAPIName'))

                        if input_field and output_field:
                            mapping['input'] = input_field
                            mapping['output'] = output_field
                            mapping['source'] = 'JSON'
                            mapping['target'] = clean_namespace(output_obj) if output_obj else 'JSON'
                            result['mappings'].append(mapping)

    elif component_type == 'IntegrationProcedure':
        # Extract element bindings from PropertySetConfig
        for root, dirs, files in os.walk(component_path):
            for file in files:
                if ('_Element_' in file or 'OmniProcessElement' in file) and file.endswith('.json'):
                    elem_path = os.path.join(root, file)
                    data = load_json(elem_path)
                    if data:
                        ele_name = data.get('Name') or data.get('name', 'Unknown')
                        ele_type = (data.get('Type') or data.get('type') or
                                   data.get('%vlocity_namespace%__Type__c') or 'Unknown')

                        # Extract PropertySetConfig
                        props = (data.get('PropertySetConfig') or data.get('propertySetConfig') or
                                data.get('PropertySetMap') or data.get('%vlocity_namespace%__PropertySet__c') or {})

                        # Only include elements that call other components
                        if any(keyword in str(ele_type) for keyword in
                               ['Integration', 'DataRaptor', 'Remote', 'HTTP', 'Rest', 'OmniScript', 'Calculation', 'Matrix']):

                            elem_info = {
                                'name': ele_name,
                                'type': ele_type,
                            }

                            # Capture input bindings
                            additional_input = props.get('additionalInput')
                            if additional_input:
                                if isinstance(additional_input, dict):
                                    elem_info['sends'] = additional_input
                                elif isinstance(additional_input, str):
                                    try:
                                        elem_info['sends'] = json.loads(additional_input)
                                    except (json.JSONDecodeError, TypeError):
                                        elem_info['sends'] = {'raw': additional_input}

                            # Capture output path
                            response_path = props.get('responseJSONPath') or props.get('responseJSONNode')
                            send_path = props.get('sendJSONPath')
                            if response_path:
                                elem_info['receives_at'] = response_path
                            if send_path:
                                elem_info['sends_from'] = send_path

                            result['elements'].append(elem_info)

    return result if (result['mappings'] or result['elements']) else None


def discover_components(vlocity_dir):
    """Discover all OmniStudio components in the vlocity directory."""
    components = {}

    for comp_type, type_path_rel in COMPONENT_TYPES.items():
        type_path = os.path.join(vlocity_dir, type_path_rel.split('/')[-1])
        if not os.path.isdir(type_path):
            continue

        for comp_name in os.listdir(type_path):
            comp_path = os.path.join(type_path, comp_name)
            if os.path.isdir(comp_path):
                components[comp_name] = {
                    'path': comp_path,
                    'type': comp_type
                }

    return components

def build_full_index(vlocity_dir, output_dir):
    """Build complete dependency index."""
    components = discover_components(vlocity_dir)

    index = {
        'meta': {
            'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'vlocity_dir': vlocity_dir,
            'component_count': len(components)
        },
        'nodes': {}
    }

    for comp_name, comp_info in sorted(components.items()):
        comp_path = comp_info['path']
        comp_type = comp_info['type']
        schema = detect_schema(comp_path)

        deps = extract_component_deps(comp_type, comp_path)

        index['nodes'][comp_name] = {
            'type': comp_type,
            'schema': schema,
            'folder': os.path.relpath(comp_path, vlocity_dir),
            'deps': deps
        }

    os.makedirs(output_dir, exist_ok=True)
    index_file = os.path.join(output_dir, 'index.json')
    with open(index_file, 'w') as f:
        json.dump(index, f, indent=2)

    generate_summary(index, output_dir)
    return index

def generate_summary(index, output_dir):
    """Generate summary markdown file."""
    nodes = index['nodes']
    meta = index['meta']

    by_type = defaultdict(list)
    orphans = []
    all_targets = set()

    for comp_name, node in nodes.items():
        by_type[node['type']].append(comp_name)
        for dep in node['deps']:
            all_targets.add(dep['target'])

    for comp_name in nodes.keys():
        if comp_name not in all_targets:
            orphans.append(comp_name)

    summary = f"""# Vlocity/OmniStudio Dependency Index Summary

**Generated:** {meta['generated_at']}
**Vlocity Directory:** {meta['vlocity_dir']}
**Total Components:** {meta['component_count']}

## Component Breakdown

"""
    for comp_type in sorted(by_type.keys()):
        components = by_type[comp_type]
        summary += f"- **{comp_type}:** {len(components)} components\n"

    summary += f"\n## Entry Points (Top-Level Components)\n\n"
    summary += f"**Orphaned/Unreferenced:** {len(orphans)} components\n\n"
    for comp_name in sorted(orphans)[:10]:
        summary += f"- {comp_name}\n"
    if len(orphans) > 10:
        summary += f"- ... and {len(orphans) - 10} more\n"

    summary_file = os.path.join(output_dir, 'summary.md')
    with open(summary_file, 'w') as f:
        f.write(summary)

def traverse_element(index, element_name, depth=None, visited=None):
    """Recursively traverse dependencies for an element."""
    if visited is None:
        visited = set()

    if element_name in visited:
        return f"[CIRCULAR → {element_name}]"

    if element_name not in index['nodes']:
        return f"[NOT FOUND: {element_name}]"

    visited.add(element_name)

    node = index['nodes'][element_name]
    result = {
        'name': element_name,
        'type': node['type'],
        'deps': []
    }

    if depth is None or depth > 0:
        next_depth = None if depth is None else depth - 1
        for dep in node['deps']:
            target = dep['target']
            if target not in visited:
                result['deps'].append({
                    'target': target,
                    'dep_type': dep['dep_type'],
                    'via': dep.get('via_element', dep.get('via_field', '')),
                    'children': traverse_element(index, target, next_depth, visited.copy())
                })
            else:
                result['deps'].append({
                    'target': target,
                    'dep_type': dep['dep_type'],
                    'via': dep.get('via_element', dep.get('via_field', '')),
                    'circular': True
                })

    visited.discard(element_name)
    return result

def print_tree(node, depth=0, max_depth=None):
    """Print tree structure."""
    indent = "  " * depth
    name = node['name'] if isinstance(node, dict) else str(node)

    if isinstance(node, str):
        print(f"{indent}{node}")
        return

    comp_type = node.get('type', 'Unknown')
    print(f"{indent}- {name} [{comp_type}]")

    if max_depth is not None and depth >= max_depth:
        return

    for dep in node.get('deps', []):
        if dep.get('circular'):
            print(f"{indent}  → {dep['target']} [CIRCULAR]")
        else:
            print_tree(dep['children'], depth + 1, max_depth)

def derive_rest_name(url):
    """Derive a readable name from REST endpoint URL."""
    if not url:
        return "RESTEndpoint"
    # Extract meaningful parts from URL
    # /services/availability/ -> AvailabilityService
    # /proxy/outbound-salesforce/vouchers/%serviceReference%/expiry/?format=json -> VouchersExpiry
    # /services/%AssetDetails:ServiceReference%/stop-payment -> StopPayment

    # Remove query string and trailing slash
    path = re.sub(r'\?.*$', '', url)
    path = path.rstrip('/')

    # Split on slashes and get non-parameter parts
    parts = [p for p in path.split('/') if p and not p.startswith('%') and not p.startswith(':')]

    if not parts:
        return "RESTEndpoint"

    # Take last 1-2 parts and titlecase them
    name_parts = parts[-2:] if len(parts) > 1 else parts[-1:]
    name = ''.join(word.capitalize() for word in name_parts if word)
    return name or "RESTEndpoint"

def sanitize_node_id(node_name):
    """Sanitize node name for Mermaid diagram."""
    if not node_name:
        return "UNKNOWN"
    # Check if it looks like a REST endpoint (contains special chars)
    if any(char in node_name for char in ['/', '%', '?', '&', ':', '#', '@', '$']):
        return None  # Mark for mapping
    # Remove/replace problematic characters for valid Mermaid IDs
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', node_name)
    return sanitized

def build_dependency_dag(node, all_edges=None, visited_nodes=None):
    """Build a deduplicated directed acyclic graph of all dependencies."""
    if all_edges is None:
        all_edges = set()
    if visited_nodes is None:
        visited_nodes = set()

    if isinstance(node, str) or not isinstance(node, dict):
        return (all_edges, visited_nodes)

    name = node['name']
    visited_nodes.add(name)

    for dep in node.get('deps', []):
        target = dep['target']
        all_edges.add((name, target, dep.get('dep_type', 'Unknown')))

        if not dep.get('circular') and isinstance(dep.get('children'), dict) and target not in visited_nodes:
            all_edges, visited_nodes = build_dependency_dag(dep['children'], all_edges, visited_nodes)

    return (all_edges, visited_nodes)

def generate_mermaid(node, visited=None, level=0, endpoint_map=None):
    """Generate Mermaid diagram for traversal. Returns (diagram_code, endpoint_map)."""
    if visited is None:
        visited = set()
    if endpoint_map is None:
        endpoint_map = {}

    # Handle circular references (string return)
    if isinstance(node, str):
        return ("", endpoint_map)

    # Build deduplicated DAG
    edges, nodes = build_dependency_dag(node)

    # Sanitize all node IDs and build node definitions
    node_map = {}
    diagram = ""

    # Track all nodes including targets from edges
    all_unique_nodes = nodes.copy()
    for source, target, _ in edges:
        all_unique_nodes.add(source)
        all_unique_nodes.add(target)

    for node_name in sorted(all_unique_nodes):
        node_id = sanitize_node_id(node_name)
        if node_id is None:
            # Derive readable name from REST endpoint
            readable_name = derive_rest_name(node_name)
            # Handle name collisions by adding suffix
            node_id = readable_name
            counter = 1
            while node_id in [v for v in node_map.values()] or node_id in endpoint_map:
                node_id = f"{readable_name}_{counter}"
                counter += 1
            endpoint_map[node_id] = node_name
        node_map[node_name] = node_id

        # Get component type from original node
        comp_type = "REST API" if sanitize_node_id(node_name) is None else "Unknown"
        if node_name == node.get('name'):
            comp_type = node.get('type', 'Unknown')

        diagram += f"    {node_id}[\"{node_id}<br/>{comp_type}\"]\n"

    # Add edges between nodes (deduplicated)
    added_edges = set()
    for source, target, dep_type in sorted(edges):
        source_id = node_map.get(source)
        target_id = node_map.get(target)

        if source_id and target_id:
            edge_key = (source_id, target_id)
            if edge_key not in added_edges:
                diagram += f"    {source_id} --> {target_id}\n"
                added_edges.add(edge_key)

    return (diagram, endpoint_map)

def command_init(vlocity_dir):
    """Initialize full index."""
    if not os.path.isdir(vlocity_dir):
        print(f"Error: Directory not found: {vlocity_dir}", file=sys.stderr)
        sys.exit(1)

    output_dir = os.path.join(vlocity_dir, '..', 'dependency-index')
    index = build_full_index(vlocity_dir, output_dir)
    print(f"✓ Index created: {os.path.join(output_dir, 'index.json')}")
    print(f"✓ Summary created: {os.path.join(output_dir, 'summary.md')}")
    print(f"✓ Total components indexed: {index['meta']['component_count']}")

def command_element(index_path, element_name, depth=None, all_deps=False):
    """Traverse a specific element."""
    if not os.path.isfile(index_path):
        print(f"Error: Index file not found: {index_path}", file=sys.stderr)
        sys.exit(1)

    index = load_json(index_path)
    if not index:
        print(f"Error: Failed to load index", file=sys.stderr)
        sys.exit(1)

    if element_name not in index['nodes']:
        print(f"Error: Element not found: {element_name}", file=sys.stderr)
        sys.exit(1)

    max_depth = None if all_deps else depth
    tree = traverse_element(index, element_name, max_depth)

    print(f"\n--- Dependency Tree: {element_name} ---\n")
    print_tree(tree)

    diagram_code, endpoint_map = generate_mermaid(tree)
    if diagram_code:
        print(f"\n--- Mermaid Diagram ---\n")
        print("graph TD")
        print(diagram_code)
        if endpoint_map:
            print("\n--- REST Endpoint Reference ---\n")
            for node_id, url in sorted(endpoint_map.items()):
                print(f"{node_id}: {url}")

def parse_ip_steps(comp_path):
    """Parse Integration Procedure steps in execution order."""
    steps = []
    step_files = []

    # Collect all step element files
    for root, dirs, files in os.walk(comp_path):
        for file in files:
            if '_Element_' in file and file.endswith('.json') and not file.endswith('_DataPack.json'):
                step_files.append(file)

    # Sort by filename to get consistent order (approximates execution order)
    for file in sorted(step_files):
        elem_path = os.path.join(comp_path, file)
        data = load_json(elem_path)
        if data:
            # Get name and type, handling both managed and native schemas
            step_name = data.get('Name') or data.get('name', 'Unknown')
            step_type = data.get('%vlocity_namespace%__Type__c') or data.get('Type') or data.get('type', 'Unknown')

            # Extract what this step calls
            calls = []
            target = get_target(data)
            if target:
                calls.append({
                    'target': target,
                    'type': step_type,
                    'field': 'target'
                })

            # Get hidden dependencies
            hidden = get_hidden_dr_deps(data)
            for dep in hidden:
                calls.append({
                    'target': dep['target'],
                    'type': dep['dep_type'],
                    'field': dep['via_field']
                })

            steps.append({
                'name': step_name,
                'type': step_type,
                'calls': calls,
                'order': len(steps)
            })

    return steps

def generate_flow_diagram_with_nesting(comp_name, comp_path, index):
    """Generate hierarchical component-flow diagram with nested subgraphs.

    For each called IP, creates a subgraph showing what that IP calls.
    Other components appear inline. Shows full hierarchy of dependencies.
    """
    steps = parse_ip_steps(comp_path)

    if not steps:
        return None

    # Extract unique components and their call order
    component_flow = []
    seen_components = set()

    for step in steps:
        for call in step['calls']:
            target = call['target']
            if target not in seen_components:
                component_flow.append({
                    'name': target,
                    'type': call['type'],
                    'called_by': step['name']
                })
                seen_components.add(target)

    if not component_flow:
        return None

    # Build hierarchical flowchart with subgraphs
    diagram = "flowchart TD\n"
    diagram += f"    Start([{comp_name}])\n"

    prev_node = "Start"
    subgraph_counter = 0

    for i, comp in enumerate(component_flow):
        comp_name_val = comp['name']
        comp_type = comp['type']
        comp_id_safe = sanitize_node_id(comp_name_val)
        if comp_id_safe is None:
            comp_id_safe = f"comp{i}"

        # Check if this component is an IntegrationProcedure - if so, create a subgraph
        is_ip = 'Integration' in comp_type
        if is_ip and comp_name_val in index.get('nodes', {}):
            # Create subgraph for nested IP
            subgraph_id = f"sg{subgraph_counter}"
            subgraph_counter += 1
            ip_deps = index['nodes'][comp_name_val].get('deps', [])

            diagram += f"    subgraph {subgraph_id}[\"{comp_name_val}\"]\n"

            # Add child components to subgraph
            child_nodes = []
            for dep in ip_deps:
                dep_target = dep['target']
                dep_type = dep['dep_type']
                dep_id = sanitize_node_id(dep_target)
                if dep_id is None:
                    dep_id = f"dep_{len(child_nodes)}"

                dep_name_short = dep_target[:30]
                diagram += f"        {dep_id}[\"{dep_name_short}<br/>{dep_type[:20]}\"]\n"
                child_nodes.append(dep_id)

            # Connect child nodes in order
            for j in range(len(child_nodes) - 1):
                diagram += f"        {child_nodes[j]} --> {child_nodes[j + 1]}\n"

            diagram += f"    end\n"
            diagram += f"    {prev_node} --> {subgraph_id}\n"
            prev_node = subgraph_id
        else:
            # Regular component (not an IP or IP not in index)
            comp_name_short = comp_name_val[:35]
            diagram += f"    {comp_id_safe}[\"{comp_name_short}<br/>{comp_type[:20]}\"]\n"
            diagram += f"    {prev_node} --> {comp_id_safe}\n"
            prev_node = comp_id_safe

    diagram += f"    {prev_node} --> End([End])\n"

    return diagram

def generate_flow_diagram(comp_name, comp_path):
    """Generate a component-flow diagram for an Integration Procedure.

    Groups steps by the components they interact with, showing data flow
    through actual called components rather than internal steps.
    """
    steps = parse_ip_steps(comp_path)

    if not steps:
        return None

    # Extract unique components and their call order
    component_flow = []
    seen_components = set()

    for step in steps:
        for call in step['calls']:
            target = call['target']
            if target not in seen_components:
                component_flow.append({
                    'name': target,
                    'type': call['type'],
                    'called_by': step['name']
                })
                seen_components.add(target)

    if not component_flow:
        return None

    # Build component-level flowchart with subgraphs for logical blocks
    diagram = "flowchart TD\n"
    diagram += f"    Start([{comp_name}])\n"

    prev_node = "Start"
    for i, comp in enumerate(component_flow):
        comp_id = f"comp{i}"
        comp_name_short = comp['name'][:35]
        comp_type = comp['type'][:30]

        # Sanitize node ID for Mermaid
        comp_id_safe = sanitize_node_id(comp['name'])
        if comp_id_safe is None:
            comp_id_safe = f"comp{i}"

        diagram += f"    {comp_id_safe}[\"{comp_name_short}<br/>{comp_type}\"]\n"
        diagram += f"    {prev_node} --> {comp_id_safe}\n"

        prev_node = comp_id_safe

    diagram += f"    {prev_node} --> End([End])\n"

    return diagram

def command_flow(vlocity_dir, element_name, output_dir, index_path=None):
    """Generate flow diagram for an Integration Procedure.

    Shows component-level data flow with hierarchical nesting for called IPs.
    If index_path provided, uses it to show nested IP dependencies in subgraphs.
    """
    components = discover_components(vlocity_dir)

    if element_name not in components:
        print(f"Error: Component not found: {element_name}", file=sys.stderr)
        sys.exit(1)

    comp_info = components[element_name]
    comp_path = comp_info['path']
    comp_type = comp_info['type']

    if comp_type != 'IntegrationProcedure':
        print(f"Error: Flow diagram only supported for IntegrationProcedure (this is {comp_type})", file=sys.stderr)
        sys.exit(1)

    # Try to load index for nested IP details
    index = None
    if index_path and os.path.isfile(index_path):
        index = load_json(index_path)

    # Generate flow diagram with nesting if index available
    if index:
        flow_diagram = generate_flow_diagram_with_nesting(element_name, comp_path, index)
    else:
        flow_diagram = generate_flow_diagram(element_name, comp_path)

    if not flow_diagram:
        print(f"Error: Could not generate flow diagram for {element_name}", file=sys.stderr)
        sys.exit(1)

    doc = f"""# {element_name} - Component Flow

**Type:** {comp_type}
**Folder:** {comp_info.get('path', 'Unknown')}

## Component Data Flow

Shows the flow through called components in execution order.
Integration Procedures are shown with their nested child components in subgraph blocks.

```mermaid
{flow_diagram}```

"""

    os.makedirs(output_dir, exist_ok=True)
    doc_file = os.path.join(output_dir, f"{element_name}-flow.md")
    with open(doc_file, 'w') as f:
        f.write(doc)

    print(f"✓ Flow diagram generated: {doc_file}")

def command_document(index_path, element_name, output_dir):
    """Generate full journey documentation."""
    if not os.path.isfile(index_path):
        print(f"Error: Index file not found: {index_path}", file=sys.stderr)
        sys.exit(1)

    index = load_json(index_path)
    if not index:
        print(f"Error: Failed to load index", file=sys.stderr)
        sys.exit(1)

    if element_name not in index['nodes']:
        print(f"Error: Element not found: {element_name}", file=sys.stderr)
        sys.exit(1)

    node = index['nodes'][element_name]
    tree = traverse_element(index, element_name, None)

    diagram_code, endpoint_map = generate_mermaid(tree)

    # Get vlocity directory and construct component path for field extraction
    vlocity_dir = index.get('meta', {}).get('vlocity_dir')
    component_path = None
    if vlocity_dir:
        component_path = os.path.join(vlocity_dir, node['folder'])

    doc = f"""# {element_name}

**Type:** {node['type']}
**Schema:** {node['schema']}
**Folder:** {node['folder']}

## Architecture

```mermaid
graph TD
{diagram_code}```

"""

    # Add REST endpoint reference if needed
    if endpoint_map:
        doc += """## REST Endpoint Reference

| ID | Endpoint |
|----|----------|
"""
        for node_id, url in sorted(endpoint_map.items()):
            doc += f"| {node_id} | `{url}` |\n"
        doc += "\n"

    # Extract and add data flow information
    if component_path and os.path.isdir(component_path):
        field_data = extract_field_mappings(element_name, component_path, node['type'], node['schema'])
        if field_data:
            doc += "## Data Flow\n\n"
            if field_data['mappings']:
                doc += "**Field Mappings:**\n\n"
                doc += "| Input Field | Input Type | Output Field | Output Type |\n"
                doc += "|-------------|-----------|--------------|-------------|\n"
                for mapping in field_data['mappings']:
                    input_field = mapping.get('input', '')
                    output_field = mapping.get('output', '')
                    source = mapping.get('source', 'JSON')
                    target = mapping.get('target', 'JSON')
                    doc += f"| {input_field} | {source} | {output_field} | {target} |\n"
                doc += "\n"

            if field_data['elements']:
                doc += "**Element Bindings:**\n\n"
                doc += "| Element | Type | Sends | Receives At |\n"
                doc += "|---------|------|-------|-------------|\n"
                for elem in field_data['elements']:
                    elem_name = elem.get('name', 'Unknown')
                    elem_type = elem.get('type', 'Unknown')
                    sends = elem.get('sends', {})
                    receives = elem.get('receives_at', '')

                    # Format sends for display
                    if sends and isinstance(sends, dict):
                        sends_str = ', '.join([f"`{k}: {v}`" for k, v in list(sends.items())[:3]])
                        if len(sends) > 3:
                            sends_str += f", ... +{len(sends) - 3}"
                    elif sends:
                        sends_str = str(sends)[:50]
                    else:
                        sends_str = '—'

                    doc += f"| {elem_name} | {elem_type} | {sends_str} | {receives} |\n"
                doc += "\n"

    doc += f"## Dependencies\n\nLevel 0: {element_name}\n\n"

    # Collect all dependencies and organize by type
    all_deps = set()
    def collect_deps(t):
        if not isinstance(t, dict):
            return
        for dep in t.get('deps', []):
            all_deps.add((dep['target'], dep['dep_type']))
            if not dep.get('circular') and isinstance(dep.get('children'), dict):
                collect_deps(dep['children'])

    collect_deps(tree)

    if all_deps:
        doc += "\nAll Dependencies:\n\n"
        doc += "| Component | Type |\n"
        doc += "|-----------|------|\n"
        for comp_name, comp_type in sorted(all_deps):
            doc += f"| {comp_name} | {comp_type} |\n"

    os.makedirs(output_dir, exist_ok=True)
    doc_file = os.path.join(output_dir, f"{element_name}-journey.md")
    with open(doc_file, 'w') as f:
        f.write(doc)

    print(f"✓ Documentation generated: {doc_file}")

def build_levels(tree, level=0, levels=None):
    """Build level-by-level structure."""
    if levels is None:
        levels = defaultdict(list)

    levels[level].append(tree)

    for dep in tree.get('deps', []):
        if not dep.get('circular') and 'children' in dep:
            build_levels(dep['children'], level + 1, levels)

    return levels

def command_generate_all(vlocity_dir, output_base_dir):
    """Generate complete documentation: index, journeys, and flows for all IPs."""
    print(f"📚 Generating complete documentation for: {vlocity_dir}\n")

    # Step 1: Build index
    print("1️⃣ Building dependency index...")
    index_dir = os.path.join(output_base_dir, "dependency-index")
    index = build_full_index(vlocity_dir, index_dir)
    index_path = os.path.join(index_dir, "index.json")
    print(f"✓ Index built: {index_path}")
    print(f"  Total components: {index['meta']['component_count']}")

    # Step 2: Generate journeys and flows for all IPs
    print("\n2️⃣ Generating journeys and flows for Integration Procedures...")
    journeys_dir = os.path.join(index_dir, "journeys")
    flows_dir = os.path.join(index_dir, "flows")
    os.makedirs(journeys_dir, exist_ok=True)
    os.makedirs(flows_dir, exist_ok=True)

    components = discover_components(vlocity_dir)
    ip_count = 0
    for comp_name, node in sorted(index['nodes'].items()):
        if node['type'] == 'IntegrationProcedure':
            ip_count += 1
            # Generate journey
            tree = traverse_element(index, comp_name, None)
            diagram_code, endpoint_map = generate_mermaid(tree)

            journey_doc = f"""# {comp_name}

**Type:** {node['type']}
**Schema:** {node['schema']}
**Folder:** {node['folder']}

## Architecture

```mermaid
graph TD
{diagram_code}```

"""
            if endpoint_map:
                journey_doc += """## REST Endpoint Reference

| ID | Endpoint |
|----|----------|
"""
                for node_id, url in sorted(endpoint_map.items()):
                    journey_doc += f"| {node_id} | `{url}` |\n"
                journey_doc += "\n"

            # Extract and add data flow information
            comp_info = components.get(comp_name, {})
            comp_path = comp_info.get('path')
            if comp_path and os.path.isdir(comp_path):
                field_data = extract_field_mappings(comp_name, comp_path, node['type'], node['schema'])
                if field_data:
                    journey_doc += "## Data Flow\n\n"
                    if field_data['mappings']:
                        journey_doc += "**Field Mappings:**\n\n"
                        journey_doc += "| Input Field | Input Type | Output Field | Output Type |\n"
                        journey_doc += "|-------------|-----------|--------------|-------------|\n"
                        for mapping in field_data['mappings']:
                            input_field = mapping.get('input', '')
                            output_field = mapping.get('output', '')
                            source = mapping.get('source', 'JSON')
                            target = mapping.get('target', 'JSON')
                            journey_doc += f"| {input_field} | {source} | {output_field} | {target} |\n"
                        journey_doc += "\n"

                    if field_data['elements']:
                        journey_doc += "**Element Bindings:**\n\n"
                        journey_doc += "| Element | Type | Sends | Receives At |\n"
                        journey_doc += "|---------|------|-------|-------------|\n"
                        for elem in field_data['elements']:
                            elem_name = elem.get('name', 'Unknown')
                            elem_type = elem.get('type', 'Unknown')
                            sends = elem.get('sends', {})
                            receives = elem.get('receives_at', '')

                            # Format sends for display
                            if sends and isinstance(sends, dict):
                                sends_str = ', '.join([f"`{k}: {v}`" for k, v in list(sends.items())[:3]])
                                if len(sends) > 3:
                                    sends_str += f", ... +{len(sends) - 3}"
                            elif sends:
                                sends_str = str(sends)[:50]
                            else:
                                sends_str = '—'

                            journey_doc += f"| {elem_name} | {elem_type} | {sends_str} | {receives} |\n"
                        journey_doc += "\n"

            all_deps = set()
            def collect_deps(t):
                if not isinstance(t, dict):
                    return
                for dep in t.get('deps', []):
                    all_deps.add((dep['target'], dep['dep_type']))
                    if not dep.get('circular') and isinstance(dep.get('children'), dict):
                        collect_deps(dep['children'])

            collect_deps(tree)

            if all_deps:
                journey_doc += "\n## All Dependencies:\n\n"
                journey_doc += "| Component | Type |\n"
                journey_doc += "|-----------|------|\n"
                for comp_dep, comp_type in sorted(all_deps):
                    journey_doc += f"| {comp_dep} | {comp_type} |\n"

            journey_file = os.path.join(journeys_dir, f"{comp_name}-journey.md")
            with open(journey_file, 'w') as f:
                f.write(journey_doc)

            # Generate flow (comp_path already extracted above)
            if comp_path:
                flow_diagram = generate_flow_diagram_with_nesting(comp_name, comp_path, index)
                if flow_diagram:
                    flow_doc = f"""# {comp_name} - Component Flow

**Type:** {node['type']}
**Folder:** {node['folder']}

## Component Data Flow

Shows the flow through called components in execution order.
Integration Procedures are shown with their nested child components in subgraph blocks.

```mermaid
{flow_diagram}```

"""
                    flow_file = os.path.join(flows_dir, f"{comp_name}-flow.md")
                    with open(flow_file, 'w') as f:
                        f.write(flow_doc)

    print(f"✓ Generated {ip_count} journey/flow pairs")

    # Step 3: Create analysis manifest
    print("\n3️⃣ Creating analysis manifest...")
    manifest = {
        'generated_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'vlocity_dir': vlocity_dir,
        'index_path': index_path,
        'total_components': index['meta']['component_count'],
        'integration_procedures': ip_count,
        'journeys_dir': journeys_dir,
        'flows_dir': flows_dir,
        'documentation': {
            'index': index_path,
            'journeys': journeys_dir,
            'flows': flows_dir
        }
    }

    manifest_path = os.path.join(index_dir, "manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    print(f"✓ Analysis manifest created: {manifest_path}")

    # Step 4: Summary
    print("\n" + "="*60)
    print("📊 DOCUMENTATION GENERATION COMPLETE")
    print("="*60)
    print(f"Index:              {index_path}")
    print(f"Journeys:           {journeys_dir}/")
    print(f"Flows:              {flows_dir}/")
    print(f"Manifest:           {manifest_path}")
    print(f"\nTotal Components:   {index['meta']['component_count']}")
    print(f"IPs Documented:     {ip_count}")
    print("\n✅ Ready for LLM impact analysis!")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python build_index.py --init <vlocity_dir>")
        print("  python build_index.py --element <index.json> <element_name> [--depth N|--all]")
        print("  python build_index.py --document <index.json> <element_name> <output_dir>")
        print("  python build_index.py --flow <vlocity_dir> <element_name> <output_dir> [index_path]")
        print("  python build_index.py --generate-all <vlocity_dir> <output_dir>")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == '--init':
        if len(sys.argv) < 3:
            print("Usage: python build_index.py --init <vlocity_dir>", file=sys.stderr)
            sys.exit(1)
        vlocity_dir = sys.argv[2]
        command_init(vlocity_dir)

    elif cmd == '--element':
        if len(sys.argv) < 4:
            print("Usage: python build_index.py --element <index.json> <element_name> [--depth N|--all]", file=sys.stderr)
            sys.exit(1)
        index_path = sys.argv[2]
        element_name = sys.argv[3]
        depth = None
        all_deps = False

        if '--all' in sys.argv:
            all_deps = True
        elif '--depth' in sys.argv:
            idx = sys.argv.index('--depth')
            if idx + 1 < len(sys.argv):
                depth = int(sys.argv[idx + 1])
        else:
            depth = 2

        command_element(index_path, element_name, depth, all_deps)

    elif cmd == '--document':
        if len(sys.argv) < 5:
            print("Usage: python build_index.py --document <index.json> <element_name> <output_dir>", file=sys.stderr)
            sys.exit(1)
        index_path = sys.argv[2]
        element_name = sys.argv[3]
        output_dir = sys.argv[4]
        command_document(index_path, element_name, output_dir)

    elif cmd == '--flow':
        if len(sys.argv) < 5:
            print("Usage: python build_index.py --flow <vlocity_dir> <element_name> <output_dir> [index_path]", file=sys.stderr)
            sys.exit(1)
        vlocity_dir = sys.argv[2]
        element_name = sys.argv[3]
        output_dir = sys.argv[4]
        index_path = sys.argv[5] if len(sys.argv) > 5 else None
        command_flow(vlocity_dir, element_name, output_dir, index_path)

    elif cmd == '--generate-all':
        if len(sys.argv) < 4:
            print("Usage: python build_index.py --generate-all <vlocity_dir> <output_dir>", file=sys.stderr)
            sys.exit(1)
        vlocity_dir = sys.argv[2]
        output_dir = sys.argv[3]
        command_generate_all(vlocity_dir, output_dir)

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
