#!/usr/bin/env python3
"""Generate aggregate summary plots for Chapter 7 of the thesis.

Uses the 200-app dataset (10 models × 20 apps each, first-20 only for Claude).
Data is hardcoded from the Overleaf LaTeX tables to ensure plot–text consistency.
Produces 5 matplotlib figures as JPGs in plots/.
"""

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

# Model keys used throughout (alphabetical by short name)
MODELS = [
    'Claude 4.5 Sonnet',
    'DeepSeek R1',
    'Gemini 3 Flash',
    'Gemini 3 Pro',
    'GLM-4.7',
    'GPT-4o Mini',
    'GPT-5.2 Codex',
    'Llama 3.1 405B',
    'Mistral Small 3.1',
    'Qwen3 Coder+',
]

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

# ── 200-app data from Overleaf tables ────────────────────────────────────────
# From Table: Code Composition and Deployment Success
LOC_PER_APP = {
    'GPT-5.2 Codex': 1945, 'DeepSeek R1': 1749, 'Claude 4.5 Sonnet': 1735,
    'Qwen3 Coder+': 1300, 'GLM-4.7': 1176, 'Gemini 3 Flash': 1104,
    'Gemini 3 Pro': 986, 'Mistral Small 3.1': 784, 'GPT-4o Mini': 370,
    'Llama 3.1 405B': 364,
}

DEPLOY_PCT = {
    'GPT-5.2 Codex': 100, 'Gemini 3 Flash': 100, 'Claude 4.5 Sonnet': 85,
    'Gemini 3 Pro': 80, 'DeepSeek R1': 70, 'Qwen3 Coder+': 65,
    'GLM-4.7': 65, 'GPT-4o Mini': 20, 'Mistral Small 3.1': 0,
    'Llama 3.1 405B': 0,
}

# From Table: Findings by Severity per Model (D/kLOC column)
DEFECT_DENSITY = {
    'Llama 3.1 405B': 143.6, 'GPT-4o Mini': 118.6, 'Mistral Small 3.1': 115.7,
    'Claude 4.5 Sonnet': 110.4, 'GLM-4.7': 102.0, 'Gemini 3 Pro': 100.2,
    'Qwen3 Coder+': 98.1, 'Gemini 3 Flash': 92.5, 'DeepSeek R1': 68.5,
    'GPT-5.2 Codex': 45.5,
}

# Severity totals (from Findings by Severity table)
# Columns: Crit (all 0), High, Med, Low
SEVERITY_HIGH = {
    'Llama 3.1 405B': 69, 'GPT-4o Mini': 32, 'Mistral Small 3.1': 139,
    'Claude 4.5 Sonnet': 133, 'GLM-4.7': 148, 'Gemini 3 Pro': 74,
    'Qwen3 Coder+': 95, 'Gemini 3 Flash': 62, 'DeepSeek R1': 103,
    'GPT-5.2 Codex': 105,
}
SEVERITY_MED = {
    'Llama 3.1 405B': 887, 'GPT-4o Mini': 792, 'Mistral Small 3.1': 1543,
    'Claude 4.5 Sonnet': 1584, 'GLM-4.7': 1159, 'Gemini 3 Pro': 1114,
    'Qwen3 Coder+': 1266, 'Gemini 3 Flash': 1387, 'DeepSeek R1': 1350,
    'GPT-5.2 Codex': 1570,
}
SEVERITY_LOW = {
    'Llama 3.1 405B': 90, 'GPT-4o Mini': 55, 'Mistral Small 3.1': 131,
    'Claude 4.5 Sonnet': 2116, 'GLM-4.7': 1092, 'Gemini 3 Pro': 787,
    'Qwen3 Coder+': 1189, 'Gemini 3 Flash': 593, 'DeepSeek R1': 943,
    'GPT-5.2 Codex': 94,
}

