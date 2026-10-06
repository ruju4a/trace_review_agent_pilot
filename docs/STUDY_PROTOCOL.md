# Study protocol template

Complete and freeze this protocol before collecting confirmatory results. Configuration examples are not a preregistration.

## Question and scope

Does observable trajectory context improve an agent reviewer's prediction of benchmark patch success compared with task and patch alone? `resolved` is an execution benchmark label, not comprehensive code quality or human review correctness. Human benefit requires a separate study.

## Design decisions to record

- Primary outcome: paired difference in case-level decision accuracy, or choose failed-patch detection in advance.
- Minimum meaningful improvement and target power; choose sample size using pilot estimates of paired discordance/variance. Three hundred cases is an example, not an established requirement.
- Reviewer model/version, date, repeats, conditions, dataset revisions and extraction source hashes.
- Sampling frame, seed, label balancing, patch-size restriction and attempt policy. First eligible attempt may introduce attempt-order bias; document it or replace it before freezing the study.
- Repository coverage: inspect manifests. Consider repository-stratified sampling and repository-level sensitivity analysis when generalizing beyond sampled repositories.
- Missing response, exclusion, malformed output, multiple comparison and stopping policies.

## Pilot gate

Use distinct pilot issues and keep them out of the confirmatory sample. Pass `--exclude-cases data/pilot.jsonl` when preparing the main sample to prevent pilot overlap; the exclusion file hash is recorded. Inspect task/patch matching, meaningful failures, trace structure and prompt lengths. Record inclusion decisions before reviewer results are available. Publish the selection log.

## Information validity

Gold patches, hidden tests, resolved labels and generated-test evaluation judgments are not rendered in prompts. Trace test observations are included intentionally. Raw trajectory snippets can still contain benchmark evaluation information or instructions: audit rendered prompts for leakage before running. Automated metadata exclusion does not prove trace-level absence of leakage.

The extractor is heuristic. Conditions show whole original events: assistant messages for rationale, path-bearing events for context, test-command events for validation and edit-related events for alternatives. These are proxies rather than verified rationale or alternatives; events may belong to multiple conditions. Validate these constructs by annotating a subset with a written rubric, ideally using independent raters. Revise extraction before freezing a main study, not after inspecting comparative outcomes.

## Analysis and reporting

Average repeated reviews within each issue and compare conditions on the same issues/repeats. Report label counts, repository counts, exclusions, parse errors, paired coverage, effect size, intervals, token usage and runtime. Bootstrap intervals in this implementation assume independent issues; repository dependence may require clustered analysis. Repeats do not increase independent sample size. Balanced-sample accuracy does not estimate natural-population accuracy.

Run power planning separately before confirmatory collection. The project does not implement power analysis, human annotation adjudication, repository-clustered inference or benchmark container execution. It consumes existing benchmark labels rather than re-running tests. These are explicit study decisions/extensions, not silently satisfied requirements.
