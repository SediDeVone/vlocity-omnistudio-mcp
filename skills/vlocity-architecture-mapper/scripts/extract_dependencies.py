import json
import sys
import os
import re

# Standard Vlocity/OmniStudio namespaces and placeholders
NAMESPACE_PLACEHOLDERS = ["%vlocity_namespace%", "vlocity_cmt", "vlocity_ins", "vlocity_ps"]

# Comprehensive list of OmniStudio element types
CONTAINER_TYPES = [
    "Block", "Try Catch Block", "Conditional Block", "Step", 
    "Loop Block", "Type Ahead Block", "Edit Block", "Input Block", "Section", "Group"
]

ACTION_TYPES = [
    "Integration Procedure Action", "DataRaptor Extract Action", 
    "DataRaptor Post Action", "DataRaptor Turbo Action", "DataRaptor Transform Action",
    "Remote Action", "HTTP Action", "OmniScript", "Calculation Procedure Action", 
    "Matrix Action", "Set Values", "Set Errors", "Response Action", 
    "Delete Action", "Batch Action", "Navigate Action", "Validation", 
    "Formula", "Email Action", "DocuSign Action", "PDF Action", "Rest Action"
]

def load_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def clean_namespace(val):
    if not val or not isinstance(val, str):
        return val
    for p in NAMESPACE_PLACEHOLDERS:
        val = val.replace(p, "").strip(".")
    return val.strip(".")

def get_target(data):
    ele_type = data.get("Type") or data.get("type")
    # Handle different property set names across Vlocity versions
    props = data.get("PropertySetConfig") or data.get("propertySetConfig") or data.get("PropertySetMap") or {}
    
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

def build_tree(elements):
    # Standard Vlocity DataPack structure uses 'Name' or 'name'
    nodes = {}
    for ele in elements:
        name = ele.get("Name") or ele.get("name")
        if name:
            nodes[name] = {"data": ele, "children": []}
            
    roots = []

    for name, node in nodes.items():
        data = node["data"]
        # Find parent reference
        parent_info = data.get("ParentElementId")
        parent_name = None
        if parent_info and isinstance(parent_info, dict):
            parent_name = parent_info.get("Name") or parent_info.get("name")
        
        if not parent_name:
            parent_name = data.get("ParentElementName") or data.get("parentElementName")

        if parent_name and parent_name in nodes:
            nodes[parent_name]["children"].append(node)
        else:
            roots.append(node)
    
    def sort_key(n):
        # Sort by Order (Vlocity standard) if it exists
        order = n["data"].get("Order") or n["data"].get("order") or 0
        name = n["data"].get("Name") or n["data"].get("name") or ""
        return order, name

    roots.sort(key=sort_key)
    for node in nodes.values():
        node["children"].sort(key=sort_key)
        
    return roots

def print_tree(node, depth=0, deep_mode=False):
    ele = node["data"]
    ele_type = ele.get("Type") or ele.get("type", "Unknown")
    name = ele.get("Name") or ele.get("name", "Unknown")
    target = get_target(ele)
    
    indent = "  " * depth
    
    is_action = ele_type in ACTION_TYPES
    is_container = ele_type in CONTAINER_TYPES
    
    if is_action:
        target_str = f" -> {target}" if target else ""
        print(f"{indent}- [{ele_type}] '{name}'{target_str}")
    elif is_container:
        print(f"{indent}+ [{ele_type}] '{name}'")
    elif deep_mode:
        print(f"{indent}. [{ele_type}] '{name}'")
    
    for child in node["children"]:
        print_tree(child, depth + 1, deep_mode)

def parse_calc_proc(target_path):
    steps_file = None
    if os.path.isdir(target_path):
        for f in os.listdir(target_path):
            if "Steps" in f and f.endswith(".json"):
                steps_file = os.path.join(target_path, f)
                break
    
    if not steps_file: return
        
    data = load_json(steps_file)
    if not data or not isinstance(data, list): return
        
    print(f"\n[Calculation Procedure Steps]")
    # Handle both namespaced and non-namespaced fields
    for step in sorted(data, key=lambda x: x.get("vlocity_cmt__Sequence__c") or x.get("Sequence__c") or 0):
        action = step.get("vlocity_cmt__Action__c") or step.get("Action__c") or "Unknown"
        formula = step.get("vlocity_cmt__CalculationFormula__c") or step.get("CalculationFormula__c") or ""
        print(f"  - Action: {action}")
        if formula: print(f"    Formula: {formula}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_dependencies.py <path> [--deep]")
        sys.exit(1)
        
    target_path = sys.argv[1]
    deep_mode = "--deep" in sys.argv
    elements = []
    
    if os.path.isdir(target_path):
        # Detect Calculation Procedure folders
        if "CalculationProcedure" in target_path:
            print(f"--- Vlocity Calculation Procedure: {os.path.basename(target_path.rstrip('/'))} ---")
            parse_calc_proc(target_path)
            return

        for root, _, files in os.walk(target_path):
            for file in files:
                # Element files are standard for exploded DataPacks
                if file.endswith('.json') and ("_Element_" in file or "OmniProcessElement" in file):
                    data = load_json(os.path.join(root, file))
                    if data: elements.append(data)
    elif os.path.isfile(target_path):
        data = load_json(target_path)
        if data:
            # Handle large single-file DataPacks
            if isinstance(data, dict) and "VlocityDataPackData" in data:
                # Some DataPacks wrap elements in a specific key
                sub_data = data["VlocityDataPackData"].get("OmniProcessElement") or data["VlocityDataPackData"].get("Element")
                if isinstance(sub_data, list): elements.extend(sub_data)
                else: elements.append(data)
            else:
                elements.append(data)
        
    if not elements:
        print(f"--- No Vlocity elements found in {target_path} ---")
        return

    print(f"--- Vlocity Architecture Tree: {os.path.basename(target_path.rstrip('/'))} ---")
    tree = build_tree(elements)
    for root_node in tree:
        print_tree(root_node, 0, deep_mode)

if __name__ == "__main__":
    main()
