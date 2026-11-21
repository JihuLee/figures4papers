import os
import numpy as np
from matplotlib import pyplot as plt
import seaborn as sns
import sys
_HERE = os.path.dirname(os.path.abspath(__file__))
# mpl_texmath: per-segment LaTeX math. Repo layout: ../scientific-figure-making/scripts; skill copy: ../../scripts
for _p in ('../scientific-figure-making/scripts', '../../scripts'):
    sys.path.insert(0, os.path.normpath(os.path.join(_HERE, _p)))
import mpl_texmath as tm  # noqa: E402


DATA = {
    'clinical_stage': [
        'Benchmark\nEvaluation', 'Expert\nEvaluation', 'Retrospective\nClinical Validation',
        'Prospective\nPilot Study', 'Full\nClinical Trial',
    ],
    'pub_by_category':
        {
            'Clinical Workflow': {
                'Screening or Diagnosis': [10, 7, 10, 3, 0],
                'Report Generation': [2, 3, 3, 0, 0],
                'Treatment Planning or\nRecommendation': [2, 3, 3, 2, 0],
            },
            'Patient Support': {
                'Patient Question Answering': [5, 13, 1, 1, 0],
                'After Visit or Discharge\nSummary Generation': [0, 2, 0, 0, 0],
                'Consultation or Interview': [0, 1, 1, 0, 0],
                'Patient Education\nMaterial Generation': [1, 6, 0, 0, 0],
                'Physician Recommendation': [0, 1, 0, 0, 0],
            },
            'Education and Training': {
                'Exam Taking': [19, 5, 0, 0, 0],
                'Medical Education and\nLearning Support': [3, 5, 0, 0, 0],
            }
        }
}

def plot_heatmap(fig_name: str):
    # Only the $...$ segments go through LaTeX (tm.mixed_text); the rest stays in the sans font.
    # Never set text.usetex globally: it would re-typeset every label, sans text included.
    tm.add_tex_font('texgyreheros')
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = ['Helvetica', 'Arial', 'TeX Gyre Heros', 'DejaVu Sans']
    tm.setup_math()   # Computer Modern; pass paper='main.tex' to use the paper's math font and macros
    plt.rcParams['font.size'] = 16
    plt.rcParams['axes.spines.right'] = False
    plt.rcParams['axes.spines.top'] = False
    plt.rcParams['axes.linewidth'] = 2

    os.makedirs(os.path.dirname(fig_name), exist_ok=True)
    fig = plt.figure(figsize=(14, 10))

    ax = fig.add_subplot(1, 1, 1)
    category_count_arr, category_arr = [], []
    subcategory_arr = []
    value_arr = []
    for category in DATA['pub_by_category']:
        subcategories = DATA['pub_by_category'][category].keys()
        category_count_arr.append(len(subcategories))
        category_arr.append(category)
        for subcategory in subcategories:
            value = DATA['pub_by_category'][category][subcategory]
            subcategory_arr.append(subcategory)
            value_arr.append(value)
    value_arr = np.stack(value_arr, axis=0)
    for loc, item in enumerate(subcategory_arr):
        item += '\n' + rf'($n={value_arr[loc, :].sum()}$)'
        subcategory_arr[loc] = item
    stage_arr = DATA['clinical_stage']
    for loc, item in enumerate(stage_arr):
        item += '\n' + rf'($n={value_arr[:, loc].sum()}$)'
        stage_arr[loc] = item

    hm = sns.heatmap(value_arr, annot=True, vmin=0, vmax=20, fmt='d', cmap='Reds',
                linewidths=1, linecolor='white', ax=ax, cbar=True)
    cbar = hm.collections[0].colorbar
    cbar.set_ticks([0, 5, 10, 15, 20])
    cbar.set_ticklabels([0, 5, 10, 15, 20])
    # Tick labels mix sans text and math ("(n = 12)"), so they are drawn as mixed text next to empty ticks.
    pad = plt.rcParams['ytick.major.size'] + plt.rcParams['ytick.major.pad']
    ax.set_yticks(np.arange(len(subcategory_arr)) + 0.5)
    ax.set_yticklabels([])
    for loc, item in enumerate(subcategory_arr):
        tm.mixed_text(ax, 0, loc + 0.5, item, ha='right', va='center', multialignment='center',
                      transform=ax.get_yaxis_transform(), offset=(-pad, 0))
    ax.set_xticks(np.arange(len(stage_arr)) + 0.5)
    ax.set_xticklabels([])
    for loc, item in enumerate(stage_arr):
        tm.mixed_text(ax, loc + 0.5, 0, item, ha='center', va='top',
                      transform=ax.get_xaxis_transform(), offset=(0, -pad))

    fig.tight_layout(pad=2)
    tm.save_figure(fig, fig_name, dpi=300)   # PDF + PNG (rasterized from the PDF when dvipng is missing)
    return


if __name__ == '__main__':
    plot_heatmap('./figures/composition_heatmap.png')