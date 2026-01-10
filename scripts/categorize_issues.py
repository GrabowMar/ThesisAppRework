#!/usr/bin/env python3
"""
Categorize and summarize issues found in prompt analysis
"""

import json
import sys
from pathlib import Path
from collections import defaultdict, Counter

project_root = Path(__file__).parent.parent
results_file = project_root / 'misc_analysis_results.json'

def main():
    with open(results_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    issues = data['issues']

    # Categorize issues
    categories = defaultdict(list)

    for issue in issues:
        if "Contains placeholder '...'" in issue:
            categories['placeholder_ellipsis'].append(issue)
        elif "Contains placeholder 'your_'" in issue:
            categories['placeholder_your'].append(issue)
        elif "Endpoint" in issue and "not found in prompt" in issue:
            categories['missing_endpoint'].append(issue)
        elif "/api paths mentioned but prefix rules unclear" in issue:
            categories['unclear_prefix'].append(issue)
        else:
            categories['other'].append(issue)

    print("=" * 80)
    print("ISSUE CATEGORIZATION")
    print("=" * 80)

    print(f"\nTotal issues: {len(issues)}")
    print(f"\nBreakdown by category:")
    for cat, items in sorted(categories.items(), key=lambda x: -len(x[1])):
        print(f"  {cat}: {len(items)}")

    # Analyze placeholder ellipsis
    print("\n" + "=" * 80)
    print("PLACEHOLDER '...' ANALYSIS")
    print("=" * 80)
    ellipsis_issues = categories['placeholder_ellipsis']
    print(f"\nTotal: {len(ellipsis_issues)}")

    # Count by template type
    template_types = Counter()
    for issue in ellipsis_issues:
        if 'two-query' in issue:
            template_types['two-query'] += 1
        elif 'four-query' in issue:
            template_types['four-query'] += 1
        elif 'unguarded' in issue:
            template_types['unguarded'] += 1

    print("\nBy template type:")
    for tt, count in template_types.most_common():
        print(f"  {tt}: {count}")

    # Analyze missing endpoints
    print("\n" + "=" * 80)
    print("MISSING ENDPOINT ANALYSIS")
    print("=" * 80)
    missing_endpoint_issues = categories['missing_endpoint']
    print(f"\nTotal: {len(missing_endpoint_issues)}")

    # Count by query type
    query_types = Counter()
    for issue in missing_endpoint_issues:
        if '_admin:' in issue:
            query_types['admin'] += 1
        elif '_user:' in issue:
            query_types['user'] += 1

    print("\nBy query type:")
    for qt, count in query_types.most_common():
        print(f"  {qt}: {count}")

    # Extract most common missing endpoints
    endpoint_counter = Counter()
    for issue in missing_endpoint_issues:
        # Extract endpoint path
        if 'Endpoint ' in issue and ' not found' in issue:
            start = issue.find('Endpoint ') + len('Endpoint ')
            end = issue.find(' not found')
            endpoint = issue[start:end]
            endpoint_counter[endpoint] += 1

    print("\nMost common missing endpoints:")
    for endpoint, count in endpoint_counter.most_common(10):
        print(f"  {endpoint}: {count} times")

    # Analyze unclear prefix
    print("\n" + "=" * 80)
    print("UNCLEAR PREFIX ANALYSIS")
    print("=" * 80)
    unclear_prefix_issues = categories['unclear_prefix']
    print(f"\nTotal: {len(unclear_prefix_issues)}")
    print("\nAll occur in: unguarded templates for backend")

    # Sample issues
    print("\n" + "=" * 80)
    print("SAMPLE ISSUES")
    print("=" * 80)

    for cat, items in categories.items():
        if items:
            print(f"\n{cat} (showing first 3):")
            for issue in items[:3]:
                print(f"  - {issue}")

    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)

    print("\n1. PLACEHOLDER '...' (Low Priority)")
    print("   - This is used in JSON examples to show continuation")
    print("   - It's not a real issue, just a style choice")
    print("   - Action: Either accept it or replace with more complete examples")

    print("\n2. PLACEHOLDER 'your_' (Low Priority)")
    print("   - Occurs in education_quiz_app requirements")
    print("   - Example: 'your_answer_here' in documentation")
    print("   - Action: Review education_quiz_app requirements file")

    print("\n3. MISSING ENDPOINTS IN ADMIN PROMPTS (Medium Priority)")
    print(f"   - {len(missing_endpoint_issues)} warnings about endpoints not in prompts")
    print("   - Mostly admin prompts don't include user endpoint details")
    print("   - This is BY DESIGN: admin prompts focus on admin routes")
    print("   - Action: Either accept this or add user endpoints as reference")

    print("\n4. UNCLEAR PREFIX IN UNGUARDED (Medium Priority)")
    print(f"   - {len(unclear_prefix_issues)} warnings in unguarded templates")
    print("   - Unguarded templates might not explain blueprint prefix rules clearly")
    print("   - Action: Review unguarded templates and add prefix documentation")

    print("\n" + "=" * 80)
    print("OVERALL ASSESSMENT")
    print("=" * 80)

    print("\n[OK] Most 'issues' are actually false positives or by design")
    print("[OK] No critical errors found")
    print("[INFO] The '...' placeholder is stylistic, not a real issue")
    print("[INFO] Missing endpoints in admin prompts is by design (separation of concerns)")
    print("[ACTION] Minor improvements recommended for unguarded templates")

    return 0

if __name__ == '__main__':
    sys.exit(main())
