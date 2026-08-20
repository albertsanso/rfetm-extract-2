#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Descarga las páginas HTML de equipos de la RFETM por temporada."""

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


RFETM_URL = "https://www.rfetm.es/public/resultados/{season}/view.php?listaeq=eq"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = REPO_ROOT / "resources" / "equipos-html"
REQUEST_DELAY = 2.0
REQUEST_TIMEOUT = 15
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def validate_season(season: str) -> bool:
    """Devuelve si *season* tiene el formato YYYY-YYYY consecutivo."""
    match = re.fullmatch(r"(\d{4})-(\d{4})", season)
    return bool(match and int(match.group(2)) == int(match.group(1)) + 1)


def seasons_between(start: str, end: str) -> List[str]:
    """Genera las temporadas del rango, incluyendo ambos extremos."""
    start_year = int(start[:4])
    end_year = int(end[:4])
    step = 1 if end_year >= start_year else -1
    return [f"{year}-{year + 1}" for year in range(start_year, end_year + step, step)]


def create_session() -> requests.Session:
    """Crea una sesión con reintentos para errores HTTP transitorios."""
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(
        total=3,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=frozenset(("GET",)),
        backoff_factor=1,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def decode_html(response: requests.Response) -> str:
    """Decodifica HTML RFETM, cuyos documentos históricos pueden ser Latin-1."""
    content = response.content
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("iso-8859-1")


def get_page(session: requests.Session, url: str) -> Optional[str]:
    """Descarga una página; RFETM usa 500 con cuerpo HTML válido en ocasiones."""
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        body = decode_html(response)
        if response.status_code in (200, 500) and body:
            return body
        logger.error("HTTP %s sin contenido útil: %s", response.status_code, url)
    except requests.RequestException as error:
        logger.error("Error al descargar %s: %s", url, error)
    finally:
        time.sleep(REQUEST_DELAY)
    return None


def save_html(content: str, path: Path) -> None:
    """Guarda el documento creando el directorio de salida si es necesario."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def download_season(
    session: requests.Session,
    season: str,
    output_dir: Path,
    overwrite: bool = False,
) -> Dict[str, int]:
    """Descarga una temporada y devuelve contadores de resultado."""
    destination = output_dir / f"{season}.html"
    if destination.exists() and not overwrite:
        logger.info("Omitido (ya existe): %s", destination)
        return {"descargados": 0, "saltados": 1, "errores": 0}

    url = RFETM_URL.format(season=season)
    logger.info("Descargando %s", url)
    html = get_page(session, url)
    if html is None:
        return {"descargados": 0, "saltados": 0, "errores": 1}

    try:
        save_html(html, destination)
    except OSError as error:
        logger.error("Error al guardar %s: %s", destination, error)
        return {"descargados": 0, "saltados": 0, "errores": 1}
    logger.info("Guardado: %s", destination)
    return {"descargados": 1, "saltados": 0, "errores": 0}


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Procesa los argumentos de línea de órdenes."""
    parser = argparse.ArgumentParser(description="Descarga páginas de equipos RFETM por temporada.")
    parser.add_argument(
        "--start-season", "--start_season", required=True, metavar="YYYY-YYYY",
        help="Primera temporada del rango (incluida).",
    )
    parser.add_argument(
        "--end-season", "--end_season", metavar="YYYY-YYYY",
        help="Última temporada del rango (incluida); por defecto, la inicial.",
    )
    parser.add_argument(
        "--output-dir", "--output_dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Directorio de salida (por defecto: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Sobrescribe los archivos HTML existentes.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Punto de entrada del descargador."""
    args = parse_args(argv)
    end_season = args.end_season or args.start_season
    if not validate_season(args.start_season) or not validate_season(end_season):
        logger.error("Formato de temporada incorrecto; use YYYY-YYYY consecutivo.")
        return 2

    seasons = seasons_between(args.start_season, end_season)
    stats = {"descargados": 0, "saltados": 0, "errores": 0}
    session = create_session()
    try:
        for season in seasons:
            result = download_season(session, season, args.output_dir, args.overwrite)
            for key in stats:
                stats[key] += result[key]
    except KeyboardInterrupt:
        logger.warning("Descarga interrumpida por el usuario.")
        return 130
    finally:
        session.close()

    logger.info(
        "Proceso completado: %d descargados, %d omitidos, %d errores.",
        stats["descargados"], stats["saltados"], stats["errores"],
    )
    return 1 if stats["errores"] else 0


if __name__ == "__main__":
    sys.exit(main())
