#!/usr/bin/env python3
"""Generate aggregate summary plots for Chapter 7 of the thesis.

Uses the 200-app dataset (10 models × 20 apps each).
Data is loaded from thesis_data_20.json to ensure accuracy.
Produces 5 matplotlib figures as JPGs in plots/.

Plot 1 uses TOPSIS (Technique for Order of Preference by Similarity to Ideal
Solution) for multi-criteria ranking. All other plots use the raw metrics.
"""

import json
import pathlib

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / 'plots'
DATA_FILE = ROOT / 'thesis_data_20.json'

# ── Load data from JSON ──────────────────────────────────────────────────────
with open(DATA_FILE) as _f:
    _RAW = json.load(_f)

_SUMMARY = _RAW['model_summary']
_PERF = _RAW['performance']
_AI_TOOLS = _RAW['ai_tools']
_STATIC = _RAW['static_tools']

# Canonical model key order (alphabetical by short name)
_MODEL_KEYS = sorted(_SUMMARY.keys(), key=lambda k: _SUMMARY[k]['short_name'])

MODELS = [_SUMMARY[k]['short_name'] for k in _MODEL_KEYS]
_MK = {_SUMMARY[k]['short_name']: k for k in _MODEL_KEYS}  # short_name → json key

N_APPS = 20

SHORT_LABELS = {
    'Claude 4.5 Sonnet': 'Claude 4.5\nSonnet',
    'DeepSeek R1': 'DeepSeek\nR1',
    'Gemini 3 Flash': 'Gemini 3\nFlash',
    'Gemini 3 Pro': 'Gemini 3\nPro',
    'GLM-4.7': 'GLM-4.7',
    'GPT-4o Mini': 'GPT-4o\nMini',
    'GPT-5.2 Codex': 'GPT-5.2\nCodex',
    'Llama 3.1 405B': 'Llama 3.1\n405B',
    'Mistral Small 3.1': 'Mistral\nSmall 3.1',
    'Qwen3 Coder+': 'Qwen3\nCoder+',
}

# ── Derived metric dicts (keyed by short name) ───────────────────────────────
LOC_PER_APP: dict[str, float] = {
    _SUMMARY[k]['short_name']: _SUMMARY[k]['total_loc'] / N_APPS
    for k in _MODEL_KEYS
}

DEFECT_DENSITY: dict[str, float] = {
    _SUMMARY[k]['short_name']: _SUMMARY[k]['defect_density_kloc']
    for k in _MODEL_KEYS
}

SEVERITY_HIGH: dict[str, int] = {
    _SUMMARY[k]['short_name']: _SUMMARY[k]['severity']['high']
    for k in _MODEL_KEYS
}
SEVERITY_MED: dict[str, int] = {
    _SUMMARY[k]['short_name']: _SUMMARY[k]['severity']['medium']
    for k in _MODEL_KEYS
}
SEVERITY_LOW: dict[str, int] = {
    _SUMMARY[k]['short_name']: _SUMMARY[k]['severity']['low']
    for k in _MODEL_KEYS
}

# True compliance: total_compliance_percentage (includes endpoint testing),
# latest task per app, first 20 apps only. The ai_tools requirements-scanner
# scores are inflated as they only count code-level feature presence.
_rs = _AI_TOOLS['requirements-scanner']['per_model']
COMPLIANCE_MEAN: dict[str, float] = {
    _SUMMARY[k]['short_name']: _rs[k]['compliance_pct']['mean']
    for k in _MODEL_KEYS
}
COMPLIANCE_STD: dict[str, float] = {
    _SUMMARY[k]['short_name']: _rs[k]['compliance_pct']['std']
    for k in _MODEL_KEYS
}

_cq = _AI_TOOLS['code-quality-analyzer']['per_model']
QUALITY_SCORE: dict[str, float] = {
    _SUMMARY[k]['short_name']: _cq[k]['score']['mean'] for k in _MODEL_KEYS
}

RPS: dict[str, float] = {
    _SUMMARY[k]['short_name']: (_PERF[k]['backend_mean'] if _PERF.get(k) else 0.0)
    for k in _MODEL_KEYS
}

