# Review coding-agent changes in GitHub Actions

The `Agent trajectory review` workflow runs when a pull request is opened, updated, reopened or its description is edited. It produces a human-readable Actions summary and a downloadable artifact containing the patch, trajectory, report and experimental-condition prompts. GitHub Actions is the presentation surface; there is no separate web UI.

## Coding-agent contract

Ask your coding agent to export its real observable activity, in chronological order, to `.agent/trajectory.json` and commit that file with its changes. Copy the shape from `examples/trajectory.json`, not its synthetic contents. Required fields are `schema_version: 1` and a nonempty `events` list, with each event containing `role` (`assistant`, `tool`, or `user`) and string `content`. Export commands, tool output, files inspected, edits and validation. Do not invent missing history or include private reasoning, secrets, hidden benchmark labels or reference patches. Keep logs under 10 MB and 10,000 events.

Example instruction to the coding agent:

> Implement the task and export your observable activity to .agent/trajectory.json using schema_version 1. Record real tool actions and results in events with role and content, in order. Include failed validation and subsequent edits. Omit credentials and private reasoning. Commit the log with the code and explain the task in the PR description.

The log is supplied by the coding agent, not automatically captured by Actions. Claims are not independently verified. Use your agent's actual history/export mechanism to obtain the events. The report identifies the base/head commits used and excludes the trace file itself from the review patch.

## Human reviewer

Open the PR's `Agent trajectory review` check, then the workflow run summary. Expand the rationale, context, validation and alternatives selections of original recorded events and the timeline events. Inspect the actual changes in the PR's Files changed tab. Download the `trajectory-review-<PR number>` artifact for full details; the summary previews at most 100 events and 20,000 patch characters.

## Reviewer agent

Download the artifact and give the desired `*_prompt.txt` to your reviewer agent. `control` contains task and patch; `full` adds the union of selected original events. The four other prompts isolate individual signal categories. The workflow does not automatically invoke a model: this supports reviewers you already use without requiring repository API secrets. The local experiment runner remains available for controlled benchmark API experiments.

Missing logs produce an explicit notice and control-only prompt. Invalid logs fail the check, rather than silently supplying an empty trajectory. Event selection remains heuristic; the timeline provides the underlying observations for inspection.

## Install on GitHub

Merge the workflow and reporter into the default/base branch first, then open a PR containing an agent trace. The workflow executes reporter code from the base commit, reads PR code only as data, needs no API key and uses read-only contents permissions. Fork PRs are supported for public repositories. It does not execute or test the proposed patch, approve/merge it or post comments.

Normal CI remains in `tests.yml`; it serves a separate purpose from presenting trajectory evidence. Reports/artifacts contain PR data and logs, so redact sensitive content before committing. Artifacts expire after 14 days by default.