# From Requirements Scanner table (mean compliance %, std)
COMPLIANCE_MEAN = {
    'GPT-5.2 Codex': 75.7, 'Gemini 3 Flash': 74.8, 'DeepSeek R1': 74.6,
    'Claude 4.5 Sonnet': 73.5, 'GLM-4.7': 68.3, 'Qwen3 Coder+': 63.7,
    'Mistral Small 3.1': 63.6, 'Gemini 3 Pro': 57.9, 'GPT-4o Mini': 56.6,
    'Llama 3.1 405B': 50.9,
}
COMPLIANCE_STD = {
    'GPT-5.2 Codex': 12.3, 'Gemini 3 Flash': 13.0, 'DeepSeek R1': 13.1,
    'Claude 4.5 Sonnet': 12.5, 'GLM-4.7': 12.6, 'Qwen3 Coder+': 11.8,
    'Mistral Small 3.1': 13.4, 'Gemini 3 Pro': 10.5, 'GPT-4o Mini': 11.2,
    'Llama 3.1 405B': 10.7,
}

# From Code Quality Analyzer table (mean score)
QUALITY_SCORE = {
    'GPT-5.2 Codex': 76.2, 'Claude 4.5 Sonnet': 75.9, 'GLM-4.7': 75.0,
    'Gemini 3 Flash': 72.6, 'DeepSeek R1': 70.5, 'Qwen3 Coder+': 68.6,
    'Gemini 3 Pro': 61.0, 'Mistral Small 3.1': 58.2, 'GPT-4o Mini': 56.1,
    'Llama 3.1 405B': 48.9,
}

# From Apache Bench table (mean RPS)
RPS = {
    'Qwen3 Coder+': 388.4, 'GPT-5.2 Codex': 383.6, 'DeepSeek R1': 382.4,
    'GPT-4o Mini': 382.1, 'Claude 4.5 Sonnet': 380.7, 'Gemini 3 Pro': 361.8,
    'GLM-4.7': 331.9, 'Gemini 3 Flash': 330.6,
    'Llama 3.1 405B': 0, 'Mistral Small 3.1': 0,
}

# Output token price ($/M tokens)
PRICES = {
    'Claude 4.5 Sonnet': 15.00, 'DeepSeek R1': 1.75, 'Gemini 3 Flash': 3.00,
    'Gemini 3 Pro': 12.00, 'GLM-4.7': 1.50, 'GPT-4o Mini': 0.60,
    'GPT-5.2 Codex': 14.00, 'Llama 3.1 405B': 4.00,
    'Mistral Small 3.1': 0.11, 'Qwen3 Coder+': 5.00,
}

# Heatmap: avg findings/app from per-tool tables
HEATMAP = {
    'Pylint': {
        'Claude 4.5 Sonnet': 134.6, 'DeepSeek R1': 51.7, 'Gemini 3 Flash': 46.7,
        'Gemini 3 Pro': 48.4, 'GLM-4.7': 50.9, 'GPT-4o Mini': 12.7,
        'GPT-5.2 Codex': 50.5, 'Llama 3.1 405B': 9.2, 'Mistral Small 3.1': 17.4,
        'Qwen3 Coder+': 50.9,
    },
    'Ruff': {
        'Claude 4.5 Sonnet': 128.7, 'DeepSeek R1': 53.4, 'Gemini 3 Flash': 45.4,
        'Gemini 3 Pro': 50.5, 'GLM-4.7': 68.4, 'GPT-4o Mini': 13.9,
        'GPT-5.2 Codex': 23.7, 'Llama 3.1 405B': 9.7, 'Mistral Small 3.1': 19.9,
        'Qwen3 Coder+': 72.0,
    },
    'ESLint': {
        'Claude 4.5 Sonnet': 50.0, 'DeepSeek R1': 53.2, 'Gemini 3 Flash': 46.0,
        'Gemini 3 Pro': 38.6, 'GLM-4.7': 39.2, 'GPT-4o Mini': 25.0,
        'GPT-5.2 Codex': 51.5, 'Llama 3.1 405B': 32.6, 'Mistral Small 3.1': 59.1,
        'Qwen3 Coder+': 46.1,
    },
    'Mypy': {
        'Claude 4.5 Sonnet': 42.2, 'DeepSeek R1': 34.4, 'Gemini 3 Flash': 26.8,
        'Gemini 3 Pro': 23.3, 'GLM-4.7': 26.3, 'GPT-4o Mini': 16.2,
        'GPT-5.2 Codex': 56.0, 'Llama 3.1 405B': 16.4, 'Mistral Small 3.1': 28.6,
        'Qwen3 Coder+': 26.1,
    },
    'Vulture': {
        'Claude 4.5 Sonnet': 15.4, 'DeepSeek R1': 13.3, 'Gemini 3 Flash': 13.7,
        'Gemini 3 Pro': 12.8, 'GLM-4.7': 12.1, 'GPT-4o Mini': 9.3,
        'GPT-5.2 Codex': 20.4, 'Llama 3.1 405B': 8.7, 'Mistral Small 3.1': 9.3,
        'Qwen3 Coder+': 8.1,
    },
    'Bandit': {
        'Claude 4.5 Sonnet': 3.9, 'DeepSeek R1': 4.5, 'Gemini 3 Flash': 2.5,
        'Gemini 3 Pro': 3.4, 'GLM-4.7': 6.7, 'GPT-4o Mini': 1.4,
        'GPT-5.2 Codex': 4.5, 'Llama 3.1 405B': 3.3, 'Mistral Small 3.1': 4.4,
        'Qwen3 Coder+': 3.8,
    },
    'Semgrep': {
        'Claude 4.5 Sonnet': 9.0, 'DeepSeek R1': 8.8, 'Gemini 3 Flash': 8.3,
        'Gemini 3 Pro': 7.4, 'GLM-4.7': 8.0, 'GPT-4o Mini': 5.4,
        'GPT-5.2 Codex': 9.2, 'Llama 3.1 405B': 6.7, 'Mistral Small 3.1': 7.6,
        'Qwen3 Coder+': 6.2,
    },
}

