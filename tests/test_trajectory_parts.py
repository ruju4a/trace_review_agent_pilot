import json
from src.trajectory_parts import select_parts
from src.prompts import build_prompt

EVENTS = [
    {'role': 'assistant', 'content': 'I will inspect the parser first.'},
    {'role': 'tool', 'content': 'Read src/parser.py: original source here'},
    {'role': 'tool', 'content': 'pytest: FAILED nested expression'},
    {'role': 'tool', 'content': 'apply_patch completed'},
    {'role': 'tool', 'content': 'unrelated status'},
]


def test_conditions_show_original_events_and_positions():
    assert [p['position'] for p in select_parts(EVENTS, 'rationale')] == [1]
    assert [p['position'] for p in select_parts(EVENTS, 'context')] == [2]
    assert [p['position'] for p in select_parts(EVENTS, 'validation')] == [3]
    assert [p['position'] for p in select_parts(EVENTS, 'alternatives')] == [4]
    assert [p['position'] for p in select_parts(EVENTS, 'full')] == [1, 2, 3, 4]
    assert select_parts(EVENTS, 'control') == []
    for p in select_parts(EVENTS, 'full'):
        assert p['event'] == EVENTS[p['position'] - 1]


def test_prompt_contains_selected_event_not_summary():
    case = {'problem_statement': 'fix', 'model_patch': '+fix', 'trajectory': EVENTS}
    prompt = build_prompt(case, 'validation')
    assert json.dumps(EVENTS[2], ensure_ascii=False, indent=2) in prompt
    assert 'original source here' not in prompt
    assert 'Failure-like observations' not in prompt
    assert 'Trajectory event 3' in prompt
