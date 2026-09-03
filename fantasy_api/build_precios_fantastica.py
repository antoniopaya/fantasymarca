"""
Construye ../webapp/public/data/precios_fantastica.json a partir del Excel de
precios de consenso de la liga (../webapp/public/data/*.xlsx).

Por qué un script separado de main.py/build_catalog.py: esos dos regeneran
players.json y players/<id>.json entero cada vez que se ejecutan (pisando
cualquier cosa que se les añada a mano), así que el precio Fantástica -que
es un dato manual, pactado por la liga y no algo que dé la API de Marca-
tiene que vivir en su propio fichero para sobrevivir a esas regeneraciones.

El Excel no trae el id de fantasy.marca.com de cada jugador (por algo lo
gestionan aparte de la propia liga), así que hay que casarlo por nombre
contra el catálogo. El fichero tiene un formato "ancho": una columna de
posición (Portero/Defensa/Medio/Delantero) que aplica a toda la fila, y
luego un bloque de 3 columnas (nombre, precio, separador) por equipo. Los
nombres del Excel suelen ser abreviados ("J. Owono", "Fdez.", "Glez.") así
que el emparejamiento es aproximado (fuzzy) y se restringe a jugadores del
mismo equipo+posición para no confundir gente.

Ese emparejamiento aproximado falla en un puñado de casos reales -jugadores
nuevos que el Excel ya incluye pero que fantasy.marca.com todavía no ha
dado de alta, o entradas que sencillamente no tienen contrapartida clara-.
MANUAL_OVERRIDES resuelve esos casos a mano (revisado contra el catálogo
completo, ver conversación de origen). Si en una actualización futura del
Excel aparecen jugadores nuevos sin match, el script los lista al final:
hay que decidir si son fichajes que Marca aún no ha añadido (se ignoran,
sin más, hasta la siguiente actualización) o si hace falta añadir un
override.

Uso:
    python build_precios_fantastica.py
"""

import difflib
import glob
import json
import math
import os
import re
import sys
import unicodedata

import openpyxl

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp", "public", "data")

# Alias del nombre de equipo tal cual aparece en el Excel -> id_team de teams.json.
# Si el Excel de una temporada futura trae equipos distintos (ascensos/descensos),
# esta tabla hay que actualizarla a mano.
TEAM_ALIAS = {
    "Alavés": 48,
    "Athletic": 1,
    "At. Madrid": 2,
    "Barcelona": 3,
    "Betis": 4,
    "Celta": 5,
    "Dep. Coruña": 6,
    "Elche": 23,
    "Español": 8,
    "Getafe": 9,
    "Levante": 12,
    "Málaga": 13,
    "Osasuna": 50,
    "Racing Santander": 1490,
    "Rayo Vallecano": 14,
    "R. Madrid": 15,
    "R. Sociedad": 16,
    "Sevilla": 17,
    "Valencia": 19,
    "Villarreal": 20,
}

POSITION_BY_LABEL = {"Portero": 1, "Defensa": 2, "Medio": 3, "Delantero": 4}

# Abreviaturas de apellido habituales en el Excel que el catálogo escribe completas.
SURNAME_ABBREVIATIONS = {
    "fdez": "fernandez",
    "glez": "gonzalez",
    "hdez": "hernandez",
    "mtnez": "martinez",
    "rguez": "rodriguez",
}

