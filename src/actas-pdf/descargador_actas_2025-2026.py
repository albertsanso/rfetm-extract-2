#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Descargador de actas RFETM 2025-2026

Descarga todas las actas de los partidos de tenis de mesa desde:
https://www.rfetm.es/public/resultados/2025-2026/

y las organiza en una estructura de carpetas:
/resources/actas/{temporada}/{categoria}/{grupo}/{sexo}/
"""

import os
import re
import sys
import time
import argparse
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from typing import Set, List, Dict, Tuple

import requests
from bs4 import BeautifulSoup

# ══════════════════════════════════════════
#  Configuración
# ══════════════════════════════════════════

BASE_URL = "https://www.rfetm.es/public/resultados/2025-2026/"
RESULTADOS_PATTERN = "https://www.rfetm.es/public/resultados/2025-2026/view.php"

# Extraer temporada de la URL base
SEASON = "2025-2026"

# Workspace
WORKSPACE_ROOT = Path(__file__).parent.parent
ACTAS_DIR = WORKSPACE_ROOT / "resources" / "actas" / SEASON

# Configuración de requests
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

DELAY_BETWEEN_REQUESTS = 2  # segundos
DELAY_BETWEEN_DOWNLOADS = 1  # segundos

# ══════════════════════════════════════════
#  Mapeo de Categorías
# ══════════════════════════════════════════
#
# IMPORTANTE: Los códigos de categoría de la URL ("MQ", "Mg", "Mw", "NA")
# NUNCA deben usarse directamente como nombres de carpetas.
# Siempre deben mapearse a sus equivalentes legibles.

CATEGORIA_MAPPING = {
    "MQ": "super-divisio",       # NUNCA usar "MQ" como nombre de carpeta
    "Mg": "divisio-honor",       # NUNCA usar "Mg" como nombre de carpeta
    "Mw": "primera-nacional",    # NUNCA usar "Mw" como nombre de carpeta
    "NA": "segona-nacional",     # NUNCA usar "NA" como nombre de carpeta
    "Ng": "fasc-super-divisio",  # NUNCA usar "Ng" como nombre de carpeta
    "Nw": "fasc-divisio-honor",  # NUNCA usar "Nw" como nombre de carpeta
    "OA": "fasc-primera-divisio", # NUNCA usar "OA" como nombre de carpeta
}

# ══════════════════════════════════════════
#  Logging
# ══════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════
#  Utilidades
# ══════════════════════════════════════════


def create_session() -> requests.Session:
    """Crea una sesión con configuración de reintentos."""
    session = requests.Session()
    session.headers.update(HEADERS)

    # Reintentos
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    retry_strategy = Retry(
        total=3,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"],
        backoff_factor=1
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


def map_categoria_code(codigo: str) -> str:
    """
    Mapea un código de categoría de URL a su nombre de carpeta legible.

    GARANTIZA que nunca se usará un código directo como nombre de carpeta.
    Los códigos válidos son: MQ, Mg, Mw, NA, Ng, Nw, OA

    Args:
        codigo: Código de categoría desde la URL

    Returns:
        Nombre legible de categoría para usar como nombre de carpeta

    Raises:
        ValueError: Si el código no es reconocido (seguridad contra códigos desconocidos)
    """
    if codigo not in CATEGORIA_MAPPING:
        raise ValueError(
            f"Código de categoría desconocido: '{codigo}'. "
            f"Códigos válidos: {', '.join(CATEGORIA_MAPPING.keys())}"
        )
    return CATEGORIA_MAPPING[codigo]


def get_page(session: requests.Session, url: str) -> str:
    """Obtiene el contenido HTML de una página con manejo de errores."""
    try:
        logger.info(f"Descargando: {url}")
        response = session.get(url, timeout=10)
        response.raise_for_status()
        time.sleep(DELAY_BETWEEN_REQUESTS)
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error al descargar {url}: {e}")
        return None


def extract_result_links(html: str) -> Set[str]:
    """
    Extrae todos los enlaces de resultados de la página principal.
    Busca enlaces con el patrón: view.php?liga=...&grupo=...&sexo=...
    """
    soup = BeautifulSoup(html, "html.parser")
    result_links = set()

    # Buscar todos los enlaces
    for link in soup.find_all("a", href=True):
        href = link["href"]

        # Normalizar URL
        if href.startswith("view.php"):
            href = urljoin(BASE_URL, href)

        # Verificar si es un enlace de resultados
        if "view.php" in href and "liga=" in href and "sexo=" in href:
            result_links.add(href)

    logger.info(f"Encontrados {len(result_links)} enlaces de resultados")
    return result_links


def extract_acta_links_from_results(session: requests.Session, result_url: str) -> List[Tuple[str, str]]:
    """
    Extrae todos los enlaces a las actas desde una página de resultados.
    Devuelve lista de tuplas (acta_url, partido_info)
    """
    html = get_page(session, result_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    acta_links = []

    # Buscar enlaces a actas: /ligas/partido/{id}/imprimir/acta
    for link in soup.find_all("a", href=True):
        href = link["href"]

        if "/ligas/partido/" in href and "/imprimir/acta" in href:
            # Normalizar URL
            if href.startswith("/"):
                acta_url = urljoin("https://clubs.rfetm.es", href)
            else:
                acta_url = urljoin("https://clubs.rfetm.es/", href)

            # Extraer ID del partido
            match = re.search(r"/partido/(\d+)/", href)
            partido_id = match.group(1) if match else "unknown"

            acta_links.append((acta_url, partido_id))

    logger.info(f"Encontradas {len(acta_links)} actas en {result_url}")
    return acta_links


def parse_result_url(url: str) -> Dict[str, str]:
    """
    Parsea una URL de resultados y extrae categoría, grupo y sexo.

    Formato: view.php?liga={categoria}==&grupo={grupo}&subgrupo=S&jornada=0&sexo={sexo}

    IMPORTANTE: Los códigos de categoría se mapean SIEMPRE a nombres legibles:
    - MQ -> super-divisio (NUNCA "MQ")
    - Mg -> divisio-honor (NUNCA "Mg")
    - Mw -> primera-nacional (NUNCA "Mw")
    - NA -> segona-nacional (NUNCA "NA")

    Lanza excepción si se recibe un código de categoría desconocido.
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    categoria_code = params.get("liga", [""])[0].replace("==", "").strip()
    grupo = params.get("grupo", [""])[0].strip()
    sexo = params.get("sexo", [""])[0].strip()

    # Mapear código de categoría al nombre legible (con validación estricta)
    # Esto garantiza que NUNCA se use un código directo como nombre de carpeta
    try:
        categoria = map_categoria_code(categoria_code)
    except ValueError as e:
        logger.error(f"Error procesando URL {url}: {e}")
        raise

    # Mapear sexo a label más legible
    sexo_label = {
        "M": "masculino",
        "F": "femenino",
    }.get(sexo, sexo)

    return {
        "categoria": categoria,
        "grupo": grupo,
        "sexo": sexo_label,
        "sexo_code": sexo,
    }


