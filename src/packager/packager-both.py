"""Empaqueta conjuntamente los datos JSON de actas y equipos."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_ACTAS_INPUT_DIR = REPO_ROOT / "resources" / "actas-json"
DEFAULT_EQUIPOS_INPUT_DIR = REPO_ROOT / "resources" / "equipos-json"
DEFAULT_OUTPUT_FILE = REPO_ROOT / "resources" / "actas-equipos-json.zip"
SEASON_PATTERN = re.compile(r"^\d{4}-\d{4}$")


def parse_seasons(value: str) -> list[str]:
    """Convierte una lista de temporadas separada por comas en valores únicos."""
    seasons = [season.strip() for season in value.split(",")]
    if not all(seasons):
        raise argparse.ArgumentTypeError(
            "--season debe contener temporadas no vacías separadas por comas."
        )
    invalid_seasons = [
        season for season in seasons if not SEASON_PATTERN.fullmatch(season)
    ]
    if invalid_seasons:
        raise argparse.ArgumentTypeError(
            "Formato de temporada no válido: " + ", ".join(invalid_seasons)
        )
    return list(dict.fromkeys(seasons))


def _relative_json_files(input_dir: Path) -> list[tuple[Path, Path]]:
    """Devuelve archivos JSON regulares junto con sus rutas relativas ordenables."""
    files = [
        (path, path.relative_to(input_dir))
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix == ".json"
    ]
    return sorted(files, key=lambda item: item[1].as_posix())


def find_actas_files(
    input_dir: Path, seasons: list[str] | str | None = None
) -> list[Path]:
    """Encuentra JSON de actas, filtrando por la primera carpeta de temporada."""
    selected_seasons = (
        parse_seasons(seasons) if isinstance(seasons, str) else seasons
    )
    return [
        path
        for path, relative_path in _relative_json_files(input_dir)
        if selected_seasons is None
        or (relative_path.parts and relative_path.parts[0] in selected_seasons)
    ]


def find_equipos_files(
    input_dir: Path, seasons: list[str] | str | None = None
) -> list[Path]:
    """Encuentra JSON de equipos en carpetas o en la raíz como <temporada>.json."""
    selected_seasons = (
        parse_seasons(seasons) if isinstance(seasons, str) else seasons
    )
    result = []
    for path, relative_path in _relative_json_files(input_dir):
        if selected_seasons is None:
            result.append(path)
            continue
        is_season_directory = (
            relative_path.parts and relative_path.parts[0] in selected_seasons
        )
        is_root_season_file = (
            len(relative_path.parts) == 1
            and relative_path.stem in selected_seasons
        )
        if is_season_directory or is_root_season_file:
            result.append(path)
    return result


def detect_seasons(files: list[Path], input_dir: Path) -> set[str]:
    """Detecta temporadas válidas en cualquier componente de las rutas relativas."""
    return {
        Path(part).stem
        for path in files
        for part in path.relative_to(input_dir).parts
        if SEASON_PATTERN.fullmatch(Path(part).stem)
    }


def _archive_paths(files: list[Path], input_dir: Path, prefix: str) -> list[str]:
    """Construye rutas POSIX del ZIP con el prefijo de una fuente."""
    return [
        f"{prefix}/{path.relative_to(input_dir).as_posix()}"
        for path in files
    ]


def build_manifest(
    actas_files: list[Path],
    actas_input_dir: Path,
    equipos_files: list[Path],
    equipos_input_dir: Path,
) -> dict[str, object]:
    """Construye el manifiesto conjunto a partir de los archivos seleccionados."""
    actas_archive_paths = _archive_paths(actas_files, actas_input_dir, "actas-json")
    equipos_archive_paths = _archive_paths(
        equipos_files, equipos_input_dir, "equipos-json"
    )
    seasons = sorted(
        detect_seasons(actas_files, actas_input_dir)
        | detect_seasons(equipos_files, equipos_input_dir)
    )
    return {
        "source": "RFETM",
        "seasons": seasons,
        "assets": {
            "ACTAS": {"files": actas_archive_paths},
            "TEAMS": {"files": equipos_archive_paths},
        },
    }


def write_zip(
    output_file: Path,
    actas_files: list[Path],
    actas_input_dir: Path,
    equipos_files: list[Path],
    equipos_input_dir: Path,
    manifest: dict[str, object],
) -> None:
    """Escribe los dos conjuntos de archivos y el manifiesto en un ZIP."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_file, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in actas_files:
            archive.write(
                path,
                arcname=f"actas-json/{path.relative_to(actas_input_dir).as_posix()}",
            )
        for path in equipos_files:
            archive.write(
                path,
                arcname=f"equipos-json/{path.relative_to(equipos_input_dir).as_posix()}",
            )
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )


