"""Reproducible streaming selection, followed by benchmark matching."""
from __future__ import annotations
import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path


def patch_size(diff: str) -> int:
    return sum(line.startswith(('+', '-')) and not line.startswith(('+++', '---'))
               for line in (diff or '').splitlines())


def select_candidates(rows, n, seed=42, balanced=True, max_patch_lines=180, max_scan=0, excluded_ids=()):
    rng = random.Random(seed)
    pools = {0: [], 1: []} if balanced else {None: []}
    quotas = {0: n // 2, 1: n - n // 2} if balanced else {None: n}
    counts = Counter()
    seen = set()
    excluded_ids = set(excluded_ids)
    for index, row in enumerate(rows):
        if max_scan and index >= max_scan:
            break
        counts['scanned'] += 1
        iid = row.get('instance_id')
        if iid in excluded_ids:
            counts['excluded_issue'] += 1
            continue
        label = row.get('resolved')
        if label not in (0, 1) or not iid:
            counts['invalid'] += 1
            continue
        patch = row.get('model_patch') or ''
        if not patch.strip() or not row.get('trajectory'):
            counts['missing_patch_or_trace'] += 1
            continue
        if max_patch_lines and patch_size(patch) > max_patch_lines:
            counts['large_patch'] += 1
            continue
        if iid in seen:
            counts['duplicate_issue'] += 1
            continue
        # Explicit policy: first eligible attempt per issue; random selection of issues.
        seen.add(iid)
        key = label if balanced else None
        counts[f'eligible_{key}'] += 1
        pool = pools[key]
        capacity = quotas[key]
        record = {k: row.get(k) for k in ('trajectory_id', 'instance_id', 'repo',
                  'trajectory', 'model_patch', 'exit_status', 'resolved')}
        if len(pool) < capacity:
            pool.append(record)
        else:
            slot = rng.randrange(counts[f'eligible_{key}'])
            if slot < capacity:
                pool[slot] = record
    selected = [row for pool in pools.values() for row in pool]
    rng.shuffle(selected)
    return selected, dict(counts)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--n', type=int, default=30)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--exclude-cases', help='JSONL pilot cases to exclude from main selection')
    p.add_argument('--out', default='data/cases.jsonl')
    p.add_argument('--sampling', choices=['balanced', 'natural'], default='balanced')
    p.add_argument('--max-patch-lines', type=int, default=180, help='0 disables this filter')
    p.add_argument('--max-scan', type=int, default=0, help='0 scans the full trajectory split')
    p.add_argument('--trajectory-dataset', default='nebius/SWE-rebench-openhands-trajectories')
    p.add_argument('--base-dataset', default='nebius/SWE-rebench')
    p.add_argument('--trajectory-revision', required=True, help='Pinned Hugging Face commit SHA')
    p.add_argument('--base-revision', required=True, help='Pinned Hugging Face commit SHA')
    args = p.parse_args()
    if args.n < 1 or args.max_scan < 0 or args.max_patch_lines < 0:
        p.error('n must be positive; limits must be nonnegative')
    out = Path(args.out)
    if out.exists():
        p.error('Output exists; choose a new path to preserve provenance')
    from datasets import load_dataset
    rows = load_dataset(args.trajectory_dataset, revision=args.trajectory_revision,
                        split='train', streaming=True)
    excluded = []
    exclusion_hash = None
    if args.exclude_cases:
        exclusion_bytes = Path(args.exclude_cases).read_bytes()
        exclusion_hash = hashlib.sha256(exclusion_bytes).hexdigest()
        excluded = [json.loads(line)['instance_id'] for line in exclusion_bytes.decode().splitlines() if line.strip()]
    chosen, counts = select_candidates(rows, args.n, args.seed,
        args.sampling == 'balanced', args.max_patch_lines, args.max_scan, excluded)
    wanted = {r['instance_id']: r for r in chosen}
    matched = {}
    if wanted:
        for row in load_dataset(args.base_dataset, revision=args.base_revision,
                                split='test', streaming=True):
            iid = row.get('instance_id')
            if iid in wanted:
                matched[iid] = {**wanted[iid], **{k: row.get(k) for k in
                    ('problem_statement', 'base_commit', 'FAIL_TO_PASS', 'PASS_TO_PASS')},
                    'gold_patch': row.get('patch'), 'test_patch': row.get('test_patch')}
            if len(matched) == len(wanted):
                break
    records = [matched[r['instance_id']] for r in chosen if r['instance_id'] in matched]
    out.parent.mkdir(parents=True, exist_ok=True)
    content = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records)
    out.write_text(content)
    manifest = {'configuration': vars(args), 'counts': counts, 'written': len(records),
        'unmatched_ids': sorted(set(wanted) - set(matched)),
        'labels': dict(Counter(r['resolved'] for r in records)),
        'repositories': dict(Counter(r['repo'] for r in records)),
        'sha256': hashlib.sha256(content.encode()).hexdigest(),
        'exclusion_sha256': exclusion_hash,
        'attempt_policy': 'first eligible trajectory per issue'}
    out.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2))
    print(f'Wrote {len(records)} / {args.n} cases to {out}; inspect the manifest and cases.')
    if len(records) != args.n:
        raise SystemExit('Selection incomplete: inspect exclusions, label availability and unmatched IDs.')

if __name__ == '__main__':
    main()
