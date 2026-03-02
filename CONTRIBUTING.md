# Contributing

## Development workflow
1. Create a branch from `main`.
2. Install dev dependencies: `pip install -e .[dev]`.
3. Run checks before push:
   - `make lint`
   - `make typecheck`
   - `make test`
4. Open a pull request with a clear summary and test evidence.

## Code standards
- Python 3.11+
- Type hints required on public functions.
- Keep service layer deterministic and testable.

## Commit style
Use Conventional Commits:
- `feat:`
- `fix:`
- `chore:`
- `docs:`
- `test:`
