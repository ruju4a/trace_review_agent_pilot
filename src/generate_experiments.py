"""Create portable reviewer packets and researcher inspection files; no API calls."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from pathlib import Path
from .prompts import build_prompt
from .trajectory_parts import CONDITIONS, trajectory_events, select_parts, render_parts


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def generate(cases_path, output, conditions=CONDITIONS, repeats=1, seed=42):
    conditions = list(conditions)
    if repeats < 1 or not conditions or len(set(conditions)) != len(conditions) or any(c not in CONDITIONS for c in conditions):
        raise ValueError('Use positive repeats and distinct valid conditions')
    source = Path(cases_path).read_bytes()
    cases = [json.loads(line) for line in source.decode().splitlines() if line.strip()]
    ids = [c.get('instance_id') for c in cases]
    if not cases or not all(isinstance(iid, str) and iid for iid in ids) or len(set(ids)) != len(ids):
        raise ValueError('Cases must have unique, nonempty instance_id strings')
    # Validate all cases and selections before creating any output.
    prepared = []
    for index, case in enumerate(cases, 1):
        if not isinstance(case.get('problem_statement'), str) or not case['problem_statement'].strip() or not isinstance(case.get('model_patch'), str) or not case['model_patch'].strip():
            raise ValueError(f'Missing task or patch: {case["instance_id"]}')
        events = trajectory_events(case.get('trajectory'))
        selections = {c: select_parts(events, c) for c in conditions}
        prepared.append((f'case_{index:04d}', case, events, selections))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    reviewer = output / 'reviewer_packets'
    researcher = output / 'researcher_only'
    reviewer.mkdir()
    researcher.mkdir()
    jobs = []
    for case_id, case, events, selections in prepared:
        inspect = researcher / case_id
        inspect.mkdir()
        write_json(inspect / 'case_metadata.json', {k: v for k, v in case.items() if k != 'trajectory'})
        write_json(inspect / 'full_trajectory.json', events)
        inspection = [f'{case_id}: {case["instance_id"]}',
                      'Researcher inspection only. Do not give this file or folder to reviewers.']
        for condition in conditions:
            parts = selections[condition]
            write_json(inspect / f'{condition}_selection.json', parts)
            inspection += [f'\n=== {condition.upper()} ===\n', render_parts(parts)]
            for repeat in range(repeats):
                packet_id = f'{case_id}_{condition}_r{repeat + 1}'
                folder = reviewer / packet_id
                folder.mkdir()
                prompt = build_prompt(case, condition)
                (folder / 'review_prompt.txt').write_text(prompt, encoding='utf-8')
                (folder / 'task.txt').write_text(case['problem_statement'], encoding='utf-8')
                (folder / 'patch.diff').write_text(case['model_patch'], encoding='utf-8')
                (folder / 'trajectory_excerpt.txt').write_text(render_parts(parts) if condition != 'control' else 'No trajectory is supplied in this condition.\n', encoding='utf-8')
                # No hidden outcome or reference material in reviewer packets.
                write_json(folder / 'response_template.json', {
                    'decision': 'APPROVE_OR_REJECT', 'defects': [], 'explanation': ''})
                jobs.append({'packet_id': packet_id, 'case_id': case_id,
                             'instance_id': case['instance_id'], 'condition': condition,
                             'repeat': repeat + 1,
                             'prompt_path': str((folder / 'review_prompt.txt').relative_to(output)),
                             'selected_positions': [p['position'] for p in parts],
                             'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()})
        (inspect / 'inspect_selections.txt').write_text('\n'.join(inspection), encoding='utf-8')
    random.Random(seed).shuffle(jobs)
    write_json(researcher / 'assignment_manifest.json', {'seed': seed, 'jobs': jobs})
    provenance = {'cases_path': str(cases_path), 'cases_sha256': hashlib.sha256(source).hexdigest(),
                  'conditions': conditions, 'repeats': repeats, 'seed': seed,
                  'n_cases': len(cases), 'n_packets': len(jobs),
                  'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                    for p in Path(__file__).parent.glob('*.py')}}
    selection_manifest = Path(cases_path).with_suffix('.manifest.json')
    if selection_manifest.exists():
        provenance['dataset_selection_manifest'] = json.loads(selection_manifest.read_text())
    write_json(researcher / 'generation_manifest.json', provenance)
    (output / 'README.txt').write_text(
        'Give each reviewer agent only its assigned reviewer_packets/<packet_id>/ folder.\n'
        'Use review_prompt.txt as the agent input and save its JSON response separately.\n'
        'Use researcher_only/<case_id>/inspect_selections.txt to check selected excerpts.\n'
        'researcher_only contains labels/reference patches and all conditions: never share it with reviewers.\n'
        'The shuffled assignment_manifest.json lists packets; assign each in a fresh session.\n'
        'No model calls were made. Repeats are identical inputs for independent review sessions.\n'
        'These are benchmark tasks and agent patches, not live GitHub PRs.\n', encoding='utf-8')
    return provenance


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cases', default='data/demo_cases.jsonl')
    p.add_argument('--out', default='outputs/experiments')
    p.add_argument('--conditions', nargs='+', choices=CONDITIONS, default=list(CONDITIONS))
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--seed', type=int, default=42)
    args = p.parse_args()
    try:
        report = generate(args.cases, args.out, args.conditions, args.repeats, args.seed)
    except (ValueError, FileExistsError) as exc:
        p.error(str(exc))
    print(f'Created {report["n_packets"]} review packets for {report["n_cases"]} cases in {args.out}')

if __name__ == '__main__':
    main()
