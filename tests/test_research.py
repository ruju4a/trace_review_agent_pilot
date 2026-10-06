import pytest
from src.prepare_cases import select_candidates
from src.prompts import build_prompt
from src.evaluate import evaluate, normalize_decision


def cases():
    return [dict(instance_id=f'repo-{i}', trajectory_id=str(i), repo='repo',
                 resolved=i % 2, model_patch='+new', trajectory=[{'content': 'pytest PASSED'}])
            for i in range(40)]


def test_sampling_reproducible_unique_and_balanced():
    rows = cases()
    first, counts = select_candidates(rows + rows, 11, seed=9)
    second, _ = select_candidates(rows + rows, 11, seed=9)
    assert first == second
    assert len(first) == len({r['instance_id'] for r in first}) == 11
    assert sum(r['resolved'] for r in first) == 6
    assert counts['duplicate_issue'] == 40
    assert first != select_candidates(rows, 11, seed=10)[0]


def test_filters_and_scan_limit():
    rows = cases()
    rows[0]['model_patch'] = ''
    rows[1]['model_patch'] = '+a\n+b'
    selected, counts = select_candidates(rows, 20, max_patch_lines=1, max_scan=5)
    assert counts['scanned'] == 5
    assert len(selected) == 3


def test_hidden_metadata_never_rendered():
    case = {**cases()[0], 'problem_statement': 'Fix parser',
            'gold_patch': 'GOLD_SENTINEL', 'test_patch': 'TEST_SENTINEL',
            'gen_tests_correct': 'JUDGMENT_SENTINEL',
            'pred_passes_gen_test': 'OUTCOME_SENTINEL'}
    for condition in ['control', 'rationale', 'context', 'validation', 'alternatives', 'full']:
        prompt = build_prompt(case, condition)
        assert all(s not in prompt for s in ['GOLD_SENTINEL', 'TEST_SENTINEL', 'JUDGMENT_SENTINEL', 'OUTCOME_SENTINEL'])
        changed = {**case, 'resolved': 1}
        assert build_prompt(changed, condition) == prompt


def test_paired_analysis_uses_cases_not_reviews():
    rows = [dict(instance_id=str(i), condition=c, repeat=r, resolved=1,
                 decision='APPROVE' if c == 'full' else 'REJECT', model='test')
            for i in range(4) for c in ['control', 'full'] for r in range(3)]
    report = evaluate(rows, bootstrap=100)
    assert report['conditions']['full']['n_reviews'] == 12
    pair = report['paired_comparisons']['full']
    assert pair['paired_cases'] == 4
    assert pair['accuracy_difference'] == 1
    assert pair['bootstrap_95_ci'] == [1, 1]
    with pytest.raises(ValueError, match='Duplicate'):
        evaluate(rows + [rows[0]])


def test_strict_decision_and_missing_usage():
    assert normalize_decision('do not APPROVE') == 'OTHER'
    report = evaluate([dict(instance_id='1', condition='control', repeat=0,
                           resolved=0, decision='bad', model='test')], bootstrap=100)
    assert report['conditions']['control']['parse_error_rate'] == 1
    assert report['conditions']['control']['mean_input_tokens'] is None


def test_runner_resumes_and_detects_case_changes(tmp_path, monkeypatch):
    import json
    import sys
    import types
    from src.run_experiment import main
    calls = []
    class FakeReviewer:
        def __init__(self, model):
            self.model = model
        def review(self, prompt):
            calls.append(prompt)
            return {'decision': 'APPROVE', 'model': self.model}
    monkeypatch.setitem(sys.modules, 'src.reviewer', types.SimpleNamespace(OpenAIReviewer=FakeReviewer))
    case_path = tmp_path / 'cases.jsonl'
    case_path.write_text(json.dumps({**cases()[0], 'problem_statement': 'Fix it'}) + '\n')
    result_path = tmp_path / 'results.jsonl'
    argv = ['run', '--cases', str(case_path), '--out', str(result_path), '--model', 'mock']
    monkeypatch.setattr(sys, 'argv', argv)
    main()
    assert len(calls) == 2
    monkeypatch.setattr(sys, 'argv', argv + ['--resume'])
    main()
    assert len(calls) == 2
    case_path.write_text(case_path.read_text() + '\n')
    with pytest.raises(SystemExit):
        main()
