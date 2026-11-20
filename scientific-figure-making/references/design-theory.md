# Publication Figure Design Theory (Derived from Repository Scripts)

This theory is inferred from the Python plotting scripts in the [figures4papers](https://github.com/ChenLiu-1996/figures4papers) repository (the `figure_*` project folders). See [demos.md](demos.md) for links to those demos.

## 1) Core Matplotlib Style System

The dominant house style is minimalist, high-contrast, and publication-oriented:

- Typography:
  - Primary: `font.family = 'helvetica'` (used in 16 scripts).
  - Secondary exception: `font.family = 'sans-serif'` (2 scripts, mostly geometric illustrations).
  - Practical portability recommendation: prefer fallback stack `['Arial', 'Helvetica', 'DejaVu Sans', 'sans-serif']`.
- Size hierarchy:
  - Large-panel bar/comparison figures: `font.size = 24`, `axes.linewidth = 3`.
  - Paper subfigures/compact analytic plots: `font.size = 15-16`, `axes.linewidth = 2`.
- Axes cleanup:
  - `axes.spines.right = False`
  - `axes.spines.top = False`
- Math (LaTeX per segment):
  - Only the `$...$` segments of a label go through LaTeX; the rest of the label stays in the sans figure font. Each
    math segment is its own `usetex=True` text object, measured and placed on the common baseline
    (`scripts/mpl_texmath.py`: `mixed_text`, `mixed_legend`, `math_labels`). See section 8b.
  - Never set `text.usetex = True` globally: it re-typesets every label, sans text and tick numbers included, in a
    LaTeX font. The example scripts used to do this; they now use the per-segment helper.
- Vector text:
  - `svg.fonttype = 'none'` appears when preserving editable text in vector exports.

## 2) Export and Output Policy

- DPI defaults:
  - Standard: `dpi=300` (dominant: 23 save calls).
  - Very dense bar panels: `dpi=600` (used in ImmunoStruct bars).
- Layout finalization:
  - `fig.tight_layout(pad=2)` is the default finishing pass (21 occurrences).
  - `pad=1` is used for compact multi-panel plots.
- Mostly opaque white-background output; occasional `bbox_inches='tight'` with explicit `pad_inches` for edge-to-edge composites.

## 3) Color Theory and Palette Structure

The repository uses a consistent semantic palette family:

- Anchor/brand blue:
  - `#0F4D92` and `#3775BA` (method-of-interest / reference baseline).
- Green performance bands (often incremental gains):
  - `#DDF3DE`, `#AADCA9`, `#8BCF8B`.
- Warm red/pink comparator bands:
  - `#F6CFCB`, `#E9A6A1`, `#B64342`.
- Neutral support grays:
  - `#CFCECE`, `#767676`, `#4D4D4D`, `#272727`.
- Occasional accent/highlight colors:
  - Gold `#FFD700`, magenta-like `#EA84DD`, teal `#42949E`, violet `#9A4D8E`.

Design intent:

- Use blue for "proposed" or key method.
- Use green shades for related positives/improvements.
- Use pink/red shades for alternatives or contrasts.
- Keep neutrals for baselines and background categories.

## 4) Layout and Composition Logic

Common geometric/layout decisions:

- **Ultra-Wide Aspect Ratios:** For multi-metric comparisons (e.g., 3-4 metrics), the repository uses extremely wide canvases (e.g., `figsize=(45, 12)` or `(28, 6)`). This prevents vertical crowding and allows metrics to be read as a narrative from left to right.
- **Dedicated Legend Panels:** In complex multi-axis figures, a sub-plot is often dedicated solely to the legend (`ax.set_axis_off()`). This keeps the data panels clean and prevents legend boxes from overlapping critical data regions.
- **Categorical Abstracting:** Category bars usually hide x-tick labels (`ax.set_xticks([])`) and rely on legends/titles instead. This is particularly effective when comparing many methods across multiple metrics.
- **Dynamic Y-Axis Scaling:** Y-limits are manually tightened to relevant ranges (often derived from `data.min() - data.std()`), emphasizing comparative differences rather than absolute values.
- **Consistency over Embellishment:** Multi-panel consistency is favored over per-axis embellishment. All subplots in a row share the same font sizes, linewidths, and color semantic mapping.

## 5) Bar Encoding Strategy

For publication-grade grouped/ablation bars:

- **In-Place Annotation:** Scientific values are often printed directly above bars (`ax.text`) with large fonts (36pt) to make exact numbers readable without a grid.
- **Manual Tick Positioning:** Uses `FixedLocator` for precise control over Y-axis granularity.
- **Strong edge treatment:** Bars use black edges (`edgecolor='black'`) with `linewidth=1.5-3` for sharp separation.
- **Alpha-Based Ablation:** Ablation studies often use the same primary color (e.g., `blue_secondary`) with varying `alpha` levels (0.2 to 1.0) to represent the "completeness" of a method.
- **Hatch Encoding:** Optional hatch channels (slashes/backslashes/dots) are used for subtype overlays to remain readable in grayscale print.

## 6) Trend/Line Encoding Strategy

- Limited line count per axis (usually 2-4 primary curves).
- Use consistent line width around `2-3` with controlled alpha.
- Use `fill_between` for uncertainty when needed.
- Keep grid minimal or absent; rely on axis ticks and direct legend reading.

**Polar / radar:** Keep the number of series readable at publication size; use the same line-weight and label discipline as Cartesian trends. Repository examples live under `figure_VIGIL` (see [demos.md](demos.md)).

## 7) Scatter/Illustration Encoding Strategy

- Dense geometric scenes use lowered alpha and muted fills.
- Important trajectories/relations use saturated warm accents with arrows.
- Axis ticks often removed for conceptual diagrams.

## 8) Recommended Reusable rcParams Preset

```python
PUBLICATION_RCPARAMS = {
    "font.family": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "font.size": 16,            # use 24 for large comparison bars
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 2.5,      # 3 for big bars, 2 for compact figures
    "legend.frameon": False,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,         # TrueType text in PDFs; the default (3) embeds Type 3 fonts that camera-ready checks reject
    "ps.fonttype": 42,
}
```

## 8b) Math in Labels

Typeset math with real LaTeX, in the paper's math font and notation, and leave the sans text alone:

```python
import mpl_texmath as tm                      # scientific-figure-making/scripts/mpl_texmath.py

tm.setup_math(paper="paper/main.tex")         # math setup, packages and \newcommand macros of the paper
tm.mixed_text(ax, 0.5, 0.9, r"scores $S[i,v,p]$", ha="center", transform=ax.transAxes)
tm.mixed_text(ax, x, y, "$c_{FA}, c_{FR}$ and $c_{view}$", fontsize=6)   # segments on one baseline
tm.mixed_legend(ax.legend())                  # legend entries such as r"$\ell_2$-repel"
tm.math_labels(ax.get_xticklabels())          # labels that are one $...$ segment each
tm.save_figure(fig, "figures/fig1")           # PDF + PNG, font and size check
```

- **Font matching.** `setup_math(paper=...)` reads the preamble, `\input` macro files and local `.sty`/`.cls`. The math is
  Computer Modern unless the paper loads a math font package (`newtxmath`, `mathptmx`, `newpxmath`, ...).
  `\usepackage{times}` (cvpr.sty) changes only the text font, so the math stays Computer Modern. Override with
  `math="newtx"` or verbatim LaTeX. The paper's macros are copied, so write the paper's notation (`$c_{FA}$`, not
  `$c_{\mathrm{FA}}$` when the paper writes `c_{FA}`).
- **Sizes.** The math base size equals the label's font size, and LaTeX sets the scripts: 6pt → 5pt, 7pt → 5pt,
  8pt → 6pt, 10pt → 7pt (other sizes are declared with 0.7×/0.5× and a 5pt floor). Make `figsize` the printed size
  so these are printed sizes. `check_pdf` (run by `save_figure`) fails on text below 5pt and warns when math scripts
  fall below 6pt. Fix it with a larger base size or a `\DeclareMathSizes` line (`setup_math(extra=...)`), never by
  shrinking or hand-drawing subscripts.
- **Output.** Math embeds Type 1 fonts (CMMI6, CMR5, ...); text uses TrueType (`pdf.fonttype = 42`); Type 3 is an
  error. Without `dvipng`, `save_figure` rasterizes the PNG from the PDF (PyMuPDF or `pdftoppm`).
- **Don'ts.** No global `text.usetex`; no subscripts drawn as separate smaller text; no mathtext in the sans font for
  math (`$x_i$` without LaTeX); no silent change of the paper's notation.
- **Tools.** Needs `latex` (TeX Live, MiKTeX or TinyTeX); `kpsewhich` lets `tm.add_tex_font('texgyreheros')` register
  the TeX tree's Helvetica clone. Without LaTeX the helper warns and falls back to mathtext in Computer Modern.

## 9) Recommended Default Palette

```python
PALETTE = {
    "blue_main": "#0F4D92",
    "blue_secondary": "#3775BA",
    "green_1": "#DDF3DE",
    "green_2": "#AADCA9",
    "green_3": "#8BCF8B",
    "red_1": "#F6CFCB",
    "red_2": "#E9A6A1",
    "red_strong": "#B64342",
    "neutral": "#CFCECE",
    "highlight": "#FFD700",
}
```

## 10) Reproduction Rules

To match the repository's visual identity for new figures:

1. Apply minimalist spines (top/right off), frameless legends, and explicit y-limits.
2. Use Helvetica/Arial-like sans fonts with larger sizing for bars. Typeset math per segment with LaTeX (section 8b),
   never with a global `text.usetex`.
3. Choose colors from the blue-green-red-neutral family above; avoid unrelated palettes.
4. Finalize with `tight_layout(pad=2)` and export at `dpi=300` (or `600` for dense bar panels).
5. Use hatch/edge encodings for print-safe category separation when bars overlap in hue.

## Related files

- [SKILL.md](../SKILL.md) — When to load this skill
- [api.md](api.md) — Formal `PALETTE` and function contracts
- [demos.md](demos.md) — Repository scripts this theory summarizes
- [common-patterns.md](common-patterns.md) — Operational patterns from the theory
- [tutorials.md](tutorials.md) — Hands-on flows grounded in this theory
