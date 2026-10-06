from src.signals import extract_signals, render_signal_block


def test_extract_signals_smoke():
    case = {
        "problem_statement": "Fix parser handling of nested expressions.",
        "trajectory": [
            {"role": "assistant", "content": "Open src/parser.py and inspect tests/test_parser.py"},
            {"role": "tool", "content": "pytest tests/test_parser.py FAILED"},
            {"role": "assistant", "content": "apply_patch src/parser.py"},
            {"role": "tool", "content": "pytest tests/test_parser.py PASSED"},
        ],
        "gen_tests_correct": None,
        "pred_passes_gen_test": None,
    }
    signals = extract_signals(case)
    assert "src/parser.py" in signals["context"]["observed_paths"]
    assert signals["validation"]["failure_like_observations"] >= 1
    assert "Context explored" in render_signal_block(signals, "context")
