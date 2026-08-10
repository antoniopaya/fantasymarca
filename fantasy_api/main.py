"""
Genera en webapp/public/data/ todos los JSON que consume la webapp.

Pensado para ejecutarse a mano de vez en cuando (1-2 veces por semana, cuando
se jueguen partidos), no en cada visita: la webapp se compila como sitio
100% estático y solo lee estos archivos, sin llamar nunca a fantasy.marca.com
en producción. Todo lo que necesita curl_cffi/Cloudflare pasa por aquí,
offline, en tu máquina.

Escribe:
  teams.json          catálogo de equipos
  gameweeks.json       catálogo de jornadas de la temporada
  players.json         catálogo de jugadores (id/nombre/slug/equipo/posición)
  matches/<n>.json     partidos de la jornada n
  players/<id>.json    ficha completa (valor, cláusula, bio, calendario...) de cada jugador

Uso:
    python main.py
"""

import json
import os
import re
import sys
import time
import unicodedata

import client

WEBAPP_DATA_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "webapp", "public", "data"
)

SEED_GAMEWEEK_ID = 3968
REQUEST_DELAY_SECONDS = 0.2  # cortesía con el servidor entre llamada y llamada


def slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()


def write_json(relative_path: str, payload) -> None:
    path = os.path.join(WEBAPP_DATA_DIR, relative_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def fetch_gameweeks_and_teams():
    """Una sola llamada a /gameweek trae las 38 jornadas y (via sus partidos) los 20 equipos."""
    data = client.call("gameweek", id=SEED_GAMEWEEK_ID, slug="x", comments=0)["data"]

    gameweeks = [
        {
            "id": gw["id"],
            "number": gw["gameweek"],
            "name": f"Jornada {gw['gameweek']}",
            "season": gw["season"],
            "status": gw["status"],
        }
        for gw in data["gameweeks"]
    ]

    teams_by_id = {}
    for game in data["games"]:
        for id_key, name_key in (("id_home", "home"), ("id_away", "away")):
            team_id = game[id_key]
            name = game[name_key]
            teams_by_id[team_id] = {"id": team_id, "name": name, "slug": slugify(name)}

    teams = sorted(teams_by_id.values(), key=lambda t: t["id"])
    return gameweeks, teams


def fetch_all_matches(gameweeks) -> None:
    print(f"Descargando partidos de {len(gameweeks)} jornadas...", file=sys.stderr)
    for gw in gameweeks:
        data = client.call("gameweek", id=gw["id"], slug="x", comments=0)["data"]
        write_json(f"matches/{gw['number']}.json", data["games"])
        time.sleep(REQUEST_DELAY_SECONDS)
    print("  jornadas listas", file=sys.stderr)


def fetch_all_players(teams) -> list:
    print(f"Descargando plantillas de {len(teams)} equipos...", file=sys.stderr)
    catalog = []
    for team in teams:
        data = client.call("teams", id=team["id"], slug=team["slug"], comments=0)["data"]
        for p in data["players"]:
            catalog.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "slug": slugify(p["name"]),
                    "position": p["position"],
                    "id_team": p["id_team"],
                    "team_name": team["name"],
                }
            )
        time.sleep(REQUEST_DELAY_SECONDS)
    catalog.sort(key=lambda p: p["id"])

    print(f"Descargando fichas de {len(catalog)} jugadores...", file=sys.stderr)
    for i, p in enumerate(catalog, start=1):
        detail = client.call("players", id=p["id"], slug=p["slug"], comments=0)["data"]
        write_json(f"players/{p['id']}.json", detail)
        if i % 50 == 0 or i == len(catalog):
            print(f"  {i}/{len(catalog)} jugadores", file=sys.stderr)
        time.sleep(REQUEST_DELAY_SECONDS)

    return catalog


def main() -> None:
    print("Obteniendo jornadas y equipos...", file=sys.stderr)
    gameweeks, teams = fetch_gameweeks_and_teams()
    write_json("gameweeks.json", gameweeks)
    write_json("teams.json", teams)
    print(f"  {len(gameweeks)} jornadas, {len(teams)} equipos", file=sys.stderr)

    fetch_all_matches(gameweeks)

    players = fetch_all_players(teams)
    write_json("players.json", players)

    print(f"\nListo. {len(players)} jugadores. Datos generados en {WEBAPP_DATA_DIR}", file=sys.stderr)


if __name__ == "__main__":
    main()
