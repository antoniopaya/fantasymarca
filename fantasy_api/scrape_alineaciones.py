"""
Alineaciones probables de dos fuentes, contrastadas, ->
../webapp/data/alineaciones.json, emparejadas con los ids de Marca.

futbolfantasy.com (una página por equipo): la sección "Posible alineación"
trae el 11 probable y los suplentes con atributos data-* en cada jugador:
probabilidad de ser titular (data-probabilidad="70%"), sanción, no
disponible... Se distinguen de la "alineación confirmada" de la jornada
anterior (misma sección) porque solo los de la posible llevan `tipo_campo`.

analiticafantasy.com (una página por jornada con los 10 partidos): es una
web Next.js que incrusta los datos en el HTML (self.__next_f.push). Por
cada partido trae homeLineup/awayLineup con 11 titulares y 5 alternativas:
"chance" (probabilidad), "esTitular" y, si es duda/lesión, el motivo. Su
robots.txt prohíbe /api/, así que solo se lee la página, nunca su API.

Contraste: para cada jugador se guardan las dos probabilidades y su media
("prob", la que usa el modelo), y se marca "discrepancy" cuando una fuente
lo pone de titular y la otra no, o sus probabilidades se separan 40 puntos
o más. Si un jugador no aparece en una fuente que sí tiene a su equipo,
cuenta como que esa fuente no espera que juegue (0% en futbolfantasy, que
lista toda la plantilla; 10% en analiticafantasy, que solo lista 16).

Además se guarda una copia por jornada en alineaciones_hist/<n>.json (la
de antes del cierre) para que ml_model.py aprenda el peso de la
probabilidad cuando haya historia.

Educación con los servidores: los dos robots.txt permiten estas páginas;
se identifica el cliente, se espera entre petición y petición y solo se
ejecuta junto al refresco de datos (unas pocas veces por semana).

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

DELAY_SECONDS = 3
USER_AGENT = "FantasyMarcaPayas/1.0 (uso personal; github.com/antoniopaya/fantasymarca)"
MIN_NAME_SCORE = 0.7
DISCREPANCY_POINTS = 40
AF_ABSENT_PROB = 10

FF_BASE_URL = "https://www.futbolfantasy.com/laliga/equipos/"
# slug de futbolfantasy -> id de equipo de Marca (teams.json)
FF_TEAMS = {
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

AF_BASE = "https://www.analiticafantasy.com"
AF_INDEX_URL = AF_BASE + "/la-liga/alineaciones-probables"
# id de equipo de analiticafantasy -> id de Marca
AF_TEAMS = {
    542: 48,  # Alaves
    531: 1,  # Athletic Club
    530: 2,  # Atletico Madrid
    529: 3,  # Barcelona
    538: 5,  # Celta Vigo
    544: 6,  # Deportivo La Coruna
    797: 23,  # Elche
    540: 8,  # Espanyol
    546: 9,  # Getafe
    539: 12,  # Levante
    535: 13,  # Malaga
    727: 50,  # Osasuna
    4665: 1490,  # Racing Santander
    728: 14,  # Rayo Vallecano
    543: 4,  # Real Betis
    541: 15,  # Real Madrid
    548: 16,  # Real Sociedad
    536: 17,  # Sevilla
    532: 19,  # Valencia
    533: 20,  # Villarreal
}

# nombre en la fuente -> id de Marca, para lo que el emparejamiento por
# nombre no resuelve (apodos muy distintos, homónimos...).
ALIASES: dict[str, int] = {
    "Vini Jr.": 12900,  # Vinícius Júnior (analiticafantasy)
    "Ez Abde": 33734,  # Abde Ezzalzouli (analiticafantasy)
    "Dela": 33053,  # Adrián de la Fuente (analiticafantasy)
}


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


# --- futbolfantasy ---------------------------------------------------------------


def parse_ff_team(html: str) -> tuple[int | None, list[dict]]:
    soup = BeautifulSoup(html, "lxml")
    section = soup.select_one("section.alineacion_wrapper")
    if section is None:
        return None, []

    # "J 8" en la cabecera de la sección: jornada a la que se refiere.
    header_el = section.select_one("header")
    header = " ".join(header_el.stripped_strings) if header_el else ""
    match = re.search(r"\bJ\s+(\d+)\b", header)
    jornada = int(match.group(1)) if match else None

    players = []
    for wrapper in section.select(".camiseta-wrapper.tipo_campo"):
        a = wrapper.select_one("a.camiseta")
        img = wrapper.select_one("img.fotozoom")
        if a is None or img is None or not img.get("alt"):
            continue
        players.append(
            {
                "name": img["alt"].strip(),
                "starter": (wrapper.get("data-onceff") or "suplente") == "titular",
                "prob": to_int(a.get("data-probabilidad"), 0),
                # Código de lesión tal cual: no está documentado (hay titulares
                # al 70% con valor 2), así que no se interpreta; la
                # probabilidad ya recoge si el jugador está disponible.
                "lesion_code": to_int(a.get("data-lesion"), -1),
                "sanctioned": to_int(a.get("data-sancionado"), 0) == 1,
                "unavailable": to_int(a.get("data-nodisponible"), 0) == 1,
            }
        )
    return jornada, players


def scrape_ff(session, problems: list[str]) -> tuple[int | None, dict[int, list[dict]]]:
    teams: dict[int, list[dict]] = {}
    jornadas: set[int] = set()
    for i, (slug, team_id) in enumerate(FF_TEAMS.items()):
        if i:
            time.sleep(DELAY_SECONDS)
        try:
            resp = session.get(FF_BASE_URL + slug, headers={"User-Agent": USER_AGENT}, timeout=30)
            resp.raise_for_status()
        except Exception as err:  # una caída puntual no debe tumbar el resto
            problems.append(f"futbolfantasy {slug}: {err}")
            continue
        jornada, players = parse_ff_team(resp.text)
        if not players:
            problems.append(f"futbolfantasy {slug}: sin sección de posible alineación")
            continue
        if jornada:
            jornadas.add(jornada)
        teams[team_id] = players
    print(f"  futbolfantasy: {len(teams)}/20 equipos", file=sys.stderr)
    return (max(jornadas) if jornadas else None), teams


# --- analiticafantasy -------------------------------------------------------------


def next_flight_data(html: str) -> str:
    """Concatena los trozos de datos de Next.js (self.__next_f.push([1, "..."]))."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    return "".join(json.loads(f'"{c}"') for c in chunks)