# (equipo excel, posición excel, nombre excel) -> id de fantasy.marca.com, o None
# para marcar explícitamente "sin contrapartida en el catálogo, no forzar match".
# Revisado a mano para el Excel "Listado Jugadores 26-27" (ver histórico del repo).
MANUAL_OVERRIDES = {
    # Estos 25 estaban a `None` (sin contrapartida) porque en su momento el
    # catálogo de fantasy.marca.com todavía no había dado de alta a estos
    # jugadores; main.py ya los tiene ahora y el emparejamiento automático
    # los encuentra con score perfecto, así que se fija el id explícito en
    # vez de dejarlo a merced de que la próxima regeneración del catálogo
    # no cambie el orden de los candidatos.
    ("Racing Santander", "Portero", "Laro Gómez"): 71638,
    ("Villarreal", "Portero", "Péter Gulácsi"): 71649,
    ("Celta", "Defensa", "Abdoulaye Faye"): 71642,
    ("Racing Santander", "Defensa", "P. Felipe"): 71791,
    ("Racing Santander", "Defensa", "P. Ramón"): 60858,
    ("Español", "Defensa", "Roger Hinojo"): 71623,
    ("Español", "Defensa", "Unai Núñez"): 7784,
    ("Málaga", "Defensa", "J. Salinas"): 64038,
    ("Getafe", "Defensa", "Sazonov"): 71790,
    ("Elche", "Medio", "J. Morcillo"): 70150,
    ("Elche", "Delantero", "Fer Niño"): 20449,
    ("Elche", "Delantero", "U. Konare"): 71794,
    ("Osasuna", "Delantero", "Dubasin"): 48210,
    ("Rayo Vallecano", "Defensa", "Kumbulla"): 59532,
    ("Sevilla", "Medio", "Miguel Sierra"): 71640,
    ("Levante", "Portero", "Mathew Ryan"): 28612,
    ("Barcelona", "Medio", "Jesse Bisiwu"): 71622,
    ("Athletic", "Medio", "Generabarrena"): 71639,  # "Generabarrena" = Beñat Gerenabarrena, único candidato con score alto
    ("Celta", "Portero", "A. Bayindir"): 78393,  # "A. Bayindir" = Altay Bayındır (la ı turca no afecta al id)
    ("Racing Santander", "Delantero", "Yassir Zabiri"): 71616,
    ("Celta", "Medio", "Hugo Glez."): 55439,
    ("Dep. Coruña", "Defensa", "Angeliño"): 71795,
    ("Sevilla", "Portero", "Fran Glez."): 62910,
    ("Levante", "Delantero", "Yanis Musuayi"): 71633,
    ("Sevilla", "Defensa", "Julio Díaz"): 69744,
    # Estos, en cambio, se revisaron a mano y de verdad no tienen contrapartida
    # clara en el catálogo actual (o el mejor candidato tiene un score demasiado
    # bajo para forzarlo) — se dejan fuera a propósito.
    ("Sevilla", "Medio", "P. Mercado"): None,
    # Error de columna en el propio Excel: esta fila cae bajo el bloque de
    # "R. Madrid" pero el nombre solo existe en el catálogo como delantero
    # del Levante (id 63780), que si no se queda sin precio.
    ("R. Madrid", "Delantero", "Carlos Espí"): 63780,
}

# Precio dado a mano por el usuario para jugadores que ni siquiera aparecen
# en el Excel bajo ningún nombre razonable (alta demasiado reciente para que
# la liga los haya incluido en el reparto todavía). id de fantasy.marca.com
# -> precio en millones de euros. Se aplica después del emparejamiento con el
# Excel, así que sobrevive a que un futuro cambio en el Excel no los toque.
EXTRA_PRICES: dict[int, float] = {}


def find_excel_path() -> str:
    matches = glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
    if len(matches) != 1:
        raise SystemExit(
            f"Esperaba exactamente un .xlsx en {DATA_DIR}, encontrados {len(matches)}: {matches}"
        )
    return matches[0]


def normalize_tokens(name: str) -> list[str]:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.lower().replace("-", " ")
    ascii_name = re.sub(r"[^a-z0-9. ]", "", ascii_name)
    tokens = []
    for tok in ascii_name.split():
        tok = tok.rstrip(".")
        tokens.append(SURNAME_ABBREVIATIONS.get(tok, tok))
    return tokens


def round_price(value: float) -> int:
    """Los precios Fantástica son siempre enteros. Un puñado de celdas del Excel
    quedaron con la media sin redondear de varios votos (p.ej. 20.428571... = 143/7):
    parece el resultado de una fórmula de promedio a la que nunca se le aplicó ROUND()
    antes de convertirla a valor. Redondeo normal (mitad hacia arriba, no bancario)."""
    return math.floor(value + 0.5)


def token_score(e_tokens: list[str], c_tokens: list[str]) -> float:
    total_weight = total_score = 0.0
    for tok in e_tokens:
        weight = 1.0 if len(tok) > 1 else 0.4  # una inicial sola pesa menos que un nombre completo
        if len(tok) == 1:
            best = 1.0 if any(c.startswith(tok) for c in c_tokens) else 0.0
        else:
            best = max((difflib.SequenceMatcher(None, tok, c).ratio() for c in c_tokens), default=0.0)
        total_score += weight * best
        total_weight += weight
    return total_score / total_weight if total_weight else 0.0


