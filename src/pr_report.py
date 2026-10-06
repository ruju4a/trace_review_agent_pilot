"""Render a PR patch and agent-supplied trace without executing PR code."""
from __future__ import annotations
import argparse
import html
import json
import re
from pathlib import Path
from .prompts import build_prompt
from .trajectory_parts import select_parts, render_parts

CONDITIONS = ('control', 'rationale', 'context', 'validation', 'alternatives', 'full')


def fenced(value, language='text'):
    value = str(value)
    fence = '`' * max(3, max((len(part) for part in re.findall(r'`+', value)), default=0) + 1)
    # HTML escaping also prevents supplied HTML from changing report presentation.
    return f'{fence}{language}\n{html.escape(value)}\n{fence}'


def validate_trace(trace):
    if not isinstance(trace, dict) or trace.get('schema_version') != 1:
        raise ValueError('Trace must be an object with schema_version=1')
    events = trace.get('events')
    if not isinstance(events, list) or not events:
        raise ValueError('Trace requires a nonempty events list')
    if len(events) > 10000:
        raise ValueError('Trace exceeds 10,000 events')
    for event in events:
        if not isinstance(event, dict) or event.get('role') not in ('assistant', 'tool', 'user') or not isinstance(event.get('content'), str):
            raise ValueError('Each event requires role (assistant/tool/user) and string content')
    return events


def generate_report(task, patch, trace, output, head_sha, base_sha):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    sections = ['# Agent trajectory review',
                f'Base commit: `{base_sha}`\n\nHead commit: `{head_sha}`',
                'This report pairs the PR diff with agent-supplied observations. Trace claims are not independently verified. '
                'Use the Files changed tab to inspect the code. No PR code was executed by this report job.',
                '## Task / PR description', fenced(task)]
    if trace is None:
        sections += ['## Trajectory unavailable',
                     'The PR does not contain `.agent/trajectory.json`. Only the control prompt can be generated. '
                     'Have the coding agent export its activity log using the documented schema.']
        events = []
        conditions = ('control',)
    else:
        events = validate_trace(trace)
        conditions = CONDITIONS
    case = {'problem_statement': task, 'model_patch': patch, 'trajectory': events}
    for condition in conditions:
        (output / f'{condition}_prompt.txt').write_text(build_prompt(case, condition), encoding='utf-8')
    if events:
        sections += ['## Experimental trajectory selections']
        for condition in CONDITIONS[1:-1]:
            sections += [f'<details><summary>{condition.title()}</summary>\n',
                         fenced(render_parts(select_parts(events, condition))), '\n</details>']
        sections += ['## Trajectory timeline',
                     'Events appear in the order provided by the coding agent. The full JSON is in the artifact.']
        for index, event in enumerate(events[:100], 1):
            sections += [f'<details><summary>Event {index}: {event["role"]}</summary>\n',
                         fenced(event['content'][:2000]), '\n</details>']
        if len(events) > 100:
            sections += [f'Timeline preview shows 100 of {len(events)} events.']
        (output / 'trajectory.json').write_text(json.dumps(trace, indent=2), encoding='utf-8')
    sections += ['## Proposed patch', fenced(patch[:20000], 'diff'),
                 'The full patch is available as `patch.diff` in the artifact.',
                 '## Reviewer-agent input',
                 'Download the artifact and supply a condition’s `*_prompt.txt` to your reviewer agent. '
                 'Each prompt contains the same task and patch; only trajectory context differs. '
                 'This workflow prepares inputs; it does not call a paid model or post a PR comment.']
    (output / 'patch.diff').write_text(patch, encoding='utf-8')
    report = '\n\n'.join(sections)
    (output / 'report.md').write_text(report, encoding='utf-8')
    # GitHub step summaries have a 1 MiB limit; maintain a conservative preview bound.
    if len(report.encode()) > 900000:
        report = report[:100000] + '\n\nPreview truncated; download report.md for the full report.\n'
    (output / 'summary.md').write_text(report, encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event', required=True)
    parser.add_argument('--patch', required=True)
    parser.add_argument('--trace', required=True)
    parser.add_argument('--out', default='outputs/pr-review')
    args = parser.parse_args()
    event = json.loads(Path(args.event).read_text())
    pr = event['pull_request']
    task = pr.get('title', '') + '\n\n' + (pr.get('body') or '')
    trace_path = Path(args.trace)
    trace = json.loads(trace_path.read_text()) if trace_path.exists() else None
    generate_report(task, Path(args.patch).read_text(), trace, args.out,
                    pr['head']['sha'], pr['base']['sha'])

if __name__ == '__main__':
    main()
