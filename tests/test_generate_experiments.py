import json
import pytest
from src.generate_experiments import generate


def test_packets_selections_and_no_hidden_material(tmp_path):
    cases = tmp_path / 'cases.jsonl'
    case = {'instance_id': 'repo/unsafe/../../name', 'problem_statement': 'Fix parser',
            'model_patch': '+fix', 'resolved': 0, 'gold_patch': 'HIDDEN_GOLD',
            'trajectory': [{'role': 'tool', 'content': 'pytest FAILED'},
                           {'role': 'tool', 'content': 'read src/parser.py'}]}
    cases.write_text(json.dumps(case) + '\n')
    out = tmp_path / 'packets'
    report = generate(cases, out, ['control', 'validation'], repeats=2)
    assert report['n_packets'] == 4
    for path in (out / 'reviewer_packets').rglob('*'):
        if path.is_file():
            assert 'HIDDEN_GOLD' not in path.read_text()
            assert 'resolved' not in path.read_text()
    inspection = out / 'researcher_only' / 'case_0001'
    selection = json.loads((inspection / 'validation_selection.json').read_text())
    assert selection[0]['event'] == case['trajectory'][0]
    assert selection[0]['position'] == 1
    assert 'HIDDEN_GOLD' in (inspection / 'case_metadata.json').read_text()
    control = (out / 'reviewer_packets' / 'case_0001_control_r1' / 'review_prompt.txt').read_text()
    assert 'pytest' not in control
    assert 'pytest FAILED' in (out / 'reviewer_packets' / 'case_0001_validation_r1' / 'review_prompt.txt').read_text()
    with pytest.raises(FileExistsError):
        generate(cases, out)


def test_bad_case_does_not_create_outputs(tmp_path):
    cases = tmp_path / 'cases.jsonl'
    cases.write_text(json.dumps({'instance_id': 'bad'}) + '\n')
    out = tmp_path / 'bad'
    with pytest.raises(ValueError):
        generate(cases, out)
    assert not out.exists()
