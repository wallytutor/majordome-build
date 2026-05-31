# -*- coding: utf-8 -*-

import argparse
import sys

from pathlib import Path
from subprocess import run
from types import ModuleType

PROJECT_ROOT = Path.cwd()


def main() -> None:
    print("=" * 70)
    print("Majordome Build Script")
    print("=" * 70)
    print("")

    _validate_directory()

    args = _get_arguments()

    should_release = args.release
    should_docs    = args.docs
    open_docs      = args.open_docs

    ### clippy

    if _run("cargo clippy --no-deps") != 0:
        sys.exit("Error: Crate clippy failed")

    ### build

    if _run(f"cargo build {"--release" if should_release else ""}") != 0:
        sys.exit("Error: Crate build failed")

    ### install

    if _run("uv pip install -e .") != 0:
        sys.exit(f"Error: Crate install failed")

    ### docs

    if should_docs:
        if _run("cargo doc --no-deps" + (" --open" if open_docs else "")) != 0:
            sys.exit(f"Error: Crate docs failed")

    print("=" * 70)
    print("Build script completed successfully!")
    print("=" * 70)


def _validate_directory() -> None:
    """ Validate that the script is running in the repository root. """
    if not (PROJECT_ROOT / "pyproject.toml").exists():
        sys.exit(f"Error: pyproject.toml not found in {PROJECT_ROOT}.")

    if not (PROJECT_ROOT / "Cargo.toml").exists():
        sys.exit(f"Error: Cargo.toml not found in {PROJECT_ROOT}.")


def _get_arguments() -> argparse.Namespace:
    """ Get arguments from the command line. """
    parser = argparse.ArgumentParser("Build and import the extension.")

    parser.add_argument(
        "--release",
        action = "store_true",
        help   = "build the extension in release mode."
    )

    parser.add_argument(
        "--build",
        action  = argparse.BooleanOptionalAction,
        default = True,
        help    = "build the extension."
    )

    parser.add_argument(
        "--docs",
        action  = argparse.BooleanOptionalAction,
        default = True,
        help    = "build the extension documentation."
    )

    parser.add_argument(
        "--open-docs",
        action = "store_true",
        help   = "open the extension documentation after building."
    )

    return parser.parse_args()


def _run(command: str) -> None:
    """ Run a command in the project root directory. """
    proc = run(command.split(), cwd=PROJECT_ROOT, check=True)
    return proc.returncode
