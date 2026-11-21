"""The ``onboardkit-gen`` command line: generate, list, verify, check, and show datasets.

Exit codes: 0 success, 1 verification problems, 2 invalid arguments or configuration,
3 dataset already exists, 4 unexpected error. Output is plain text, one fact per line;
errors go to stderr.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from pydantic import ValidationError

from onboardkit.datagen.answer_keys.checks import check_truth
from onboardkit.datagen.config import (
    DatasetConfig,
    apply_overrides,
    available_presets,
    load_preset,
    resolve_config,
)
from onboardkit.datagen.manifest import MANIFEST_NAME, verify_manifest
from onboardkit.datagen.pipeline import DEFAULT_OUT_ROOT, DatasetExistsError, generate_dataset

EXIT_OK = 0
EXIT_VERIFY = 1
EXIT_INVALID = 2
EXIT_EXISTS = 3
EXIT_ERROR = 4

DEFAULT_PRESET = "typical"
DEFAULT_SIZE = "default"
DEFAULT_SEED = 42
# Keys a --config file may set that the command line has no flag for.
CONFIG_SECTIONS = ("coverage", "book_of_business", "mess", "firm_profile")

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Generate, list, verify, and inspect synthetic advisor-firm datasets.",
)


def fail(message: str, code: int) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code)


def guarded[T](action: Callable[[], T]) -> T:
    """Run ``action`` and turn failures into the documented exit codes."""
    try:
        return action()
    except typer.Exit:
        raise
    except DatasetExistsError as exc:
        raise fail(f"error: {exc}; use --overwrite to replace it", EXIT_EXISTS) from exc
    except (ValueError, ValidationError, yaml.YAMLError, OSError) as exc:
        raise fail(f"error: {_one_line(exc)}", EXIT_INVALID) from exc
    except Exception as exc:
        raise fail(f"unexpected error: {type(exc).__name__}: {exc}", EXIT_ERROR) from exc


def _one_line(exc: BaseException) -> str:
    return " ".join(str(exc).split())


def _read_config_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"config file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"config file {path} must contain a mapping")
    return data


def build_config(
    preset: str | None,
    size: str | None,
    seed: int | None,
    mess: list[str],
    as_of: str | None,
    config_file: Path | None,
) -> DatasetConfig:
    """Defaults, then the config file, then explicit flags; each later layer wins."""
    file_data = _read_config_file(config_file) if config_file else {}
    unknown = set(file_data) - {"preset", "size", "seed", "as_of_date", *CONFIG_SECTIONS}
    if unknown:
        raise ValueError(f"unknown keys in config file: {sorted(unknown)}")
    file_size = file_data.get("size", {})
    chosen_size: str | int = (
        size
        or (file_size.get("households") if isinstance(file_size, dict) else None)
        or DEFAULT_SIZE
    )
    chosen_seed = seed if seed is not None else file_data.get("seed", DEFAULT_SEED)
    when = as_of or file_data.get("as_of_date")
    config = resolve_config(
        preset or file_data.get("preset") or DEFAULT_PRESET,
        chosen_size,
        int(chosen_seed),
        {key: file_data[key] for key in CONFIG_SECTIONS if key in file_data},
        date.fromisoformat(str(when)) if when else None,
    )
    if mess:
        config = config.model_copy(update={"mess": apply_overrides(config.mess, mess)})
    return config


@app.command()
def generate(
    preset: Annotated[
        str | None, typer.Option(help="Preset name; see `presets`. Default: typical.")
    ] = None,
    size: Annotated[
        str | None, typer.Option(help="sample, default, or a number of households.")
    ] = None,
    seed: Annotated[int | None, typer.Option(help="Random seed. Default: 42.")] = None,
    mess: Annotated[
        list[str] | None,
        typer.Option(
            "--mess",
            help="Override a mess type, as NAME=LEVEL (off, light, moderate, heavy, max, or "
            "0 to 1). Repeatable, for example --mess names=heavy --mess balances=0.2.",
        ),
    ] = None,
    as_of: Annotated[
        str | None, typer.Option("--as-of", help="As-of date, YYYY-MM-DD. Default: 2025-12-31.")
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option(help="YAML file with settings; explicit flags override its values."),
    ] = None,
    out: Annotated[
        Path, typer.Option(help="Output root; the dataset goes in a folder named by its id.")
    ] = DEFAULT_OUT_ROOT,
    overwrite: Annotated[
        bool, typer.Option("--overwrite", help="Replace the dataset if it already exists.")
    ] = False,
    quiet: Annotated[bool, typer.Option("--quiet", help="Print only the dataset path.")] = False,
) -> None:
    """Generate one dataset: exports, truth folder, and manifest.

    Only exports/ is what a firm would deliver; truth/ is internal answer material.
    """

    def run() -> None:
        resolved = build_config(preset, size, seed, mess or [], as_of, config)
        result = generate_dataset(resolved, out, overwrite=overwrite)
        if quiet:
            typer.echo(str(result.path))
            return
        typer.echo(f"dataset: {result.dataset_id}")
        typer.echo(f"path: {result.path}")
        for key, value in result.counts.items():
            typer.echo(f"{key}: {value}")

    guarded(run)


@app.command()
def presets() -> None:
    """List the available presets with their description and mess settings."""

    def run() -> None:
        for name in available_presets():
            data = load_preset(name)
            typer.echo(f"{name}: {data['description']}")
            settings = data.get("mess", {})
            active = [
                f"{key}={value['intensity']}"
                for key, value in settings.items()
                if value.get("enabled") and value.get("intensity", 0) > 0
            ]
            typer.echo(f"  mess: {', '.join(active) if active else 'none'}")

    guarded(run)


def _dataset_dir(path: Path) -> Path:
    if not path.is_dir():
        raise ValueError(f"not a dataset directory: {path}")
    return path


@app.command()
def verify(
    dataset_dir: Annotated[Path, typer.Argument(help="A dataset folder with a manifest.json.")],
) -> None:
    """Check a dataset's files against the manifest; exit 1 if anything differs."""

    def run() -> None:
        problems = verify_manifest(_dataset_dir(dataset_dir))
        if not problems:
            typer.echo("ok: all files match the manifest")
            return
        for problem in problems:
            typer.echo(str(problem))
        typer.echo(f"{len(problems)} problem(s) found")
        raise typer.Exit(EXIT_VERIFY)

    guarded(run)


