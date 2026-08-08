#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Descargador de páginas web RFETM

Descarga el contenido HTML de las páginas de resultados de tenis de mesa desde:
https://www.rfetm.es/public/resultados/<season>/

y los organiza en una estructura de carpetas:
/resources/web-downloader/<season>/<category>/<day>/<sex>/

Uso:
    python web_downloader_rfetm.py --season 2024-2025
    python web_downloader_rfetm.py --season 2023-2024 --force
"""

import re
import sys
import time
import argparse
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from typing import Set, Dict, Optional

import requests
from bs4 import BeautifulSoup

# ══════════════════════════════════════════
#  Constantes
# ══════════════════════════════════════════

RFETM_BASE = "https://www.rfetm.es/public/resultados"

# Rango de temporadas soportadas (desde 2024-2025 hacia atrás hasta 2010-2011)
SEASON_START = 2024
SEASON_END = 2010

# Jornadas a recorrer: 1-22 (rondas individuales)
JORNADAS = list(range(1, 23))

# Sexos disponibles
SEXOS = ["M", "F"]

# Mapeo de códigos de liga (sin los '==') a nombres de carpeta
LIGA_MAPPING = {
    "MQ": "super-divisio",
    "Mg": "divisio-honor",
    "Mw": "primera-divisio",
    "NA": "segona-divisio",
    # Ligas adicionales detectadas en temporadas recientes
    "Ng": "fasc-super-divisio",
    "Nw": "fasc-divisio-honor",
    "OA": "fasc-primera-divisio",
}

# Mapeo de sexo a nombre de carpeta
SEXO_LABEL = {
    "M": "masculino",
    "F": "femenino",
}

# Workspace
WORKSPACE_ROOT = Path(__file__).parent.parent
WEB_DOWNLOADER_DIR = WORKSPACE_ROOT / "resources" / "web-downloader"

# Configuración de requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

DELAY_BETWEEN_REQUESTS = 2   # segundos entre peticiones HTTP
DELAY_ON_SKIP = 0            # segundos cuando se salta un archivo existente

# ══════════════════════════════════════════
#  Logging
# ══════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════
#  Utilidades de red
# ══════════════════════════════════════════


def create_session() -> requests.Session:
    """Crea una sesión HTTP con reintentos automáticos."""
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    session = requests.Session()
    session.headers.update(HEADERS)

    retry_strategy = Retry(
        total=3,
        # 500 se excluye: el servidor lo usa para "sin datos", no es un error transitorio
        status_forcelist=[429, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        backoff_factor=1,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def get_page(session: requests.Session, url: str, timeout: int = 15) -> Optional[str]:
    """
    Descarga el contenido HTML de una URL.

    NOTA: El servidor RFETM devuelve HTTP 500 con contenido HTML válido.
    Se considera exitosa cualquier respuesta que tenga contenido suficiente,
    independientemente del código de estado HTTP.

    Returns:
        Contenido HTML como string, o None si hubo error de red o sin contenido.
    """
    try:
        logger.debug(f"GET {url}")
        response = session.get(url, timeout=timeout)
        status = response.status_code
        body = response.text
        logger.debug(f"  → HTTP {status}, {len(body)} bytes")

        # El servidor RFETM devuelve 500 con HTML real - aceptar cualquier respuesta con contenido
        if status in (200, 500) and body:
            time.sleep(DELAY_BETWEEN_REQUESTS)
            return body

        # 404 u otros errores reales sin contenido útil
        if status == 404:
            logger.debug(f"404 Not Found: {url}")
        else:
            logger.debug(f"HTTP {status} sin contenido útil: {url}")
        return None

    except requests.RequestException as e:
        logger.warning(f"Error al descargar {url}: {e}")
        return None


# ══════════════════════════════════════════
#  Lógica de descubrimiento de temporada
# ══════════════════════════════════════════


def validate_season_format(season: str) -> bool:
    """Valida que la temporada tenga el formato YYYY-YYYY."""
    pattern = r"^\d{4}-\d{4}$"
    if not re.match(pattern, season):
        return False
    start_year, end_year = season.split("-")
    return int(end_year) == int(start_year) + 1


def build_season_url(season: str) -> str:
    """Construye la URL base de una temporada."""
    return f"{RFETM_BASE}/{season}/"


def build_results_url(season: str, liga_code: str, grupo: str, jornada: int, sexo: str) -> str:
    """
    Construye la URL de resultados para una combinación específica.
    El parámetro `liga` se incluye sin codificar (el servidor lo espera así).

    Args:
        season:     Temporada en formato YYYY-YYYY
        liga_code:  Código de liga en Base64 (ej: 'MQ==')
        grupo:      Número de grupo
        jornada:    Número de jornada (0=general, 1-22=por ronda)
        sexo:       'M' o 'F'

    Returns:
        URL completa de la página de resultados.
    """
    # El servidor espera 'liga=MQ==' sin URL-encoding del '=='
    return (
        f"{RFETM_BASE}/{season}/view.php"
        f"?liga={liga_code}&grupo={grupo}&subgrupo=S&jornada={jornada}&sexo={sexo}"
    )


def discover_liga_grupos(session: requests.Session, season: str) -> Dict[str, Set[str]]:
    """
    Descarga la página principal de la temporada y extrae las combinaciones
    liga+grupo disponibles parseando los enlaces <a href='view.php?...'>.

    Returns:
        Diccionario {liga_code_base64: set_of_grupos}
        Ejemplo: {'MQ==': {'0'}, 'Mg==': {'1', '2', '3'}}
    """
    season_url = build_season_url(season)
    logger.info(f"Descubriendo ligas/grupos para temporada {season}: {season_url}")

    html = get_page(session, season_url)
    if not html:
        logger.warning(f"No se pudo descargar la página de la temporada {season}. Se usarán valores por defecto.")
        return {}

    soup = BeautifulSoup(html, "html.parser")
    liga_grupos: Dict[str, Set[str]] = {}

    for link in soup.find_all("a", href=True):
        href = link["href"]

        # Normalizar URL relativa
        if href.startswith("view.php"):
            href = urljoin(season_url, href)

        if "view.php" not in href or "liga=" not in href:
            continue

        parsed = urlparse(str(href))
        params = parse_qs(parsed.query)

        liga_values = params.get("liga", [""])
        grupo_values = params.get("grupo", ["0"])
        liga: str = str(liga_values[0]) if liga_values else ""
        grupo: str = str(grupo_values[0]) if grupo_values else "0"

        if not liga:
            continue

        if liga not in liga_grupos:
            liga_grupos[liga] = set()
        liga_grupos[liga].add(grupo)

    if liga_grupos:
        for liga, grupos in sorted(liga_grupos.items()):
            code = liga.rstrip("=")
            name = LIGA_MAPPING.get(code, f"liga-{code}")
            logger.info(f"  Liga: {liga} ({name}) → grupos: {sorted(grupos)}")
    else:
        logger.warning("  No se encontraron ligas/grupos en la página de la temporada.")

    return liga_grupos


# ══════════════════════════════════════════
#  Gestión de archivos descargados
# ══════════════════════════════════════════


def map_liga_to_category(liga_code: str) -> str:
    """
    Mapea un código de liga (con o sin '==') al nombre de categoría para carpeta.

    Args:
        liga_code: Código de liga tal como aparece en la URL (ej: 'MQ==')

    Returns:
        Nombre de categoría (ej: 'super-divisio')
    """
    # Eliminar los '==' del final para obtener la clave del mapping
    base_code = liga_code.rstrip("=")
    if base_code not in LIGA_MAPPING:
        logger.warning(f"Código de liga desconocido: '{liga_code}'. Se usará como nombre de carpeta.")
        return f"liga-{base_code.lower()}"
    return LIGA_MAPPING[base_code]


def get_save_path(season: str, category: str, grupo: str, jornada: int, sexo: str) -> Path:
    """
    Construye la ruta de guardado para un archivo HTML.

    Estructura: resources/web-downloader/<season>/<category>/<day>/<sex>/
    Nombre de archivo: grupo_<grupo>.html

    Args:
        season:    Temporada (ej: '2024-2025')
        category:  Nombre de categoría (ej: 'super-divisio')
        grupo:     Número de grupo
        jornada:   Número de jornada
        sexo:      'M' o 'F'

    Returns:
        Path completo al archivo HTML de destino.
    """
    sexo_folder = SEXO_LABEL.get(sexo, sexo.lower())
    folder = WEB_DOWNLOADER_DIR / season / category / str(jornada) / sexo_folder
    filename = f"grupo_{grupo}.html"
    return folder / filename


def save_html(content: str, path: Path) -> bool:
    """
    Guarda contenido HTML en el archivo especificado, creando carpetas si es necesario.

    Returns:
        True si se guardó correctamente, False en caso de error.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Guardado: {path}")
        return True
    except OSError as e:
        logger.error(f"Error al guardar {path}: {e}")
        return False