def package_both(
    actas_input_dir: Path,
    equipos_input_dir: Path,
    output_file: Path,
    force: bool = False,
    seasons: list[str] | str | None = None,
) -> tuple[int, int]:
    """Empaqueta actas y equipos y devuelve sus cantidades de archivos JSON."""
    if not actas_input_dir.is_dir():
        raise FileNotFoundError(
            f"No existe el directorio de entrada de actas: {actas_input_dir}"
        )
    if not equipos_input_dir.is_dir():
        raise FileNotFoundError(
            f"No existe el directorio de entrada de equipos: {equipos_input_dir}"
        )
    if output_file.exists() and not force:
        raise FileExistsError(
            f"El archivo de salida ya existe: {output_file}. Usa --force para reemplazarlo."
        )

    actas_files = find_actas_files(actas_input_dir, seasons)
    equipos_files = find_equipos_files(equipos_input_dir, seasons)
    manifest = build_manifest(
        actas_files,
        actas_input_dir,
        equipos_files,
        equipos_input_dir,
    )
    write_zip(
        output_file,
        actas_files,
        actas_input_dir,
        equipos_files,
        equipos_input_dir,
        manifest,
    )
    return len(actas_files), len(equipos_files)


def parse_args() -> argparse.Namespace:
    """Define y analiza las opciones de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Empaqueta conjuntamente los JSON de actas y equipos."
    )
    parser.add_argument(
        "--actas-input-dir",
        type=Path,
        default=DEFAULT_ACTAS_INPUT_DIR,
        help=f"Directorio de actas (por defecto: {DEFAULT_ACTAS_INPUT_DIR}).",
    )
    parser.add_argument(
        "--equipos-input-dir",
        type=Path,
        default=DEFAULT_EQUIPOS_INPUT_DIR,
        help=f"Directorio de equipos (por defecto: {DEFAULT_EQUIPOS_INPUT_DIR}).",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help=(
            "ZIP de salida (por defecto: actas-equipos-json.zip, o "
            "actas-equipos-json-<temporadas>.zip si se indica --season)."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reemplaza el ZIP de salida si ya existe.",
    )
    parser.add_argument(
        "--season",
        type=parse_seasons,
        help=(
            "Limita el paquete a una o varias temporadas separadas por comas, "
            "por ejemplo 2023-2024,2024-2025."
        ),
    )
    return parser.parse_args()


def main() -> None:
    """Ejecuta el empaquetador y muestra un resumen en español."""
    args = parse_args()
    output_file = args.output_file
    if output_file is None:
        output_file = (
            DEFAULT_OUTPUT_FILE.parent
            / f"actas-equipos-json-{','.join(args.season)}.zip"
            if args.season
            else DEFAULT_OUTPUT_FILE
        )

    try:
        actas_count, equipos_count = package_both(
            args.actas_input_dir,
            args.equipos_input_dir,
            output_file,
            args.force,
            args.season,
        )
    except (FileNotFoundError, FileExistsError) as error:
        raise SystemExit(f"Error: {error}") from error

    print(
        f"Se han empaquetado {actas_count} archivos de actas y "
        f"{equipos_count} archivos de equipos en {output_file}"
    )


if __name__ == "__main__":
    main()

