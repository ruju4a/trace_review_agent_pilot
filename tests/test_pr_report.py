import json
import pytest
from src.pr_report import generate_report, validate_trace, fenced


def test_report_has_categories_timeline_and_exact_patch(tmp_path):
    trace = json.loads(open('examples/trajectory.json').read())
    patch = '--- a/parser.py\n+++ b/parser.py\n+fix\n'
    report = generate_report('Fix nesting', patch, trace, tmp_path, 'head123', 'base123')
    assert 'Trajectory timeline' in report
    for condition in ('control', 'rationale', 'context', 'validation', 'alternatives', 'full'):
        prompt = (tmp_path / f'{condition}_prompt.txt').read_text()
        assert patch in prompt
    assert 'Validation' in report
    assert 'head123' in report
    assert (tmp_path / 'patch.diff').read_text() == patch
    assert 'Selected recorded trajectory events' not in (tmp_path / 'control_prompt.txt').read_text()
    assert 'Selected recorded trajectory events' in (tmp_path / 'full_prompt.txt').read_text()


def test_missing_log_is_explicit(tmp_path):
    report = generate_report('Task', '+code', None, tmp_path, 'head', 'base')
    assert 'Trajectory unavailable' in report
    assert (tmp_path / 'control_prompt.txt').exists()
    assert not (tmp_path / 'full_prompt.txt').exists()


def test_invalid_log_rejected():
    for trace in ([], {}, {'schema_version': 1, 'events': []},
                  {'schema_version': 1, 'events': [{'role': 'tool', 'content': {}}]}):
        with pytest.raises(ValueError):
            validate_trace(trace)


def test_untrusted_markup_and_fences():
    value = fenced('```diff\n<script>alert(1)</script>\n```')
    assert value.startswith('````text')
    assert '<script>' not in value
    assert '&lt;script&gt;' in value


def test_timeline_preview_is_bounded(tmp_path):
    trace = {'schema_version': 1, 'events': [{'role': 'tool', 'content': 'x' * 3000}] * 101}
    report = generate_report('Task', '+code', trace, tmp_path, 'head', 'base')
    assert '100 of 101' in report
    assert 'Event 101' not in report
    assert len(json.loads((tmp_path / 'trajectory.json').read_text())['events']) == 101