# ══════════════════════════════════════════
#  Función principal de descarga
# ══════════════════════════════════════════


def download_season(
    session: requests.Session,
    season: str,
    force: bool = False,
) -> Dict[str, int]:
    """
    Descarga todas las páginas de resultados de una temporada.

    Proceso:
    1. Descubre las ligas y grupos disponibles en la página de la temporada.
    2. Para cada liga+grupo, itera sobre todas las jornadas (1-22) y sexos (M, F).
    3. Descarga el HTML de cada URL y lo guarda en la estructura de carpetas.

    Args:
        session: Sesión HTTP.
        season:  Temporada en formato YYYY-YYYY.
        force:   Si True, descarga aunque el archivo ya exista.

    Returns:
        Diccionario con contadores: descargados, saltados, errores, no_existe.
    """
    stats = {
        "descargados": 0,
        "saltados": 0,
        "errores": 0,
        "no_existe": 0,
    }

    # 1. Descubrir ligas y grupos
    liga_grupos = discover_liga_grupos(session, season)

    if not liga_grupos:
        logger.warning(
            f"No se encontraron ligas/grupos para {season}. "
            "Usando ligas principales con grupo 0 como fallback."
        )
        # Fallback: ligas principales con grupo 0
        liga_grupos = {
            "MQ==": {"0"},
            "Mg==": {"0"},
            "Mw==": {"0"},
            "NA==": {"0"},
        }

    # 2. Iterar sobre todas las combinaciones
    total_combinations = (
        sum(len(grupos) for grupos in liga_grupos.values())
        * len(JORNADAS)
        * len(SEXOS)
    )
    logger.info(
        f"Temporada {season}: {len(liga_grupos)} ligas, "
        f"{sum(len(g) for g in liga_grupos.values())} combos liga+grupo, "
        f"{len(JORNADAS)} jornadas, {len(SEXOS)} sexos "
        f"→ máximo {total_combinations} páginas"
    )

    processed = 0
    for liga_code, grupos in sorted(liga_grupos.items()):
        category = map_liga_to_category(liga_code)

        for grupo in sorted(grupos):
            for jornada in JORNADAS:
                for sexo in SEXOS:
                    processed += 1
                    url = build_results_url(season, liga_code, grupo, jornada, sexo)
                    save_path = get_save_path(season, category, grupo, jornada, sexo)

                    # Saltar si ya existe y no se fuerza
                    if save_path.exists() and not force:
                        logger.debug(f"Saltado (ya existe): {save_path.name}")
                        stats["saltados"] += 1
                        continue

                    # Descargar
                    logger.info(
                        f"[{processed}/{total_combinations}] "
                        f"{season} | {category} | grupo {grupo} | "
                        f"jornada {jornada} | {sexo}"
                    )
                    html = get_page(session, url)

                    if html is None:
                        stats["no_existe"] += 1
                        logger.debug(f"  Sin contenido o error: {url}")
                        continue

                    # Guardar
                    if save_html(html, save_path):
                        stats["descargados"] += 1
                    else:
                        stats["errores"] += 1

    return stats


