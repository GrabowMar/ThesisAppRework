#!/usr/bin/env python3
"""
AI Analyzer Calibration Script
===============================

Compares AI analyzer requirement verdicts against manually verified ground truth
to measure precision, recall, F1 score, and false positive/negative rates.

Usage:
    python3 scripts/calibrate_ai_analyzer.py
    python3 scripts/calibrate_ai_analyzer.py --ground-truth path/to/ground_truth.json
    python3 scripts/calibrate_ai_analyzer.py --verbose

Output:
    - Per-app comparison table
    - Per-template summary
    - Overall precision/recall/F1
    - JSON report saved to scripts/calibration_report.json
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def find_ai_results(model_slug: str, app_number: int, results_dir: Path) -> Optional[Dict]:
    """Find and load the latest AI analysis results for an app.

    Args:
        model_slug: Model identifier (e.g., 'anthropic_claude-4.5-sonnet-20250929')
        app_number: App number (e.g., 1)
        results_dir: Base results directory

    Returns:
        Requirements scanner results dict, or None if not found
    """
    app_path = results_dir / model_slug / f"app{app_number}"
    if not app_path.is_dir():
        return None

    # Find task directories
    task_dirs = [d for d in app_path.iterdir() if d.is_dir() and d.name.startswith("task_")]
    if not task_dirs:
        return None

    # Try each task dir, prefer the one with a manifest pointing to latest
    for task_dir in sorted(task_dirs, reverse=True):
        manifest_path = task_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        with open(manifest_path) as f:
            manifest = json.load(f)

        result_file = manifest.get("main_result_file", "")
        result_path = task_dir / result_file
        if not result_path.exists():
            continue

        try:
            with open(result_path) as f:
                data = json.load(f)

            # Navigate to requirements-scanner results
            tools = (
                data.get("services", {})
                .get("ai-analyzer", {})
                .get("payload", {})
                .get("analysis", {})
                .get("tools", {})
            )
            rs = tools.get("requirements-scanner", {})
            if rs and rs.get("results"):
                return rs
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    return None


def normalize_requirement(text: str) -> str:
    """Normalize requirement text for matching.

    Strips numbering prefixes and normalizes whitespace for fuzzy matching.
    """
    import re
    # Remove leading numbers like "1. " or "2. "
    text = re.sub(r"^\d+\.\s*", "", text.strip())
    # Normalize whitespace
    text = " ".join(text.split())
    return text.lower()


def match_requirements(
    gt_reqs: List[Dict], ai_reqs: List[Dict]
) -> List[Tuple[Dict, Optional[Dict]]]:
    """Match ground truth requirements to AI requirements.

    Uses normalized text matching to pair up requirements.

    Returns:
        List of (ground_truth_req, ai_req_or_None) tuples
    """
    # Build normalized lookup for AI results
    ai_lookup: Dict[str, Dict] = {}
    for req in ai_reqs:
        key = normalize_requirement(req.get("requirement", ""))
        ai_lookup[key] = req

    matches = []
    for gt_req in gt_reqs:
        gt_key = normalize_requirement(gt_req.get("requirement", ""))
        ai_match = ai_lookup.get(gt_key)

        if ai_match is None:
            # Try substring matching for partial matches
            for ai_key, ai_req in ai_lookup.items():
                # Check if one contains the other (handles prefix differences)
                if gt_key in ai_key or ai_key in gt_key:
                    ai_match = ai_req
                    break

        matches.append((gt_req, ai_match))

    return matches


def compute_metrics(
    matches: List[Tuple[Dict, Optional[Dict]]]
) -> Dict[str, Any]:
    """Compute precision, recall, F1, and error rates from matched requirements.

    For binary classification where:
    - Positive = requirement is MET
    - True Positive = AI says MET, ground truth says MET
    - False Positive = AI says MET, ground truth says NOT MET
    - False Negative = AI says NOT MET, ground truth says MET

    Returns:
        Dict with tp, fp, fn, tn, precision, recall, f1, fpr, fnr
    """
    tp = fp = fn = tn = 0
    unmatched = 0

    for gt_req, ai_req in matches:
        gt_met = gt_req.get("met", False)

        if ai_req is None:
            unmatched += 1
            # AI didn't produce a result — treat as NOT MET prediction
            if gt_met:
                fn += 1
            else:
                tn += 1
            continue

        ai_met = ai_req.get("met", False)

        if ai_met and gt_met:
            tp += 1
        elif ai_met and not gt_met:
            fp += 1
        elif not ai_met and gt_met:
            fn += 1
        else:
            tn += 1

    total = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0  # False positive rate
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0  # False negative rate
    accuracy = (tp + tn) / total if total > 0 else 0.0

    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "total": total,
        "unmatched": unmatched,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fpr, 4),
        "false_negative_rate": round(fnr, 4),
        "accuracy": round(accuracy, 4),
    }


def print_comparison_table(
    app_label: str,
    matches: List[Tuple[Dict, Optional[Dict]]],
    category: str,
    verbose: bool = False,
) -> None:
    """Print a per-requirement comparison table."""
    print(f"\n  {category.upper()} Requirements:")
    print(f"  {'#':>3}  {'GT':>4}  {'AI':>4}  {'Match':>5}  Requirement")
    print(f"  {'─' * 3}  {'─' * 4}  {'─' * 4}  {'─' * 5}  {'─' * 50}")

    for i, (gt_req, ai_req) in enumerate(matches, 1):
        gt_met = gt_req.get("met", False)
        ai_met = ai_req.get("met", False) if ai_req else None

        gt_str = " MET" if gt_met else "  NO"
        if ai_met is None:
            ai_str = "  N/A"
            match_str = "  ???"
        elif ai_met == gt_met:
            ai_str = " MET" if ai_met else "  NO"
            match_str = "   OK"
        else:
            ai_str = " MET" if ai_met else "  NO"
            match_str = " **FP" if ai_met else " **FN"

        req_text = gt_req.get("requirement", "")[:60]
        print(f"  {i:3d}  {gt_str}  {ai_str}  {match_str}  {req_text}")

        if verbose and ai_req:
            explanation = ai_req.get("explanation", "")[:100]
            print(f"       AI explanation: {explanation}")
            if gt_req.get("notes"):
                print(f"       GT notes: {gt_req['notes']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate AI analyzer against ground truth")
    parser.add_argument(
        "--ground-truth",
        default="scripts/calibration_ground_truth.json",
        help="Path to ground truth JSON file",
    )
    parser.add_argument(
        "--results-dir",
        default="results",
        help="Path to results directory",
    )
    parser.add_argument(
        "--output",
        default="scripts/calibration_report.json",
        help="Path to output JSON report",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed comparisons")
    args = parser.parse_args()

    # Load ground truth
    gt_path = Path(args.ground_truth)
    if not gt_path.exists():
        print(f"Error: Ground truth file not found: {gt_path}")
        sys.exit(1)

    with open(gt_path) as f:
        ground_truth = json.load(f)

    results_dir = Path(args.results_dir)
    if not results_dir.is_dir():
        print(f"Error: Results directory not found: {results_dir}")
        sys.exit(1)

    print("=" * 70)
    print("AI Analyzer Calibration Report")
    print("=" * 70)
    print(f"Ground truth: {gt_path} ({len(ground_truth['apps'])} apps)")
    print(f"Results dir: {results_dir}")

    # Process each app
    all_matches_by_template: Dict[str, List[Tuple[Dict, Optional[Dict]]]] = defaultdict(list)
    all_matches: List[Tuple[Dict, Optional[Dict]]] = []
    app_reports = []

    for app_gt in ground_truth["apps"]:
        model_slug = app_gt["model_slug"]
        app_number = app_gt["app_number"]
        template_slug = app_gt["template_slug"]
        app_label = f"{model_slug}/app{app_number} ({template_slug})"

        print(f"\n{'─' * 70}")
        print(f"App: {app_label}")

        # Find AI results
        ai_results = find_ai_results(model_slug, app_number, results_dir)
        if ai_results is None:
            print(f"  WARNING: No AI results found for {app_label}")
            app_reports.append({
                "model_slug": model_slug,
                "app_number": app_number,
                "template_slug": template_slug,
                "status": "no_results",
            })
            continue

        ai_result_data = ai_results.get("results", {})
        app_matches = []

        for category in ["backend", "frontend"]:
            gt_reqs = app_gt.get("requirements", {}).get(category, [])
            ai_reqs = ai_result_data.get(f"{category}_requirements", [])

            if not gt_reqs:
                continue

            matches = match_requirements(gt_reqs, ai_reqs)
            app_matches.extend(matches)
            all_matches.extend(matches)
            all_matches_by_template[template_slug].extend(matches)

            print_comparison_table(app_label, matches, category, args.verbose)

        # Per-app metrics
        if app_matches:
            metrics = compute_metrics(app_matches)
            print(f"\n  App metrics: P={metrics['precision']:.2f} R={metrics['recall']:.2f} "
                  f"F1={metrics['f1']:.2f} | TP={metrics['tp']} FP={metrics['fp']} "
                  f"FN={metrics['fn']} TN={metrics['tn']}")
            app_reports.append({
                "model_slug": model_slug,
                "app_number": app_number,
                "template_slug": template_slug,
                "status": "compared",
                "metrics": metrics,
            })

    # Per-template summary
    print(f"\n{'=' * 70}")
    print("Per-Template Summary")
    print(f"{'=' * 70}")
    template_reports = {}
    for template, matches in sorted(all_matches_by_template.items()):
        metrics = compute_metrics(matches)
        template_reports[template] = metrics
        print(f"  {template:35s} P={metrics['precision']:.2f} R={metrics['recall']:.2f} "
              f"F1={metrics['f1']:.2f} FPR={metrics['false_positive_rate']:.2f} "
              f"(n={metrics['total']})")

    # Overall summary
    print(f"\n{'=' * 70}")
    print("Overall Summary")
    print(f"{'=' * 70}")
    if all_matches:
        overall = compute_metrics(all_matches)
        print(f"  Total requirements compared: {overall['total']}")
        print(f"  Precision:          {overall['precision']:.4f}  (of AI's MET verdicts, how many are correct)")
        print(f"  Recall:             {overall['recall']:.4f}  (of truly MET requirements, how many did AI find)")
        print(f"  F1 Score:           {overall['f1']:.4f}")
        print(f"  Accuracy:           {overall['accuracy']:.4f}")
        print(f"  False Positive Rate: {overall['false_positive_rate']:.4f}  (AI says MET when it shouldn't)")
        print(f"  False Negative Rate: {overall['false_negative_rate']:.4f}  (AI says NO when it should be MET)")
        print(f"  Confusion Matrix: TP={overall['tp']} FP={overall['fp']} FN={overall['fn']} TN={overall['tn']}")
    else:
        print("  No matches found!")
        overall = {}

    # Save report
    report = {
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "ground_truth_file": str(gt_path),
        "apps_compared": len(app_reports),
        "overall_metrics": overall,
        "template_metrics": template_reports,
        "app_details": app_reports,
    }

    output_path = Path(args.output)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {output_path}")


if __name__ == "__main__":
    main()
