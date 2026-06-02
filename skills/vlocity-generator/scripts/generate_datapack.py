#!/usr/bin/env python3
"""
Vlocity DataPack Generator
Generates schema-correct Vlocity JSON files for DataRaptors, Integration Procedures, and more.
Supports both managed (%vlocity_namespace%) and native (OmniProcess/OmniDataTransform) schema flavors.
"""
import argparse
import json
import os
import sys
import uuid
import glob
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

MANAGED_SCHEMA = {
    "dr_sobject": "%vlocity_namespace%__DRBundle__c",
    "dr_item_sobject": "%vlocity_namespace%__DRMapItem__c",
    "ip_sobject": "%vlocity_namespace%__OmniScript__c",
    "element_sobject": "%vlocity_namespace%__Element__c",
    "card_sobject": "%vlocity_namespace%__VlocityCard__c",
    "dr_name_field": "%vlocity_namespace%__DRMapName__c",
    "dr_type_field": "%vlocity_namespace%__Type__c",
    "dr_input_type_field": "%vlocity_namespace%__InputType__c",
    "dr_output_type_field": "%vlocity_namespace%__OutputType__c",
    "dr_input_json_field": "%vlocity_namespace%__InputJson__c",
    "dr_map_item_field": "%vlocity_namespace%__DRMapItem__c",
    "dr_sample_input_field": "%vlocity_namespace%__SampleInputJSON__c",
    "dr_batch_size_field": "%vlocity_namespace%__BatchSize__c",
    "dr_global_key_field": "%vlocity_namespace%__GlobalKey__c",
    "dr_interface_object_field": "%vlocity_namespace%__InterfaceObject__c",
    "dr_check_fls_field": "%vlocity_namespace%__CheckFieldLevelSecurity__c",
    "dr_ignore_errors_field": "%vlocity_namespace%__IgnoreErrors__c",
    "dr_rollback_field": "%vlocity_namespace%__RollbackOnError__c",
    "dr_overwrite_null_field": "%vlocity_namespace%__OverwriteAllNullValues__c",
    "dr_omp_sync_field": "%vlocity_namespace%__OMplusSyncEnabled__c",
    "ip_type_field": "%vlocity_namespace%__Type__c",
    "ip_subtype_field": "%vlocity_namespace%__SubType__c",
    "ip_language_field": "%vlocity_namespace%__Language__c",
    "ip_is_procedure_field": "%vlocity_namespace%__IsProcedure__c",
    "ip_is_lwc_field": "%vlocity_namespace%__IsLwcEnabled__c",
    "ip_is_reusable_field": "%vlocity_namespace%__IsReusable__c",
    "ip_is_test_field": "%vlocity_namespace%__IsTest__c",
    "ip_property_set_field": "%vlocity_namespace%__PropertySet__c",
    "ip_element_list_field": "%vlocity_namespace%__Element__c",
    "ip_procedure_key_field": "%vlocity_namespace%__ProcedureKey__c",
    "ip_omni_process_type_field": "%vlocity_namespace%__OmniProcessType__c",
    "ip_additional_info_field": "%vlocity_namespace%__AdditionalInformation__c",
    "ip_custom_js_field": "%vlocity_namespace%__CustomJavaScript__c",
    "elem_active_field": "%vlocity_namespace%__Active__c",
    "elem_type_field": "%vlocity_namespace%__Type__c",
    "elem_property_set_field": "%vlocity_namespace%__PropertySet__c",
    "elem_reusable_field": "%vlocity_namespace%__ReusableOmniScript__c",
    "elem_omniscript_id_field": "%vlocity_namespace%__OmniScriptId__c",
    # DR Item fields
    "item_domain_obj_api_name": "%vlocity_namespace%__DomainObjectAPIName__c",
    "item_domain_creation_order": "%vlocity_namespace%__DomainObjectCreationOrder__c",
    "item_domain_field_api": "%vlocity_namespace%__DomainObjectFieldAPIName__c",
    "item_filter_group": "%vlocity_namespace%__FilterGroup__c",
    "item_filter_operator": "%vlocity_namespace%__FilterOperator__c",
    "item_filter_value": "%vlocity_namespace%__FilterValue__c",
    "item_global_key": "%vlocity_namespace%__GlobalKey__c",
    "item_interface_field_api": "%vlocity_namespace%__InterfaceFieldAPIName__c",
    "item_lookup_order": "%vlocity_namespace%__InterfaceObjectLookupOrder__c",
    "item_interface_obj_name": "%vlocity_namespace%__InterfaceObjectName__c",
    "item_is_disabled": "%vlocity_namespace%__IsDisabled__c",
    "item_is_required_upsert": "%vlocity_namespace%__IsRequiredForUpsert__c",
    "item_map_id": "%vlocity_namespace%__MapId__c",
    "item_omp_sync": "%vlocity_namespace%__OMplusSyncEnabled__c",
    "item_upsert_key": "%vlocity_namespace%__UpsertKey__c",
}

