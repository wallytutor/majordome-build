# -*- coding: utf-8 -*-

import argparse
import os
import subprocess
import sys

from pathlib import Path
from typing import TextIO


def find_project_root() -> Path:
    """ Find the project root directory containing pyproject.toml. """
    current = Path(__file__).resolve().parent
    candidates = [current] + list(current.parents)

    for parent in candidates:
        if (parent / "pyproject.toml").exists():
            return parent

    if len(current.parents) >= 2:
        current = current.parents[1]

    os.chdir(current)

    return current


def check_uv() -> bool:
    """ Check if the uv tool is installed and accessible. """
    try:
        subprocess.run(
            ["uv", "--version"],
            check  = True,
            stdout = subprocess.DEVNULL,
            stderr = subprocess.DEVNULL
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def parse_extras(extras_str: str | None) -> list[str]:
    """ Parse the comma-separated extras string. """
    if not extras_str:
        return []

    extras = [e.strip() for e in extras_str.split(",") if e.strip()]
    uv_args = []

    for extra in extras:
        uv_args.extend(["--extra", extra])

    return uv_args


def ensure_dependencies(project_root: Path, extras: str | None) -> None:
    """ Ensure dependencies are installed using uv sync. """
    if not check_uv():
        raise RuntimeError("Project is managed only through 'uv'...")

    try:
        print("Ensuring dependencies are installed...")
        subprocess.run(
            ["uv", "sync"] + parse_extras(extras),
            check = True,
            cwd   = project_root
        )
    except subprocess.CalledProcessError as e:
        print(f"Error: 'uv sync' failed with exit code {e.returncode}.")
        sys.exit(e.returncode)


def get_venv_python(project_root: Path, extras: str | None) -> Path:
    """ Determine virtual environment python path based on the OS. """
    ensure_dependencies(project_root, extras)

    match os.name:
        case "nt":
            return project_root / ".venv" / "Scripts" / "python.exe"
        case "posix":
            return project_root / ".venv" / "bin" / "python"
        case _:
            raise RuntimeError(f"Unsupported OS: {os.name}")


def get_quarto_command(file_path: str | None) -> list[str]:
    """ Get the quarto render command with custom arguments. """
    quarto_args = ["quarto", "render"]

    if file_path:
        quarto_args.append(file_path)
    else:
        quarto_args.append("docs")

    return quarto_args


def compile_report(
        project_root: Path,
        venv_python: Path,
        file_path: str | None
    ) -> None:
    """ Core compilation and logging logic. """
    quarto_args = get_quarto_command(file_path)
    log_file_path = project_root / "compile.log"

    print(f"Running Quarto with {os.environ['QUARTO_PYTHON']}")
    print(f"Executing command: {' '.join(quarto_args)}")
    print(f"Capturing outputs to: {log_file_path}")

    with open(log_file_path, "w", encoding="utf-8") as log_file:
        log_file.write("=== Report Compilation Log ===\n")
        log_file.write(f"Command: {' '.join(quarto_args)}\n")
        log_file.write(f"QUARTO_PYTHON: {venv_python}\n\n")

        process = subprocess.Popen(
            quarto_args,
            stdout   = subprocess.PIPE,
            stderr   = subprocess.STDOUT,
            text     = True,
            cwd      = project_root,
            encoding = "utf-8",
            errors   = "replace"
        )

        while True:
            line = process.stdout.readline()

            if not line and process.poll() is not None:
                break
            if line:
                sys.stdout.write(line)
                sys.stdout.flush()
                log_file.write(line)
                log_file.flush()

        if (returncode := process.wait()) != 0:
            raise subprocess.CalledProcessError(returncode, quarto_args)

        print("Report compiled successfully.")


def main() -> None:
    """ Compile the paper or report using Quarto. """
    parser = argparse.ArgumentParser(
        description="Compile QMD report using Quarto."
    )
    parser.add_argument(
        "--extras",
        type=str,
        default=None,
        help="Comma-separated list of extras to install via uv sync."
    )
    parser.add_argument(
        "--file",
        type=str,
        default=None,
        help="The file (or directory) to render using Quarto."
    )
    args = parser.parse_args()

    project_root = find_project_root()
    venv_python = get_venv_python(project_root, args.extras)

    if not venv_python.exists():
        raise RuntimeError("Missing project virtual environment.")

    os.environ["QUARTO_PYTHON"] = str(venv_python)

    try:
        compile_report(project_root, venv_python, args.file)
    except FileNotFoundError:
        print("Error: 'quarto' executable not found.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error: Quarto rendering failed with exit code {e.returncode}.")
        sys.exit(e.returncode)


if __name__ == "__main__":
    main()
