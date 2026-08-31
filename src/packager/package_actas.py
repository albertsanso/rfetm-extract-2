"""Empaqueta los datos JSON de actas en un archivo ZIP con manifiesto."""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INPUT_DIR = REPO_ROOT / "resources" / "actas-json"
DEFAULT_OUTPUT_FILE = REPO_ROOT / "resources" / "actas-json.zip"


def find_json_files(input_dir: Path, season: str | None = None) -> list[Path]:
    """Devuelve los JSON ordenados, opcionalmente limitados a una temporada."""
    return sorted(
        (
            path
            for path in input_dir.rglob("*.json")
            if path.is_file()
            and (
                season is None
                or (
                    path.relative_to(input_dir).parts
                    and path.relative_to(input_dir).parts[0] == season
                )
            )
        ),
        key=lambda path: path.relative_to(input_dir).as_posix(),
    )


def build_manifest(files: list[Path], input_dir: Path) -> dict[str, str | list[dict[str, str | int]]]:
    """Construye el manifiesto con las rutas relativas y tamaños de los archivos."""
    return {
        "source": "RFETM",
        "files": [
            {
                "path": path.relative_to(input_dir).as_posix(),
                "size": path.stat().st_size,
            }
            for path in files
        ]
    }


def package_actas(
    input_dir: Path,
    output_file: Path,
    force: bool = False,
    season: str | None = None,
) -> int:
    """Crea el ZIP y devuelve el número de JSON empaquetados."""
    if not input_dir.is_dir():
        raise FileNotFoundError(f"No existe el directorio de entrada: {input_dir}")
    if output_file.exists() and not force:
        raise FileExistsError(
            f"El archivo de salida ya existe: {output_file}. Usa --force para reemplazarlo."
        )

    files = find_json_files(input_dir, season)
    manifest = build_manifest(files, input_dir)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=path.relative_to(input_dir).as_posix())
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )

    return len(files)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Empaqueta resources/actas-json en actas-json.zip."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directorio con los JSON (por defecto: {DEFAULT_INPUT_DIR}).",
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        help=(
            "ZIP de salida (por defecto: actas-json.zip, o "
            "actas-json-<season>.zip si se indica --season)."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reemplaza el ZIP de salida si ya existe.",
    )
    parser.add_argument(
        "--season",
        help="Limita el paquete a una temporada, por ejemplo 2025-2026.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_file = args.output_file
    if output_file is None:
        output_file = (
            DEFAULT_OUTPUT_FILE.parent / f"actas-json-{args.season}.zip"
            if args.season
            else DEFAULT_OUTPUT_FILE
        )

    count = package_actas(args.input_dir, output_file, args.force, args.season)
    print(f"Se han empaquetado {count} archivos JSON en {output_file}")


if __name__ == "__main__":
    main()