NATIVE_SCHEMA = {
    "dr_sobject": "OmniDataTransform",
    "dr_item_sobject": "OmniDataTransformItem",
    "ip_sobject": "OmniProcess",
    "element_sobject": "OmniProcessElement",
    "card_sobject": "FlexCard",
    "dr_name_field": "Name",
    "dr_type_field": "Type",
    "dr_input_type_field": "InputType",
    "dr_output_type_field": "OutputType",
    "dr_input_json_field": "ExpectedInputJson",
    "dr_map_item_field": "OmniDataTransformItem",
    "dr_sample_input_field": "PreviewJsonData",
    "dr_batch_size_field": "BatchSize",
    "dr_global_key_field": "GlobalKey",
    "dr_interface_object_field": "SourceObject",
    "dr_check_fls_field": "IsFieldLevelSecurityEnabled",
    "dr_ignore_errors_field": "IsErrorIgnored",
    "dr_rollback_field": "IsRollbackOnError",
    "dr_overwrite_null_field": "IsNullInputsIncludedInOutput",
    "dr_omp_sync_field": None,  # Not used in native
    "ip_type_field": "Type",
    "ip_subtype_field": "SubType",
    "ip_language_field": "Language",
    "ip_is_procedure_field": "IsIntegrationProcedure",
    "ip_is_lwc_field": "IsWebCompEnabled",
    "ip_is_reusable_field": "IsOmniScriptEmbeddable",
    "ip_is_test_field": "IsTestProcedure",
    "ip_property_set_field": "PropertySetConfig",
    "ip_element_list_field": "OmniProcessElement",
    "ip_procedure_key_field": "OmniProcessKey",
    "ip_omni_process_type_field": "OmniProcessType",
    "ip_additional_info_field": "Description",
    "ip_custom_js_field": "CustomJavaScript",
    "elem_active_field": "IsActive",
    "elem_type_field": "Type",
    "elem_property_set_field": "PropertySetConfig",
    "elem_reusable_field": "IsOmniScriptEmbeddable",
    "elem_omniscript_id_field": "OmniProcessId",
    # DR Item fields
    "item_domain_obj_api_name": "OutputObjectName",
    "item_domain_creation_order": "OutputCreationSequence",
    "item_domain_field_api": "OutputFieldName",
    "item_filter_group": "FilterGroup",
    "item_filter_operator": "FilterOperator",
    "item_filter_value": "FilterValue",
    "item_global_key": "GlobalKey",
    "item_interface_field_api": "InputFieldName",
    "item_lookup_order": "InputObjectQuerySequence",
    "item_interface_obj_name": "InputObjectName",
    "item_is_disabled": "IsDisabled",
    "item_is_required_upsert": "IsRequiredForUpsert",
    "item_map_id": None,
    "item_omp_sync": None,
    "item_upsert_key": "IsUpsertKey",
}

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def detect_schema(vlocity_dir):
    """Detect managed vs native schema by scanning DataPack files."""
    for root, _, files in os.walk(vlocity_dir):
        for f in files:
            if f.endswith("_DataPack.json"):
                try:
                    with open(os.path.join(root, f), 'r', encoding='utf-8') as fh:
                        data = json.load(fh)
                    sobj = data.get("VlocityRecordSObjectType", "")
                    if "OmniProcess" in sobj or "OmniDataTransform" in sobj:
                        return "native"
                    if "%vlocity_namespace%" in sobj:
                        return "managed"
                except:
                    pass
    return "managed"  # Default to managed if cannot detect

def get_schema(flavor):
    return NATIVE_SCHEMA if flavor == "native" else MANAGED_SCHEMA