def create_acta_folder(categoria: str, grupo: str, sexo: str) -> Path:
    """Crea la estructura de carpetas y devuelve la ruta."""
    folder = ACTAS_DIR / categoria / grupo / sexo
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def download_acta(session: requests.Session, acta_url: str, save_path: Path, force: bool = False) -> Tuple[bool, bool]:
    """
    Descarga un PDF de acta y lo guarda en la ruta especificada.

    Returns:
        Tuple[bool, bool]: (éxito, descargado)
        - éxito: True si la descarga fue exitosa o el archivo ya existe
        - descargado: True si se descargó un nuevo archivo (no existía antes)
    """
    try:
        if save_path.exists() and not force:
            logger.debug(f"Archivo ya existe (saltado): {save_path}")
            return True, False  # Éxito pero no descargado

        if save_path.exists() and force:
            logger.info(f"Reemplazando archivo existente: {save_path}")

        logger.info(f"Descargando acta: {acta_url}")
        response = session.get(acta_url, timeout=15)
        response.raise_for_status()

        # Verificar que sea PDF
        if response.headers.get("content-type", "").lower().startswith("application/pdf"):
            with open(save_path, "wb") as f:
                f.write(response.content)
            logger.info(f"Guardado: {save_path}")
            time.sleep(DELAY_BETWEEN_DOWNLOADS)
            return True, True  # Éxito y descargado
        else:
            logger.warning(f"No es PDF: {acta_url}")
            return False, False
    except Exception as e:
        logger.error(f"Error al descargar acta {acta_url}: {e}")
        return False, False


