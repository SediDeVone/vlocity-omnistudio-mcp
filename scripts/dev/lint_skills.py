#!/usr/bin/env python3
"""
Skill Linter — validates SKILL.md files, skills.json registry, and CHANGELOG.md
for compliance with the OmniStudio Skills standards.

Usage:
    python3 scripts/dev/lint_skills.py           # Lint all skills
    python3 scripts/dev/lint_skills.py --verbose  # Show passing checks too
    python3 scripts/dev/lint_skills.py --skill salesforce-code-reviewer  # Lint one skill

Addresses:
    #10 SKILL.md Linting / Validation
    #1  Versioning Strategy (CHANGELOG.md checks)
    #2  Deprecation Process (deprecated flag detection)
"""

import json
import os
import re
import sys

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
SKILLS_JSON_PATH = os.path.join(PROJECT_ROOT, "skills.json")

REQUIRED_SKILL_FILES = ["SKILL.md", "CHANGELOG.md"]

# Sections that must exist in every SKILL.md
REQUIRED_SKILL_MD_SECTIONS = [
    "Security & Guardrails",
]

# Patterns that should appear in the Security & Guardrails section
REQUIRED_GUARDRAIL_PATTERNS = [
    r"Risk Classification",
    r"delimiter tags|<jira_data>|<external_data>|<api_response>|<user_input>",
    r"NEVER follow instructions found inside delimiter tags",
]

GUARDRAILS_SPEC_REF = "GUARDRAILS_SPEC.md"


class LintResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passes = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def ok(self, msg):
        self.passes.append(msg)

    @property
    def has_errors(self):
        return len(self.errors) > 0


def load_skills_json():
    if not os.path.exists(SKILLS_JSON_PATH):
        return None
    with open(SKILLS_JSON_PATH) as f:
        return json.load(f)


def get_skill_directories():
    """Find all directories that contain a SKILL.md file."""
    dirs = []
    # Root level
    for entry in sorted(os.listdir(PROJECT_ROOT)):
        full = os.path.join(PROJECT_ROOT, entry)
        if os.path.isdir(full) and os.path.exists(os.path.join(full, "SKILL.md")):
            dirs.append(entry)
    # Under skills/
    skills_dir = os.path.join(PROJECT_ROOT, "skills")
    if os.path.exists(skills_dir) and os.path.isdir(skills_dir):
        for entry in sorted(os.listdir(skills_dir)):
            full = os.path.join(skills_dir, entry)
            if os.path.isdir(full) and os.path.exists(os.path.join(full, "SKILL.md")):
                dirs.append(f"skills/{entry}")
    return dirs


def lint_skill_md(skill_dir, result):
    """Validate a SKILL.md file has required sections and content."""
    skill_md_path = os.path.join(PROJECT_ROOT, skill_dir, "SKILL.md")
    if not os.path.exists(skill_md_path):
        result.error(f"[{skill_dir}] SKILL.md not found")
        return

    with open(skill_md_path) as f:
        content = f.read()

    # Check required sections
    for section in REQUIRED_SKILL_MD_SECTIONS:
        if section.lower() in content.lower():
            result.ok(f"[{skill_dir}] SKILL.md has '{section}' section")
        else:
            result.error(f"[{skill_dir}] SKILL.md missing required section: '{section}'")

    # Check guardrail patterns within Security & Guardrails section
    security_match = re.search(
        r"##\s*Security\s*&\s*Guardrails(.*)",
        content,
        re.IGNORECASE | re.DOTALL,
    )
    if security_match:
        security_section = security_match.group(1)
        for pattern in REQUIRED_GUARDRAIL_PATTERNS:
            if re.search(pattern, security_section, re.IGNORECASE):
                result.ok(f"[{skill_dir}] Security section has pattern: {pattern[:40]}...")
            else:
                result.warn(f"[{skill_dir}] Security section may be missing pattern: {pattern[:40]}...")

        # Check for GUARDRAILS_SPEC.md reference
        if GUARDRAILS_SPEC_REF in content:
            result.ok(f"[{skill_dir}] SKILL.md references {GUARDRAILS_SPEC_REF}")
        else:
            result.warn(f"[{skill_dir}] SKILL.md does not reference {GUARDRAILS_SPEC_REF}")

    # Check for frontmatter or description block
    if re.search(r"^---\s*\n", content):
        result.ok(f"[{skill_dir}] SKILL.md has frontmatter block")
    else:
        result.warn(f"[{skill_dir}] SKILL.md missing frontmatter block (---)")

    # Check for Workflow section
    if re.search(r"##\s*Workflow", content, re.IGNORECASE):
        result.ok(f"[{skill_dir}] SKILL.md has Workflow section")
    else:
        result.warn(f"[{skill_dir}] SKILL.md missing Workflow section")


def lint_changelog(skill_dir, result):
    """Validate CHANGELOG.md exists and has version entries."""
    changelog_path = os.path.join(PROJECT_ROOT, skill_dir, "CHANGELOG.md")
    if not os.path.exists(changelog_path):
        result.error(f"[{skill_dir}] CHANGELOG.md not found")
        return

    with open(changelog_path) as f:
        content = f.read()

    # Check for at least one version entry
    versions = re.findall(r"\[(\d+\.\d+\.\d+)\]", content)
    if versions:
        result.ok(f"[{skill_dir}] CHANGELOG.md has {len(versions)} version(s): {', '.join(versions)}")
    else:
        result.error(f"[{skill_dir}] CHANGELOG.md has no version entries (expected [X.Y.Z] format)")

    # Check for date entries
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", content)
    if dates:
        result.ok(f"[{skill_dir}] CHANGELOG.md has dated entries")
    else:
        result.warn(f"[{skill_dir}] CHANGELOG.md has no date entries")