# Thesis-friendly colour palette
COLORS = [
    '#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#3B1F2B',
    '#44BBA4', '#E94F37', '#393E41', '#8D6A9F', '#5FAD56',
]

plt.rcParams.update({
    'font.size': 11,
    'axes.titlesize': 13,
    'axes.labelsize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 10,
    'legend.fontsize': 9,
    'figure.dpi': 200,
    'savefig.dpi': 200,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.15,
})


def _labels(models: list[str]) -> list[str]:
    return [SHORT_LABELS[m] for m in models]


def _norm(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]


# ── Plot 1: Model Scorecard ─────────────────────────────────────────────────
def plot_model_scorecard() -> None:
    """Grouped bar chart: 6 normalised metrics × 10 models."""
    models = MODELS
    labels = _labels(models)

    compliance = [COMPLIANCE_MEAN[m] for m in models]
    quality = [QUALITY_SCORE[m] for m in models]
    loc_app = [LOC_PER_APP[m] for m in models]
    dd_inv = [1000 / max(DEFECT_DENSITY[m], 1) for m in models]
    rps = [RPS[m] for m in models]
    cost_eff = [1.0 / PRICES[m] for m in models]

    metrics = {
        'Compliance': _norm(compliance),
        'Code Quality': _norm(quality),
        'Code Volume': _norm(loc_app),
        'Low Defect\nDensity': _norm(dd_inv),
        'Performance\n(RPS)': _norm(rps),
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
                 f'{val:,.0f}', ha='center', va='bottom', fontsize=8, color='#2E86AB')

    ax2 = ax1.twinx()
    ax2.plot(x, dd, 'o-', color='#C73E1D', linewidth=2, markersize=7, label='D/kLOC', zorder=3)
    ax2.set_ylabel('Defects per 1,000 LOC', color='#C73E1D')
    ax2.tick_params(axis='y', labelcolor='#C73E1D')

    for xi, val in zip(x, dd):
        ax2.annotate(f'{val:.1f}', (xi, val), textcoords='offset points',
                     xytext=(0, 10), ha='center', fontsize=8, color='#C73E1D')

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
                ax.text(j, i, f'{matrix[i, j]:.1f}', ha='center', va='center', fontsize=8)
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
        ax.text(xi, t + 3, f'{t:.0f}', ha='center', va='bottom', fontsize=8, fontweight='bold')

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
        ax.text(xi, m + s + 1.5, f'{m:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(labels, ha='center')
    ax.set_ylabel('Requirements Compliance (%)')
    ax.set_title('AI-Assessed Requirements Compliance by Model')
    ax.set_ylim(0, 115)
    avg = np.mean(means)
    ax.axhline(y=avg, color='#888', linestyle='--', linewidth=1, alpha=0.6)
    ax.text(len(models) - 0.5, avg + 1, f'Mean: {avg:.1f}%', ha='right', fontsize=9, color='#666')
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
