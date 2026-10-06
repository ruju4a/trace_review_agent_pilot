# Contributing

Install `requirements-dev.txt`, run `python -m pytest -q`, and run a demo `--dry-run` before submitting changes. Tests must not call paid APIs or download benchmark data.

Describe how changes affect sampling, label leakage, prompt contents or comparability. Changes to prompts/extraction invalidate resume manifests and require a new experiment output. Preserve prior research artifacts. Use synthetic fixtures for regression tests and keep credentials out of issues and commits.