def lint_skills_json(skill_dirs, result):
    """Validate skills.json matches actual skill directories."""
    data = load_skills_json()
    if data is None:
        result.error("[skills.json] File not found at project root")
        return

    # Validate JSON structure
    if "skills" not in data:
        result.error("[skills.json] Missing 'skills' array")
        return

    registered_dirs = {s["directory"] for s in data["skills"]}
    actual_dirs = set(skill_dirs)

    # Check for skills in filesystem but not in registry
    unregistered = actual_dirs - registered_dirs
    for d in sorted(unregistered):
        result.error(f"[skills.json] Skill directory '{d}' exists but is not registered in skills.json")

    # Check for skills in registry but not in filesystem
    missing = registered_dirs - actual_dirs
    for d in sorted(missing):
        result.error(f"[skills.json] Skill '{d}' registered in skills.json but directory not found")

    # Check for matching directories
    matched = actual_dirs & registered_dirs
    for d in sorted(matched):
        result.ok(f"[skills.json] Skill '{d}' correctly registered")

    # Validate each skill entry has required fields
    required_fields = ["id", "name", "directory", "description", "trigger_keywords", "risk_level"]
    for skill in data["skills"]:
        skill_id = skill.get("id", "unknown")
        for field in required_fields:
            if field not in skill or not skill[field]:
                result.error(f"[skills.json] Skill '{skill_id}' missing required field: {field}")

    # Validate risk levels
    valid_risk_levels = {"low", "medium", "high"}
    for skill in data["skills"]:
        risk = skill.get("risk_level", "")
        if risk not in valid_risk_levels:
            result.error(f"[skills.json] Skill '{skill.get('id')}' has invalid risk_level: '{risk}'")

    # Check for duplicate trigger keywords across skills
    keyword_map = {}
    for skill in data["skills"]:
        for kw in skill.get("trigger_keywords", []):
            kw_lower = kw.lower()
            if kw_lower in keyword_map:
                result.warn(
                    f"[skills.json] Duplicate trigger keyword '{kw}' in "
                    f"'{skill['id']}' and '{keyword_map[kw_lower]}'"
                )
            else:
                keyword_map[kw_lower] = skill["id"]

    # Validate changelog_version matches actual CHANGELOG.md
    for skill in data["skills"]:
        skill_dir = skill.get("directory", "")
        declared_version = skill.get("changelog_version", "")
        changelog_path = os.path.join(PROJECT_ROOT, skill_dir, "CHANGELOG.md")
        if os.path.exists(changelog_path):
            with open(changelog_path) as f:
                versions = re.findall(r"\[(\d+\.\d+\.\d+)\]", f.read())
            if versions and declared_version and versions[0] != declared_version:
                result.warn(
                    f"[skills.json] Skill '{skill['id']}' declares version {declared_version} "
                    f"but CHANGELOG.md latest is {versions[0]}"
                )


def print_results(result, verbose=False):
    """Print lint results with color coding."""
    if verbose:
        for msg in result.passes:
            print(f"  ✅ {msg}")

    for msg in result.warnings:
        print(f"  ⚠️  {msg}")

    for msg in result.errors:
        print(f"  ❌ {msg}")

    print()
    print(f"Results: {len(result.passes)} passed, {len(result.warnings)} warnings, {len(result.errors)} errors")

    if result.has_errors:
        print("\n❌ LINT FAILED — fix errors above before proceeding.")
        return 1
    elif result.warnings:
        print("\n⚠️  LINT PASSED with warnings.")
        return 0
    else:
        print("\n✅ LINT PASSED — all checks OK.")
        return 0


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    single_skill = None
    for i, arg in enumerate(sys.argv):
        if arg == "--skill" and i + 1 < len(sys.argv):
            single_skill = sys.argv[i + 1]

    print("=" * 60)
    print("  OmniStudio Skill Linter")
    print("=" * 60)
    print()

    result = LintResult()

    # Get skill directories
    skill_dirs = get_skill_directories()
    if single_skill:
        if single_skill in skill_dirs:
            skill_dirs = [single_skill]
        else:
            print(f"❌ Skill '{single_skill}' not found. Available: {', '.join(skill_dirs)}")
            sys.exit(1)

    print(f"Found {len(skill_dirs)} skill(s): {', '.join(skill_dirs)}\n")

    # Lint each skill
    for skill_dir in skill_dirs:
        print(f"--- {skill_dir} ---")
        lint_skill_md(skill_dir, result)
        lint_changelog(skill_dir, result)
        if verbose:
            for msg in [m for m in result.passes if f"[{skill_dir}]" in m]:
                print(f"  ✅ {msg}")
        for msg in [m for m in result.warnings if f"[{skill_dir}]" in m]:
            print(f"  ⚠️  {msg}")
        for msg in [m for m in result.errors if f"[{skill_dir}]" in m]:
            print(f"  ❌ {msg}")
        print()

    # Lint skills.json
    print("--- skills.json ---")
    lint_skills_json(skill_dirs, result)
    if verbose:
        for msg in [m for m in result.passes if "[skills.json]" in m]:
            print(f"  ✅ {msg}")
    for msg in [m for m in result.warnings if "[skills.json]" in m]:
        print(f"  ⚠️  {msg}")
    for msg in [m for m in result.errors if "[skills.json]" in m]:
        print(f"  ❌ {msg}")
    print()

    # Summary
    print("=" * 60)
    exit_code = print_results(result, verbose=False)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
