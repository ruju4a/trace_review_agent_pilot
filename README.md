# Trace-assisted agent code review

The current workflow selects SWE-rebench tasks and agent-generated patches, then creates experiment packets that you can hand to different reviewer agents. It saves original condition-specific trajectory excerpts as text and JSON for researcher inspection. No UI or model API call is needed to generate experiments.

## Generate experiments

Try the included synthetic cases:

```bash
python -m src.generate_experiments --cases data/demo_cases.jsonl --out outputs/demo_experiments
```

For real dataset cases, first sample and match the datasets (replace revision placeholders with dataset commit SHAs):

```bash
python -m src.prepare_cases --n 30 --seed 42 \
  --trajectory-revision TRAJECTORY_COMMIT_SHA \
  --base-revision BENCHMARK_COMMIT_SHA \
  --out data/selected_cases.jsonl

python -m src.generate_experiments \
  --cases data/selected_cases.jsonl \
  --conditions control rationale context validation alternatives full \
  --repeats 1 --seed 42 \
  --out outputs/experiments
```

These cases pair a benchmark task with a recorded agent attempt; the reviewed patch is the agent's patch, not the reference PR patch. The current sample policy selects one eligible attempt per distinct issue. Existing output directories are never overwritten; choose a new path for each generation.

Output structure:

```text
outputs/experiments/
  reviewer_packets/
    case_0001_validation_r1/
      review_prompt.txt
      task.txt
      patch.diff
      trajectory_excerpt.txt
      response_template.json
    ...
  researcher_only/
    assignment_manifest.json
    generation_manifest.json
    case_0001/
      case_metadata.json
      full_trajectory.json
      inspect_selections.txt
      validation_selection.json
      ...
  README.txt
```

Give an agent only its assigned packet folder and use `review_prompt.txt` as its input. Use a fresh session for each independent review. Compare different reviewer agents on the same packets. Never share `researcher_only`: it includes hidden labels, reference patches and all experimental conditions. The shuffled assignment manifest lets you track which packet each agent reviews; assignment and collecting their responses are manual for now. Repeats create identical inputs for independent sessions.

Inspect `inspect_selections.txt` to see the selected parts under every condition, or open a packet's `trajectory_excerpt.txt` to see exactly the excerpt supplied to that reviewer. Selection JSON retains original positions and events. `full_trajectory.json` lets you check against the complete record. Selected events are not paraphrased or silently truncated.

Condition selectors are initial heuristics: assistant messages for rationale, path mentions for context, test commands for validation, and edits for alternatives. `full` combines them in order and `control` has no trajectory. Categories may overlap and are not validated constructs. Audit selections for hidden outcomes, private reasoning and irrelevant content before assigning packets.

The following sections describe setup, dataset provenance and optional API evaluation. GitHub presentation is an earlier optional path, not required for this experiment-generation workflow.


A research pipeline for testing whether information from a coding agent's trajectory improves review of its generated patch. Each distinct issue is reviewed in independent sessions under `control` (task + patch) and `full` (task + patch + selected recorded trace events), with optional ablations.

**Status:** research infrastructure, not completed research. The two included cases are synthetic fixtures. No real benchmark data or paid reviewer results are bundled. See [study protocol](docs/STUDY_PROTOCOL.md) before the main study.

## Setup

Python 3.10 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
python -m src.run_experiment --dry-run
```

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in your shell for live reviews. `.env.example` documents the variables; `.env` is not automatically loaded. Never commit credentials.

## Obtain real cases

Data comes from the Hugging Face datasets `nebius/SWE-rebench` (tasks/reference material, test split) and `nebius/SWE-rebench-openhands-trajectories` (patches/traces/outcomes, train split). Matching uses `instance_id`. Choose immutable commit SHAs from each dataset's revision history and replace the placeholders:

```bash
python -m src.prepare_cases --n 30 --seed 42 \
  --trajectory-revision TRAJECTORY_COMMIT_SHA \
  --base-revision BENCHMARK_COMMIT_SHA \
  --out data/pilot.jsonl
