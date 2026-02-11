#!/usr/bin/env python3
"""
RULES_INDEX.md Generator

Generates RULES_INDEX.md from rules_index.yaml (the source of truth).
Run this script after editing the YAML to regenerate the markdown.

Usage:
    python scripts/regenerate_rules_index.py
"""

import yaml
from pathlib import Path


def generate_markdown(yaml_path: Path) -> str:
    """Generate RULES_INDEX.md from YAML."""
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    categories = data['categories']
    enforcement_points = data['enforcement_points']

    lines = [
        '# Werewolf Game Rules - Assertion Index',
        '',
        '> **WARNING: This file is auto-generated. Edit `scripts/rules_index.yaml` instead.**',
        '> Run `python scripts/regenerate_rules_index.py` after modifying the YAML.',
        '',
        'This document provides a canonical indexed list of **hard constraints** for the game',
        'validator. Each rule is written as an assertion with "MUST" or "CANNOT" for',
        'unambiguous enforcement. Optional player choices (e.g., Hunter activation, badge',
        'transfer) are NOT included here.',
        '',
    ]

    total_rules = 0

    for cat in categories:
        cat_id = cat['id']
        cat_name = cat['name']
        rules = cat['rules']

        lines.append(f'## {cat_name}')
        ''

        for idx, rule in enumerate(rules, 1):
            rule_id = f"{cat_id}.{idx}"
            lines.append(f'- **{rule_id}** {rule}')

        lines.append('')
        total_rules += len(rules)

    # Summary table
    lines.extend([
        '## Summary',
        '',
        '| Category | Rules | Enforcement Point |',
        '|----------|-------|-------------------|',
    ])

    for cat in categories:
        cat_name = cat['name']
        count = len(cat['rules'])
        point = enforcement_points.get(cat_name, 'TBD')
        lines.append(f'| {cat_name} | {count} | {point} |')

    lines.extend([
        '',
        f'**Total: {total_rules} assertions**',
    ])

    return '\n'.join(lines)


def main():
    # Find files
    repo_root = Path(__file__).parent.parent
    yaml_path = repo_root / 'scripts' / 'rules_index.yaml'
    md_path = repo_root / 'RULES_INDEX.md'

    if not yaml_path.exists():
        print(f"Error: {yaml_path} not found")
        return 1

    print(f"Reading {yaml_path}...")

    # Generate markdown
    print("Generating markdown...")
    content = generate_markdown(yaml_path)

    # Write to file
    with open(md_path, 'w') as f:
        f.write(content)

    print(f"Done! Generated {md_path}")
    return 0


if __name__ == '__main__':
    exit(main())
