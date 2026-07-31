# Changelog

## 0.1.2 - 2026-07-31

- Improved the looks and robustness of documentation with a better design. Quarto callout was replaced by inline HTML for better control. Still needs some graphical improvement in a future update.

## 0.1.1 - 2026-07-30

- Included new module `compile_qmd.py` which is exposed through `majordome-build-qmd`; this will by default build the contents of `docs/` in a project, otherwise will be used to compile specific files. Its goal in a uv-managed project is to ensure that synchronization is performed before each run and that output is logged to file.

- Documented the package components under `docs/`.

## 0.1.0 - 2026-05-31

Initial pre-release of the package.