```

The selector streams the trajectory split, keeps the first eligible attempt per distinct issue, and uses seeded reservoir sampling within success/failure groups. It does not guarantee repository balance. Default sampling is balanced and patches are limited to 180 changed lines. `--sampling natural` samples without label quotas; `--max-patch-lines 0` disables the size filter. `--max-scan` limits scanning for development and makes the sample represent only that prefix. Full scanning can take time and bandwidth.

A sidecar manifest records configuration, revisions, exclusions, repository/label counts, unmatched IDs and the case file hash. An incomplete selection exits with an error and leaves artifacts for inspection. Use a new output path when changing selection.

## Pilot and main runs

Inspect case quality and generated prompts before running:

```bash
python -m src.run_experiment --config configs/pilot.json --dry-run
python -m src.run_experiment --config configs/pilot.json --model YOUR_MODEL
python -m src.evaluate --results outputs/pilot.jsonl
```

API runs incur charges. Estimate cost from pilot token usage and your chosen model's pricing. The main config uses three repeats and two conditions; sample size is determined separately by the study design. Prepare `data/main.jsonl` using the same pinned sources, your selected sample size and `--exclude-cases data/pilot.jsonl`, then:

```bash
python -m src.run_experiment --config configs/main.json --dry-run
python -m src.run_experiment --config configs/main.json --model YOUR_MODEL
python -m src.evaluate --results outputs/main.jsonl
```

Add `--resume` after interruption. Each completed response is appended and flushed. Resume checks case/configuration/source hashes and skips completed jobs. Output files are never silently overwritten. API errors stop the run; malformed responses are recorded as parse errors. If a process stops during a write, inspect and repair an incomplete last JSONL line before resuming, preserving the original file.

Evaluation writes a JSON summary and scored CSV. Metrics average repeats within issues; paired accuracy differences use issue bootstrap intervals. Missing or unpaired conditions are reported; mismatched repeat sets are rejected. Parse errors count as incorrect and are reported separately. Analyze different reviewer models separately.

For exploratory ablations pass `--conditions control rationale context validation alternatives full`. Predefine how multiple comparisons will be handled before making confirmatory claims.

## GitHub repository

Commit source, configs, docs, tests and demo fixtures. `.gitignore` excludes credentials, downloaded cases, prompts and experiment outputs. GitHub Actions runs tests and a free demo dry run on Python 3.10 and 3.13. See [contributing](CONTRIBUTING.md) and [data management](docs/DATA_MANAGEMENT.md).

No code license has been selected; choose one before inviting reuse. Dataset licenses are separate. Before publication, record the exact dependency environment with `python -m pip freeze > outputs/environment.txt`, archive run manifests and follow upstream dataset terms.

## Review live agent pull requests in GitHub Actions

The `Agent trajectory review` workflow presents a PR's patch and agent-supplied trajectory in the Actions run summary, with expandable selections of original events and timeline events. It uploads full reports and condition-specific prompts for reviewer agents. The coding agent must commit `.agent/trajectory.json`; GitHub does not capture its activity automatically. See [PR review setup and log format](docs/PR_REVIEW.md). Merge the workflow into the base branch before trying it on subsequent PRs. Test CI and trajectory presentation are separate workflows.

## Experimental information shown

Conditions now expose original recorded events, not generated trajectory summaries. Each event retains its original position and fields. `context` selects path-bearing events; `validation` selects test-command events; `alternatives` selects edit-related events; `rationale` selects assistant messages; `full` includes the union in chronological order without duplicates. `control` includes no trajectory. These heuristic selectors can overlap and do not establish that a rationale or alternative solution actually occurred. See `src/trajectory_parts.py`.

Selected events are not truncated in reviewer prompts. Long traces may exceed the model context limit; inspect prompts before calls. Redact private reasoning, hidden outcomes and secrets during log preparation. An event containing multiple kinds of information is shown whole, so categories are not perfectly isolated. Unsupported trajectory schemas fail explicitly and must be normalized to an event list. Existing results using summaries belong to a different experimental version and must not be pooled with event-based results.