def check_season_exists(session: requests.Session, season: str) -> bool:
    """
    Comprueba si la temporada existe en el servidor (responde con 200).

    Returns:
        True si la temporada existe, False en caso contrario.
    """
    url = build_season_url(season)
    try:
        response = session.head(url, timeout=10)
        time.sleep(0.5)
        return response.status_code == 200
    except requests.RequestException:
        return False


# ══════════════════════════════════════════
#  Punto de entrada
# ══════════════════════════════════════════


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descargador de páginas web de resultados RFETM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python web_downloader_rfetm.py --season 2024-2025
  python web_downloader_rfetm.py --season 2023-2024 --force
  python web_downloader_rfetm.py --season 2024-2025 --all-seasons
        """,
    )
    parser.add_argument(
        "--season",
        required=True,
        metavar="YYYY-YYYY",
        help="Temporada a descargar (ej: 2024-2025). Punto de partida si se usa --all-seasons.",
    )
    parser.add_argument(
        "--all-seasons",
        action="store_true",
        help=(
            f"Descarga desde la temporada indicada hacia atrás hasta {SEASON_END}-{SEASON_END + 1} "
            "o hasta que la URL no exista."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fuerza la descarga aunque los archivos ya existan.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Muestra mensajes de depuración.",
    )
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Validar formato de temporada
    if not validate_season_format(args.season):
        logger.error(f"Formato de temporada incorrecto: '{args.season}'. Use YYYY-YYYY (ej: 2024-2025).")
        return 1

    logger.info("=" * 60)
    logger.info("Descargador de páginas web RFETM")
    logger.info("=" * 60)
    logger.info(f"Destino base: {WEB_DOWNLOADER_DIR}")
    if args.force:
        logger.warning("MODO FUERZA: Se sobreescribirán archivos existentes.")

    session = create_session()

    try:
        # Determinar lista de temporadas
        if args.all_seasons:
            start_year = int(args.season.split("-")[0])
            seasons = [
                f"{y}-{y + 1}"
                for y in range(start_year, SEASON_END - 1, -1)
            ]
            logger.info(f"Modo multi-temporada: {len(seasons)} temporadas desde {seasons[0]} hasta {seasons[-1]}")
        else:
            seasons = [args.season]

        global_stats = {"descargados": 0, "saltados": 0, "errores": 0, "no_existe": 0}

        for season in seasons:
            logger.info(f"\n{'─' * 60}")
            logger.info(f"Procesando temporada: {season}")
            logger.info(f"{'─' * 60}")

            # Comprobar si la temporada existe (solo en modo multi-temporada)
            if args.all_seasons:
                if not check_season_exists(session, season):
                    logger.info(f"Temporada {season} no encontrada en el servidor. Deteniendo.")
                    break

            stats = download_season(session, season, force=args.force)

            for key in global_stats:
                global_stats[key] += stats[key]

            logger.info(
                f"Temporada {season} completada: "
                f"{stats['descargados']} descargados, "
                f"{stats['saltados']} saltados, "
                f"{stats['no_existe']} sin contenido, "
                f"{stats['errores']} errores."
            )

        logger.info(f"\n{'=' * 60}")
        logger.info("Descarga global completada")
        logger.info(f"{'=' * 60}")
        logger.info(f"  Páginas descargadas:    {global_stats['descargados']}")
        logger.info(f"  Páginas saltadas:       {global_stats['saltados']}")
        logger.info(f"  URLs sin contenido:     {global_stats['no_existe']}")
        logger.info(f"  Errores:                {global_stats['errores']}")
        logger.info(f"  Destino: {WEB_DOWNLOADER_DIR}")
        logger.info(f"{'=' * 60}")

        return 0

    except KeyboardInterrupt:
        logger.warning("\nDescarga interrumpida por el usuario.")
        return 130
    except Exception as e:
        logger.error(f"Error no manejado: {e}", exc_info=True)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())




