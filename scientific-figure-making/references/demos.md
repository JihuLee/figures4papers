# Real-World Demos and Figure Scripts

The design theory, patterns, and guidance in this skill are derived from the figure-making scripts in the [figures4papers](https://github.com/ChenLiu-1996/figures4papers) repository. Those scripts are the canonical demos for this skill.

**Repository:** [https://github.com/ChenLiu-1996/figures4papers](https://github.com/ChenLiu-1996/figures4papers)

## Project folders (demos)

The Python scripts ship with this skill under [`examples/`](../examples/), one folder per project. Read them directly; they need no network access. Each script is self-contained (data is hard-coded in the script, or in `raw_data.py` for ImmunoStruct). The scripts save to `./figures/` relative to the working directory, so copy and adapt them rather than running them inside the skill folder.

The rendered outputs (`figures/*.png`, `*.pdf`) are not bundled. To see what a script produces, open its GitHub folder.

| Project | Scripts in `examples/` | Shows | Outputs on GitHub |
|--------|------|--------|------|
| **figure_ImmunoStruct** | `plot_bars.py`, `raw_data.py` | Bar plots for quantitative comparison and ablation | [figure_ImmunoStruct](https://github.com/ChenLiu-1996/figures4papers/tree/main/figure_ImmunoStruct) |
| **figure_CellSpliceNet** | `plot_comparison.py`, `plot_ablation.py` | Bar comparison, ablation | [figure_CellSpliceNet](https://github.com/ChenLiu-1996/figures4papers/tree/main/figure_CellSpliceNet) |
| **figure_Brainteaser** | `plot_brute_force.py`, `plot_correctness_by_category.py`, `plot_correctness_by_subcategory.py`, `plot_rewriting.py`, `plot_selfcorrection_math.py` | Bar composition breakdown | [figure_Brainteaser](https://github.com/ChenLiu-1996/figures4papers/tree/main/figure_Brainteaser) |
| **figure_VIGIL** | `plot_comparison_radar.py`, `plot_posttraining.py`, `plot_ablation.py`, `plot_concept.py` | Radar plots, line plots, concept plots | [figure_VIGIL](https://github.com/ChenLiu-1996/figures4papers/tree/main/figure_VIGIL) |
| **figure_ophthal_review** | `plot_trend.py`, `plot_composition.py` | Trend plots | [figure_ophthal_review](https://github.com/ChenLiu-1996/figures4papers/tree/main/figure_ophthal_review) |
| **figure_RNAGenScape** | `plot_comparison.py`, `plot_comparison_speed.py`, `plot_sweep.py`, `plot_manifold.py`, `plot_hole_manifold.py` | Heat maps, manifolds, sweeps | [figure_RNAGenScape](https://github.com/ChenLiu-1996/figures4papers/tree/main/figure_RNAGenScape) |
| **figure_Dispersion** | `plot_illustration.py`, `plot_idea.py` | 3D-style spheres, performance plots | [figure_Dispersion](https://github.com/ChenLiu-1996/figures4papers/tree/main/figure_Dispersion) |
| **figure_Cflows** | `plot_comparison_Ablation.py`, `plot_comparison_GeneRegulatory.py`, `plot_comparison_Trajectory.py`, `diffusion_swiss_roll.py` | Comparison, ablation, trajectory plots | [figure_Cflows](https://github.com/ChenLiu-1996/figures4papers/tree/main/figure_Cflows) |

The `figure_*` folders in the figures4papers repository are the source of truth. `examples/` is a copy refreshed with `scripts/sync_skill_examples.sh` from the repository root.

## Related files

- [SKILL.md](../SKILL.md) — When to load this skill
- [api.md](api.md) — Constants, helpers, validation
- [common-patterns.md](common-patterns.md) — Layout and legend patterns
- [design-theory.md](design-theory.md) — Style theory and reproduction rules
- [tutorials.md](tutorials.md) — Step-by-step figure builds