def main():
    """Función principal."""
    # Parsear argumentos
    parser = argparse.ArgumentParser(
        description="Descargador de actas RFETM 2025-2026",
        epilog="Ejemplo: python descargador_actas_2025-2026.py --force"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fuerza la descarga incluso si los archivos ya existen (por defecto: salta archivos existentes)"
    )
    args = parser.parse_args()

    force_download = args.force

    logger.info("Iniciando descargador de actas RFETM")
    logger.info(f"URL base: {BASE_URL}")
    logger.info(f"Carpeta de destino: {ACTAS_DIR}")
    if force_download:
        logger.warning("MODO FUERZA ACTIVADO: Se descargarán incluso los archivos ya existentes")
    else:
        logger.info("MODO NORMAL: Se saltarán los archivos ya descargados")

    # Crear sesión
    session = create_session()

    try:
        # 1. Obtener página principal
        logger.info("Descargando página principal...")
        html = get_page(session, BASE_URL)
        if not html:
            logger.error("No se pudo descargar la página principal")
            return 1

        # 2. Extraer enlaces de resultados
        result_links = extract_result_links(html)
        if not result_links:
            logger.warning("No se encontraron enlaces de resultados")
            return 1

        logger.info(f"Total de enlaces de resultados: {len(result_links)}")

        # 3. Para cada enlace de resultados, extraer actas
        total_actas_encontradas = 0
        total_actas_descargadas = 0
        total_actas_saltadas = 0
        total_actas_error = 0

        for i, result_url in enumerate(sorted(result_links), 1):
            logger.info(f"\n[{i}/{len(result_links)}] Procesando: {result_url}")

            # Parsear URL
            try:
                url_info = parse_result_url(result_url)
            except ValueError as e:
                logger.error(f"Error al procesar URL: {e}")
                total_actas_error += 1
                continue

            categoria = url_info["categoria"]
            grupo = url_info["grupo"]
            sexo = url_info["sexo"]

            logger.info(f"  Categoría: {categoria}, Grupo: {grupo}, Sexo: {sexo}")

            # Extraer actas
            acta_links = extract_acta_links_from_results(session, result_url)

            if not acta_links:
                logger.info(f"  Sin actas en esta página")
                continue

            # Crear carpeta de destino
            acta_folder = create_acta_folder(categoria, grupo, sexo)

            # Descargar cada acta
            for acta_url, partido_id in acta_links:
                total_actas_encontradas += 1
                acta_filename = f"acta_{partido_id}.pdf"
                acta_path = acta_folder / acta_filename

                exitoso, descargado = download_acta(session, acta_url, acta_path, force=force_download)

                if exitoso:
                    if descargado:
                        total_actas_descargadas += 1
                    else:
                        total_actas_saltadas += 1
                else:
                    total_actas_error += 1

        logger.info(f"\n{'='*60}")
        logger.info(f"Descarga completada")
        logger.info(f"{'='*60}")
        logger.info(f"Total de actas encontradas: {total_actas_encontradas}")
        logger.info(f"Total de actas descargadas: {total_actas_descargadas}")
        logger.info(f"Total de actas saltadas (ya existentes): {total_actas_saltadas}")
        if total_actas_error > 0:
            logger.warning(f"Total de actas con error: {total_actas_error}")
        logger.info(f"Carpeta de destino: {ACTAS_DIR}")
        logger.info(f"{'='*60}")

        return 0

    except Exception as e:
        logger.error(f"Error no manejado: {e}", exc_info=True)
        return 1

    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())


