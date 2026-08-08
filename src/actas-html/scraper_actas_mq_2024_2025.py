#!/usr/bin/env python3
"""
scraper_actas_mq_2024_2025.py

Extrae las actas de partidos de la RFETM desde la página web y las convierte a JSON.

Compatible con cualquier categoría y jornada de la temporada 2024-2025.
URL base: https://www.rfetm.es/public/resultados/2024-2025/view.php

Características:
  - Detección dinámica de columnas: J1-J5 (y JUEG/TOT si existen) se localizan
    leyendo el header de la tabla interior en lugar de asumir posiciones fijas.
  - Soporte de dobles (Db): los dos jugadores de cada pareja se guardan como
    lista en el campo "jugadores"; el campo "tipo" distingue "individual"/"dobles".
  - ABC no siempre es local: el nombre del equipo ABC (col 1 del header de la
    tabla interior) se compara con el equipo local del acta (header exterior) para
    determinar abc_es_local. Sets, juegos y marcadores se mapean a local/visitante
    en consecuencia. El campo abc_es_local queda en el JSON para trazabilidad.

Uso:
  # Superdivisión Masculina, jornada 1 (valores por defecto)
  python scraper_actas_mq_2024_2025.py

  # Jornada 3, guardar en archivo
  python scraper_actas_mq_2024_2025.py --jornada 3 -o jornada3.json

  # División de Honor Masculina Grupo 1, jornada 5
  python scraper_actas_mq_2024_2025.py --liga Mg== --grupo 1 --jornada 5

  # URL directa
  python scraper_actas_mq_2024_2025.py --url "https://www.rfetm.es/public/resultados/2024-2025/view.php?liga=MQ==&grupo=0&subgrupo=S&jornada=1&sexo=M"
"""

import json
import re
import sys
import argparse
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup


# ══════════════════════════════════════════
#  Constantes
# ══════════════════════════════════════════