def make_global_key(name, suffix=""):
    """Generate a deterministic-looking global key."""
    import hashlib
    raw = f"{name}{suffix}{datetime.now().isoformat()}"
    h = hashlib.md5(raw.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

# ─────────────────────────────────────────────────────────────────────────────
# DATARAPTOR EXTRACT GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_dr_extract(name, sobject, fields, filters, schema_flavor, output_dir):
    """Generate all files for a DataRaptor Extract component."""
    s = get_schema(schema_flavor)
    os.makedirs(output_dir, exist_ok=True)

    # ── _DataPack.json ──────────────────────────────────────────────────────
    if schema_flavor == "managed":
        datapack = {
            s["dr_batch_size_field"]: "",
            s["dr_check_fls_field"]: False,
            "%vlocity_namespace%__CustomInputClass__c": "",
            "%vlocity_namespace%__CustomOutputClass__c": "",
            s["dr_map_item_field"]: f"{name}_Mappings.json",
            s["dr_name_field"]: name,
            "%vlocity_namespace%__DeleteOnSuccess__c": False,
            "%vlocity_namespace%__Description__c": "",
            s["dr_global_key_field"]: make_global_key(name),
            s["dr_ignore_errors_field"]: False,
            "%vlocity_namespace%__InputCustom__c": "",
            "%vlocity_namespace%__InputJson__c": f"{name}_InputJson.json",
            s["dr_input_type_field"]: "JSON",
            "%vlocity_namespace%__InputXml__c": "",
            s["dr_interface_object_field"]: "json",
            "%vlocity_namespace%__IsDefaultForInterface__c": False,
            "%vlocity_namespace%__IsProcessSuperBulk__c": False,
            s["dr_omp_sync_field"]: True,
            "%vlocity_namespace%__OuboundStagingObjectDataField__c": "",
            "%vlocity_namespace%__OutboundConfigurationField__c": "",
            "%vlocity_namespace%__OutboundConfigurationName__c": "",
            "%vlocity_namespace%__OutboundStagingObjectName__c": "",
            s["dr_output_type_field"]: "JSON",
            s["dr_overwrite_null_field"]: False,
            "%vlocity_namespace%__PreprocessorClassName__c": "",
            "%vlocity_namespace%__ProcessNowThreshold__c": "",
            "%vlocity_namespace%__RequiredPermission__c": "",
            s["dr_rollback_field"]: False,
            "%vlocity_namespace%__SalesforcePlatformCacheType__c": "",
            "%vlocity_namespace%__SampleInputCustom__c": "",
            s["dr_sample_input_field"]: f"{name}_SampleInputJson.json",
            "%vlocity_namespace%__SampleInputRows__c": "",
            "%vlocity_namespace%__SampleInputXML__c": "",
            "%vlocity_namespace%__TargetOutCustom__c": "",
            "%vlocity_namespace%__TargetOutDocuSignTemplateId__c": "",
            "%vlocity_namespace%__TargetOutJson__c": "",
            "%vlocity_namespace%__TargetOutPdfDocName__c": "",
            "%vlocity_namespace%__TargetOutXml__c": "",
            "%vlocity_namespace%__TimeToLiveMinutes__c": "",
            s["dr_type_field"]: "Extract",
            "%vlocity_namespace%__UseAssignmentRules__c": False,
            "%vlocity_namespace%__UseTranslations__c": False,
            "%vlocity_namespace%__XmlOutputSequence__c": "",
            "%vlocity_namespace%__XmlRemoveDeclaration__c": False,
            "Name": name,
            "VlocityDataPackType": "SObject",
            "VlocityRecordSObjectType": s["dr_sobject"],
            "VlocityRecordSourceKey": f"{s['dr_sobject']}/{name}",
        }
    else:
        datapack = {
            "BatchSize": "",
            "Description": "",
            "ExpectedInputJson": "",
            "ExpectedInputOtherData": "",
            "ExpectedInputXml": "",
            "ExpectedOutputJson": "",
            "ExpectedOutputOtherData": "",
            "ExpectedOutputXml": "",
            "GlobalKey": make_global_key(name),
            "InputParsingClass": "",
            "InputType": "JSON",
            "IsAssignmentRulesUsed": False,
            "IsDeletedOnSuccess": False,
            "IsErrorIgnored": False,
            "IsFieldLevelSecurityEnabled": False,
            "IsNullInputsIncludedInOutput": False,
            "IsProcessSuperBulk": False,
            "IsRollbackOnError": False,
            "IsSourceObjectDefault": False,
            "IsXmlDeclarationRemoved": False,
            "Name": name,
            "OmniDataTransformItem": f"{name}_Items.json",
            "OutputParsingClass": "",
            "OutputType": "JSON",
            "OverrideKey": "",
            "PreprocessorClassName": "",
            "PreviewJsonData": f"{name}_SampleInputJson.json",
            "PreviewOtherData": "",
            "PreviewSourceObjectData": "",
            "PreviewXmlData": "",
            "RequiredPermission": "",
            "ResponseCacheTtlMinutes": "",
            "ResponseCacheType": "",
            "SourceObject": "json",
            "SynchronousProcessThreshold": "",
            "TargetOutputDocumentIdentifier": "",
            "TargetOutputFileName": "",
            "Type": "Extract",
            "VersionNumber": 1,
            "VlocityDataPackType": "SObject",
            "VlocityRecordSObjectType": "OmniDataTransform",
            "VlocityRecordSourceKey": f"OmniDataTransform/{name}",
            "XmlOutputTagsOrder": "",
        }

    write_json(os.path.join(output_dir, f"{name}_DataPack.json"), datapack)

    # ── Mappings / Items ─────────────────────────────────────────────────────
    # Parse filter string e.g. "Id=ContextId,Status=Active"
    filter_items = []
    for fstr in filters:
        parts = fstr.split("=", 1)
        if len(parts) == 2:
            filter_items.append({"field": parts[0].strip(), "value": parts[1].strip()})

    # Parse field list
    field_list = [f.strip() for f in fields]

    mappings = []
    if schema_flavor == "managed":
        # Filter rows
        for i, fi in enumerate(filter_items):
            mappings.append({
                s["item_domain_obj_api_name"]: "json",
                s["item_domain_creation_order"]: 0,
                s["item_domain_field_api"]: sobject,
                s["item_filter_group"]: 0,
                s["item_filter_operator"]: "=",
                s["item_filter_value"]: fi["value"],
                s["item_global_key"]: make_global_key(name, f"filter{i}"),
                s["item_interface_field_api"]: fi["field"],
                s["item_lookup_order"]: 1,
                s["item_interface_obj_name"]: sobject,
                s["item_is_disabled"]: False,
                s["item_is_required_upsert"]: False,
                s["item_map_id"]: f"{name}Custom{1000 + i}",
                s["item_omp_sync"]: True,
                s["item_upsert_key"]: False,
                "Name": name,
                "VlocityDataPackType": "SObject",
                "VlocityRecordSObjectType": s["dr_item_sobject"],
            })
        # Output field rows
        for i, field in enumerate(field_list):
            mappings.append({
                s["item_domain_obj_api_name"]: "json",
                s["item_domain_creation_order"]: 0,
                s["item_domain_field_api"]: sobject,
                s["item_filter_group"]: 0,
                s["item_global_key"]: make_global_key(name, f"field{i}"),
                s["item_interface_field_api"]: f"{sobject}:{field}",
                s["item_lookup_order"]: 1,
                s["item_interface_obj_name"]: sobject,
                s["item_is_disabled"]: False,
                s["item_is_required_upsert"]: False,
                s["item_map_id"]: f"{name}Custom{2000 + i}",
                s["item_omp_sync"]: True,
                s["item_upsert_key"]: False,
                "Name": name,
                "VlocityDataPackType": "SObject",
                "VlocityRecordSObjectType": s["dr_item_sobject"],
            })
        write_json(os.path.join(output_dir, f"{name}_Mappings.json"), mappings)
    else:
        # Native schema items
        # Filter row: InputFieldName = SObject.Field, FilterOperator/Value set
        for i, fi in enumerate(filter_items):
            mappings.append({
                "FilterGroup": 0,
                "FilterOperator": "=",
                "FilterValue": fi["value"],
                "GlobalKey": make_global_key(name, f"filter{i}"),
                "InputFieldName": fi["field"],
                "InputObjectName": sobject,
                "InputObjectQuerySequence": 1,
                "IsDisabled": False,
                "IsRequiredForUpsert": False,
                "IsUpsertKey": False,
                "Name": name,
                "OmniDataTransformationId": {
                    "Name": name,
                    "VlocityDataPackType": "VlocityMatchingKeyObject",
                    "VlocityMatchingRecordSourceKey": f"OmniDataTransform/{name}",
                    "VlocityRecordSObjectType": "OmniDataTransform",
                },
                "OutputCreationSequence": i,
                "OutputFieldName": fi["field"],
                "OutputObjectName": "json",
                "VlocityDataPackType": "SObject",
                "VlocityRecordSObjectType": "OmniDataTransformItem",
            })
        for i, field in enumerate(field_list):
            mappings.append({
                "GlobalKey": make_global_key(name, f"field{i}"),
                "InputFieldName": f"{sobject}:{field}",
                "IsDisabled": False,
                "IsRequiredForUpsert": False,
                "IsUpsertKey": False,
                "Name": name,
                "OmniDataTransformationId": {
                    "Name": name,
                    "VlocityDataPackType": "VlocityMatchingKeyObject",
                    "VlocityMatchingRecordSourceKey": f"OmniDataTransform/{name}",
                    "VlocityRecordSObjectType": "OmniDataTransform",
                },
                "OutputCreationSequence": len(filter_items) + i,
                "OutputFieldName": field,
                "OutputObjectName": "json",
                "VlocityDataPackType": "SObject",
                "VlocityRecordSObjectType": "OmniDataTransformItem",
            })
        write_json(os.path.join(output_dir, f"{name}_Items.json"), mappings)

    # ── InputJson.json ───────────────────────────────────────────────────────
    input_json = {"ContextId": None}
    for fi in filter_items:
        if fi["value"] != "ContextId":
            input_json[fi["value"]] = None
    if schema_flavor == "managed":
        write_json(os.path.join(output_dir, f"{name}_InputJson.json"), input_json)

    # ── SampleInputJson.json ─────────────────────────────────────────────────
    sample = {"ContextId": "INSERT_RECORD_ID_HERE"}
    write_json(os.path.join(output_dir, f"{name}_SampleInputJson.json"), sample)

    print(f"[✓] Generated DataRaptor Extract: {name} ({schema_flavor} schema)")
    print(f"    Output: {output_dir}")

# ─────────────────────────────────────────────────────────────────────────────
# DATARAPTOR LOAD GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_dr_load(name, sobject, upsert_key, field_mappings, schema_flavor, output_dir):
    """Generate all files for a DataRaptor Load (upsert) component."""
    s = get_schema(schema_flavor)
    os.makedirs(output_dir, exist_ok=True)

    if schema_flavor == "managed":
        datapack = {
            s["dr_batch_size_field"]: "",
            s["dr_check_fls_field"]: False,
            "%vlocity_namespace%__CustomInputClass__c": "",
            "%vlocity_namespace%__CustomOutputClass__c": "",
            s["dr_map_item_field"]: f"{name}_Mappings.json",
            s["dr_name_field"]: name,
            "%vlocity_namespace%__DeleteOnSuccess__c": False,
            "%vlocity_namespace%__Description__c": "",
            s["dr_global_key_field"]: make_global_key(name),
            s["dr_ignore_errors_field"]: False,
            "%vlocity_namespace%__InputJson__c": f"{name}_InputJson.json",
            s["dr_input_type_field"]: "JSON",
            s["dr_interface_object_field"]: "json",
            "%vlocity_namespace%__IsDefaultForInterface__c": False,
            "%vlocity_namespace%__IsProcessSuperBulk__c": False,
            s["dr_omp_sync_field"]: True,
            s["dr_output_type_field"]: "JSON",
            s["dr_overwrite_null_field"]: False,
            s["dr_rollback_field"]: True,
            s["dr_sample_input_field"]: f"{name}_SampleInputJson.json",
            s["dr_type_field"]: "Load",
            "%vlocity_namespace%__UseAssignmentRules__c": False,
            "%vlocity_namespace%__UseTranslations__c": False,
            "Name": name,
            "VlocityDataPackType": "SObject",
            "VlocityRecordSObjectType": s["dr_sobject"],
            "VlocityRecordSourceKey": f"{s['dr_sobject']}/{name}",
        }
    else:
        datapack = {
            "BatchSize": "",
            "Description": "",
            "GlobalKey": make_global_key(name),
            "InputType": "JSON",
            "IsAssignmentRulesUsed": False,
            "IsDeletedOnSuccess": False,
            "IsErrorIgnored": False,
            "IsFieldLevelSecurityEnabled": False,
            "IsNullInputsIncludedInOutput": False,
            "IsRollbackOnError": True,
            "Name": name,
            "OmniDataTransformItem": f"{name}_Items.json",
            "OutputType": "JSON",
            "PreviewJsonData": f"{name}_SampleInputJson.json",
            "SourceObject": "json",
            "Type": "Load",
            "VersionNumber": 1,
            "VlocityDataPackType": "SObject",
            "VlocityRecordSObjectType": "OmniDataTransform",
            "VlocityRecordSourceKey": f"OmniDataTransform/{name}",
        }

    write_json(os.path.join(output_dir, f"{name}_DataPack.json"), datapack)

    # Build mappings from "inputField=sobjectField" pairs
    mappings = []
    for i, mapping in enumerate(field_mappings):
        parts = mapping.split("=", 1)
        if len(parts) != 2:
            continue
        input_field, sf_field = parts[0].strip(), parts[1].strip()
        is_upsert = (sf_field == upsert_key or input_field == upsert_key)

        if schema_flavor == "managed":
            mappings.append({
                s["item_domain_obj_api_name"]: sobject,
                s["item_domain_creation_order"]: 1,
                s["item_domain_field_api"]: sf_field,
                s["item_global_key"]: make_global_key(name, f"load{i}"),
                s["item_interface_field_api"]: input_field,
                s["item_lookup_order"]: 1,
                s["item_interface_obj_name"]: "json",
                s["item_is_disabled"]: False,
                s["item_is_required_upsert"]: is_upsert,
                s["item_map_id"]: f"{name}Custom{1000 + i}",
                s["item_omp_sync"]: True,
                s["item_upsert_key"]: is_upsert,
                "Name": name,
                "VlocityDataPackType": "SObject",
                "VlocityRecordSObjectType": s["dr_item_sobject"],
            })
        else:
            mappings.append({
                "GlobalKey": make_global_key(name, f"load{i}"),
                "InputFieldName": input_field,
                "InputObjectName": "json",
                "InputObjectQuerySequence": 1,
                "IsDisabled": False,
                "IsRequiredForUpsert": is_upsert,
                "IsUpsertKey": is_upsert,
                "Name": name,
                "OmniDataTransformationId": {
                    "Name": name,
                    "VlocityDataPackType": "VlocityMatchingKeyObject",
                    "VlocityMatchingRecordSourceKey": f"OmniDataTransform/{name}",
                    "VlocityRecordSObjectType": "OmniDataTransform",
                },
                "OutputCreationSequence": i,
                "OutputFieldName": sf_field,
                "OutputObjectName": sobject,
                "VlocityDataPackType": "SObject",
                "VlocityRecordSObjectType": "OmniDataTransformItem",
            })

    items_file = f"{name}_Mappings.json" if schema_flavor == "managed" else f"{name}_Items.json"
    write_json(os.path.join(output_dir, items_file), mappings)
    write_json(os.path.join(output_dir, f"{name}_SampleInputJson.json"), {"ContextId": None})

    print(f"[✓] Generated DataRaptor Load: {name} ({schema_flavor} schema)")
    print(f"    Output: {output_dir}")

# ─────────────────────────────────────────────────────────────────────────────
# DATARAPTOR TRANSFORM GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_dr_transform(name, mappings_list, schema_flavor, output_dir):
    """Generate all files for a DataRaptor Transform component."""
    s = get_schema(schema_flavor)
    os.makedirs(output_dir, exist_ok=True)

    if schema_flavor == "managed":
        datapack = {
            s["dr_batch_size_field"]: "",
            s["dr_check_fls_field"]: False,
            s["dr_map_item_field"]: f"{name}_Mappings.json",
            s["dr_name_field"]: name,
            s["dr_global_key_field"]: make_global_key(name),
            s["dr_ignore_errors_field"]: False,
            s["dr_input_type_field"]: "JSON",
            s["dr_interface_object_field"]: "json",
            s["dr_omp_sync_field"]: True,
            s["dr_output_type_field"]: "JSON",
            s["dr_overwrite_null_field"]: False,
            s["dr_rollback_field"]: False,
            s["dr_type_field"]: "Transform",
            "Name": name,
            "VlocityDataPackType": "SObject",
            "VlocityRecordSObjectType": s["dr_sobject"],
            "VlocityRecordSourceKey": f"{s['dr_sobject']}/{name}",
        }
    else:
        datapack = {
            "GlobalKey": make_global_key(name),
            "InputType": "JSON",
            "Name": name,
            "OmniDataTransformItem": f"{name}_Items.json",
            "OutputType": "JSON",
            "SourceObject": "json",
            "Type": "Transform",
            "VersionNumber": 1,
            "VlocityDataPackType": "SObject",
            "VlocityRecordSObjectType": "OmniDataTransform",
            "VlocityRecordSourceKey": f"OmniDataTransform/{name}",
        }

    write_json(os.path.join(output_dir, f"{name}_DataPack.json"), datapack)

    # Transform mappings: "inputPath=outputPath"
    items = []
    for i, m in enumerate(mappings_list):
        parts = m.split("=", 1)
        if len(parts) != 2:
            continue
        src, tgt = parts[0].strip(), parts[1].strip()
        if schema_flavor == "managed":
            items.append({
                s["item_domain_obj_api_name"]: "json",
                s["item_domain_field_api"]: tgt,
                s["item_global_key"]: make_global_key(name, f"t{i}"),
                s["item_interface_field_api"]: src,
                s["item_interface_obj_name"]: "json",
                s["item_is_disabled"]: False,
                s["item_is_required_upsert"]: False,
                s["item_map_id"]: f"{name}Custom{1000 + i}",
                s["item_omp_sync"]: True,
                s["item_upsert_key"]: False,
                "Name": name,
                "VlocityDataPackType": "SObject",
                "VlocityRecordSObjectType": s["dr_item_sobject"],
            })
        else:
            items.append({
                "GlobalKey": make_global_key(name, f"t{i}"),
                "InputFieldName": src,
                "InputObjectName": "json",
                "IsDisabled": False,
                "IsRequiredForUpsert": False,
                "IsUpsertKey": False,
                "Name": name,
                "OmniDataTransformationId": {
                    "Name": name,
                    "VlocityDataPackType": "VlocityMatchingKeyObject",
                    "VlocityMatchingRecordSourceKey": f"OmniDataTransform/{name}",
                    "VlocityRecordSObjectType": "OmniDataTransform",
                },
                "OutputCreationSequence": i,
                "OutputFieldName": tgt,
                "OutputObjectName": "json",
                "VlocityDataPackType": "SObject",
                "VlocityRecordSObjectType": "OmniDataTransformItem",
            })

    items_file = f"{name}_Mappings.json" if schema_flavor == "managed" else f"{name}_Items.json"
    write_json(os.path.join(output_dir, items_file), items)

    print(f"[✓] Generated DataRaptor Transform: {name} ({schema_flavor} schema)")

# ─────────────────────────────────────────────────────────────────────────────
# INTEGRATION PROCEDURE GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_ip(name, type_prefix, subtype, description, schema_flavor, output_dir):
    """Generate skeleton files for an Integration Procedure."""
    s = get_schema(schema_flavor)
    os.makedirs(output_dir, exist_ok=True)

    display_name = subtype

    if schema_flavor == "managed":
        datapack = {
            s["ip_additional_info_field"]: description,
            s["ip_custom_js_field"]: f"{name}_SampleInput.json",
            "%vlocity_namespace%__DisableMetadataCache__c": False,
            "%vlocity_namespace%__ElementTypeToHTMLTemplateList__c": '{"ElementTypeToHTMLTemplateList":[]}',
            s["ip_element_list_field"]: [],
            s["ip_is_lwc_field"]: False,
            s["ip_is_procedure_field"]: True,
            s["ip_is_reusable_field"]: False,
            s["ip_is_test_field"]: False,
            s["ip_language_field"]: "Procedure",
            s["ip_omni_process_type_field"]: "Integration Procedure",
            s["ip_procedure_key_field"]: name,
            s["ip_property_set_field"]: f"{name}_PropertySet.json",
            s["ip_subtype_field"]: subtype,
            s["ip_type_field"]: type_prefix,
            "Name": display_name,
            "VlocityDataPackType": "SObject",
            "VlocityRecordSObjectType": s["ip_sobject"],
            "VlocityRecordSourceKey": f"{s['ip_sobject']}/{type_prefix}/{subtype}/Procedure",
        }
    else:
        datapack = {
            "CustomJavaScript": f"{name}_SampleInput.json",
            "Description": description,
            "ElementTypeComponentMapping": '{"ElementTypeToHTMLTemplateList":[]}',
            "IsIntegrationProcedure": True,
            "IsMetadataCacheDisabled": False,
            "IsOmniScriptEmbeddable": False,
            "IsTestProcedure": False,
            "IsWebCompEnabled": False,
            "Language": "Procedure",
            "Name": display_name,
            "OmniProcessElement": [],
            "OmniProcessKey": name,
            "OmniProcessType": "Integration Procedure",
            "PropertySetConfig": f"{name}_PropertySetConfig.json",
            "SubType": subtype,
            "Type": type_prefix,
            "UniqueName": f"{type_prefix}_{subtype}_Procedure_1",
            "VlocityDataPackType": "SObject",
            "VlocityRecordSObjectType": "OmniProcess",
            "VlocityRecordSourceKey": f"OmniProcess/{type_prefix}/{subtype}/Procedure",
            "WebComponentKey": make_global_key(name, "wck"),
        }

    write_json(os.path.join(output_dir, f"{name}_DataPack.json"), datapack)

    # PropertySet / PropertySetConfig
    property_set = {
        "additionalChainableResponse": {},
        "chainableActualTimeLimit": None,
        "chainableCpuLimit": 2000,
        "chainableDMLRowsLimit": None,
        "chainableDMLStatementsLimit": None,
        "chainableHeapSizeLimit": None,
        "chainableQueriesLimit": 50,
        "chainableQueryRowsLimit": None,
        "chainableSoslQueriesLimit": None,
        "columnsPropertyMap": [],
        "description": description,
        "includeAllActionsInResponse": False,
        "labelPlural": "",
        "labelSingular": "",
        "linkToExternalObject": "",
        "mockResponseMap": {},
        "nameColumn": "",
        "queueableChainableCpuLimit": 40000,
        "queueableChainableHeapSizeLimit": 6,
        "queueableChainableQueriesLimit": 120,
        "relationshipFieldsMap": [],
        "rollbackOnError": False,
        "trackingCustomData": {},
        "ttlMinutes": 5,
    }
    ps_filename = f"{name}_PropertySet.json" if schema_flavor == "managed" else f"{name}_PropertySetConfig.json"
    write_json(os.path.join(output_dir, ps_filename), property_set)

    # ParentKeys
    write_json(os.path.join(output_dir, f"{name}_ParentKeys.json"), [])

    # SampleInput
    write_json(os.path.join(output_dir, f"{name}_SampleInput.json"), {
        "input": {"ContextId": "INSERT_CONTEXT_ID"}
    })

    print(f"[✓] Generated Integration Procedure skeleton: {name} ({schema_flavor} schema)")
    print(f"    Add elements by running: --type ip_element --ip-key {name} --element-type <TYPE>")

# ─────────────────────────────────────────────────────────────────────────────
# IP ELEMENT GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

IP_ELEMENT_TEMPLATES = {
    "Set Values": {
        "description": "Sets one or more output variables from input values or formulas",
        "property_set": {
            "elementValueMap": {},
            "formulaMap": {},
            "label": "TODO_LABEL",
            "show": None,
            "useFormulas": False,
        },
    },
    "Remote Action": {
        "description": "Calls an Apex Remote Action method",
        "property_set": {
            "actionMessage": "",
            "additionalChainableResponse": {},
            "additionalInput": {
                "inputFields": [],
                "objectType": "TODO_SOBJECT",
            },
            "additionalOutput": {},
            "chainOnStep": False,
            "disOnTplt": False,
            "executionConditionalFormula": "",
            "failOnStepError": True,
            "failureConditionalFormula": "",
            "failureResponse": {},
            "label": "TODO_LABEL",
            "remoteClass": "%vlocity_namespace%.CpqAppHandler",
            "remoteMethod": "TODO_METHOD",
            "remoteOptions": {},
            "responseJSONNode": "",
            "responseJSONPath": "",
            "returnOnlyAdditionalOutput": False,
            "returnOnlyFailureResponse": False,
            "sendJSONNode": "",
            "sendJSONPath": "",
            "sendOnlyAdditionalInput": True,
            "show": None,
            "useFormulas": True,
        },
    },
    "DataRaptor Extract Action": {
        "description": "Calls a DataRaptor Extract to query Salesforce data",
        "property_set": {
            "bundle": "TODO_DR_NAME",
            "chainOnStep": False,
            "executionConditionalFormula": "",
            "extraPayload": {},
            "label": "TODO_LABEL",
            "postTransformBundle": "",
            "preTransformBundle": "",
            "show": None,
            "useContinuation": False,
        },
    },
    "DataRaptor Turbo Action": {
        "description": "Calls a DataRaptor Extract with turbo (cached) mode",
        "property_set": {
            "bundle": "TODO_DR_NAME",
            "chainOnStep": False,
            "executionConditionalFormula": "",
            "extraPayload": {},
            "label": "TODO_LABEL",
            "postTransformBundle": "",
            "preTransformBundle": "",
            "show": None,
            "useContinuation": False,
        },
    },
    "DataRaptor Post Action": {
        "description": "Calls a DataRaptor Load to save/upsert data",
        "property_set": {
            "bundle": "TODO_DR_NAME",
            "chainOnStep": False,
            "executionConditionalFormula": "",
            "extraPayload": {},
            "label": "TODO_LABEL",
            "postTransformBundle": "",
            "preTransformBundle": "",
            "show": None,
        },
    },
    "DataRaptor Transform Action": {
        "description": "Calls a DataRaptor Transform to reshape data",
        "property_set": {
            "bundle": "TODO_DR_NAME",
            "chainOnStep": False,
            "executionConditionalFormula": "",
            "extraPayload": {},
            "label": "TODO_LABEL",
            "show": None,
        },
    },
    "HTTP Action": {
        "description": "Makes an external HTTP/REST callout",
        "property_set": {
            "chainOnStep": False,
            "executionConditionalFormula": "",
            "failOnStepError": True,
            "label": "TODO_LABEL",
            "restHeaders": {"Content-Type": "application/json"},
            "restHttpMethod": "POST",
            "restPath": "TODO_ENDPOINT_PATH",
            "restPayload": "{}",
            "responseJSONNode": "",
            "show": None,
        },
    },
    "Response Action": {
        "description": "Returns the final response of the Integration Procedure",
        "property_set": {
            "chainOnStep": False,
            "executionConditionalFormula": "",
            "label": "Response",
            "postTransformBundle": "",
            "preTransformBundle": "",
            "responseJSONNode": "",
            "responseJSONPath": "",
            "show": None,
        },
    },
    "Try Catch Block": {
        "description": "Container that catches errors from child elements",
        "property_set": {
            "executionConditionalFormula": "",
            "label": "TODO_LABEL",
            "show": None,
        },
    },
    "Conditional Block": {
        "description": "Container that executes children only when condition is true",
        "property_set": {
            "conditionalFormula": "TODO_CONDITION",
            "executionConditionalFormula": "",
            "label": "TODO_LABEL",
            "show": None,
        },
    },
    "Loop Block": {
        "description": "Container that iterates over a list",
        "property_set": {
            "loopInput": "TODO_LIST_VARIABLE",
            "loopOutput": "TODO_OUTPUT_VARIABLE",
            "executionConditionalFormula": "",
            "label": "TODO_LABEL",
            "show": None,
        },
    },
    "Integration Procedure Action": {
        "description": "Calls another Integration Procedure (chained)",
        "property_set": {
            "chainOnStep": False,
            "executionConditionalFormula": "",
            "extraPayload": {},
            "integrationProcedureKey": "TODO_IP_KEY",
            "label": "TODO_LABEL",
            "postTransformBundle": "",
            "preTransformBundle": "",
            "remoteOptions": {"chainable": False, "useFuture": False},
            "remoteTimeout": 30000,
            "responseJSONNode": "",
            "responseJSONPath": "",
            "sendJSONNode": "",
            "sendJSONPath": "",
            "sendOnlyExtraPayload": False,
            "show": None,
        },
    },
}

def generate_ip_element(name, element_type, ip_key, ip_type, ip_subtype, schema_flavor, output_dir, parent_element=None):
    """Generate a single IP Element file."""
    s = get_schema(schema_flavor)
    os.makedirs(output_dir, exist_ok=True)

    template = IP_ELEMENT_TEMPLATES.get(element_type, {
        "description": element_type,
        "property_set": {"label": "TODO_LABEL", "show": None},
    })

    ip_source_key = (f"{s['ip_sobject']}/{ip_type}/{ip_subtype}/Procedure"
                     if schema_flavor == "managed"
                     else f"OmniProcess/{ip_type}/{ip_subtype}/Procedure")

    if schema_flavor == "managed":
        elem = {
            s["elem_active_field"]: True,
            s["elem_omniscript_id_field"]: {
                "Name": ip_subtype,
                "VlocityDataPackType": "VlocityMatchingKeyObject",
                "VlocityMatchingRecordSourceKey": ip_source_key,
                "VlocityRecordSObjectType": s["ip_sobject"],
            },
            s["elem_property_set_field"]: template["property_set"],
            s["elem_reusable_field"]: False,
            s["elem_type_field"]: element_type,
            "Name": name,
            "VlocityDataPackType": "SObject",
            "VlocityRecordSObjectType": s["element_sobject"],
            "VlocityRecordSourceKey": f"{s['element_sobject']}/{ip_source_key}/{name}",
        }
        if parent_element:
            elem["ParentElementId"] = {
                "Name": parent_element,
                "VlocityDataPackType": "VlocityMatchingKeyObject",
                "VlocityMatchingRecordSourceKey": f"{s['element_sobject']}/{ip_source_key}/{parent_element}",
                "VlocityRecordSObjectType": s["element_sobject"],
            }
            elem["ParentElementName"] = parent_element
    else:
        elem = {
            s["elem_active_field"]: True,
            s["elem_reusable_field"]: False,
            "Name": name,
            "OmniProcessId": {
                "Name": ip_subtype,
                "VlocityDataPackType": "VlocityMatchingKeyObject",
                "VlocityMatchingRecordSourceKey": ip_source_key,
                "VlocityRecordSObjectType": "OmniProcess",
            },
            s["elem_property_set_field"]: template["property_set"],
            s["elem_type_field"]: element_type,
            "VlocityDataPackType": "SObject",
            "VlocityRecordSObjectType": "OmniProcessElement",
            "VlocityRecordSourceKey": f"OmniProcessElement/{ip_source_key}/{name}",
        }
        if parent_element:
            elem["ParentElementId"] = {
                "Name": parent_element,
                "VlocityDataPackType": "VlocityMatchingKeyObject",
                "VlocityMatchingRecordSourceKey": f"OmniProcessElement/{ip_source_key}/{parent_element}",
                "VlocityRecordSObjectType": "OmniProcessElement",
            }
            elem["ParentElementName"] = parent_element
            elem["ParentElementType"] = "TODO_PARENT_TYPE"

    write_json(os.path.join(output_dir, f"{ip_key}_Element_{name}.json"), elem)
    print(f"[✓] Generated IP Element: {name} ({element_type}) for {ip_key}")

# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def write_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Vlocity DataPack Generator")
    parser.add_argument("--type", choices=[
        "dr_extract", "dr_load", "dr_transform", "ip", "ip_element", "detect-schema"
    ], required=True, help="Component type to generate")
    parser.add_argument("--name", help="Component name")
    parser.add_argument("--schema", choices=["managed", "native", "auto"], default="auto")
    parser.add_argument("--sobject", help="Salesforce SObject API name")
    parser.add_argument("--fields", nargs="+", help="Fields to extract (for dr_extract)")
    parser.add_argument("--filters", nargs="+", default=[], help="Filter expressions e.g. Id=ContextId")
    parser.add_argument("--upsert-key", help="Upsert key field (for dr_load)")
    parser.add_argument("--field-mappings", nargs="+", default=[], help="inputField=sfField pairs (dr_load)")
    parser.add_argument("--mappings", nargs="+", default=[], help="src=tgt pairs (dr_transform)")
    parser.add_argument("--type-prefix", help="IP type prefix e.g. 'sales', 'customGuidedSelling'")
    parser.add_argument("--subtype", help="IP subtype / procedure name")
    parser.add_argument("--description", default="", help="IP description")
    parser.add_argument("--element-type", help="IP element type (for ip_element)")
    parser.add_argument("--ip-key", help="IP key for element (for ip_element)")
    parser.add_argument("--parent-element", help="Parent element name (for nested elements)")
    parser.add_argument("--output-dir", help="Output directory")
    parser.add_argument("--detect-schema", metavar="DIR", help="Detect schema flavor of a vlocity dir")

    args = parser.parse_args()

    # Schema detection shortcut
    if args.type == "detect-schema" or args.detect_schema:
        detect_path = args.detect_schema or args.output_dir or "."
        flavor = detect_schema(detect_path)
        print(f"Detected schema: {flavor}")
        return

    # Auto-detect schema if needed
    schema_flavor = args.schema
    if schema_flavor == "auto":
        detect_dir = args.output_dir or "."
        parent_dir = os.path.dirname(detect_dir)
        schema_flavor = detect_schema(parent_dir) if os.path.isdir(parent_dir) else "managed"
        print(f"[Auto-detected schema: {schema_flavor}]")

    if not args.name:
        print("Error: --name is required")
        sys.exit(1)

    output_dir = args.output_dir or os.path.join(".", args.name)

    if args.type == "dr_extract":
        if not args.sobject or not args.fields:
            print("Error: --sobject and --fields are required for dr_extract")
            sys.exit(1)
        generate_dr_extract(args.name, args.sobject, args.fields, args.filters, schema_flavor, output_dir)

    elif args.type == "dr_load":
        if not args.sobject:
            print("Error: --sobject is required for dr_load")
            sys.exit(1)
        generate_dr_load(args.name, args.sobject, args.upsert_key or "Id", args.field_mappings, schema_flavor, output_dir)

    elif args.type == "dr_transform":
        generate_dr_transform(args.name, args.mappings, schema_flavor, output_dir)

    elif args.type == "ip":
        if not args.type_prefix or not args.subtype:
            print("Error: --type-prefix and --subtype are required for ip")
            sys.exit(1)
        generate_ip(args.name, args.type_prefix, args.subtype, args.description, schema_flavor, output_dir)

    elif args.type == "ip_element":
        if not args.element_type or not args.ip_key:
            print("Error: --element-type and --ip-key are required for ip_element")
            sys.exit(1)
        # Extract type/subtype from ip-key (format: type_subtype or type_SubType)
        parts = args.ip_key.split("_", 1)
        ip_type = parts[0] if len(parts) > 1 else "sales"
        ip_subtype = parts[1] if len(parts) > 1 else args.ip_key
        generate_ip_element(
            args.name, args.element_type, args.ip_key,
            ip_type, ip_subtype, schema_flavor, output_dir, args.parent_element
        )

if __name__ == "__main__":
    main()
