# Tests

Tests are organized to mirror the layers in `src/app`:

- `tests/domain/` and `tests/application/` contain focused unit tests.
- `tests/infrastructure/` covers integrations and adapters.
- `tests/ui/` covers UI handlers and state.
- `tests/integration/` contains tests spanning multiple layers, including
  Qt/video tests that may need a display server and suitable test media.

Install the project and its development tools with
`python -m pip install -e ".[dev]"`, then run the standard suite from the
repository root:

```bash
python -m pytest -q
```

For a quick iteration on domain and shared utilities:

```bash
python -m pytest tests/domain tests/shared -q
```

Some tests use lightweight stubs for optional, hardware-dependent libraries.
The video worker integration tests are skipped unless
`BLURZY_TEST_VIDEO_PATH` points to suitable local media; tests that exercise
model inference may also require model weights and compatible hardware.
