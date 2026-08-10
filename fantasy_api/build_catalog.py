"""
Construye ../data/{teams,gameweeks,players}.json a partir de la API.

Cómo se obtiene cada catálogo sin tener que adivinar ids uno a uno:
- gameweeks: una sola llamada a /ajax/sw/gameweek devuelve las 38 jornadas
  de la temporada en data.gameweeks.
- teams: esa misma llamada devuelve en data.games los partidos de la
  jornada 1, con id_home/id_away y sus nombres -> los 20 equipos de la liga.
- players: por cada equipo, /ajax/sw/teams devuelve su plantilla completa
  (23 jugadores) en data.players.

El "slug" de cada request es solo cosmético (comprobado empíricamente: la API
devuelve el mismo resultado con cualquier slug, incluso inválido), así que el
slug guardado aquí es una aproximación generada a partir del nombre y puede no
coincidir exactamente con el que usa marca.com para esa entidad.

Uso:
    python build_catalog.py
"""

import json
import os
import re
import sys
import unicodedata

import client

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")

SEED_GAMEWEEK_ID = 3968
SEED_GAMEWEEK_SLUG = "37162"


def slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug


def build_gameweeks_and_teams():
    data = client.call("gameweek", id=SEED_GAMEWEEK_ID, slug=SEED_GAMEWEEK_SLUG, comments=0)["data"]

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


def build_players(teams):
    players = []
    for team in teams:
        data = client.call("teams", id=team["id"], slug=team["slug"], comments=0)["data"]
        for p in data["players"]:
            players.append(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "slug": slugify(p["name"]),
                    "position": p["position"],
                    "id_team": p["id_team"],
                    "team_name": team["name"],
                }
            )
        print(f"  {team['name']}: {len(data['players'])} jugadores", file=sys.stderr)
    players.sort(key=lambda p: p["id"])
    return players


def main() -> None:
    print("Obteniendo jornadas y equipos...", file=sys.stderr)
    gameweeks, teams = build_gameweeks_and_teams()

    print(f"Obteniendo plantillas de {len(teams)} equipos...", file=sys.stderr)
    players = build_players(teams)

    os.makedirs(DATA_DIR, exist_ok=True)
    for filename, payload in (
        ("gameweeks.json", gameweeks),
        ("teams.json", teams),
        ("players.json", players),
    ):
        path = os.path.join(DATA_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Guardado {path} ({len(payload)} entradas)", file=sys.stderr)


if __name__ == "__main__":
    main()
