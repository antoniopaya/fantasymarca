"""
Alineaciones probables de futbolfantasy.com (una página por equipo) ->
../webapp/data/alineaciones.json, emparejadas con los ids de Marca.

En cada página de equipo, la sección "Posible alineación" trae, para la
próxima jornada, el 11 probable y los suplentes con atributos data-* en
cada jugador: probabilidad de ser titular (data-probabilidad="70%"),
lesión, sanción, no disponible... Se distinguen de la "alineación
confirmada" de la jornada anterior (que va en la misma sección) porque solo
los de la posible llevan la clase `tipo_campo`.

Además de alineaciones.json se guarda una copia por jornada en
../webapp/data/alineaciones_hist/<n>.json (la última de antes del cierre),
para poder usar la probabilidad de titularidad como dato de entrenamiento
en ml_model.py cuando haya historia suficiente.

Educación con el servidor: robots.txt lo permite todo, pero se identifica
el cliente, se espera entre equipo y equipo y solo se ejecuta junto al
refresco de datos (unas pocas veces por semana).

Uso:
    python scrape_alineaciones.py
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from curl_cffi import requests

from name_matching import normalize_tokens, token_score

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA_DIR = os.path.join(ROOT, "webapp", "data")
HIST_DIR = os.path.join(DATA_DIR, "alineaciones_hist")

BASE_URL = "https://www.futbolfantasy.com/laliga/equipos/"
DELAY_SECONDS = 3
USER_AGENT = "FantasyMarcaPayas/1.0 (uso personal; github.com/antoniopaya/fantasymarca)"

# slug de futbolfantasy -> id de equipo de Marca (teams.json)
TEAM_SLUGS = {
    "alaves": 48,
    "athletic": 1,
    "atletico": 2,
    "barcelona": 3,
    "betis": 4,
    "celta": 5,
    "deportivo": 6,
    "elche": 23,
    "espanyol": 8,
    "getafe": 9,
    "levante": 12,
    "malaga": 13,
    "osasuna": 50,
    "racing": 1490,
    "rayo-vallecano": 14,
    "real-madrid": 15,
    "real-sociedad": 16,
    "sevilla": 17,
    "valencia": 19,
    "villarreal": 20,
}

# nombre de futbolfantasy -> id de Marca, para los que el emparejamiento por
# nombre no resuelve (apodos muy distintos, homónimos...).
ALIASES: dict[str, int] = {}

MIN_NAME_SCORE = 0.7


def to_int(value, default=None):
    try:
        return int(str(value).strip().rstrip("%"))
    except (TypeError, ValueError):
        return default


def to_float(value):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def parse_team(html: str) -> tuple[int | None, list[dict]]:
    soup = BeautifulSoup(html, "lxml")
    section = soup.select_one("section.alineacion_wrapper")
    if section is None:
        return None, []

    # "J 8" en la cabecera de la sección: jornada a la que se refiere.
    header = " ".join(section.select_one("header").stripped_strings) if section.select_one("header") else ""
    match = re.search(r"\bJ\s+(\d+)\b", header)
    jornada = int(match.group(1)) if match else None

    players = []
    for wrapper in section.select(".camiseta-wrapper.tipo_campo"):
        a = wrapper.select_one("a.camiseta")
        img = wrapper.select_one("img.fotozoom")
        if a is None or img is None or not img.get("alt"):
            continue
        ff_id = next((c.split("_", 1)[1] for c in wrapper.get("class", []) if c.startswith("jugador_")), None)
        players.append(
            {
                "ff_id": to_int(ff_id),
                "name": img["alt"].strip(),
                "status": wrapper.get("data-onceff") or "suplente",
                "prob": to_int(a.get("data-probabilidad"), 0),
                # Código de lesión tal cual: no está documentado (hay titulares
                # al 70% con valor 2), así que no se interpreta; la
                # probabilidad ya recoge si el jugador está disponible.
                "lesion_code": to_int(a.get("data-lesion"), -1),
                "sanctioned": to_int(a.get("data-sancionado"), 0) == 1,
                "unavailable": to_int(a.get("data-nodisponible"), 0) == 1,
                "form": to_float(a.get("data-forma_value")),
                "position": wrapper.get("data-posicion"),
            }
        )
    return jornada, players


def match_players(team_id: int, players: list[dict], catalog: list[dict]) -> list[str]:
    """Añade "id" (Marca) a cada jugador; devuelve los nombres sin emparejar."""
    squad = [(p, normalize_tokens(p["name"])) for p in catalog if p["id_team"] == team_id]
    unmatched = []
    taken: set[int] = set()
    for pl in sorted(players, key=lambda x: -x["prob"]):
        if pl["name"] in ALIASES:
            pl["id"] = ALIASES[pl["name"]]
            taken.add(pl["id"])
            continue
        tokens = normalize_tokens(pl["name"])
        # En los dos sentidos: futbolfantasy usa el nombre completo ("Pedri
        # González") y Marca a menudo el corto ("Pedri"), o al revés.
        scored = sorted(
            (
                (max(token_score(tokens, c_tokens), token_score(c_tokens, tokens)), p)
                for p, c_tokens in squad
                if p["id"] not in taken
            ),
            key=lambda x: -x[0],
        )
        if scored and scored[0][0] >= MIN_NAME_SCORE:
            pl["id"] = scored[0][1]["id"]
            taken.add(pl["id"])
        else:
            pl["id"] = None
            unmatched.append(pl["name"])
    return unmatched


def jornada_started(jornada: int) -> bool:
    try:
        with open(os.path.join(DATA_DIR, "matches", f"{jornada}.json"), encoding="utf-8") as f:
            matches = json.load(f)
    except FileNotFoundError:
        return False
    kickoffs = [m["date"]["ts"] for m in matches if m.get("date", {}).get("ts")]
    return bool(kickoffs) and time.time() >= min(kickoffs)


def write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> None:
    with open(os.path.join(DATA_DIR, "players.json"), encoding="utf-8") as f:
        catalog = json.load(f)

    session = requests.Session(impersonate="chrome")
    teams: dict[str, list[dict]] = {}
    jornadas: set[int] = set()
    problems: list[str] = []

    for i, (slug, team_id) in enumerate(TEAM_SLUGS.items()):
        if i:
            time.sleep(DELAY_SECONDS)
        try:
            resp = session.get(BASE_URL + slug, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
        except Exception as err:  # una caída puntual no debe tumbar el resto
            problems.append(f"{slug}: {err}")
            continue
        jornada, players = parse_team(resp.text)
        if not players:
            problems.append(f"{slug}: sin sección de posible alineación")
            continue
        if jornada:
            jornadas.add(jornada)
        unmatched = match_players(team_id, players, catalog)
        if unmatched:
            problems.append(f"{slug}: sin emparejar en Marca -> {', '.join(unmatched)}")
        teams[str(team_id)] = sorted(players, key=lambda p: -p["prob"])
        titulares = sum(1 for p in players if p["status"] == "titular")
        print(f"  {slug}: {len(players)} jugadores ({titulares} titulares)", file=sys.stderr)

    if not teams:
        raise SystemExit("No se ha podido leer ninguna alineación:\n  " + "\n  ".join(problems))

    jornada = max(jornadas) if jornadas else None
    payload = {
        "jornada": jornada,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "source": "futbolfantasy.com",
        "teams": teams,
    }
    write_json(os.path.join(DATA_DIR, "alineaciones.json"), payload)
    # Para entrenar sirve la foto de antes del cierre: una vez empezada la
    # jornada no se pisa (las alineaciones ya reflejarían lo que pasó).
    if jornada and not jornada_started(jornada):
        write_json(os.path.join(HIST_DIR, f"{jornada}.json"), payload)

    print(f"\nListo: {len(teams)}/20 equipos, jornada {jornada}.", file=sys.stderr)
    if problems:
        print(f"\n{len(problems)} avisos:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)


if __name__ == "__main__":
    main()
