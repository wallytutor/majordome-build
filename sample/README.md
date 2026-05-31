# majordome-sample

Sample crate to be used as a base in the Majordome stack.

## Development builds

> For quality control, the build of all Majordome components is done with `majordome-build` script, which ensures a certain workflow. Upon running `uv sync --refresh` in a fresh version of the project, *i.e.* just cloned, the build is run automatically with default `uv` workflow. This is fine because a project should always be committed with a working build. After modifying the project, the following workflow must be enforced.

```bash
# Create the environment
uv sync --refresh

# Activate (Windows)
.venv\Scripts\activate

# Activate (Linux/Mac)
source .venv/bin/activate

# Run the build script
uv run majordome-build
```