BASE_URL = "https://www.rfetm.es/public/resultados/{temporada}/view.php"


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
    - Dobles:     2 enlaces con los nombres de los jugadores (sin Lic/Rk).

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

        # Individual: href contiene jugador=XXXX
        m = re.search(r"jugador=(\d+)", href)
        if m:
            jugador_id = m.group(1)
        else:
            # Dobles: segundo jugador con href="#XXXX#"
            m = re.search(r"#(\d+)#", href)
            if m:
                jugador_id = m.group(1)

        player = {"nombre": nombre}

        # Licencia y ranking solo en individuales (1 link por celda)
        if len(links) == 1:
            lic_m = re.search(r"Lic:\s*(\d+)", full_text)
            if lic_m:
                player["licencia"] = lic_m.group(1)
            rk_m = re.search(r"Rk:\s*([\d.]+)", full_text)
            if rk_m:
                player["ranking"] = float(rk_m.group(1))

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

    Los datos se devuelven en términos de ABC/XYZ; la conversión a
    local/visitante la realiza parse_match_outer_table al conocer qué
    equipo es el local.

    Mejoras respecto a la versión anterior:
      - Detección dinámica de columnas J1-J5 desde la fila de cabecera
        (evita asumir posiciones fijas que pueden variar según la categoría).
      - Soporte de dobles (Db): los dos jugadores de cada pareja se guardan
        como lista en "jugadores" y el tipo distingue "individual" / "dobles".
      - Los sets se almacenan como {set, abc, xyz} para que la función
        llamante pueda invertirlos si ABC es el visitante.

    Devuelve dict con:
      equipo_abc        nombre del equipo ABC (col 1 del header de la tabla)
      equipo_xyz        nombre del equipo XYZ (col 3 del header de la tabla)
      encuentros_raw    lista de dicts en términos ABC/XYZ
      alineaciones_abc  {letra: player_info}
      alineaciones_xyz  {letra: player_info}
      marcador_abc      partidos ganados por ABC
      marcador_xyz      partidos ganados por XYZ
      totales           dict con alineacion_abc/xyz, juegos_abc/xyz, puntos_abc/xyz
    """
    rows = table.find_all("tr", recursive=False)

    equipo_abc = equipo_xyz = None
    # col_map: {J1..J5, JUEG, TOT} -> índice de columna (detección dinámica)
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

        # ── Fila 0: cabecera — detectar equipos y columnas J1-J5 ─────
        if row_idx == 0:
            if len(cells) >= 4:
                equipo_abc = clean(cells[1].get_text())
                equipo_xyz = clean(cells[3].get_text())
            # Detección dinámica: leer cada celda del header para localizar
            # J1-J5 (y JUEG / TOT si los hay, como en algunos PDFs)
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

        # ── Detectar fila de totales ──────────────────────────────────
        any_text = " ".join(c.get_text() for c in cells)
        if any(kw in any_text for kw in ("Alineaci", "Juegos", "Puntos")):
            for cell in cells:
                ct = cell.get_text(separator="\n")
                m = re.search(
                    r"Alineaci[oó]n\s+ABC[^\d]*([\d.]+)", ct,
                    re.IGNORECASE | re.DOTALL,
                )
                if m:
                    try:
                        totales["alineacion_abc"] = float(m.group(1))
                    except ValueError:
                        pass
                m = re.search(
                    r"Alineaci[oó]n\s+XYZ[^\d]*([\d.]+)", ct,
                    re.IGNORECASE | re.DOTALL,
                )
                if m:
                    try:
                        totales["alineacion_xyz"] = float(m.group(1))
                    except ValueError:
                        pass
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

        # ── Fila de encuentro ─────────────────────────────────────────
        if len(cells) < 6:
            continue

        letra_abc = clean(cells[0].get_text())
        letra_xyz = clean(cells[2].get_text())

        # Solo procesar letras válidas (A-Z única)
        if not letra_abc or not re.match(r"^[A-Z]$", letra_abc):
            continue
        if not letra_xyz or not re.match(r"^[A-Z]$", letra_xyz):
            continue

        players_abc = extract_players_from_td(cells[1])
        players_xyz = extract_players_from_td(cells[3])

        # Detectar dobles: letra D en ambos lados o más de 1 jugador por celda
        es_dobles = (letra_abc == "D" and letra_xyz == "D") or (
            len(players_abc) > 1 or len(players_xyz) > 1
        )

        # ── Sets J1..J5 — detección dinámica de columnas ──────────────
        # Usar col_map construido desde el header; fallback a posiciones
        # fijas (J1=col4, J2=col5, …) si el header no las indicó.
        sets_abc_xyz = []
        for j_num in range(1, 6):
            key = f"J{j_num}"
            col_idx = col_map.get(key, 3 + j_num)  # fallback: 4, 5, 6, 7, 8
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

        # ── Resultado de juegos (celda con fonts de colores) ─────────
        # Columna JUEG si la detectamos dinámicamente, o J5+1 como fallback
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

        # Calcular desde sets si no hay marcador explícito de juegos
        juegos_abc = juegos_xyz = 0
        if games_score:
            juegos_abc, juegos_xyz = games_score
        else:
            for s in sets_abc_xyz:
                if s["abc"] > s["xyz"]:
                    juegos_abc += 1
                else:
                    juegos_xyz += 1

        # ── Ganador del encuentro (en términos ABC/XYZ) ───────────────
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

        # ── Registrar alineaciones (solo individuales, primera aparición)
        if not es_dobles:
            if players_abc and letra_abc not in alineaciones_abc:
                alineaciones_abc[letra_abc] = players_abc[0]
            if players_xyz and letra_xyz not in alineaciones_xyz:
                alineaciones_xyz[letra_xyz] = players_xyz[0]

        # ── Construir encuentro crudo (en términos ABC/XYZ) ───────────
        # Los dobles se almacenan con letra "Db" y lista de jugadores,
        # igual que en el parser de PDF (field tipo = "dobles").
        if es_dobles:
            abc_info = {
                "letra": "Db",
                "jugadores": [p["nombre"] for p in players_abc],
            }
            xyz_info = {
                "letra": "Db",
                "jugadores": [p["nombre"] for p in players_xyz],
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
            # Datos en términos ABC/XYZ — se mapean a local/visitante fuera
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

    Determina abc_es_local comparando el nombre del equipo ABC (col 1 del
    header de la tabla interior) con el equipo local del acta (header exterior).
    El campo abc_es_local queda registrado en el resultado para trazabilidad.

    Devuelve dict con:
      abc_es_local, encuentros, alineaciones (local/visitante), dobles, totales
    """
    equipo_abc = inner_result.get("equipo_abc") or ""
    equipo_xyz = inner_result.get("equipo_xyz") or ""

    # ABC no siempre es local: comparar nombre con el equipo local real
    abc_es_local = True
    if equipo_abc and equipo_local_nombre:
        abc_es_local = equipo_abc.upper() == equipo_local_nombre.upper()

    encuentros_raw = inner_result.get("encuentros_raw", [])
    alin_abc = inner_result.get("alineaciones_abc", {})
    alin_xyz = inner_result.get("alineaciones_xyz", {})
    totales_raw = inner_result.get("totales", {})

    # ── Mapear alineaciones ───────────────────────────────────────────
    alineaciones = {
        "local":     alin_abc if abc_es_local else alin_xyz,
        "visitante": alin_xyz if abc_es_local else alin_abc,
    }

    # ── Mapear totales ────────────────────────────────────────────────
    totales = {}
    if totales_raw:
        if abc_es_local:
            totales["alineacion_local"]     = totales_raw.get("alineacion_abc")
            totales["alineacion_visitante"] = totales_raw.get("alineacion_xyz")
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
            totales["alineacion_local"]     = totales_raw.get("alineacion_xyz")
            totales["alineacion_visitante"] = totales_raw.get("alineacion_abc")
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

    # ── Mapear encuentros ─────────────────────────────────────────────
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
            "marcador_acumulado": acum_mapped,
            "ganador":            ganador,
        }
        if raw.get("no_disputado"):
            enc["no_disputado"] = True

        encuentros.append(enc)

    # ── Dobles ────────────────────────────────────────────────────────
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

    Identidad: class='table table-sm', style contiene 'border: #F1F1F0'.

    Estructura del tr de cabecera (6 celdas, la primera con colspan=2):
      [fecha/hora] | [equipo_local] | [score_local] | [score_visitante]
                   | [equipo_visitante] | [link_acta]

    El segundo tr contiene un único td con:
      - tabla interna de encuentros (class='table-borderer')
      - font con "Lugar:" y "Árbitro:"

    Devuelve dict con todos los datos del partido o None si no se puede parsear.
    El campo abc_es_local queda registrado para trazabilidad.
    """
    rows = table.find_all("tr", recursive=False)
    if not rows:
        return None

    # ── Fila 0: cabecera del partido ──────────────────────────────────
    header_row = rows[0]
    header_cells = header_row.find_all("td", recursive=False)

    if len(header_cells) < 5:
        return None

    # Fecha y hora (primera celda, puede tener colspan=2)
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

    # ── Fila 1: tabla interior + lugar/árbitro ────────────────────────
    lugar = None
    arbitro = None
    inner_result = None

    if len(rows) > 1:
        inner_td = rows[1].find("td", recursive=False)
        if inner_td:
            # Tabla de encuentros
            borderer = inner_td.find("table")
            if borderer:
                inner_result = parse_inner_table(borderer)

            # Lugar y árbitro en el tag <font> anidado
            for font in inner_td.find_all("font"):
                font_text = font.get_text(separator="\n")

                m = re.search(
                    r"Lugar:\s*(.+?)(?:\n|$)", font_text, re.IGNORECASE
                )
                if m:
                    val = clean(m.group(1))
                    # Ignorar valores vacíos del tipo "- ()"
                    if val and not re.match(r"^[-\s()]+$", val):
                        lugar = val

                # Árbitro: la Á puede aparecer como \xc1 por encoding
                m = re.search(
                    r"[\xc1A]?rbitro:\s*(.+?)(?:\n|$)", font_text, re.IGNORECASE
                )
                if m:
                    val = clean(m.group(1))
                    if val and val.lower() != "sin designar":
                        arbitro = val

    # ── Ganador final del partido ─────────────────────────────────────
    ganador_final = None
    if score_local is not None and score_visitante is not None:
        if score_local > score_visitante:
            ganador_final = equipo_local_nombre
        elif score_visitante > score_local:
            ganador_final = equipo_visitante_nombre

    # ── Mapear ABC/XYZ → local/visitante usando el nombre del equipo local
    abc_es_local = True   # valor por defecto si no hay tabla interior
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

    return {
        "fecha":  fecha,
        "hora":   hora,
        "equipos": {
            "local": {
                "nombre": equipo_local_nombre,
                "id":     equipo_local_id,
            },
            "visitante": {
                "nombre": equipo_visitante_nombre,
                "id":     equipo_visitante_id,
            },
        },
        "abc_es_local": abc_es_local,
        "link_acta":    link_acta,
        "lugar":        lugar,
        "arbitros": {
            "principal": arbitro,
            "asistente": None,
        },
        "alineaciones": alineaciones,
        "dobles":        dobles,
        "partidos":      encuentros,
        "totales":       totales,
        "resultado_final": {
            "ganador": ganador_final,
            "marcador_partidos": {
                "local":     score_local,
                "visitante": score_visitante,
            },
        },
    }


# ══════════════════════════════════════════
#  Scraper principal de la página
# ══════════════════════════════════════════

def scrape_page(url):
    """
    Descarga y parsea una página de resultados de la RFETM.
    Devuelve un dict con la información completa de la jornada.

    El dict incluye:
      federacion, temporada, competicion, liga, grupo, sexo, jornada, url
      partidos: lista de dicts, uno por partido de la jornada
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=30)
    # El servidor RFETM devuelve HTTP 500 incluso cuando el contenido es válido.
    # Solo lanzar excepción en errores de cliente (4xx) o errores graves de red.
    if response.status_code >= 400 and response.status_code != 500:
        response.raise_for_status()

    soup = BeautifulSoup(response.content, "html.parser")

    # ── Temporada (enlace "Temporada YYYY/YYYY" en el breadcrumb) ──
    temporada = None
    for a in soup.find_all("a"):
        m = re.match(
            r"Temporada\s+(\d{4}/\d{4})", a.get_text().strip(), re.IGNORECASE
        )
        if m:
            temporada = m.group(1)
            break

    # ── Parámetros de la URL ──
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    liga = params.get("liga", [""])[0]
    grupo = int(params.get("grupo", [0])[0])
    sexo = params.get("sexo", [""])[0]
    jornada = int(params.get("jornada", [0])[0])

    # ── Jornada (encabezado de la sección de resultados) ──
    for t in soup.find_all("table"):
        thead = t.find("thead")
        if thead:
            link = thead.find("a", class_="link_white")
            if link:
                m = re.search(r"Jornada\s+(\d+)", link.get_text(), re.IGNORECASE)
                if m:
                    jornada = int(m.group(1))
                    break

    # ── Competición (desde el menú de navegación desplegable) ──
    competicion = None
    for a in soup.find_all("a", class_="dropdown-item"):
        href = a.get("href", "")
        if (
            f"liga={liga}" in href
            and f"grupo={grupo}" in href
            and f"sexo={sexo}" in href
            and "jornada=0" in href
        ):
            text = clean(a.get_text())
            if text:
                competicion = text
                break

    # ── Tabla de clasificación (standings) ──
    clasificacion = []
    for t in soup.find_all("table"):
        classes = t.get("class", [])
        if "table-striped" in classes and "table-hover" in classes:
            tbody = t.find("tbody")
            if not tbody:
                continue
            for tr in tbody.find_all("tr"):
                tds = tr.find_all("td")
                if len(tds) < 9:
                    continue
                try:
                    pos_text = clean(tds[0].get_text())
                    equipo_link = tds[1].find("a")
                    equipo_nombre = clean(tds[1].get_text())
                    equipo_id = None
                    if equipo_link:
                        m = re.search(r"eqdat=(\d+)", equipo_link.get("href", ""))
                        if m:
                            equipo_id = m.group(1)
                    pj = int(clean(tds[2].get_text()) or 0)
                    pg = int(clean(tds[3].get_text()) or 0)
                    pe = int(clean(tds[4].get_text()) or 0)
                    pp = int(clean(tds[5].get_text()) or 0)
                    pf = int(clean(tds[6].get_text()) or 0)
                    pc = int(clean(tds[7].get_text()) or 0)
                    ptos_text = clean(tds[8].get_text())
                    ptos = None
                    if ptos_text:
                        try:
                            ptos = int(re.search(r"-?\d+", ptos_text).group())
                        except (AttributeError, ValueError):
                            pass
                    clasificacion.append({
                        "posicion": pos_text,
                        "equipo": equipo_nombre,
                        "equipo_id": equipo_id,
                        "PJ": pj,
                        "PG": pg,
                        "PE": pe,
                        "PP": pp,
                        "PF": pf,
                        "PC": pc,
                        "PTOS": ptos,
                    })
                except (IndexError, ValueError):
                    continue
            break  # Solo procesar la primera tabla de clasificación

    # ── Partidos de la jornada ──
    partidos = []
    for table in soup.select("table.table.table-sm"):
        style = table.get("style", "")
        if "border: #F1F1F0" not in style:
            continue
        partido = parse_match_outer_table(table)
        if partido:
            partidos.append(partido)

    return {
        "federacion": "Real Federación Española de Tenis de Mesa",
        "temporada": temporada,
        "competicion": competicion,
        "liga": liga,
        "grupo": grupo,
        "sexo": sexo,
        "jornada": jornada,
        "url": url,
        "clasificacion": clasificacion,
        "partidos": partidos,
    }