@app.command()
def check(
    dataset_dir: Annotated[Path, typer.Argument(help="A dataset folder with a truth/ folder.")],
) -> None:
    """Check the internal truth/ folder: completeness, consistency, and no leaks into exports/."""

    def run() -> None:
        problems = check_truth(_dataset_dir(dataset_dir))
        if not problems:
            typer.echo("ok: truth is complete, consistent, and separate from the exports")
            return
        for problem in problems:
            typer.echo(str(problem))
        typer.echo(f"{len(problems)} problem(s) found")
        raise typer.Exit(EXIT_VERIFY)

    guarded(run)


@app.command()
def show(
    dataset_dir: Annotated[Path, typer.Argument(help="A dataset folder with a manifest.json.")],
) -> None:
    """Print a summary of a dataset's manifest."""

    def run() -> None:
        path = _dataset_dir(dataset_dir) / MANIFEST_NAME
        if not path.is_file():
            raise ValueError(f"no {MANIFEST_NAME} in {dataset_dir}")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        config = manifest["config"]
        typer.echo(f"dataset: {manifest['dataset_id']}")
        typer.echo(f"preset: {config.get('preset')}")
        typer.echo(f"seed: {config['seed']}")
        typer.echo(f"generator version: {manifest['generator_version']}")
        typer.echo(f"manifest version: {manifest['manifest_version']}")
        typer.echo(f"config hash: {manifest['config_hash']}")
        for key, value in manifest["counts"].items():
            typer.echo(f"{key}: {value}")
        typer.echo(f"files: {len(manifest['files'])}")
        listed = [f["path"] for f in manifest["files"]]
        delivered = sum(1 for path in listed if path.startswith("exports/"))
        internal = sum(1 for path in listed if path.startswith("truth/"))
        typer.echo(f"exports (what a firm delivers): {delivered} files")
        typer.echo(f"truth (INTERNAL, never part of a delivery): {internal} files")

    guarded(run)
