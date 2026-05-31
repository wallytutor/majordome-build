# -*- coding: utf-8 -*-

import argparse
import sys

from pathlib import Path
from subprocess import run
from types import ModuleType

PROJECT_ROOT = Path.cwd()


def main() -> None:
    _print_header("Majordome Build Script")

    _validate_directory()

    args = _get_arguments()

    ### clippy

    if _run("cargo clippy --no-deps") != 0:
        sys.exit("Error: Crate clippy failed")

    ### build

    if _run(f"cargo build {"--release" if args.release else ""}") != 0:
        sys.exit("Error: Crate build failed")

    ### install

    if _run("uv pip install -e .") != 0:
        sys.exit(f"Error: Crate install failed")

    ### docs

    if args.docs:
        _build_docs(args.open_docs)

    _print_header("Build script completed successfully!")

    if args.run_interactive:
        _interactive()


def _print_header(txt: str) -> None:
    """ Print a header. """
    print(f"\033[32m{'=' * 70}\033[0m")
    print(f"\033[32m{txt}\033[0m")
    print(f"\033[32m{'=' * 70}\033[0m")


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

    parser.add_argument(
        "--run-interactive",
        action  = argparse.BooleanOptionalAction,
        default = True,
        help    = "run an interactive session after building the project."
    )

    return parser.parse_args()


def _build_docs(show: bool) -> None:
    """ Build the extension documentation. """
    if _run("cargo doc --no-deps" + (" --open" if show else "")) != 0:
        sys.exit(f"Error: Crate docs failed")


def _run(command: str) -> None:
    """ Run a command in the project root directory. """
    proc = run(command.split(), cwd=PROJECT_ROOT, check=True)
    return proc.returncode


def _get_packages() -> list[str]:
    """ Get the list of packages to import from pyproject.toml. """
    import tomllib

    packages = []
    pyproject_path = PROJECT_ROOT / "pyproject.toml"

    if not pyproject_path.exists():
        sys.exit("Error: pyproject.toml not found")

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)

            packages = data\
                .get("tool", {})\
                .get("maturin", {})\
                .get("python-packages", [])

            if not packages:
                name = data.get("project", {}).get("name")
                if name:
                    packages = [name.replace("-", "_")]
    except Exception as e:
        sys.exit(f"Error: Failed to parse pyproject.toml: {e}")

    return packages


def _interactive() -> None:
    """ Run an interactive session in the project root directory. """
    def print_contents(extension: ModuleType) -> None:
        print("    Available contents:")

        for x in sorted(dir(extension)):
            if x.startswith("_"):
                continue
            print(f"    - {x}")

    from IPython import embed
    from importlib import import_module
    import tomllib

    user_ns = {}

    for pkg in _get_packages():
        try:
            mod = import_module(pkg)
            user_ns[pkg] = mod
            print(f"\nImported package: {pkg}")
            print_contents(mod)
        except ImportError as e:
            print(f"Warning: Could not import package {pkg}: {e}")

    embed(colors="Linux",user_ns=user_ns)