# ══════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════

def build_url(temporada, liga, grupo, subgrupo, jornada, sexo):
    """Construye la URL de la página de resultados de la RFETM."""
    base = BASE_URL.format(temporada=temporada)
    # Nota: liga contiene '=' (base64) que NO deben codificarse como %3D
    query = (
        f"liga={liga}"
        f"&grupo={grupo}"
        f"&subgrupo={subgrupo}"
        f"&jornada={jornada}"
        f"&sexo={sexo}"
    )
    return f"{base}?{query}"


def main():
    ap = argparse.ArgumentParser(
        description="Extrae actas de la web RFETM y las convierte a JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  # Superdivisión Masculina 2024-2025, Jornada 1 (por defecto)
  python scraper_actas_mq_2024_2025.py

  # Jornada 3, guardar en archivo
  python scraper_actas_mq_2024_2025.py --jornada 3 -o jornada3.json

  # División de Honor Masculina Grupo 1, Jornada 5
  python scraper_actas_mq_2024_2025.py --liga Mg== --grupo 1 --jornada 5 --sexo M

  # URL directa (ignora todos los parámetros de construcción de URL)
  python scraper_actas_mq_2024_2025.py --url "https://www.rfetm.es/public/resultados/2024-2025/view.php?liga=MQ==&grupo=0&subgrupo=S&jornada=1&sexo=M"
        """,
    )
    ap.add_argument(
        "--url",
        help="URL directa de la página (ignora los demás parámetros de URL)",
    )
    ap.add_argument(
        "--temporada",
        default="2024-2025",
        help="Temporada en formato YYYY-YYYY (por defecto: 2024-2025)",
    )
    ap.add_argument(
        "--liga",
        default="MQ==",
        help="Código de liga en base64 (por defecto: MQ== = Superdivisión)",
    )
    ap.add_argument(
        "--grupo",
        type=int,
        default=0,
        help="Número de grupo (por defecto: 0)",
    )
    ap.add_argument(
        "--subgrupo",
        default="S",
        help="Subgrupo (por defecto: S)",
    )
    ap.add_argument(
        "--jornada",
        type=int,
        default=1,
        help="Número de jornada (por defecto: 1)",
    )
    ap.add_argument(
        "--sexo",
        default="M",
        choices=["M", "F"],
        help="M (masculino) o F (femenino) (por defecto: M)",
    )
    ap.add_argument(
        "-o", "--output",
        help="Archivo JSON de salida (por defecto: escribe en stdout)",
    )
    ap.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indentación del JSON de salida (por defecto: 2)",
    )

    args = ap.parse_args()

    url = args.url if args.url else build_url(
        args.temporada, args.liga, args.grupo,
        args.subgrupo, args.jornada, args.sexo,
    )

    print(f"Scrapeando: {url}", file=sys.stderr)
    data = scrape_page(url)

    json_str = json.dumps(data, ensure_ascii=False, indent=args.indent)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"JSON guardado en: {args.output}", file=sys.stderr)
    else:
        print(json_str)

    return data


if __name__ == "__main__":
    main()