def parse_af_jornada(html: str) -> dict[int, list[dict]]:
    flight = next_flight_data(html)
    decoder = json.JSONDecoder()
    teams: dict[int, list[dict]] = {}
    for m in re.finditer(r'\{"fixtureId":', flight):
        try:
            fixture, _ = decoder.raw_decode(flight, m.start())
        except ValueError:
            continue
        for side in ("home", "away"):
            lineup = fixture.get(f"{side}Lineup")
            team = fixture.get(side)
            # Otros componentes de la página también llevan "fixtureId" pero
            # con otra forma: solo valen los que traen la alineación.
            if not isinstance(lineup, dict) or not isinstance(team, dict):
                continue
            marca_id = AF_TEAMS.get(team.get("teamId"))
            if marca_id is None:
                continue
            players = []
            for p in lineup.get("players", []):
                extras = p.get("playerExtras") or {}
                players.append(
                    {
                        "name": p.get("name", "").strip(),
                        "starter": bool(p.get("esTitular")),
                        "prob": to_int(p.get("chance"), 0),
                        "status": extras.get("status"),
                        "info": extras.get("statusInfo"),
                        "sanctioned": bool(extras.get("isSanctioned")),
                    }
                )
            teams[marca_id] = players
    return teams


def scrape_af(session, problems: list[str]) -> tuple[int | None, dict[int, list[dict]]]:
    try:
        index = session.get(AF_INDEX_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
        index.raise_for_status()
    except Exception as err:
        problems.append(f"analiticafantasy: {err}")
        return None, {}
    links = re.findall(r'href="(/alineaciones-probables/la-liga/temporada-\d+/jornada-(\d+))"', index.text)
    if not links:
        problems.append("analiticafantasy: no encuentro el enlace a la jornada")
        return None, {}
    path, jornada = max(links, key=lambda x: int(x[1]))
    time.sleep(DELAY_SECONDS)
    try:
        resp = session.get(AF_BASE + path, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
    except Exception as err:
        problems.append(f"analiticafantasy {path}: {err}")
        return None, {}
    teams = parse_af_jornada(resp.text)
    if not teams:
        problems.append("analiticafantasy: la página no trae alineaciones (¿ha cambiado el formato?)")
    print(f"  analiticafantasy: {len(teams)}/20 equipos (jornada {jornada})", file=sys.stderr)
    return int(jornada), teams


# --- Emparejado y contraste ---------------------------------------------------------


def match_players(team_id: int, players: list[dict], catalog: list[dict], source: str, problems: list[str]) -> None:
    """Añade "id" (Marca) a cada jugador de una fuente."""
    squad = [(p, normalize_tokens(p["name"])) for p in catalog if p["id_team"] == team_id]
    taken: set[int] = set()
    unmatched = []
    for pl in sorted(players, key=lambda x: -x["prob"]):
        if pl["name"] in ALIASES:
            pl["id"] = ALIASES[pl["name"]]
            taken.add(pl["id"])
            continue
        tokens = normalize_tokens(pl["name"])
        # En los dos sentidos: una fuente usa el nombre completo ("Pedri
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
            if pl["prob"] >= 30:  # los de 0-20% suelen ser canteranos sin ficha en Marca
                unmatched.append(pl["name"])
    if unmatched:
        problems.append(f"{source} equipo {team_id}: sin emparejar en Marca -> {', '.join(unmatched)}")


def combine(ff: dict[int, list[dict]], af: dict[int, list[dict]]) -> dict[str, list[dict]]:
    teams: dict[str, list[dict]] = {}
    for team_id in sorted(set(ff) | set(af)):
        ff_by_id = {p["id"]: p for p in ff.get(team_id, []) if p.get("id") is not None}
        af_by_id = {p["id"]: p for p in af.get(team_id, []) if p.get("id") is not None}
        rows = []
        for pid in set(ff_by_id) | set(af_by_id):
            f, a = ff_by_id.get(pid), af_by_id.get(pid)
            prob_ff = f["prob"] if f else (0 if team_id in ff else None)
            prob_af = a["prob"] if a else (AF_ABSENT_PROB if team_id in af else None)
            available = [x for x in (prob_ff, prob_af) if x is not None]
            prob = round(sum(available) / len(available))
            starter_ff = f["starter"] if f else False
            starter_af = a["starter"] if a else False
            discrepancy = (
                prob_ff is not None
                and prob_af is not None
                and max(prob_ff, prob_af) >= 40
                and (starter_ff != starter_af or abs(prob_ff - prob_af) >= DISCREPANCY_POINTS)
            )
            rows.append(
                {
                    "id": pid,
                    "name": (f or a)["name"],
                    "prob": prob,
                    "status": "titular" if prob >= 50 else "suplente",
                    "prob_ff": prob_ff,
                    "prob_af": prob_af,
                    "starter_ff": starter_ff if f else None,
                    "starter_af": starter_af if a else None,
                    "af_info": a.get("info") if a else None,
                    "sanctioned": bool((f and f["sanctioned"]) or (a and a["sanctioned"])),
                    "discrepancy": discrepancy,
                }
            )
        teams[str(team_id)] = sorted(rows, key=lambda r: -r["prob"])
    return teams


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
        json.dump(payload, f, indent=1, ensure_ascii=False)
        f.write("\n")


def main() -> None:
    with open(os.path.join(DATA_DIR, "players.json"), encoding="utf-8") as f:
        catalog = json.load(f)

    session = requests.Session(impersonate="chrome")
    problems: list[str] = []
    ff_jornada, ff = scrape_ff(session, problems)
    time.sleep(DELAY_SECONDS)
    af_jornada, af = scrape_af(session, problems)

    jornada = max(j for j in (ff_jornada, af_jornada, 0) if j is not None) or None
    # Una fuente que todavía muestra otra jornada no se mezcla.
    if ff_jornada and jornada and ff_jornada != jornada:
        problems.append(f"futbolfantasy está en la J{ff_jornada}, no en la J{jornada}: se descarta")
        ff = {}
    if af_jornada and jornada and af_jornada != jornada:
        problems.append(f"analiticafantasy está en la J{af_jornada}, no en la J{jornada}: se descarta")
        af = {}
    if not ff and not af:
        raise SystemExit("No se ha podido leer ninguna alineación:\n  " + "\n  ".join(problems))

    for source, data in (("futbolfantasy", ff), ("analiticafantasy", af)):
        for team_id, players in data.items():
            match_players(team_id, players, catalog, source, problems)

    teams = combine(ff, af)
    discrepancies = sum(1 for t in teams.values() for p in t if p["discrepancy"])
    payload = {
        "jornada": jornada,
        "scraped_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "sources": {
            "futbolfantasy": len(ff),
            "analiticafantasy": len(af),
        },
        "teams": teams,
    }
    write_json(os.path.join(DATA_DIR, "alineaciones.json"), payload)
    # Para entrenar sirve la foto de antes del cierre: una vez empezada la
    # jornada no se pisa (las alineaciones ya reflejarían lo que pasó).
    if jornada and not jornada_started(jornada):
        write_json(os.path.join(HIST_DIR, f"{jornada}.json"), payload)

    print(
        f"\nListo: jornada {jornada}, {len(teams)} equipos "
        f"(futbolfantasy {len(ff)}, analiticafantasy {len(af)}), {discrepancies} discrepancias.",
        file=sys.stderr,
    )
    if problems:
        print(f"\n{len(problems)} avisos:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)


if __name__ == "__main__":
    main()