# Deploy% = apps that completed performance testing × 2 runs / (20 apps)
DEPLOY_PCT: dict[str, float] = {
    _SUMMARY[k]['short_name']: (
        (_PERF[k]['tests'] // 2) / N_APPS * 100 if _PERF.get(k) else 0.0
    )
    for k in _MODEL_KEYS
}

# Output token price ($/M tokens) — kept as external knowledge
PRICES: dict[str, float] = {
    'Claude 4.5 Sonnet': 15.00, 'DeepSeek R1': 1.75, 'Gemini 3 Flash': 3.00,
    'Gemini 3 Pro': 12.00, 'GLM-4.7': 1.50, 'GPT-4o Mini': 0.60,
    'GPT-5.2 Codex': 14.00, 'Llama 3.1 405B': 4.00,
    'Mistral Small 3.1': 0.11, 'Qwen3 Coder+': 5.00,
}

# Heatmap: avg findings/app per tool (from static_tools per_model)
_TOOL_MAP = {'Pylint': 'pylint', 'Ruff': 'ruff', 'ESLint': 'eslint',
             'Mypy': 'mypy', 'Vulture': 'vulture', 'Bandit': 'bandit',
             'Semgrep': 'semgrep'}
HEATMAP: dict[str, dict[str, float]] = {}
for _display, _key in _TOOL_MAP.items():
    HEATMAP[_display] = {
        _SUMMARY[k]['short_name']: _STATIC[_key]['per_model'][k]['avg_per_run']
        for k in _MODEL_KEYS
    }

# Thesis-friendly colour palette
COLORS = [
    '#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B',
    '#44BBA4', '#E94F37', '#393E41', '#8D6A9F', '#5FAD56',
]

plt.rcParams.update({
    'font.size': 14,
    'axes.titlesize': 16,
    'axes.labelsize': 15,
    'xtick.labelsize': 13,
    'ytick.labelsize': 13,
    'legend.fontsize': 16,
    'figure.dpi': 200,
    'savefig.dpi': 200,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.15,
})


def _labels(models: list[str]) -> list[str]:
    return [SHORT_LABELS[m] for m in models]


def _norm(vals: list[float]) -> list[float]:
    """Min-max normalise to [0, 1]."""
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


# ── Plot 1: Model Scorecard (grouped bar, min-max normalised) ─────────────────
def plot_model_scorecard() -> None:
    """Grouped bar chart: 6 min-max normalised metrics × 10 models.

    Metrics:
      Compliance%     — requirements scanner mean score
      Code Quality    — AI quality analyser mean score
      Code Volume     — LOC/App (more = more functionality)
      Low Defect Den. — 1000/D/kLOC (inverted so higher = better)
      Deploy%         — deployment success rate
      Cost Efficiency — 1/price (inverted so higher = better)
    """
    models = MODELS
    labels = _labels(models)

    compliance = [COMPLIANCE_MEAN[m] for m in models]
    quality = [QUALITY_SCORE[m] for m in models]
    loc_app = [LOC_PER_APP[m] for m in models]
    dd_inv = [1000 / max(DEFECT_DENSITY[m], 1) for m in models]
    deploy = [DEPLOY_PCT[m] for m in models]
    cost_eff = [1.0 / PRICES[m] for m in models]

    metrics = {
        'Compliance': _norm(compliance),
        'Code Quality': _norm(quality),
        'Code Volume': _norm(loc_app),
        'Low Defect\nDensity': _norm(dd_inv),
        'Deploy%': _norm(deploy),
        'Cost\nEfficiency': _norm(cost_eff),
    }

    n_models = len(models)
    n_metrics = len(metrics)
    x = np.arange(n_models)
    width = 0.12
    offsets = np.arange(n_metrics) - (n_metrics - 1) / 2

    fig, ax = plt.subplots(figsize=(14, 5.5))
    metric_colors = ['#2E86AB', '#A23B72', '#F18F01', '#44BBA4', '#E94F37', '#8D6A9F']

    for i, (name, vals) in enumerate(metrics.items()):
        ax.bar(x + offsets[i] * width, vals, width * 0.9, label=name,
               color=metric_colors[i], edgecolor='white', linewidth=0.3)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, ha='center')
    ax.set_ylabel('Normalised Score (0–1)')
    ax.set_title('Model Scorecard: Normalised Metrics Comparison')
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.12), ncol=6, frameon=False)
    ax.set_ylim(0, 1.1)
    ax.grid(axis='y', alpha=0.3, linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    fig.savefig(OUT_DIR / 'scorecard.jpg', format='jpeg')
    plt.close(fig)
    print('  ✓ scorecard.jpg')


# ── Plot 2: Code Volume vs Defect Density ────────────────────────────────────
def plot_volume_vs_defects() -> None:
    """Dual-axis: LOC/app bars vs D/kLOC line, sorted by LOC/app."""
    models = sorted(MODELS, key=lambda m: LOC_PER_APP[m])
    labels = _labels(models)

    loc_app = [LOC_PER_APP[m] for m in models]
    dd = [DEFECT_DENSITY[m] for m in models]

    fig, ax1 = plt.subplots(figsize=(12, 5))
    x = np.arange(len(models))

    bars = ax1.bar(x, loc_app, 0.55, color='#2E86AB', alpha=0.85, label='LOC/App', zorder=2)
    ax1.set_ylabel('Lines of Code per Application', color='#2E86AB')
    ax1.tick_params(axis='y', labelcolor='#2E86AB')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, ha='center')

    for bar, val in zip(bars, loc_app):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 30,
                 f'{val:,.0f}', ha='center', va='bottom', fontsize=14, color='#2E86AB')

    ax2 = ax1.twinx()
    ax2.plot(x, dd, 'o-', color='#C73E1D', linewidth=2, markersize=7, label='D/kLOC', zorder=3)
    ax2.set_ylabel('Defects per 1,000 LOC', color='#C73E1D')
    ax2.tick_params(axis='y', labelcolor='#C73E1D')

    for xi, val in zip(x, dd):
        ax2.annotate(f'{val:.1f}', (xi, val), textcoords='offset points',
                     xytext=(0, 10), ha='center', fontsize=14, color='#C73E1D')

    ax1.set_title('Code Volume vs. Defect Density by Model')
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=False)
    ax1.grid(axis='y', alpha=0.2, linewidth=0.5)
    ax1.spines['top'].set_visible(False)

    fig.savefig(OUT_DIR / 'volume_vs_defects.jpg', format='jpeg')
    plt.close(fig)
    print('  ✓ volume_vs_defects.jpg')


