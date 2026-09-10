#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
convert-html-actas-to-json.py

Parsea los archivos HTML descargados en /resources/web-downloader/ y extrae
información de partidos de tenis de mesa, guardando cada partido como un
archivo JSON individual en /resources/actas-json/ manteniendo la misma
estructura de carpetas:

  actas-json/<season>/<category>/<jornada>/<sex>/acta_<match_id>.json

Las funciones de parsing HTML se basan en scraper_actas_mq_2024_2025.py y
reutilizan la misma lógica de extracción de tablas de la web RFETM.

Uso:
  # Procesar todos los HTML disponibles
  python convert-html-actas-to-json.py

  # Solo una temporada
  python convert-html-actas-to-json.py --season 2024-2025

  # Solo una categoría dentro de una temporada
  python convert-html-actas-to-json.py --season 2024-2025 --category divisio-honor

  # Forzar reescritura de archivos ya existentes
  python convert-html-actas-to-json.py --force

  # Verbose para ver detalles
  python convert-html-actas-to-json.py --verbose
"""

import json
import re
import sys
import argparse
import logging
from pathlib import Path

from bs4 import BeautifulSoup


# ══════════════════════════════════════════
#  Rutas del workspace
# ══════════════════════════════════════════

WORKSPACE_ROOT = Path(__file__).parent.parent.parent
WEB_DOWNLOADER_DIR = WORKSPACE_ROOT / "resources" / "web-downloader"
ACTAS_JSON_DIR = WORKSPACE_ROOT / "resources" / "actas-json"

# ══════════════════════════════════════════
#  Logging
# ══════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════
#  Mapeos de categorías a nombres de competición
# ══════════════════════════════════════════

CATEGORY_NAME = {
    "super-divisio":      "Superdivisión",
    "divisio-honor":      "División de Honor",
    "primera-divisio":    "Primera División",
    "primera-nacional":   "Primera Nacional",
    "segona-divisio":     "Segunda División",
    "segona-nacional":    "Segunda Nacional",
    "fasc-super-divisio": "FASC Superdivisión",
    "fasc-divisio-honor": "FASC División de Honor",
    "fasc-primera-divisio": "FASC Primera División",
}

SEX_LABEL = {
    "masculino": "Masculina",
    "femenino":  "Femenina",
}


# ══════════════════════════════════════════
#  Utilidades generales
# ══════════════════════════════════════════

def clean(text):
    """Elimina espacios extra. Devuelve None si el resultado está vacío."""
    if text is None:
        return None
    t = " ".join(str(text).split()).strip()
    return t if t else None


def parse_score(text):
    """Convierte 'X-Y' en la tupla (X, Y). Devuelve None si no aplica."""
    if not text:
        return None
    m = re.match(r"(\d+)\s*[-–]\s*(\d+)", str(text).strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def parse_date_dmy(date_str):
    """Convierte 'DD/MM/YYYY' a 'YYYY-MM-DD'."""
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", str(date_str).strip())
    if m:
        return f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
    return date_str


# ══════════════════════════════════════════
#  Extracción de jugadores de una celda HTML
# ══════════════════════════════════════════

def extract_players_from_td(td):
    """
    Extrae la lista de jugadores de una celda 'tdacta'.

    - Individual: 1 enlace con el nombre del jugador + texto con 'Lic:' y 'Rk:'.
    - Dobles:     2 enlaces con los nombres de los jugadores. El número de
                  licencia se obtiene del identificador del enlace, porque
                  estas celdas normalmente no muestran el texto 'Lic:'.

    Devuelve lista de dicts: [{nombre, licencia?, ranking?, id?}, ...]
    """
    if not td:
        return []

    links = td.find_all("a")
    full_text = td.get_text()
    players = []

    for link in links:
        nombre = clean(link.get_text())
        if not nombre:
            continue

        href = link.get("href", "")
        jugador_id = None

        m = re.search(r"jugador=(\d+)", href)
        if m:
            jugador_id = m.group(1)
        else:
            m = re.search(r"#(\d+)#", href)
            if m:
                jugador_id = m.group(1)

        player = {"nombre": nombre}

        if len(links) == 1:
            lic_m = re.search(r"Lic:\s*(\d+)", full_text)
            if lic_m:
                player["licencia"] = lic_m.group(1)
            rk_m = re.search(r"Rk:\s*([\d.]+)", full_text)
            if rk_m:
                player["ranking"] = float(rk_m.group(1))

        # En las celdas de dobles RFETM no aparece "Lic:". El identificador
        # de cada enlace sí corresponde al número de licencia, tanto en
        # `jugador=<licencia>` como en el formato antiguo `#<licencia>#`.
        if jugador_id and "licencia" not in player:
            player["licencia"] = jugador_id

        if jugador_id:
            player["id"] = jugador_id

        players.append(player)

    return players


# ══════════════════════════════════════════
#  Extracción del resultado de juegos (games)
# ══════════════════════════════════════════

def extract_games_score(td):
    """
    Extrae el marcador de juegos de la celda con fuentes de colores.
    Formato HTML: <font color="verde">X</font> - <font color="naranja">Y</font>
    Devuelve (X, Y) o None.
    """
    if not td:
        return None
    fonts = td.find_all("font")
    nums = []
    for font in fonts:
        t = font.get_text().strip()
        if re.match(r"^\d+$", t):
            nums.append(int(t))
    if len(nums) == 2:
        return (nums[0], nums[1])
    return None


# ══════════════════════════════════════════
#  Parser de la tabla interior de encuentros
# ══════════════════════════════════════════

def parse_inner_table(table):
    """
    Parsea la tabla interior (class='table-borderer') de un partido.

    Devuelve dict con:
      equipo_abc, equipo_xyz, encuentros_raw, alineaciones_abc/xyz,
      marcador_abc/xyz, totales
    """
    rows = table.find_all("tr", recursive=False)

    equipo_abc = equipo_xyz = None
    col_map = {}
    alineaciones_abc = {}
    alineaciones_xyz = {}
    encuentros_raw = []
    marcador_abc = 0
    marcador_xyz = 0
    totales = {}

    for row_idx, row in enumerate(rows):
        cells = row.find_all("td", recursive=False)
        if not cells:
            continue

        # ── Fila 0: cabecera — detectar equipos y columnas J1-J5
        if row_idx == 0:
            if len(cells) >= 4:
                equipo_abc = clean(cells[1].get_text())
                equipo_xyz = clean(cells[3].get_text())
            for i, cell in enumerate(cells):
                val = clean(cell.get_text())
                if val:
                    vu = val.upper()
                    if re.match(r"^J[1-5]$", vu):
                        col_map[vu] = i
                    elif vu.startswith("JUEG"):
                        col_map["JUEG"] = i
                    elif vu.startswith("TOT"):
                        col_map["TOT"] = i
            continue

        # ── Detectar fila de totales
        any_text = " ".join(c.get_text() for c in cells)
        if any(kw in any_text for kw in ("Juegos", "Puntos")):
            for cell in cells:
                ct = cell.get_text(separator="\n")
                m = re.search(
                    r"Juegos[^\d]*(\d+)\s*/\s*(\d+)", ct,
                    re.IGNORECASE | re.DOTALL,
                )
                if m:
                    totales["juegos_abc"] = int(m.group(1))
                    totales["juegos_xyz"] = int(m.group(2))
                m = re.search(
                    r"Puntos[^\d]*(\d+)\s*/\s*(\d+)", ct,
                    re.IGNORECASE | re.DOTALL,
                )
                if m:
                    totales["puntos_abc"] = int(m.group(1))
                    totales["puntos_xyz"] = int(m.group(2))
            continue

        # ── Fila de encuentro
        if len(cells) < 6:
            continue

        letra_abc = clean(cells[0].get_text())
        letra_xyz = clean(cells[2].get_text())

        if not letra_abc or not re.match(r"^[A-Z]$", letra_abc):
            continue
        if not letra_xyz or not re.match(r"^[A-Z]$", letra_xyz):
            continue

        players_abc = extract_players_from_td(cells[1])
        players_xyz = extract_players_from_td(cells[3])

        es_dobles = (letra_abc == "D" and letra_xyz == "D") or (
            len(players_abc) > 1 or len(players_xyz) > 1
        )

        # ── Sets J1..J5 — detección dinámica de columnas
        sets_abc_xyz = []
        for j_num in range(1, 6):
            key = f"J{j_num}"
            col_idx = col_map.get(key, 3 + j_num)
            if col_idx >= len(cells):
                break
            score_text = clean(cells[col_idx].get_text())
            if score_text:
                score = parse_score(score_text)
                if score:
                    sets_abc_xyz.append({
                        "set": j_num,
                        "abc": score[0],
                        "xyz": score[1],
                    })

        # ── Resultado de juegos
        j5_col   = int(col_map.get("J5")   or 8)
        jueg_col = int(col_map.get("JUEG") or (j5_col + 1))
        tot_col  = int(col_map.get("TOT")  or (jueg_col + 1))

        games_score = None
        acum_score  = None
        if jueg_col < len(cells):
            games_score = extract_games_score(cells[jueg_col])
        if tot_col < len(cells):
            acum_text = clean(cells[tot_col].get_text())
            acum_score = parse_score(acum_text)

        juegos_abc = juegos_xyz = 0
        if games_score:
            juegos_abc, juegos_xyz = games_score
        else:
            for s in sets_abc_xyz:
                if s["abc"] > s["xyz"]:
                    juegos_abc += 1
                else:
                    juegos_xyz += 1

        if not sets_abc_xyz:
            ganador_abc_xyz = None
            no_disputado = True
        else:
            no_disputado = False
            if juegos_abc > juegos_xyz:
                ganador_abc_xyz = "abc"
                marcador_abc += 1
            elif juegos_xyz > juegos_abc:
                ganador_abc_xyz = "xyz"
                marcador_xyz += 1
            else:
                ganador_abc_xyz = None

        if not es_dobles:
            if players_abc and letra_abc not in alineaciones_abc:
                alineaciones_abc[letra_abc] = players_abc[0]
            if players_xyz and letra_xyz not in alineaciones_xyz:
                alineaciones_xyz[letra_xyz] = players_xyz[0]

        if es_dobles:
            abc_info = {
                "letra": "Db",
                "jugadores": players_abc,
            }
            xyz_info = {
                "letra": "Db",
                "jugadores": players_xyz,
            }
        else:
            abc_info = {
                "letra": letra_abc,
                **(players_abc[0] if players_abc else {}),
            }
            xyz_info = {
                "letra": letra_xyz,
                **(players_xyz[0] if players_xyz else {}),
            }

        enc_raw = {
            "numero": len(encuentros_raw) + 1,
            "tipo": "dobles" if es_dobles else "individual",
            "cruce": f"{letra_abc} vs {letra_xyz}",
            "abc": abc_info,
            "xyz": xyz_info,
            "sets_abc_xyz": sets_abc_xyz,
            "juegos_abc": juegos_abc,
            "juegos_xyz": juegos_xyz,
            "ganador_abc_xyz": ganador_abc_xyz,
            "acum_score": acum_score,
        }
        if no_disputado:
            enc_raw["no_disputado"] = True

        encuentros_raw.append(enc_raw)

    return {
        "equipo_abc": equipo_abc,
        "equipo_xyz": equipo_xyz,
        "encuentros_raw": encuentros_raw,
        "alineaciones_abc": alineaciones_abc,
        "alineaciones_xyz": alineaciones_xyz,
        "marcador_abc": marcador_abc,
        "marcador_xyz": marcador_xyz,
        "totales": totales,
    }


def _map_inner_to_local_visitante(inner_result, equipo_local_nombre):
    """
    Convierte los datos en términos ABC/XYZ a local/visitante.
    """
    equipo_abc = inner_result.get("equipo_abc") or ""

    abc_es_local = True
    if equipo_abc and equipo_local_nombre:
        abc_es_local = equipo_abc.upper() == equipo_local_nombre.upper()

    encuentros_raw = inner_result.get("encuentros_raw", [])
    alin_abc = inner_result.get("alineaciones_abc", {})
    alin_xyz = inner_result.get("alineaciones_xyz", {})
    totales_raw = inner_result.get("totales", {})

    alineaciones = {
        "local":     alin_abc if abc_es_local else alin_xyz,
        "visitante": alin_xyz if abc_es_local else alin_abc,
    }

    totales = {}
    if totales_raw:
        if abc_es_local:
            if "juegos_abc" in totales_raw:
                totales["juegos"] = {
                    "local":     totales_raw["juegos_abc"],
                    "visitante": totales_raw["juegos_xyz"],
                }
            if "puntos_abc" in totales_raw:
                totales["puntos"] = {
                    "local":     totales_raw["puntos_abc"],
                    "visitante": totales_raw["puntos_xyz"],
                }
        else:
            if "juegos_abc" in totales_raw:
                totales["juegos"] = {
                    "local":     totales_raw["juegos_xyz"],
                    "visitante": totales_raw["juegos_abc"],
                }
            if "puntos_abc" in totales_raw:
                totales["puntos"] = {
                    "local":     totales_raw["puntos_xyz"],
                    "visitante": totales_raw["puntos_abc"],
                }

    encuentros = []
    for raw in encuentros_raw:
        abc_info = raw["abc"]
        xyz_info = raw["xyz"]

        if abc_es_local:
            local_info     = abc_info
            visitante_info = xyz_info
            sets_mapped = [
                {"set": s["set"], "local": s["abc"], "visitante": s["xyz"]}
                for s in raw["sets_abc_xyz"]
            ]
            res_juegos = (
                {"local": raw["juegos_abc"], "visitante": raw["juegos_xyz"]}
                if not raw.get("no_disputado") else None
            )
            acum = raw["acum_score"]
            acum_mapped = (
                {"local": acum[0], "visitante": acum[1]} if acum else None
            )
            ganador = (
                "local"     if raw["ganador_abc_xyz"] == "abc" else
                "visitante" if raw["ganador_abc_xyz"] == "xyz" else None
            )
        else:
            local_info     = xyz_info
            visitante_info = abc_info
            sets_mapped = [
                {"set": s["set"], "local": s["xyz"], "visitante": s["abc"]}
                for s in raw["sets_abc_xyz"]
            ]
            res_juegos = (
                {"local": raw["juegos_xyz"], "visitante": raw["juegos_abc"]}
                if not raw.get("no_disputado") else None
            )
            acum = raw["acum_score"]
            acum_mapped = (
                {"local": acum[1], "visitante": acum[0]} if acum else None
            )
            ganador = (
                "local"     if raw["ganador_abc_xyz"] == "xyz" else
                "visitante" if raw["ganador_abc_xyz"] == "abc" else None
            )

        enc = {
            "numero":             raw["numero"],
            "tipo":               raw["tipo"],
            "cruce":              raw["cruce"],
            "local":              local_info,
            "visitante":          visitante_info,
            "sets":               sets_mapped,
            "resultado_juegos":   res_juegos,
            "ganador":            ganador,
            "marcador_acumulado": acum_mapped,
        }
        if raw.get("no_disputado"):
            enc["no_disputado"] = True
            # Añadir motivo si el marcador acumulado está disponible
            if acum_mapped:
                enc["motivo"] = (
                    f"Victoria decidida "
                    f"({acum_mapped['local']}-{acum_mapped['visitante']})"
                )

        encuentros.append(enc)

    dobles = None
    for enc in encuentros:
        if enc["tipo"] == "dobles":
            dobles = {
                "local":     enc["local"].get("jugadores"),
                "visitante": enc["visitante"].get("jugadores"),
            }
            break

    return {
        "abc_es_local":  abc_es_local,
        "encuentros":    encuentros,
        "alineaciones":  alineaciones,
        "dobles":        dobles,
        "totales":       totales or None,
    }


# ══════════════════════════════════════════
#  Parser de la tabla exterior de cada partido
# ══════════════════════════════════════════

def parse_match_outer_table(table):
    """
    Parsea la tabla exterior de un partido.

    Devuelve dict con todos los datos del partido o None si no se puede parsear.
    """
    rows = table.find_all("tr", recursive=False)
    if not rows:
        return None

    # ── Fila 0: cabecera del partido
    header_row = rows[0]
    header_cells = header_row.find_all("td", recursive=False)

    if len(header_cells) < 5:
        return None

    fecha_hora_text = clean(header_cells[0].get_text(separator=" "))
    fecha = hora = None
    if fecha_hora_text:
        m = re.search(r"(\d{1,2}/\d{1,2}/\d{4})\s+(\d{2}:\d{2})", fecha_hora_text)
        if m:
            fecha = parse_date_dmy(m.group(1))
            hora = m.group(2)

    # Equipo local (celda 1)
    equipo_local_td = header_cells[1]
    equipo_local_nombre = clean(equipo_local_td.get_text())
    equipo_local_id = None
    link = equipo_local_td.find("a")
    if link:
        m = re.search(r"equipo=(\d+)", link.get("href", ""))
        if m:
            equipo_local_id = m.group(1)

    # Marcadores (celdas 2 y 3)
    score_local = score_visitante = None
    try:
        score_local = int(clean(header_cells[2].get_text()))
    except (TypeError, ValueError):
        pass
    try:
        score_visitante = int(clean(header_cells[3].get_text()))
    except (TypeError, ValueError):
        pass

    # Equipo visitante (celda 4)
    equipo_visitante_td = header_cells[4]
    equipo_visitante_nombre = clean(equipo_visitante_td.get_text())
    equipo_visitante_id = None
    link = equipo_visitante_td.find("a")
    if link:
        m = re.search(r"equipo=(\d+)", link.get("href", ""))
        if m:
            equipo_visitante_id = m.group(1)

    # Link a la acta PDF (celda 5, opcional)
    link_acta = None
    if len(header_cells) > 5:
        a = header_cells[5].find("a")
        if a:
            link_acta = a.get("href")

    # ── Fila 1: tabla interior + lugar/árbitro
    lugar_raw = None
    arbitro = None
    inner_result = None
    incidencia = None

    if len(rows) > 1:
        inner_td = rows[1].find("td", recursive=False)
        if inner_td:
            borderer = inner_td.find("table")
            if borderer:
                inner_result = parse_inner_table(borderer)

            for font in inner_td.find_all("font"):
                font_text = font.get_text(separator="\n")

                # Incidencia / resolución (p.ej. "Resultado por decisión de la
                # Juez Único. Descalificado XXX." o textos de incomparecencia).
                # Estos partidos suelen no tener tabla de encuentros individual
                # porque la propia acta de la RFETM no la publica.
                if not incidencia:
                    incidencia_m = re.search(
                        r"(resultado por decisi[oó]n|incomparecencia|"
                        r"descalificad[oa]|no\s+presentad|walkover|w\.?o\.?)",
                        font_text,
                        re.IGNORECASE,
                    )
                    if incidencia_m:
                        val = clean(font_text.split("\n")[0])
                        if val:
                            incidencia = val

                m = re.search(
                    r"^(.+?)\s*[-–]\s*(.+?)(?:\n|$)", font_text.strip(), re.MULTILINE
                )
                if m and not lugar_raw:
                    val = clean(font_text.split("\n")[0])
                    if val and not re.match(r"^[-\s()]+$", val):
                        lugar_raw = val

                # Árbitro
                m = re.search(
                    r"[\xc1A]?rbitro:\s*(.+?)(?:\n|$)", font_text, re.IGNORECASE
                )
                if m:
                    val = clean(m.group(1))
                    if val and val.lower() != "sin designar":
                        arbitro = val

    # Parsear lugar: "RECINTO - Ciudad (Provincia)"
    lugar = _parse_lugar(lugar_raw)

    # ── Ganador final del partido
    ganador_final = None
    if score_local is not None and score_visitante is not None:
        if score_local > score_visitante:
            ganador_final = equipo_local_nombre
        elif score_visitante > score_local:
            ganador_final = equipo_visitante_nombre

    abc_es_local = True
    alineaciones = {"local": {}, "visitante": {}}
    dobles       = None
    encuentros   = []
    totales      = None

    if inner_result:
        mapped = _map_inner_to_local_visitante(inner_result, equipo_local_nombre)
        abc_es_local = mapped["abc_es_local"]
        alineaciones = mapped["alineaciones"]
        dobles       = mapped["dobles"]
        encuentros   = mapped["encuentros"]
        totales      = mapped["totales"]

    # Calcular marcador_juegos total
    marcador_juegos = None
    if encuentros:
        total_local = total_visitante = 0
        for enc in encuentros:
            rj = enc.get("resultado_juegos")
            if rj:
                total_local += rj.get("local", 0)
                total_visitante += rj.get("visitante", 0)
        marcador_juegos = {"local": total_local, "visitante": total_visitante}

    return {
        "fecha":  fecha,
        "hora":   hora,
        "lugar":  lugar,
        "equipos": {
            "local": {
                "nombre":    equipo_local_nombre,
                "id":        equipo_local_id,
                "delegado":  None,
                "entrenador": None,
            },
            "visitante": {
                "nombre":    equipo_visitante_nombre,
                "id":        equipo_visitante_id,
                "delegado":  None,
                "entrenador": None,
            },
        },
        "abc_es_local": abc_es_local,
        "link_acta":    link_acta,
        "arbitros": {
            "principal": {"nombre": arbitro, "licencia": None} if arbitro else None,
            "asistente": None,
        },
        "alineaciones": alineaciones,
        "dobles":        dobles,
        "partidos":      encuentros,
        "totales":       totales,
        "incidencia":    incidencia,
        "resultado_final": {
            "ganador": ganador_final,
            "marcador_partidos": {
                "local":     score_local,
                "visitante": score_visitante,
            },
            "marcador_juegos": marcador_juegos,
        },
    }


def _parse_lugar(lugar_raw):
    """
    Parsea la cadena de texto del lugar de celebración.
    Formato esperado: "NOMBRE RECINTO - Ciudad (Provincia)"
    Devuelve dict {recinto, ciudad} o None si no se puede parsear.
    """
    if not lugar_raw:
        return None
    # Buscar separador " - " entre recinto y ciudad
    m = re.match(r"^(.+?)\s*-\s*(.+)$", lugar_raw)
    if m:
        recinto = clean(m.group(1))
        ciudad  = clean(m.group(2))
        return {"recinto": recinto, "ciudad": ciudad}
    return {"recinto": lugar_raw, "ciudad": None}


# ══════════════════════════════════════════
#  Extracción de metadatos de la página HTML
# ══════════════════════════════════════════

def extract_page_metadata(soup, season_slug, category_slug, jornada, sex_slug):
    """
    Extrae los metadatos de página: temporada, competición y jornada.
    Se intenta leer del HTML cuando es posible; si no, se deriva de la ruta.
    """
    # Temporada: leer del HTML o derivar del slug
    temporada = None
    for tag in soup.find_all(["h4", "h5", "p"]):
        t = clean(tag.get_text())
        if t:
            m = re.match(r"Temporada\s+(\d{4}/\d{4})", t, re.IGNORECASE)
            if m:
                temporada = m.group(1)
                break

    if not temporada:
        # Convertir "2024-2025" → "2024/2025"
        temporada = season_slug.replace("-", "/", 1)

    # Competición: leer del encabezado h3/h4 o derivar del slug
    competicion = None
    for tag in soup.find_all(["h3", "h4"]):
        t = clean(tag.get_text())
        if not t:
            continue
        # Ejemplo: "DIVISIÓN DE HONOR FEMENINA Grupo 1 - Temporada 2019/2020"
        # Eliminar la parte de temporada
        t_clean = re.sub(r"\s*-?\s*Temporada\s+\d{4}/\d{4}", "", t, flags=re.IGNORECASE).strip()
        # Quitar "Grupo N"
        t_clean = re.sub(r"\s+Grupo\s+\d+", "", t_clean, flags=re.IGNORECASE).strip()
        if len(t_clean) > 5 and not t_clean.startswith("Result"):
            competicion = t_clean.title()
            break

    if not competicion:
        cat_name = CATEGORY_NAME.get(category_slug, category_slug.replace("-", " ").title())
        sex_name = SEX_LABEL.get(sex_slug, sex_slug.title())
        competicion = f"{cat_name} {sex_name}"

    # Jornada desde la navegación de jornadas
    jornada_num = int(jornada) if jornada.isdigit() else 0
    for tag in soup.find_all("a", class_="link_white"):
        t = clean(tag.get_text())
        if t:
            m = re.search(r"Jornada\s+(\d+)", t, re.IGNORECASE)
            if m:
                jornada_num = int(m.group(1))
                break
            # A veces solo aparece el número de la jornada
            if re.match(r"^\d+$", t):
                jornada_num = int(t)
                break

    return temporada, competicion, jornada_num


# ══════════════════════════════════════════
#  Generación del ID de partido
# ══════════════════════════════════════════

def match_id_from(partido, idx):
    """
    Genera un ID para el partido a partir de los IDs de equipos o del índice.
    Formato: "{local_id}_{visitante_id}" o "match_{idx:04d}"
    """
    local_id     = partido["equipos"]["local"].get("id")
    visitante_id = partido["equipos"]["visitante"].get("id")
    if local_id and visitante_id:
        return f"{local_id}_{visitante_id}"
    return f"match_{idx:04d}"


# ══════════════════════════════════════════
#  Parser de un archivo HTML completo
# ══════════════════════════════════════════

def parse_html_file(html_path: Path):
    """
    Lee y parsea un archivo HTML de la carpeta web-downloader.

    Devuelve lista de dicts, uno por partido, listos para serializar a JSON.
    Retorna lista vacía si el archivo no contiene partidos válidos.

    La ruta esperada es:
      resources/web-downloader/<season>/<category>/<jornada>/<sex>/grupo_<N>.html
    """
    # Extraer metadatos de la ruta
    parts = html_path.relative_to(WEB_DOWNLOADER_DIR).parts
    if len(parts) < 5:
        logger.warning(f"Ruta inesperada (faltan segmentos): {html_path}")
        return []

    season_slug   = parts[0]   # e.g. "2024-2025"
    category_slug = parts[1]   # e.g. "divisio-honor"
    jornada_slug  = parts[2]   # e.g. "1"
    sex_slug      = parts[3]   # e.g. "femenino"
    grupo_file    = parts[4]   # e.g. "grupo_1.html"

    # Número de grupo desde el nombre del archivo
    grupo_m = re.match(r"grupo_(\d+)\.html?$", grupo_file, re.IGNORECASE)
    grupo_num = int(grupo_m.group(1)) if grupo_m else 0

    # Leer el HTML
    try:
        content = html_path.read_bytes()
        # Intentar detectar el encoding: ISO-8859-1 es común en webs RFETM antiguas
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("iso-8859-1", errors="replace")
        soup = BeautifulSoup(text, "html.parser")
    except Exception as e:
        logger.error(f"Error leyendo {html_path}: {e}")
        return []

    # Metadatos de página
    temporada, competicion, jornada_num = extract_page_metadata(
        soup, season_slug, category_slug, jornada_slug, sex_slug
    )

    # Localizar tablas de partido
    partidos = []
    for table in soup.select("table.table.table-sm"):
        style = table.get("style", "")
        if "border: #F1F1F0" not in style:
            continue
        partido = parse_match_outer_table(table)
        if not partido:
            continue

        # Añadir metadatos de la página al partido
        partido["federacion"]  = "Real Federación Española de Tenis de Mesa"
        partido["temporada"]   = temporada
        partido["competicion"] = competicion
        partido["grupo"]       = grupo_num
        partido["jornada"]     = jornada_num
        partido["acta_protestada"] = False

        # Eliminar campos internos no necesarios en el JSON final
        partido.pop("link_acta", None)
        partido.pop("totales", None)
        # "incidencia" solo se conserva cuando aporta información real, para
        # no ensuciar con `null` las actas normales que sí tienen encuentros.
        if not partido.get("incidencia"):
            partido.pop("incidencia", None)

        partidos.append(partido)

    return partidos, season_slug, category_slug, jornada_slug, sex_slug


# ══════════════════════════════════════════
#  Escritura de JSON
# ══════════════════════════════════════════

def save_partido_json(partido, season_slug, category_slug, jornada_slug,
                      sex_slug, match_id, force=False):
    """
    Guarda un partido como archivo JSON en la carpeta de salida correspondiente.
    Devuelve True si se escribió, False si se saltó (ya existía).
    """
    out_dir = (
        ACTAS_JSON_DIR
        / season_slug
        / category_slug
        / jornada_slug
        / sex_slug
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"acta_{match_id}.json"

    if out_file.exists() and not force:
        logger.debug(f"  Saltando (ya existe): {out_file.name}")
        return False

    # Ordenar campos del JSON para mayor legibilidad
    ordered = _order_partido_fields(partido)

    out_file.write_text(
        json.dumps(ordered, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return True


def _order_partido_fields(partido):
    """
    Devuelve el partido con los campos en el orden canónico del acta JSON.
    """
    field_order = [
        "federacion", "temporada", "competicion", "grupo", "jornada",
        "fecha", "hora", "lugar", "equipos", "abc_es_local", "arbitros",
        "alineaciones", "dobles", "partidos", "incidencia", "resultado_final",
        "acta_protestada",
    ]
    ordered = {}
    for key in field_order:
        if key in partido:
            ordered[key] = partido[key]
    # Añadir campos extra no contemplados en el orden
    for key, val in partido.items():
        if key not in ordered:
            ordered[key] = val
    return ordered


# ══════════════════════════════════════════
#  Proceso principal
# ══════════════════════════════════════════

def process_all(season_filter=None, category_filter=None, force=False):
    """
    Recorre todos los archivos HTML en WEB_DOWNLOADER_DIR y los convierte a JSON.
    """
    if not WEB_DOWNLOADER_DIR.exists():
        logger.error(f"Directorio no encontrado: {WEB_DOWNLOADER_DIR}")
        sys.exit(1)

    html_files = sorted(WEB_DOWNLOADER_DIR.rglob("*.html"))

    if season_filter:
        html_files = [f for f in html_files if f.parts[
            len(WEB_DOWNLOADER_DIR.parts)] == season_filter]
    if category_filter:
        html_files = [f for f in html_files if f.parts[
            len(WEB_DOWNLOADER_DIR.parts) + 1] == category_filter]

    total_files    = len(html_files)
    total_partidos = 0
    total_written  = 0
    total_skipped  = 0
    total_errors   = 0

    logger.info(f"Archivos HTML encontrados: {total_files}")

    for idx, html_path in enumerate(html_files, 1):
        rel = html_path.relative_to(WEB_DOWNLOADER_DIR)
        logger.info(f"[{idx}/{total_files}] {rel}")

        try:
            result = parse_html_file(html_path)
            if not result:
                continue
            partidos, season_slug, category_slug, jornada_slug, sex_slug = result
        except Exception as e:
            logger.error(f"  Error parseando {html_path.name}: {e}", exc_info=True)
            total_errors += 1
            continue

        if not partidos:
            logger.debug(f"  Sin partidos en {html_path.name}")
            continue

        for match_idx, partido in enumerate(partidos, 1):
            mid = match_id_from(partido, match_idx)
            try:
                written = save_partido_json(
                    partido, season_slug, category_slug,
                    jornada_slug, sex_slug, mid, force=force
                )
                total_partidos += 1
                if written:
                    total_written += 1
                    logger.debug(f"  ✓ acta_{mid}.json")
                else:
                    total_skipped += 1
            except Exception as e:
                logger.error(f"  Error guardando partido {mid}: {e}", exc_info=True)
                total_errors += 1

    logger.info("=" * 60)
    logger.info(f"Archivos HTML procesados : {total_files}")
    logger.info(f"Partidos encontrados     : {total_partidos}")
    logger.info(f"Archivos JSON escritos   : {total_written}")
    logger.info(f"Archivos JSON saltados   : {total_skipped}")
    logger.info(f"Errores                  : {total_errors}")


# ══════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(
        description=(
            "Convierte actas HTML descargadas de RFETM a archivos JSON "
            "individuales por partido."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Procesar todos los HTML
  python convert-html-actas-to-json.py

  # Solo la temporada 2024-2025
  python convert-html-actas-to-json.py --season 2024-2025

  # Solo división de honor en 2024-2025
  python convert-html-actas-to-json.py --season 2024-2025 --category divisio-honor

  # Forzar sobreescritura
  python convert-html-actas-to-json.py --force

  # Ver más detalle
  python convert-html-actas-to-json.py --verbose
        """,
    )
    ap.add_argument(
        "--season",
        help="Filtrar por temporada (e.g. 2024-2025)",
    )
    ap.add_argument(
        "--category",
        help="Filtrar por categoría (e.g. divisio-honor, super-divisio)",
    )
    ap.add_argument(
        "--force",
        action="store_true",
        help="Sobreescribir archivos JSON ya existentes",
    )
    ap.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Mostrar más detalle en el log",
    )

    args = ap.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    process_all(
        season_filter=args.season,
        category_filter=args.category,
        force=args.force,
    )


if __name__ == "__main__":
    main()

