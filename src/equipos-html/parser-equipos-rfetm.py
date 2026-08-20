#!/usr/bin/env python3
"""Extrae los equipos de las páginas HTML descargadas de la RFETM."""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup


RAIZ_REPOSITORIO = Path(__file__).resolve().parent.parent.parent
DIRECTORIO_ENTRADA = RAIZ_REPOSITORIO / "resources" / "equipos-html"
DIRECTORIO_SALIDA = RAIZ_REPOSITORIO / "resources" / "equipos-json"
TEMPORADA_RE = re.compile(r"^(\d{4})-(\d{4})$")

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def limpiar(texto: str) -> str:
    """Normaliza espacios, saltos de línea y espacios no separables."""
    return " ".join(texto.replace("\xa0", " ").split())


def temporada_valida(temporada: str) -> bool:
    """Comprueba que una temporada tenga años consecutivos."""
    coincidencia = TEMPORADA_RE.fullmatch(temporada)
    return bool(coincidencia and int(coincidencia.group(2)) == int(coincidencia.group(1)) + 1)


def leer_html(ruta: Path) -> str:
    """Lee HTML RFETM, admitiendo tanto UTF-8 como Latin-1."""
    contenido = ruta.read_bytes()
    try:
        return contenido.decode("utf-8")
    except UnicodeDecodeError:
        return contenido.decode("iso-8859-1")


def texto_visible(celda) -> str:
    """Obtiene texto visible, ignorando elementos con ``display:none``."""
    for elemento in celda.select("[style*='display:none'], [style*='display: none']"):
        elemento.extract()
    return limpiar(celda.get_text(" "))


def encontrar_indices(tabla) -> tuple[int, int, int] | None:
    """Devuelve los índices de Equipo, Club y Liga de una tabla."""
    for fila in tabla.find_all("tr"):
        celdas = fila.find_all(["th", "td"], recursive=False)
        cabeceras = [limpiar(celda.get_text(" ")).casefold() for celda in celdas]
        indices = {}
        for nombre in ("equipo", "club", "liga"):
            if nombre in cabeceras:
                indices[nombre] = cabeceras.index(nombre)
        if len(indices) == 3:
            return indices["equipo"], indices["club"], indices["liga"]
    return None


def extraer_equipos(html: str, temporada: str) -> list[dict[str, str]]:
    """Extrae los equipos de un documento HTML de una temporada."""
    soup = BeautifulSoup(html, "html.parser")
    equipos: list[dict[str, str]] = []

    for tabla in soup.find_all("table"):
        indices = encontrar_indices(tabla)
        if indices is None:
            continue
        indice_equipo, indice_club, indice_liga = indices
        for fila in tabla.find_all("tr")[1:]:
            celdas = fila.find_all("td", recursive=False)
            maximo = max(indices)
            if len(celdas) <= maximo:
                continue
            equipo = texto_visible(celdas[indice_equipo])
            club = texto_visible(celdas[indice_club])
            liga = texto_visible(celdas[indice_liga])
            if not equipo and not club and not liga:
                continue
            if not equipo or not club:
                logger.warning("Fila ignorada por datos incompletos en la temporada %s", temporada)
                continue
            equipos.append(
                {
                    "season": temporada,
                    "club_name": club,
                    "team_name": equipo,
                    "category": liga,
                }
            )
        break

    if not equipos:
        raise ValueError(f"No se encontró la tabla de equipos en {temporada}")
    return equipos


def obtener_archivos(directorio: Path, temporada: str | None) -> list[tuple[str, Path]]:
    """Obtiene archivos HTML y temporadas a partir de sus nombres."""
    if temporada:
        ruta = directorio / f"{temporada}.html"
        if not ruta.is_file():
            raise FileNotFoundError(f"No existe el HTML de la temporada: {ruta}")
        return [(temporada, ruta)]

    archivos = []
    for ruta in sorted(directorio.glob("*.html")):
        nombre = ruta.stem
        if temporada_valida(nombre):
            archivos.append((nombre, ruta))
        else:
            logger.warning("Se omite un archivo con nombre de temporada no válido: %s", ruta.name)
    if not archivos:
        raise FileNotFoundError(f"No hay archivos YYYY-YYYY.html en {directorio}")
    return archivos


def ruta_salida(argumento: str | None, temporada: str) -> Path:
    """Resuelve la ruta de salida, admitiendo el marcador ``{season}``."""
    if argumento is None:
        return DIRECTORIO_SALIDA / f"{temporada}.json"
    return Path(argumento.format(season=temporada))


def guardar(equipos: Iterable[dict[str, str]], ruta: Path, overwrite: bool) -> bool:
    """Guarda equipos salvo que exista el destino y no se permita sobrescribir."""
    if ruta.exists() and not overwrite:
        logger.info("Se omite el archivo existente: %s", ruta)
        return False
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(list(equipos), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logger.info("Guardados los equipos en %s", ruta)
    return True


def crear_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", "--input_dir", type=Path, default=DIRECTORIO_ENTRADA,
                        help="Directorio con los archivos HTML de equipos.")
    parser.add_argument("--output-file", "--output_file",
                        help="Archivo JSON; admite {season} al procesar varias temporadas.")
    parser.add_argument("--season", help="Procesa únicamente esta temporada (YYYY-YYYY).")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescribe los JSON existentes.")
    parser.add_argument("--verbose", action="store_true", help="Muestra mensajes de depuración.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = crear_parser()
    argumentos = parser.parse_args(argv)
    if argumentos.verbose:
        logger.setLevel(logging.DEBUG)
    if argumentos.season and not temporada_valida(argumentos.season):
        parser.error("--season debe tener el formato YYYY-YYYY con años consecutivos")
    try:
        archivos = obtener_archivos(argumentos.input_dir, argumentos.season)
        if len(archivos) > 1 and argumentos.output_file and "{season}" not in argumentos.output_file:
            parser.error("--output-file debe incluir {season} al procesar varias temporadas")
        for temporada, ruta in archivos:
            equipos = extraer_equipos(leer_html(ruta), temporada)
            guardar(equipos, ruta_salida(argumentos.output_file, temporada), argumentos.overwrite)
    except (FileNotFoundError, OSError, ValueError) as error:
        logger.error("%s", error)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