# ── Plot 3: Static Analysis Heatmap ──────────────────────────────────────────
def plot_static_heatmap() -> None:
    """Heatmap: discriminating static tools × models (avg findings/app)."""
    tools = ['Pylint', 'Ruff', 'ESLint', 'Mypy', 'Vulture', 'Bandit', 'Semgrep']
    models = MODELS
    model_labels = [SHORT_LABELS[m].replace('\n', ' ') for m in models]

    matrix = np.zeros((len(tools), len(models)))
    for i, tool in enumerate(tools):
        for j, m in enumerate(models):
            matrix[i, j] = HEATMAP[tool][m]

    fig, ax = plt.subplots(figsize=(12, 5))

    if HAS_SEABORN:
        sns.heatmap(matrix, annot=True, fmt='.1f', cmap='YlOrRd',
                    xticklabels=model_labels, yticklabels=tools,
                    ax=ax, linewidths=0.5, linecolor='white',
                    cbar_kws={'label': 'Avg. Findings per Application'})
    else:
        im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')
        ax.set_xticks(range(len(model_labels)))
        ax.set_xticklabels(model_labels, rotation=45, ha='right')
        ax.set_yticks(range(len(tools)))
        ax.set_yticklabels(tools)
        for i in range(len(tools)):
            for j in range(len(models)):
                ax.text(j, i, f'{matrix[i, j]:.1f}', ha='center', va='center', fontsize=14)
        plt.colorbar(im, ax=ax, label='Avg. Findings per Application')

    ax.set_title('Static Analysis Tool Findings Heatmap (Avg. per Application)')
    plt.tight_layout()

    fig.savefig(OUT_DIR / 'static_heatmap.jpg', format='jpeg')
    plt.close(fig)
    print('  ✓ static_heatmap.jpg')


