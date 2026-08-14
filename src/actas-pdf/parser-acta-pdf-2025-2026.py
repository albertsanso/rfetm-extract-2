
import json
import re
import sys
import argparse
import pdfplumber


# ══════════════════════════════════════════
#  Utilidades
# ══════════════════════════════════════════

def clean(text):
    """Elimina espacios extra y devuelve None si está vacío."""
    if text is None:
        return None
    t = " ".join(str(text).split()).strip()
    return t if t else None


def parse_score(cell):
    """Convierte '11 - 8' en (11, 8)."""
    if not cell:
        return None
    m = re.match(r"(\d+)\s*-\s*(\d+)", str(cell).strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def extract_player(text):
    """Extrae nombre y licencia de 'APELLIDO, NOMBRE (12345)'."""
    if not text:
        return None
    text = clean(text)
    if not text:
        return None
    m = re.match(r"(.+?)\s*\((\d+)\)", text)
    if m:
        return {"nombre": m.group(1).strip(), "licencia": m.group(2)}
    return None


def extract_players(cell):
    """
    Extrae uno o varios jugadores de una celda.
    - Individual: 'APELLIDO, NOMBRE (12345)' → [dict]
    - Dobles: 'JUGADOR1 (111)\nJUGADOR2 (222)' → [dict, dict]
    Devuelve lista de dicts o lista vacía.
    """
    if not cell:
        return []
    lines = str(cell).split("\n")
    players = []
    for line in lines:
        p = extract_player(line)
        if p:
            players.append(p)
    return players


def extract_person_from_line(line, role_prefix):
    """
    Extrae nombre y licencia de un rol (Delegado/Entrenador) en una línea.
    Busca 'role_prefix: NOMBRE Lic: XXXX' devolviendo dict o None.
    """
    # Con licencia
    m = re.search(
        rf"{role_prefix}:\s+(.+?)\s+Lic:\s+(\d+)",
        line
    )
    if m:
        nombre = clean(m.group(1))
        if nombre:
            return {"nombre": nombre, "licencia": m.group(2)}

    # Sin licencia: capturar hasta el siguiente campo conocido o fin
    m = re.search(
        rf"{role_prefix}:\s+(.+?)(?:\s+Lic:|\s+Delegado|\s+Entrenador|$)",
        line
    )
    if m:
        nombre = clean(m.group(1))
        # Filtrar capturas vacías o que son solo "Lic:"
        if nombre and nombre not in ("Lic:", ""):
            return {"nombre": nombre, "licencia": None}

    return None


# ══════════════════════════════════════════
#  Detección dinámica de columnas de sets
# ══════════════════════════════════════════

def detect_set_columns(header_row):
    """
    Dado el header de la tabla de partidos, detecta los índices
    de las columnas J1-J5, JUEG y TOT.
    Devuelve dict con claves 'J1'..'J5', 'JUEG', 'TOT'.
    """
    cols = {}
    for i, cell in enumerate(header_row):
        if not cell:
            continue
        val = str(cell).strip().upper()
        if val in ("J1", "J2", "J3", "J4", "J5"):
            cols[val] = i
        elif val.startswith("JUEG"):
            cols["JUEG"] = i
        elif val.startswith("TOT"):
            cols["TOT"] = i
    return cols


# ══════════════════════════════════════════
#  Parser principal
# ══════════════════════════════════════════

def parse_acta(pdf_path):
    """Lee un PDF de acta RFETM y devuelve un dict con toda la información."""

    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        tables = page.extract_tables()

    if not tables:
        raise ValueError("No se encontraron tablas en el PDF")

    table = tables[0]

    # ── Reconstruir líneas de cabecera ──
    # pdfplumber separa la primera letra en col[0] y el resto en col[1]
    header_lines = []
    for row in table:
        if not row:
            continue
        col0 = str(row[0]) if row[0] else ""
        col1 = str(row[1]) if row[1] else ""
        if "\n" in col0 and col1 and "\n" in col1:
            parts0 = col0.split("\n")
            parts1 = col1.split("\n")
            for p0, p1 in zip(parts0, parts1):
                header_lines.append(p0.strip() + p1.strip())
        elif len(col0) == 1 and col0.isalpha() and col1:
            # Si col1 tiene saltos de línea, dividirla y reconstruir cada parte:
            # las líneas que empiezan por minúscula son la continuación de col0.
            if "\n" in col1:
                for part in col1.split("\n"):
                    if not part:
                        continue
                    if part[0].islower():
                        header_lines.append(col0 + part)
                    else:
                        header_lines.append(part)
            else:
                header_lines.append(col0 + col1)

    # ── Datos generales ──
    full_text = " ".join(header_lines)

    meses = {
        "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
        "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
        "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
    }

    fecha = hora = None
    m = re.search(
        r"el\s+d[ií]a\s+(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s+a\s+las\s+(\d{1,2}:\d{2})",
        full_text, re.IGNORECASE,
    )
    if m:
        fecha = f"{m.group(3)}-{meses.get(m.group(2).lower(), '00')}-{m.group(1).zfill(2)}"
        hora = m.group(4)

    ciudad = None
    m = re.search(r"celebrado\s+en\s+(.+?)\s+el\s+d[ií]a", full_text, re.IGNORECASE)
    if m:
        ciudad = clean(m.group(1))

    recinto = None
    m = re.search(r"juego\s+(.+?)\s+Competici[oó]n", full_text, re.IGNORECASE)
    if m:
        recinto = clean(m.group(1))

    competicion = None
    m = re.search(r"Competici[oó]n\s+(.+?)\s+Grupo", full_text, re.IGNORECASE)
    if m:
        competicion = clean(m.group(1))

    grupo = None
    m = re.search(r"Grupo\s+(\d+)", full_text, re.IGNORECASE)
    if m:
        grupo = int(m.group(1))

    jornada = None
    m = re.search(r"J\.\s*(\d+)", full_text)
    if m:
        jornada = int(m.group(1))

    temporada = None
    m = re.search(r"TEMPORADA\s+(\d{4}/\d{4})", full_text, re.IGNORECASE)
    if m:
        temporada = m.group(1)

    # ── Equipos ──
    equipo_local = equipo_visitante = None
    for line in header_lines:
        m = re.search(r"Equipo\s+Local:\s+(.+?)\s+Equipo\s+Visitante:", line)
        if m:
            equipo_local = clean(m.group(1))
        m = re.search(r"Equipo\s+Visitante:\s+(.+?)$", line)
        if m:
            equipo_visitante = clean(m.group(1))

    # ── Delegados y entrenadores ──
    delegado_local = delegado_visitante = None
    entrenador_local = entrenador_visitante = None

    for line in header_lines:
        if "Delegado" in line:
            delegado_local = extract_person_from_line(line, "Delegado Local")
            delegado_visitante = extract_person_from_line(line, "Delegado Visitante")
        if "Entrenador" in line:
            entrenador_local = extract_person_from_line(line, "Entrenador Local")
            entrenador_visitante = extract_person_from_line(line, "Entrenador Visitante")

    # ── Árbitros ──
    arbitro_principal = arbitro_asistente = None
    for line in header_lines:
        if "rbitro Principal" in line:
            m = re.search(r"rbitro\s+Principal:\s+(.+?)\s+Lic:\s+(\d+)", line)
            if m:
                arbitro_principal = {"nombre": clean(m.group(1)), "licencia": m.group(2)}
            m = re.search(r"rbitro\s+Asistente:\s+(.+?)\s+Lic:\s+(\d+)", line)
            if m:
                arbitro_asistente = {"nombre": clean(m.group(1)), "licencia": m.group(2)}

    # ══════════════════════════════════════════
    #  Tabla de partidos
    # ══════════════════════════════════════════

    # Encontrar fila cabecera (la que contiene "ABC")
    header_idx = None
    for i, row in enumerate(table):
        if row and any(str(c).strip() == "ABC" for c in row if c):
            header_idx = i
            break

    alineaciones_abc = {}
    alineaciones_xyz = {}
    partidos = []
    marcador_abc = 0
    marcador_xyz = 0

    # Detectar qué equipo es ABC y cuál XYZ desde la cabecera de la tabla
    equipo_abc = equipo_xyz = None
    if header_idx is not None:
        hdr = table[header_idx]
        # col[2] = nombre equipo ABC
        equipo_abc = clean(hdr[2])
        # Buscar equipo XYZ: primera celda no vacía tras el marcador 'XYZ'
        # (la columna puede variar según el PDF)
        xyz_label_idx = next(
            (i for i, c in enumerate(hdr) if c and str(c).strip() == "XYZ"), None
        )
        if xyz_label_idx is not None:
            for c in hdr[xyz_label_idx + 1:]:
                v = clean(c)
                if v and not re.match(r"^J\d$|^JUEG|^TOT", v, re.IGNORECASE):
                    equipo_xyz = v
                    break

    # Determinar si ABC es local o visitante
    abc_es_local = True
    if equipo_abc and equipo_local:
        abc_es_local = equipo_abc.upper() == equipo_local.upper()

    # Mapeo: "local" y "visitante" en el JSON = equipo ABC y XYZ
    # pero etiquetados según quién juega en casa
    if abc_es_local:
        nombre_local = equipo_abc or equipo_local
        nombre_visitante = equipo_xyz or equipo_visitante
    else:
        nombre_local = equipo_xyz or equipo_local
        nombre_visitante = equipo_abc or equipo_visitante

    # Detectar columnas dinámicamente
    col_map = {}
    if header_idx is not None:
        col_map = detect_set_columns(table[header_idx])

    set_keys = ["J1", "J2", "J3", "J4", "J5"]

    if header_idx is not None:
        data_rows = table[header_idx + 1:]

        for i, row in enumerate(data_rows):
            if not row or len(row) < 6:
                continue

            letra_abc = clean(row[1])
            jugadores_abc_raw = str(row[2]) if row[2] else ""
            letra_xyz = clean(row[3])
            jugadores_xyz_raw = str(row[4]) if row[4] else ""

            if not letra_abc or not letra_xyz:
                continue
            if "GANADOR" in str(row[1] or ""):
                break

            es_dobles = letra_abc.upper() == "DB"

            # ── Extraer jugadores ──
            players_abc = extract_players(jugadores_abc_raw)
            players_xyz = extract_players(jugadores_xyz_raw)

            # Registrar alineaciones (solo individuales, primera aparición)
            if not es_dobles:
                if players_abc and letra_abc not in alineaciones_abc:
                    alineaciones_abc[letra_abc] = players_abc[0]
                if players_xyz and letra_xyz not in alineaciones_xyz:
                    alineaciones_xyz[letra_xyz] = players_xyz[0]

            # ── Extraer sets ──
            sets = []
            juegos_abc = 0
            juegos_xyz = 0
            no_disputado = True

            for s_num, key in enumerate(set_keys, 1):
                col_idx = col_map.get(key)
                if col_idx is None or col_idx >= len(row):
                    continue
                score = parse_score(row[col_idx])
                if score:
                    no_disputado = False
                    sets.append({
                        "set": s_num,
                        "abc": score[0],
                        "xyz": score[1],
                    })
                    if score[0] > score[1]:
                        juegos_abc += 1
                    else:
                        juegos_xyz += 1

            # Resultado de juegos del acta
            jueg_col = col_map.get("JUEG")
            jueg_acta = parse_score(row[jueg_col] if jueg_col and jueg_col < len(row) else None)
            if jueg_acta:
                juegos_abc, juegos_xyz = jueg_acta

            # Resultado acumulado del acta
            tot_col = col_map.get("TOT")
            tot_acta = parse_score(row[tot_col] if tot_col and tot_col < len(row) else None)

            # Ganador
            if no_disputado:
                ganador = None
            elif juegos_abc > juegos_xyz:
                ganador = "abc"
                marcador_abc += 1
            else:
                ganador = "xyz"
                marcador_xyz += 1

            # ── Construir estructura del partido ──
            # Formatear jugadores según individuales o dobles
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
                    "nombre": players_abc[0]["nombre"] if players_abc else None,
                }
                xyz_info = {
                    "letra": letra_xyz,
                    "nombre": players_xyz[0]["nombre"] if players_xyz else None,
                }

            # Mapear abc/xyz a local/visitante
            if abc_es_local:
                local_info, visitante_info = abc_info, xyz_info
                sets_mapped = [{"set": s["set"], "local": s["abc"], "visitante": s["xyz"]} for s in sets]
                res_juegos = {"local": juegos_abc, "visitante": juegos_xyz} if not no_disputado else None
                ganador_label = "local" if ganador == "abc" else ("visitante" if ganador == "xyz" else None)
                acum = {
                    "local": tot_acta[0] if tot_acta else marcador_abc,
                    "visitante": tot_acta[1] if tot_acta else marcador_xyz,
                }
            else:
                local_info, visitante_info = xyz_info, abc_info
                sets_mapped = [{"set": s["set"], "local": s["xyz"], "visitante": s["abc"]} for s in sets]
                res_juegos = {"local": juegos_xyz, "visitante": juegos_abc} if not no_disputado else None
                ganador_label = "local" if ganador == "xyz" else ("visitante" if ganador == "abc" else None)
                acum = {
                    "local": tot_acta[1] if tot_acta else marcador_xyz,
                    "visitante": tot_acta[0] if tot_acta else marcador_abc,
                }

            partido = {
                "numero": i + 1,
                "tipo": "dobles" if es_dobles else "individual",
                "cruce": f"{letra_abc} vs {letra_xyz}",
                "local": local_info,
                "visitante": visitante_info,
                "sets": sets_mapped,
                "resultado_juegos": res_juegos,
                "ganador": ganador_label,
                "marcador_acumulado": acum,
            }
            if no_disputado:
                partido["no_disputado"] = True
                if abc_es_local:
                    partido["motivo"] = f"Victoria decidida ({marcador_abc}-{marcador_xyz})"
                else:
                    partido["motivo"] = f"Victoria decidida ({marcador_xyz}-{marcador_abc})"

            partidos.append(partido)

    # ══════════════════════════════════════════
    #  Resultado final
    # ══════════════════════════════════════════
    ganador_final = None
    marcador_final_abc = marcador_abc
    marcador_final_xyz = marcador_xyz
    juegos_final_abc = juegos_final_xyz = None

    for row in table:
        if not row:
            continue
        cell1 = str(row[1]) if row[1] else ""
        if "GANADOR" in cell1:
            m = re.search(r"GANADOR:\s*(.+)", cell1, re.DOTALL)
            if m:
                ganador_final = clean(m.group(1))
            for cell in row:
                if not cell:
                    continue
                s = str(cell)
                mr = re.search(r"RESULTADO\s+GENERAL.*?(\d+)\s*/\s*(\d+)", s, re.DOTALL | re.IGNORECASE)
                if mr:
                    marcador_final_abc = int(mr.group(1))
                    marcador_final_xyz = int(mr.group(2))
                mj = re.search(r"JUEGOS.*?(\d+)\s*/\s*(\d+)", s, re.DOTALL | re.IGNORECASE)
                if mj:
                    juegos_final_abc = int(mj.group(1))
                    juegos_final_xyz = int(mj.group(2))
            break

    # Mapear ABC/XYZ a local/visitante en resultado final
    if abc_es_local:
        marcador_final = {"local": marcador_final_abc, "visitante": marcador_final_xyz}
        juegos_final = {"local": juegos_final_abc, "visitante": juegos_final_xyz}
    else:
        marcador_final = {"local": marcador_final_xyz, "visitante": marcador_final_abc}
        juegos_final = {"local": juegos_final_xyz, "visitante": juegos_final_abc}

    # Acta protestada
    acta_protestada = False
    for row in table:
        if not row:
            continue
        for cell in row:
            if not cell:
                continue
            s = str(cell)
            if "ACTA PROTESTADA POR:" in s:
                m = re.search(r"ACTA\s+PROTESTADA\s+POR:\s*(.+)", s)
                if m:
                    val = clean(m.group(1))
                    if val:
                        acta_protestada = val

    # ── Alineaciones: mapear a local/visitante ──
    if abc_es_local:
        alin_local = alineaciones_abc
        alin_visitante = alineaciones_xyz
    else:
        alin_local = alineaciones_xyz
        alin_visitante = alineaciones_abc

    # Dobles: extraer jugadores del partido de dobles si existe
    dobles_local = dobles_visitante = None
    for p in partidos:
        if p["tipo"] == "dobles":
            dobles_local = p["local"].get("jugadores")
            dobles_visitante = p["visitante"].get("jugadores")
            break

    # ══════════════════════════════════════════
    #  JSON final
    # ══════════════════════════════════════════
    acta = {
        "federacion": "Real Federación Española de Tenis de Mesa",
        "temporada": temporada,
        "competicion": competicion,
        "grupo": grupo,
        "jornada": jornada,
        "fecha": fecha,
        "hora": hora,
        "lugar": {
            "ciudad": ciudad,
            "recinto": recinto,
        },
        "equipos": {
            "local": {
                "nombre": nombre_local,
                "delegado": delegado_local,
                "entrenador": entrenador_local,
            },
            "visitante": {
                "nombre": nombre_visitante,
                "delegado": delegado_visitante,
                "entrenador": entrenador_visitante,
            },
        },
        "abc_es_local": abc_es_local,
        "arbitros": {
            "principal": arbitro_principal,
            "asistente": arbitro_asistente,
        },
        "alineaciones": {
            "local": alin_local,
            "visitante": alin_visitante,
        },
        "dobles": {
            "local": dobles_local,
            "visitante": dobles_visitante,
        } if dobles_local else None,
        "partidos": partidos,
        "resultado_final": {
            "ganador": ganador_final,
            "marcador_partidos": marcador_final,
            "marcador_juegos": juegos_final,
        },
        "acta_protestada": acta_protestada,
    }

    return acta


# ══════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Convierte un acta RFETM de tenis de mesa (PDF) a JSON.",
    )
    parser.add_argument("pdf", help="Ruta al archivo PDF del acta")
    parser.add_argument(
        "-o", "--output",
        help="Ruta de salida para el JSON (por defecto: mismo nombre con .json)",
        default=None,
    )
    parser.add_argument(
        "--indent", type=int, default=2,
        help="Indentación del JSON (por defecto: 2)",
    )

    args = parser.parse_args()

    output_path = args.output
    if not output_path:
        output_path = re.sub(r"\.pdf$", ".json", args.pdf, flags=re.IGNORECASE)
        if output_path == args.pdf:
            output_path = args.pdf + ".json"

    print(f"Leyendo acta: {args.pdf}")
    acta = parse_acta(args.pdf)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(acta, f, ensure_ascii=False, indent=args.indent)

    print(f"JSON generado: {output_path}")
    return acta


if __name__ == "__main__":
    main()
