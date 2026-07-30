# majordome-build

Provides a standard strict build workflow for working on the Majordome stack.

## 📃 Documentation build

```bash
# Only the first time in a new environment:
uv sync

# This will automatically sync the project later:
uv run majordome-build-qmd --extras docs
```
