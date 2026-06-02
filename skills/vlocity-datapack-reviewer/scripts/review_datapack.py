import json
import sys
import os
import re

# Standard Vlocity/OmniStudio namespaces
NAMESPACE_PLACEHOLDERS = ["%vlocity_namespace%", "vlocity_cmt", "vlocity_ins", "vlocity_ps"]

# Salesforce ID regex (15 or 18 characters)
ID_REGEX = r'\b[0-9a-zA-Z]{15}(?:[0-9a-zA-Z]{3})?\b'

# Metadata keys to ignore for hardcoded ID checks
IGNORE_KEYS = [
    "VlocityMatchingRecordSourceKey", "VlocityRecordSourceKey", "Name", "name",
    "ParentElementName", "ParentElementId", "OmniProcessId", "OmniDataTransformationId",
    "Order", "order", "VlocityDataPackType", "VlocityRecordSObjectType"
]

def check_hardcoded_ids(data, findings, path=""):
    if isinstance(data, dict):
        for k, v in data.items():
            if k in IGNORE_KEYS: continue
            new_path = f"{path}.{k}" if path else k
            if isinstance(v, str):
                if re.search(ID_REGEX, v) and not (v.startswith("%") and v.endswith("%")):
                    # Heuristic: standard IDs usually start with '00' (Account, Contact), '02' (Asset), '0Q' (Quote), etc.
                    if any(v.startswith(prefix) for prefix in ['001', '003', '02i', '0Q0', '0QL', '006']):
                        findings.append(f"Potential Hardcoded ID found at '{new_path}': {v}")
            check_hardcoded_ids(v, findings, new_path)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            check_hardcoded_ids(item, findings, f"{path}[{i}]")

def build_tree(elements):
    nodes = {ele["Name"]: {"data": ele, "children": []} for ele in elements if isinstance(ele, dict) and "Name" in ele}
    roots = []
    for name, node in nodes.items():
        parent_info = node["data"].get("ParentElementId")
        parent_name = parent_info.get("Name") if isinstance(parent_info, dict) else node["data"].get("ParentElementName")
        if parent_name and parent_name in nodes:
            nodes[parent_name]["children"].append(node)
        else:
            roots.append(node)
    return roots, nodes

def get_ancestor_types(node_name, nodes):
    ancestors = []
    curr = nodes.get(node_name)
    while curr:
        p_info = curr["data"].get("ParentElementId")
        p_name = p_info.get("Name") if isinstance(p_info, dict) else curr["data"].get("ParentElementName")
        if p_name and p_name in nodes:
            curr = nodes[p_name]
            ancestors.append(curr["data"].get("Type"))
        else:
            curr = None
    return ancestors

def review_ip(elements, findings):
    roots, nodes = build_tree(elements)
    has_response = False
    
    for name, node in nodes.items():
        ele = node["data"]
        ele_type = ele.get("Type")
        
        if ele_type == "Response Action": has_response = True
        
        if ele_type == "HTTP Action":
            ancestors = get_ancestor_types(name, nodes)
            if "Try Catch Block" not in ancestors:
                findings.append(f"High Risk: HTTP Action '{name}' is not wrapped in a Try-Catch block.")
        
        if ele_type == "Remote Action":
            ancestors = get_ancestor_types(name, nodes)
            if "Try Catch Block" not in ancestors:
                findings.append(f"Medium Risk: Remote Action '{name}' is not wrapped in a Try-Catch block.")

    if not has_response:
        findings.append("Architectural Gap: Integration Procedure missing 'Response Action'.")

def review_dataraptor(elements, findings):
    for item in elements:
        if not isinstance(item, dict): continue
        filter_val = item.get("Filter Value") or item.get("filterValue")
        if filter_val and "==" in filter_val:
            parts = filter_val.split("==")
            if len(parts) > 1:
                val = parts[1].strip().strip("'").strip('"')
                if val and not (val.startswith("%") and val.endswith("%")) and val.lower() not in ["true", "false", "null"]:
                    if re.search(ID_REGEX, val):
                        findings.append(f"High Risk: Hardcoded ID '{val}' used in DataRaptor filter.")
                    else:
                        findings.append(f"Low Risk: Literal value '{val}' used in filter. Ensure this shouldn't be dynamic.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python review_datapack.py <directory_path>")
        sys.exit(1)
        
    target_path = sys.argv[1]
    elements = []
    
    if os.path.isdir(target_path):
        for root, _, files in os.walk(target_path):
            for file in files:
                # Ignore test/sample data files
                if "SampleInputJson" in file or "InputJson" in file or "SampleInput" in file:
                    continue
                
                if file.endswith('.json') and ("_Element_" in file or "Items" in file or "_DataPack" in file):
                    try:
                        with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            if isinstance(data, list):
                                elements.extend(data)
                            elif data:
                                elements.append(data)
                    except: pass
    
    if not elements:
        return

    findings = []
    is_ip = any(isinstance(e, dict) and e.get("VlocityRecordSObjectType") == "OmniProcessElement" for e in elements)
    is_dr = any(isinstance(e, dict) and "OmniDataTransformItem" in str(e.get("VlocityRecordSObjectType", "")) for e in elements)
    
    comp_name = os.path.basename(target_path.rstrip('/'))
    
    if is_ip: review_ip(elements, findings)
    elif is_dr: review_dataraptor(elements, findings)
    
    for e in elements:
        check_hardcoded_ids(e, findings)
    
    unique_findings = list(set(findings))
    
    if unique_findings:
        print(f"--- Reviewing Vlocity Component: {comp_name} ---")
        for f in sorted(unique_findings):
            print(f"- [ ] {f}")

if __name__ == "__main__":
    main()