def parse_excel(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Precios Jugadores"] if "Precios Jugadores" in wb.sheetnames else wb.worksheets[0]

    team_cols = {}
    for col in range(2, ws.max_column + 1):
        value = ws.cell(row=1, column=col).value
        if value:
            team_cols[col] = value

    unknown_teams = sorted(set(team_cols.values()) - set(TEAM_ALIAS))
    if unknown_teams:
        raise SystemExit(
            f"Equipos del Excel sin alias en TEAM_ALIAS: {unknown_teams}. "
            "Añádelos a TEAM_ALIAS (o revisa si son un renombrado de uno existente)."
        )

    records = []
    current_position = None
    for row in range(2, ws.max_row + 1):
        label = ws.cell(row=row, column=1).value
        if label:
            current_position = label
        for col, team in team_cols.items():
            name = ws.cell(row=row, column=col).value
            price = ws.cell(row=row, column=col + 1).value
            if name:
                records.append({"team": team, "position": current_position, "name": name, "price": price})
    return records



# Sin este mínimo, un equipo con más candidatos del catálogo que filas en el
# Excel para ese hueco (típico cuando llega un fichaje nuevo) acaba
# emparejando lo que sea con lo que sea aunque el score sea pésimo: se
# comprobó en vivo y estaba poniendo el precio de Nahuel Molina a Dani
# Martínez, el de Ronald Araújo a Álvaro Cortés, etc. (todos con score
# 0.20-0.50). El valor 0.7 se calibró a mano contra esos falsos positivos
# reales y contra aciertos legítimos que puntúan bajo por cómo compara el
# algoritmo apodos/abreviaturas poco habituales ("Vinicius Jr." vs
# "Vinícius Júnior" = 0.75, "Alex Balde" vs "Alejandro Balde" = 0.83):
# separa limpiamente ambos grupos.
MIN_AUTO_MATCH_SCORE = 0.7


def match_records(records: list[dict], players: list[dict]) -> tuple[dict, list[dict]]:
    players_by_group = {}
    for p in players:
        players_by_group.setdefault((p["id_team"], p["position"]), []).append(p)

    price_by_id: dict[int, float] = {}
    unmatched: list[dict] = []
    reserved_player_ids: set[int] = set()  # ids ya resueltos a mano, no elegibles para el matching automático

    # Los overrides manuales se aplican primero, y reservan su id de destino
    # para que el matching automático no se lo pueda quedar por error en otra fila.
    auto_indices = []
    for idx, rec in enumerate(records):
        override_key = (rec["team"], rec["position"], rec["name"])
        if override_key in MANUAL_OVERRIDES:
            override_id = MANUAL_OVERRIDES[override_key]
            if override_id is None:
                unmatched.append(rec)
            else:
                price_by_id[override_id] = rec["price"]
                reserved_player_ids.add(override_id)
        elif rec["price"] is None:
            # Fila con nombre pero sin precio puesto todavía en el Excel: no hay
            # nada que asignar, y no debe competir por un candidato con otra fila
            # que sí tenga precio.
            unmatched.append(rec)
        else:
            auto_indices.append(idx)

    groups = {}
    for idx in auto_indices:
        rec = records[idx]
        key = (TEAM_ALIAS[rec["team"]], POSITION_BY_LABEL[rec["position"]])
        groups.setdefault(key, []).append(idx)

    for key, rec_indices in groups.items():
        candidates = [c for c in players_by_group.get(key, []) if c["id"] not in reserved_player_ids]
        pairs = []
        for idx in rec_indices:
            e_tokens = normalize_tokens(records[idx]["name"])
            for c in candidates:
                pairs.append((token_score(e_tokens, normalize_tokens(c["name"])), idx, c["id"]))
        pairs.sort(key=lambda item: -item[0])

        claimed_records, claimed_players = set(), set()
        for score, idx, player_id in pairs:
            if score < MIN_AUTO_MATCH_SCORE:
                break  # pairs va de mayor a menor score: a partir de aquí todo es peor todavía
            if idx in claimed_records or player_id in claimed_players:
                continue
            claimed_records.add(idx)
            claimed_players.add(player_id)
            price_by_id[player_id] = records[idx]["price"]

        for idx in rec_indices:
            if idx not in claimed_records:
                unmatched.append(records[idx])

    return price_by_id, unmatched


def main() -> None:
    excel_path = find_excel_path()
    print(f"Leyendo {excel_path}...", file=sys.stderr)
    records = parse_excel(excel_path)
    print(f"  {len(records)} filas de jugador", file=sys.stderr)

    players_path = os.path.join(DATA_DIR, "players.json")
    with open(players_path, encoding="utf-8") as f:
        players = json.load(f)

    price_by_id, unmatched = match_records(records, players)

    for player_id, price in EXTRA_PRICES.items():
        if player_id in price_by_id:
            print(
                f"Aviso: EXTRA_PRICES pisa un precio ya asignado por el Excel para el id {player_id} "
                f"({price_by_id[player_id]} -> {price})",
                file=sys.stderr,
            )
        price_by_id[player_id] = price

    output = {str(pid): round_price(price) for pid, price in sorted(price_by_id.items())}

    out_path = os.path.join(DATA_DIR, "precios_fantastica.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nGuardado {out_path}: {len(output)} jugadores con precio Fantástica.", file=sys.stderr)

    if unmatched:
        print(f"\n{len(unmatched)} filas del Excel sin match en el catálogo (sin precio asignado):", file=sys.stderr)
        for rec in sorted(unmatched, key=lambda r: (r["team"], r["position"])):
            print(f"  {rec['team']:18s} {rec['position']:10s} {rec['name']}", file=sys.stderr)
        print(
            "  -> normalmente son fichajes de este verano que fantasy.marca.com "
            "todavía no ha dado de alta; si alguno lleva tiempo sin aparecer, "
            "revisa MANUAL_OVERRIDES.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
