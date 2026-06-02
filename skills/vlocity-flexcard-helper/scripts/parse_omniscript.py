#!/usr/bin/env python3
"""
parse_omniscript.py
Parses a local Vlocity OmniScript directory containing _DataPack.json and
individual _Element_*.json files to output a structured human-readable breakdown
of the wizard's steps, inputs, formulas, and integration actions.
"""

import os
import sys
import json
import glob
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Parse local Vlocity OmniScript files into structured summaries.")
    parser.add_argument("omniscript_dir", help="Path to the directory containing OmniScript files.")
    parser.add_argument("--deep", action="store_true", help="Include full details for inner element configurations.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    return parser.parse_args()

def load_datapack(dir_path):
    # Try finding _DataPack.json
    dp_paths = glob.glob(os.path.join(dir_path, "*_DataPack.json"))
    if not dp_paths:
        return None
    
    with open(dp_paths[0], 'r', encoding='utf-8') as f:
        return json.load(f)

def load_elements(dir_path):
    elements = []
    element_paths = glob.glob(os.path.join(dir_path, "*_Element_*.json"))
    
    for path in element_paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                elements.append(data)
        except Exception as e:
            print(f"Warning: Failed to load element {path}: {e}", file=sys.stderr)
            
    # Sort elements by Order (managed or native key)
    def get_order(elem):
        return elem.get("%vlocity_namespace%__Order__c") or elem.get("Order") or 0
    
    elements.sort(key=get_order)
    return elements

def get_property_set(elem):
    config = elem.get("%vlocity_namespace%__PropertySetConfig__c") or elem.get("PropertySetConfig") or {}
    if isinstance(config, str):
        try:
            config = json.loads(config)
        except:
            config = {}
    return config

def get_referenced_bundle_or_key(config, element_type):
    if "DataRaptor" in element_type:
        return config.get("bundle") or ""
    elif "Integration Procedure" in element_type:
        return config.get("integrationProcedureKey") or ""
    elif "Remote Action" in element_type:
        remote_class = config.get("remoteClass") or ""
        remote_method = config.get("remoteMethod") or ""
        if remote_class:
            return f"{remote_class}.{remote_method}"
    return ""

def summarize_omniscript(dir_path, deep_mode=False):
    dp = load_datapack(dir_path)
    if not dp:
        return {"error": f"No Vlocity OmniScript DataPack found in: {dir_path}"}
    
    # Root level fields
    name = dp.get("Name") or dp.get("Name__c") or ""
    os_type = dp.get("%vlocity_namespace%__Type__c") or dp.get("Type") or ""
    os_subtype = dp.get("%vlocity_namespace%__SubType__c") or dp.get("SubType") or ""
    os_language = dp.get("%vlocity_namespace%__Language__c") or dp.get("Language") or ""
    
    # Global PropertySet configuration
    raw_props = dp.get("%vlocity_namespace%__PropertySet__c") or dp.get("PropertySetConfig") or "{}"
    if isinstance(raw_props, str):
        try:
            global_props = json.loads(raw_props)
        except:
            global_props = {}
    else:
        global_props = raw_props
        
    elements = load_elements(dir_path)
    
    # Build tree
    steps = []
    actions_and_inputs = []
    
    steps_count = 0
    dr_calls = []
    ip_calls = []
    set_values_count = 0
    
    # Group elements by parent element
    parent_map = {}
    for elem in elements:
        parent_id = elem.get("%vlocity_namespace%__ParentElementId__c") or elem.get("ParentElementId")
        if parent_id:
            parent_name = parent_id.get("Name") if isinstance(parent_id, dict) else str(parent_id)
            if parent_name not in parent_map:
                parent_map[parent_name] = []
            parent_map[parent_name].append(elem)
            
    # Process steps and top level elements
    for elem in elements:
        parent_id = elem.get("%vlocity_namespace%__ParentElementId__c") or elem.get("ParentElementId")
        # Top-level elements have no parent element
        if not parent_id:
            elem_name = elem.get("Name") or elem.get("Name__c") or ""
            elem_type = elem.get("%vlocity_namespace%__Type__c") or elem.get("Type") or ""
            config = get_property_set(elem)
            
            show_formula = config.get("show") or ""
            ref = get_referenced_bundle_or_key(config, elem_type)
            
            if elem_type == "Step":
                steps_count += 1
                step_children = []
                
                # Fetch step children
                children = parent_map.get(elem_name, [])
                for child in children:
                    c_name = child.get("Name") or child.get("Name__c") or ""
                    c_type = child.get("%vlocity_namespace%__Type__c") or child.get("Type") or ""
                    c_config = get_property_set(child)
                    c_ref = get_referenced_bundle_or_key(c_config, c_type)
                    c_show = c_config.get("show") or ""
                    
                    if "DataRaptor" in c_type and c_ref:
                        dr_calls.append(c_ref)
                    elif "Integration Procedure" in c_type and c_ref:
                        ip_calls.append(c_ref)
                    elif c_type == "Set Values":
                        set_values_count += 1
                        
                    child_info = {
                        "name": c_name,
                        "type": c_type,
                        "reference": c_ref,
                        "show_condition": c_show
                    }
                    if deep_mode:
                        child_info["property_set"] = c_config
                    step_children.append(child_info)
                    
                step_info = {
                    "name": elem_name,
                    "type": "Step",
                    "label": config.get("label") or elem_name,
                    "children": step_children,
                    "show_condition": show_formula
                }
                steps.append(step_info)
            else:
                # Top-level non-step action (e.g., initial DRE or remote action)
                if "DataRaptor" in elem_type and ref:
                    dr_calls.append(ref)
                elif "Integration Procedure" in elem_type and ref:
                    ip_calls.append(ref)
                elif elem_type == "Set Values":
                    set_values_count += 1
                    
                action_info = {
                    "name": elem_name,
                    "type": elem_type,
                    "reference": ref,
                    "show_condition": show_formula
                }
                if deep_mode:
                    action_info["property_set"] = config
                actions_and_inputs.append(action_info)
                
    summary = {
        "omniscript": {
            "name": name,
            "type": os_type,
            "subtype": os_subtype,
            "language": os_language,
            "procedure_key": f"{os_type}_{os_subtype}"
        },
        "settings": {
            "allow_cancel": global_props.get("allowCancel", False),
            "allow_save_later": global_props.get("allowSaveForLater", False),
            "hide_step_chart": global_props.get("hideStepChart", False),
            "auto_focus": global_props.get("autoFocus", False)
        },
        "counts": {
            "steps": steps_count,
            "set_values": set_values_count,
            "dataraptor_calls": len(dr_calls),
            "ip_calls": len(ip_calls),
            "total_elements": len(elements)
        },
        "references": {
            "dataraptors": list(set(dr_calls)),
            "integration_procedures": list(set(ip_calls))
        },
        "structure": {
            "pre_step_actions": actions_and_inputs,
            "steps": steps
        }
    }
    return summary

def render_text_summary(summary):
    os_info = summary["omniscript"]
    counts = summary["counts"]
    settings = summary["settings"]
    refs = summary["references"]
    
    print("=" * 80)
    print(f" VLOCITY OMNISCRIPT SUMMARY: {os_info['name']}")
    print("=" * 80)
    print(f"Procedure Key: {os_info['procedure_key']}")
    print(f"Type:          {os_info['type']}")
    print(f"Subtype:       {os_info['subtype']}")
    print(f"Language:      {os_info['language']}")
    print("-" * 80)
    print("GLOBAL SETTINGS:")
    print(f"  Allow Cancel:       {settings['allow_cancel']}")
    print(f"  Allow Save Later:   {settings['allow_save_later']}")
    print(f"  Hide Step Chart:    {settings['hide_step_chart']}")
    print(f"  Auto Focus:         {settings['auto_focus']}")
    print("-" * 80)
    print("COMPONENTS COUNT:")
    print(f"  Steps (Pages):       {counts['steps']}")
    print(f"  Set Values Steps:    {counts['set_values']}")
    print(f"  DataRaptor Invocations: {counts['dataraptor_calls']}")
    print(f"  IP Invocations:      {counts['ip_calls']}")
    print(f"  Total Elements:      {counts['total_elements']}")
    print("-" * 80)
    
    if refs["dataraptors"]:
        print("REFERENCED DATARAPTORS:")
        for dr in refs["dataraptors"]:
            print(f"  - {dr}")
        print("-" * 80)
        
    if refs["integration_procedures"]:
        print("REFERENCED INTEGRATION PROCEDURES:")
        for ip in refs["integration_procedures"]:
            print(f"  - {ip}")
        print("-" * 80)

    struct = summary["structure"]
    if struct["pre_step_actions"]:
        print("INITIAL ACTIONS (Pre-Step):")
        for act in struct["pre_step_actions"]:
            ref_str = f" ({act['reference']})" if act["reference"] else ""
            print(f"  ⚡ [{act['type']}] {act['name']}{ref_str}")
        print("-" * 80)
        
    print("WIZARD STEPS & INPUT FLOW:")
    for idx, step in enumerate(struct["steps"], 1):
        print(f" 📦 Step {idx}: {step['name']} (Label: '{step['label']}')")
        if step["show_condition"]:
            print(f"    Cond: {step['show_condition']}")
        for child in step["children"]:
            ref_str = f" ➔ Ref: {child['reference']}" if child["reference"] else ""
            cond_str = f" [Cond: {child['show_condition']}]" if child["show_condition"] else ""
            print(f"    ├── 📝 [{child['type']}] {child['name']}{ref_str}{cond_str}")
    print("=" * 80)

def main():
    args = parse_args()
    if not os.path.isdir(args.omniscript_dir):
        print(f"Error: Directory '{args.omniscript_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    summary = summarize_omniscript(args.omniscript_dir, args.deep)
    
    if "error" in summary:
        print(f"Error: {summary['error']}", file=sys.stderr)
        sys.exit(1)
        
    if args.format == "json":
        print(json.dumps(summary, indent=2))
    else:
        render_text_summary(summary)

if __name__ == "__main__":
    main()
