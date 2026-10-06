"""Case-level metrics and paired bootstrap intervals (repeats stay within issues)."""
from __future__ import annotations
import argparse
import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean


def normalize_decision(value):
    value = str(value).strip().upper()
    return value if value in ('APPROVE', 'REJECT') else 'OTHER'


def evaluate(rows, baseline='control', seed=42, bootstrap=5000):
    if not rows:
        raise ValueError('No result rows')
    seen = set()
    labels = {}
    grouped = defaultdict(lambda: defaultdict(list))
    for row in rows:
        key = (row['instance_id'], row['condition'], row['repeat'])
        if key in seen:
            raise ValueError(f'Duplicate review: {key}')
        seen.add(key)
        label = row['resolved']
        if label not in (0, 1) or labels.get(row['instance_id'], label) != label:
            raise ValueError('Invalid or inconsistent labels')
        labels[row['instance_id']] = label
        decision = normalize_decision(row.get('decision'))
        row['correct'] = int(decision == ('APPROVE' if label else 'REJECT'))
        row['decision_norm'] = decision
        grouped[row['condition']][row['instance_id']].append(row)
    models = {r.get('model') for r in rows}
    if len(models) > 1:
        raise ValueError('Analyze reviewer models separately')
    summary = {}
    for condition, cases in grouped.items():
        all_rows = [r for rs in cases.values() for r in rs]
        failed = [rs for iid, rs in cases.items() if labels[iid] == 0]
        success = [rs for iid, rs in cases.items() if labels[iid] == 1]
        summary[condition] = {
            'n_cases': len(cases), 'n_reviews': len(all_rows),
            'accuracy': mean(mean(r['correct'] for r in rs) for rs in cases.values()),
            'failed_patch_detection_rate': mean(mean(r['decision_norm'] == 'REJECT' for r in rs) for rs in failed) if failed else None,
            'false_rejection_rate': mean(mean(r['decision_norm'] == 'REJECT' for r in rs) for rs in success) if success else None,
            'parse_error_rate': mean(r['decision_norm'] == 'OTHER' for r in all_rows),
        }
        for field in ('elapsed_seconds', 'input_tokens', 'output_tokens'):
            vals = [r[field] for r in all_rows if isinstance(r.get(field), (int, float))]
            summary[condition]['mean_' + field] = mean(vals) if vals else None
    comparisons = {}
    for condition, cases in grouped.items():
        if condition == baseline or baseline not in grouped:
            continue
        base = grouped[baseline]
        common = sorted(set(cases) & set(base))
        if not common:
            continue
        differences = []
        for iid in common:
            left = {r['repeat']: r for r in base[iid]}
            right = {r['repeat']: r for r in cases[iid]}
            if set(left) != set(right):
                raise ValueError(f'Unpaired repeats for {iid}: {baseline}/{condition}')
            differences.append(mean(right[k]['correct'] - left[k]['correct'] for k in left))
        rng = random.Random(seed)
        samples = sorted(mean(rng.choices(differences, k=len(differences))) for _ in range(bootstrap))
        comparisons[condition] = {'baseline': baseline, 'paired_cases': len(common),
            'unpaired_cases': len(set(cases) ^ set(base)), 'accuracy_difference': mean(differences),
            'bootstrap_95_ci': [samples[int(.025 * bootstrap)], samples[min(bootstrap - 1, int(.975 * bootstrap))]]}
    return {'conditions': summary, 'paired_comparisons': comparisons,
            'interval_unit': 'issue; independent bootstrap across issues, not repositories'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results', default='outputs/results.jsonl')
    p.add_argument('--baseline', default='control')
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--bootstrap', type=int, default=5000)
    args = p.parse_args()
    if args.bootstrap < 100:
        p.error('Use at least 100 bootstrap draws')
    rows = [json.loads(s) for s in Path(args.results).read_text().splitlines() if s.strip()]
    report = evaluate(rows, args.baseline, args.seed, args.bootstrap)
    out = Path(args.results)
    out.with_suffix('.summary.json').write_text(json.dumps(report, indent=2))
    fields = sorted({k for r in rows for k in r})
    with out.with_suffix('.scored.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
