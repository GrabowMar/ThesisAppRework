#!/usr/bin/env python3
"""Generate aggregate summary plots for Chapter 7 of the thesis.

Reads thesis_data.json and produces 5 matplotlib figures as JPGs in plots/.
"""

import json
import pathlib
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

try:
    import seaborn as sns
    HAS_SEABORN = True
except ImportError:
    HAS_SEABORN = False

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / 'thesis_data.json'
OUT_DIR = ROOT / 'plots'

# Consistent short names and ordering (alphabetical by short name)
MODEL_ORDER = [
    'anthropic_claude-4.5-sonnet-20250929',
    'deepseek_deepseek-r1-0528',
    'google_gemini-3-flash-preview-20251217',
    'google_gemini-3-pro-preview-20251117',
    'z-ai_glm-4.7-20251222',
    'openai_gpt-4o-mini',
    'openai_gpt-5.2-codex-20260114',
    'meta-llama_llama-3.1-405b-instruct',
    'mistralai_mistral-small-3.1-24b-instruct-2503',
    'qwen_qwen3-coder-plus',
]

SHORT_NAMES = {
    'anthropic_claude-4.5-sonnet-20250929': 'Claude 4.5\nSonnet',
    'deepseek_deepseek-r1-0528': 'DeepSeek\nR1',
    'google_gemini-3-flash-preview-20251217': 'Gemini 3\nFlash',
    'google_gemini-3-pro-preview-20251117': 'Gemini 3\nPro',
    'z-ai_glm-4.7-20251222': 'GLM-4.7',
    'openai_gpt-4o-mini': 'GPT-4o\nMini',
    'openai_gpt-5.2-codex-20260114': 'GPT-5.2\nCodex',
    'meta-llama_llama-3.1-405b-instruct': 'Llama 3.1\n405B',
    'mistralai_mistral-small-3.1-24b-instruct-2503': 'Mistral\nSmall 3.1',
    'qwen_qwen3-coder-plus': 'Qwen3\nCoder+',
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


def load_data() -> dict:
    with open(DATA_FILE) as f:
        return json.load(f)


def _labels(slugs: list[str]) -> list[str]:
    return [SHORT_NAMES[s] for s in slugs]


# ── Plot 1: Model Scorecard ─────────────────────────────────────────────────
def plot_model_scorecard(data: dict) -> None:
    """Grouped bar chart: 6 normalised metrics × 10 models."""
    ms = data['model_summary']
    ai = data['ai_compliance']
    perf = data['performance']

    slugs = MODEL_ORDER
    labels = _labels(slugs)

    # Raw values per metric
    compliance = [ai[s]['overall']['mean'] for s in slugs]
    quality = []
    for s in slugs:
        cqa = data.get('ai_tools', {}).get('code-quality-analyzer', {}).get('per_model', {})
        model_cqa = cqa.get(s, {})
        quality.append(model_cqa.get('score', {}).get('mean', 50))

    loc_app = [ms[s]['total_loc'] / ms[s]['stats']['n'] for s in slugs]
    dd_inv = [1000 / max(ms[s]['defect_density_kloc'], 1) for s in slugs]  # inverse: higher=better
    rps = [perf[s]['backend_mean'] if perf[s] else 0 for s in slugs]

    # Cost efficiency: inverse of output price (from v3 table data)
    prices = {
        'anthropic_claude-4.5-sonnet-20250929': 15.00,
        'deepseek_deepseek-r1-0528': 1.75,
        'google_gemini-3-flash-preview-20251217': 3.00,
        'google_gemini-3-pro-preview-20251117': 12.00,
        'z-ai_glm-4.7-20251222': 1.50,
        'openai_gpt-4o-mini': 0.60,
        'openai_gpt-5.2-codex-20260114': 14.00,
        'meta-llama_llama-3.1-405b-instruct': 4.00,
        'mistralai_mistral-small-3.1-24b-instruct-2503': 0.11,
        'qwen_qwen3-coder-plus': 5.00,
    }
    cost_eff = [1.0 / prices[s] for s in slugs]

    def _norm(vals: list[float]) -> list[float]:
        lo, hi = min(vals), max(vals)
        if hi == lo:
            return [0.5] * len(vals)
        return [(v - lo) / (hi - lo) for v in vals]

    metrics = {
        'Compliance': _norm(compliance),
        'Code Quality': _norm(quality),
        'Code Volume': _norm(loc_app),
        'Low Defect\nDensity': _norm(dd_inv),
        'Performance\n(RPS)': _norm(rps),
        'Cost\nEfficiency': _norm(cost_eff),
    }

    n_models = len(slugs)
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
def plot_volume_vs_defects(data: dict) -> None:
    """Dual-axis: LOC/app bars vs D/kLOC line, sorted by LOC/app."""
    ms = data['model_summary']
    slugs = sorted(MODEL_ORDER, key=lambda s: ms[s]['total_loc'] / ms[s]['stats']['n'])
    labels = _labels(slugs)

    loc_app = [ms[s]['total_loc'] / ms[s]['stats']['n'] for s in slugs]
    dd = [ms[s]['defect_density_kloc'] for s in slugs]

    fig, ax1 = plt.subplots(figsize=(12, 5))
    x = np.arange(len(slugs))

    bars = ax1.bar(x, loc_app, 0.55, color='#2E86AB', alpha=0.85, label='LOC/App', zorder=2)
    ax1.set_ylabel('Lines of Code per Application', color='#2E86AB')
    ax1.tick_params(axis='y', labelcolor='#2E86AB')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, ha='center')

    # Value labels on bars
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
def plot_static_heatmap(data: dict) -> None:
    """Heatmap: discriminating static tools × models (avg findings/app)."""
    st = data['static_tools']
    ms = data['model_summary']

    # Most discriminating tools (exclude uniform dependency scanners)
    tools = ['pylint', 'ruff', 'eslint', 'mypy', 'vulture', 'bandit', 'semgrep']
    tool_labels = ['Pylint', 'Ruff', 'ESLint', 'Mypy', 'Vulture', 'Bandit', 'Semgrep']

    slugs = MODEL_ORDER
    model_labels = [SHORT_NAMES[s].replace('\n', ' ') for s in slugs]

    matrix = np.zeros((len(tools), len(slugs)))
    for i, tool in enumerate(tools):
        pm = st[tool]['per_model']
        for j, s in enumerate(slugs):
            n_apps = ms[s]['stats']['n']
            total = pm.get(s, {}).get('findings', 0)
            matrix[i, j] = total / n_apps

    fig, ax = plt.subplots(figsize=(12, 5))

    if HAS_SEABORN:
        sns.heatmap(matrix, annot=True, fmt='.1f', cmap='YlOrRd',
                    xticklabels=model_labels, yticklabels=tool_labels,
                    ax=ax, linewidths=0.5, linecolor='white',
                    cbar_kws={'label': 'Avg. Findings per Application'})
    else:
        im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')
        ax.set_xticks(range(len(model_labels)))
        ax.set_xticklabels(model_labels, rotation=45, ha='right')
        ax.set_yticks(range(len(tool_labels)))
        ax.set_yticklabels(tool_labels)
        for i in range(len(tools)):
            for j in range(len(slugs)):
                ax.text(j, i, f'{matrix[i, j]:.1f}', ha='center', va='center', fontsize=8)
        plt.colorbar(im, ax=ax, label='Avg. Findings per Application')

    ax.set_title('Static Analysis Tool Findings Heatmap (Avg. per Application)')
    plt.tight_layout()

    fig.savefig(OUT_DIR / 'static_heatmap.jpg', format='jpeg')
    plt.close(fig)
    print('  ✓ static_heatmap.jpg')