# ── Plot 4: Severity Distribution Stacked Bars ───────────────────────────────
def plot_severity_distribution() -> None:
    """Stacked bar chart: High/Medium/Low findings per model (per app)."""
    total_findings = {m: SEVERITY_HIGH[m] + SEVERITY_MED[m] + SEVERITY_LOW[m]
                      for m in MODELS}
    models = sorted(MODELS, key=lambda m: total_findings[m], reverse=True)
    labels = _labels(models)

    n_apps = 20
    highs_pa = [SEVERITY_HIGH[m] / n_apps for m in models]
    meds_pa = [SEVERITY_MED[m] / n_apps for m in models]
    lows_pa = [SEVERITY_LOW[m] / n_apps for m in models]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    x = np.arange(len(models))
    w = 0.55

    ax.bar(x, highs_pa, w, label='High', color='#C73E1D', edgecolor='white', linewidth=0.3)
    ax.bar(x, meds_pa, w, bottom=highs_pa, label='Medium', color='#F18F01', edgecolor='white', linewidth=0.3)
    b2 = [h + m for h, m in zip(highs_pa, meds_pa)]
    ax.bar(x, lows_pa, w, bottom=b2, label='Low', color='#44BBA4', edgecolor='white', linewidth=0.3)

    totals = [h + m + l for h, m, l in zip(highs_pa, meds_pa, lows_pa)]
    for xi, t in zip(x, totals):
        ax.text(xi, t + 3, f'{t:.0f}', ha='center', va='bottom', fontsize=14, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(labels, ha='center')
    ax.set_ylabel('Findings per Application')
    ax.set_title('Severity Distribution of Findings by Model (per Application)')
    ax.legend(loc='upper right', frameon=False)
    ax.grid(axis='y', alpha=0.2, linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    fig.savefig(OUT_DIR / 'severity_distribution.jpg', format='jpeg')
    plt.close(fig)
    print('  ✓ severity_distribution.jpg')


# ── Plot 5: AI Compliance ────────────────────────────────────────────────────
def plot_compliance() -> None:
    """Bar chart with error bars: overall compliance % per model."""
    models = sorted(MODELS, key=lambda m: COMPLIANCE_MEAN[m], reverse=True)
    labels = _labels(models)

    means = [COMPLIANCE_MEAN[m] for m in models]
    stds = [COMPLIANCE_STD[m] for m in models]

    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(models))

    ax.bar(x, means, 0.55, yerr=stds, capsize=4, color=COLORS[:len(models)],
           edgecolor='white', linewidth=0.3, error_kw={'linewidth': 1.2, 'color': '#333'})

    for xi, m, s in zip(x, means, stds):
        ax.text(xi, m + s + 1.5, f'{m:.1f}%', ha='center', va='bottom', fontsize=11, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(labels, ha='center')
    ax.set_ylabel('Requirements Compliance (%)')
    ax.set_title('AI-Assessed Requirements Compliance by Model')
    max_top = max(m + s for m, s in zip(means, stds))
    ax.set_ylim(0, min(max_top * 1.18, 135))
    avg = np.mean(means)
    ax.axhline(y=avg, color='#888', linestyle='--', linewidth=1, alpha=0.6)
    ax.text(len(models) - 0.5, avg + 1, f'Mean: {avg:.1f}%', ha='right', fontsize=11, color='#666')
    ax.grid(axis='y', alpha=0.2, linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    fig.savefig(OUT_DIR / 'compliance.jpg', format='jpeg')
    plt.close(fig)
    print('  ✓ compliance.jpg')


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    print('Generating plots (200-app dataset, 10 models × 20 apps)...')

    plot_model_scorecard()
    plot_volume_vs_defects()
    plot_static_heatmap()
    plot_severity_distribution()
    plot_compliance()

    print(f'\nAll plots saved to {OUT_DIR}/')


if __name__ == '__main__':
    main()
