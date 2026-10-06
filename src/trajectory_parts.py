"""Select recorded events for experimental conditions; never paraphrase them."""
from __future__ import annotations
import json
from .signals import PATH_RE, TEST_RE, EDIT_RE, trajectory_text

CONDITIONS = ('control', 'rationale', 'context', 'validation', 'alternatives', 'full')


def trajectory_events(trajectory):
    if isinstance(trajectory, str):
        try:
            trajectory = json.loads(trajectory)
        except json.JSONDecodeError:
            raise ValueError('Trajectory must contain structured events, not an opaque string')
    if isinstance(trajectory, dict):
        for key in ('events', 'messages', 'trajectory'):
            if isinstance(trajectory.get(key), list):
                return trajectory[key]
        raise ValueError('Unsupported trajectory object; normalize it to an events list')
    if isinstance(trajectory, list):
        return trajectory
    raise ValueError('Trajectory must be an event list or an object containing one')


def select_parts(trajectory, condition):
    if condition not in CONDITIONS:
        raise ValueError(f'Unknown condition: {condition}')
    if condition == 'control':
        return []
    selections = []
    for index, event in enumerate(trajectory_events(trajectory), 1):
        text = trajectory_text(event)
        role = event.get('role', '') if isinstance(event, dict) else ''
        groups = []
        if PATH_RE.search(text):
            groups.append('context')
        if TEST_RE.search(text):
            groups.append('validation')
        if EDIT_RE.search(text):
            groups.append('alternatives')
        # An assistant message is only rationale-related evidence, not verified reasoning.
        if role == 'assistant':
            groups.append('rationale')
        if condition in groups or (condition == 'full' and groups):
            selections.append({'position': index, 'categories': groups, 'event': event})
    return selections


def render_parts(parts):
    if not parts:
        return 'No recorded events matched this condition.'
    chunks = []
    for part in parts:
        event = part['event']
        role = event.get('role', 'unspecified') if isinstance(event, dict) else 'unspecified'
        # JSON keeps event fields and content intact; no natural-language summary.
        chunks.append(f"Trajectory event {part['position']} (role: {role})\n" +
                      json.dumps(event, ensure_ascii=False, indent=2))
    return '\n\n'.join(chunks)
