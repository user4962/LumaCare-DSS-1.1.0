# Reproducible software evaluation

Run the deterministic requirements matrix and local latency benchmark from this directory with the backend virtual environment:

```bash
../backend/.venv/bin/python run_evaluation.py --iterations 50000
```

The command writes `results/scenario_results.csv` and `results/evaluation_summary.json`. The summary records the Python and platform identifiers, a SHA-256 digest of the evaluated engine source, scenario counts, deterministic repeatability, and latency statistics.

The requirement-level metrics are:

- `action_accuracy_against_requirements`, the proportion of scenarios satisfying the expected action, required rule, determinism, and output invariants;
- `hold_requirement_pass_rate`, the pass proportion among scenarios whose requirement expects `HOLD`;
- `completion_requirement_pass_rate`, the pass proportion among scenarios whose requirement expects `COMPLETE`;
- `nonhold_requirement_pass_rate`, the pass proportion among scenarios whose requirement expects `ALLOW`, `ADJUST`, or `COMPLETE`;
- `action_counts`, the number of observed outcomes per action.

Expected actions and rules are derived from documented software requirements. Scenario labels do not represent clinical outcomes. Latency is measured on one local runtime and does not establish a real-time guarantee. The harness does not model sensor error distributions, tissue optics, or treatment efficacy, so these metrics must not be presented as clinical sensitivity, specificity, safety, or effectiveness.