# ── Plot 4: Severity Distribution Stacked Bars ───────────────────────────────
def plot_severity_distribution(data: dict) -> None:
    """Stacked bar chart: High/Medium/Low findings per model."""
    ms = data['model_summary']
    slugs = sorted(MODEL_ORDER, key=lambda s: ms[s]['total_findings'], reverse=True)
    labels = _labels(slugs)

    highs = [ms[s]['severity']['high'] for s in slugs]
    meds = [ms[s]['severity']['medium'] for s in slugs]
    lows = [ms[s]['severity']['low'] for s in slugs]

    # Per-app normalisation
    n_apps = [ms[s]['stats']['n'] for s in slugs]
    highs_pa = [h / n for h, n in zip(highs, n_apps)]
    meds_pa = [m / n for m, n in zip(meds, n_apps)]
    lows_pa = [l / n for l, n in zip(lows, n_apps)]

    fig, ax = plt.subplots(figsize=(12, 5.5))
    x = np.arange(len(slugs))
    w = 0.55

    ax.bar(x, highs_pa, w, label='High', color='#C73E1D', edgecolor='white', linewidth=0.3)
    ax.bar(x, meds_pa, w, bottom=highs_pa, label='Medium', color='#F18F01', edgecolor='white', linewidth=0.3)
    bottoms = [h + m for h, m in zip(highs_pa, meds_pa)]
    ax.bar(x, lows_pa, w, bottom=bottoms, label='Low', color='#44BBA4', edgecolor='white', linewidth=0.3)

    # Total labels
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
def plot_compliance(data: dict) -> None:
    """Bar chart with error bars: overall compliance % per model."""
    ai = data['ai_compliance']
    ms = data['model_summary']

    slugs = sorted(MODEL_ORDER, key=lambda s: ai[s]['overall']['mean'], reverse=True)
    labels = _labels(slugs)

    means = [ai[s]['overall']['mean'] for s in slugs]
    stds = [ai[s]['overall']['std'] for s in slugs]

    fig, ax = plt.subplots(figsize=(12, 5))
    x = np.arange(len(slugs))

    bars = ax.bar(x, means, 0.55, yerr=stds, capsize=4, color=COLORS[:len(slugs)],
                  edgecolor='white', linewidth=0.3, error_kw={'linewidth': 1.2, 'color': '#333'})

    for xi, m, s in zip(x, means, stds):
        ax.text(xi, m + s + 1.5, f'{m:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels(labels, ha='center')
    ax.set_ylabel('Requirements Compliance (%)')
    ax.set_title('AI-Assessed Requirements Compliance by Model')
    ax.set_ylim(0, 115)
    ax.axhline(y=np.mean(means), color='#888', linestyle='--', linewidth=1, alpha=0.6)
    ax.text(len(slugs) - 0.5, np.mean(means) + 1, f'Mean: {np.mean(means):.1f}%',
            ha='right', fontsize=9, color='#666')
    ax.grid(axis='y', alpha=0.2, linewidth=0.5)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    fig.savefig(OUT_DIR / 'compliance.jpg', format='jpeg')
    plt.close(fig)
    print('  ✓ compliance.jpg')


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    data = load_data()
    print(f'Loaded data: {len(data["model_summary"])} models, {data["overview"]["total_apps"]} apps')
    print('Generating plots...')

    plot_model_scorecard(data)
    plot_volume_vs_defects(data)
    plot_static_heatmap(data)
    plot_severity_distribution(data)
    plot_compliance(data)

    print(f'\nAll plots saved to {OUT_DIR}/')


if __name__ == '__main__':
    main()
