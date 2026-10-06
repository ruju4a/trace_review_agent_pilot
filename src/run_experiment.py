from __future__ import annotations
import argparse
import hashlib
import json
import os
import random
from pathlib import Path
from .prompts import build_prompt

VALID_CONDITIONS = ['control', 'rationale', 'context', 'validation', 'alternatives', 'full']


def load_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', help='JSON experiment configuration; CLI flags override it')
    p.add_argument('--cases', default='data/demo_cases.jsonl')
    p.add_argument('--conditions', nargs='+', default=['control', 'full'])
    p.add_argument('--repeats', type=int, default=1)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--model', default=os.getenv('OPENAI_MODEL'))
    p.add_argument('--out', default='outputs/results.jsonl')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--resume', action='store_true')
    preliminary, _ = p.parse_known_args()
    if preliminary.config:
        config = json.loads(Path(preliminary.config).read_text())
        allowed = {a.dest for a in p._actions} - {'help', 'config', 'resume', 'dry_run'}
        if set(config) - allowed:
            p.error(f'Unknown configuration keys: {set(config) - allowed}')
        p.set_defaults(**config)
    args = p.parse_args()
    if args.repeats < 1 or not args.conditions or len(set(args.conditions)) != len(args.conditions):
        p.error('Use positive repeats and distinct conditions')
    if any(c not in VALID_CONDITIONS for c in args.conditions):
        p.error('Unknown condition')
    cases = load_jsonl(args.cases)
    ids = [c.get('instance_id') for c in cases]
    if not cases or not all(ids) or len(set(ids)) != len(ids):
        p.error('Cases must be nonempty with unique instance_id values')
    if any(c.get('resolved') not in (0, 1) or not c.get('model_patch') or not c.get('problem_statement') for c in cases):
        p.error('Cases require binary resolved, a patch, and a task statement')
    jobs = [(case, condition, repeat) for case in cases for condition in args.conditions
            for repeat in range(args.repeats)]
    random.Random(args.seed).shuffle(jobs)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        folder = out.parent / (out.stem + '_prompts')
        folder.mkdir(parents=True, exist_ok=True)
        for i, (case, condition, repeat) in enumerate(jobs):
            (folder / f'{i:06d}_{condition}_{repeat}.txt').write_text(build_prompt(case, condition))
        print(f'Wrote {len(jobs)} prompts to {folder}; no API calls made.')
        return
    if not args.model:
        p.error('Set --model or OPENAI_MODEL')
    source_hashes = {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                     for f in Path(__file__).parent.glob('*.py')}
    manifest = {'cases_sha256': hashlib.sha256(Path(args.cases).read_bytes()).hexdigest(),
        'model': args.model, 'conditions': args.conditions, 'repeats': args.repeats,
        'seed': args.seed, 'source_sha256': source_hashes, 'expected_reviews': len(jobs)}
    manifest_path = out.with_suffix('.manifest.json')
    completed = set()
    if args.resume:
        if not manifest_path.exists() or json.loads(manifest_path.read_text()) != manifest:
            p.error('Resume requires an identical cases/configuration/source manifest')
        rows = load_jsonl(out)
        for row in rows:
            key = (row['instance_id'], row['condition'], row['repeat'])
            if key in completed:
                p.error('Duplicate job in existing results')
            completed.add(key)
    elif out.exists() or manifest_path.exists():
        p.error('Output exists; use --resume or choose a new path')
    from .reviewer import OpenAIReviewer
    reviewer = OpenAIReviewer(model=args.model)
    if not args.resume:
        manifest_path.write_text(json.dumps(manifest, indent=2))
    with out.open('a', encoding='utf-8') as f:
        for case, condition, repeat in jobs:
            if (case['instance_id'], condition, repeat) in completed:
                continue
            prompt = build_prompt(case, condition)
            result = reviewer.review(prompt)
            record = {**result, 'instance_id': case['instance_id'],
                'trajectory_id': case.get('trajectory_id'), 'repo': case.get('repo'),
                'condition': condition, 'repeat': repeat, 'resolved': case['resolved'],
                'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest()}
            f.write(json.dumps(record) + '\n')
            f.flush()
            print(f"{case['instance_id']} {condition} repeat={repeat}: {result['decision']}")
    print(f'Results written to {out}')

if __name__ == '__main__':
    main()
