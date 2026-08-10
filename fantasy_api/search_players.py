"""
Busca/filtra jugadores en Fantasy Marca (/ajax/sw/players, modo búsqueda).

A diferencia de get_player.py (que pide UN jugador por id/slug), esta llamada
usa post=players junto con un diccionario de filtros para listar y paginar
jugadores, igual que hace el buscador de la web (mercado, fichajes, etc.).

Uso:
    python search_players.py                    # sin filtros, primera página
    python search_players.py --name messi
    python search_players.py --team 15 --position 4
    python search_players.py --offset 20 --order 2

--team usa los ids de data/teams.json, --position usa el mismo código que el
campo "position" de data/players.json (0 = todas las posiciones).
"""

import argparse
import json
import os
import re
import sys

import client

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def search_players(
    name: str = "",
    position: int = 0,
    team: int = 0,
    value_from: int = 0,
    value_to: int = 82400000,
    clause_from: int = 0,
    clause_to: int = 82400000,
    injured: int = 0,
    favs: int = 0,
    owner: int = 0,
    benched: int = 0,
    stealable: int = 0,
    offset: int = 0,
    order: int = 1,
) -> dict:
    payload = {
        "post": "players",
        "filters[position]": position,
        "filters[value_from]": value_from,
        "filters[value_to]": value_to,
        "filters[clause_from]": clause_from,
        "filters[clause_to]": clause_to,
        "filters[team]": team,
        "filters[injured]": injured,
        "filters[favs]": favs,
        "filters[owner]": owner,
        "filters[benched]": benched,
        "filters[stealable]": stealable,
        "offset": offset,
        "order": order,
        "name": name,
        "parentElement": "#fg-content",
    }
    return client.post("players", payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Busca jugadores en Fantasy Marca")
    parser.add_argument("--name", default="", help="Texto a buscar en el nombre del jugador")
    parser.add_argument("--position", type=int, default=0, help="0 = todas las posiciones")
    parser.add_argument("--team", type=int, default=0, help="id de equipo, 0 = todos (ver data/teams.json)")
    parser.add_argument("--value-from", type=int, default=0)
    parser.add_argument("--value-to", type=int, default=82400000)
    parser.add_argument("--clause-from", type=int, default=0)
    parser.add_argument("--clause-to", type=int, default=82400000)
    parser.add_argument("--injured", type=int, default=0)
    parser.add_argument("--favs", type=int, default=0)
    parser.add_argument("--owner", type=int, default=0)
    parser.add_argument("--benched", type=int, default=0)
    parser.add_argument("--stealable", type=int, default=0)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--order", type=int, default=1)
    args = parser.parse_args()

    data = search_players(
        name=args.name,
        position=args.position,
        team=args.team,
        value_from=args.value_from,
        value_to=args.value_to,
        clause_from=args.clause_from,
        clause_to=args.clause_to,
        injured=args.injured,
        favs=args.favs,
        owner=args.owner,
        benched=args.benched,
        stealable=args.stealable,
        offset=args.offset,
        order=args.order,
    )
    text = json.dumps(data, indent=2, ensure_ascii=False)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    suffix = re.sub(r"[^a-zA-Z0-9]+", "-", args.name).strip("-").lower() or f"offset{args.offset}"
    output_path = os.path.join(OUTPUT_DIR, f"search_players_{suffix}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    print(f"\nGuardado en {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
