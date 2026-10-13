"""
Descarga el desglose de puntos de cada jugador en cada jornada ->
../webapp/data/player_stats/<n>.json

Marca puntúa con "Marca Stats": minutos, goles, asistencias, goles encajados,
paradas, pases clave, regates, tiros a puerta, intercepciones, despejes,
balones perdidos, tarjetas, penaltis... más la valoración en estrellas de
Marca. El endpoint /ajax/player-gameweek da, para un jugador y una jornada,
cuántos puntos sacó de cada una (y estadísticas de Sofascore como el xG).

Es incremental: solo pide los partidos de jugador con puntos que aún no estén
guardados, o cuyos puntos ya no coincidan con los de su ficha (Marca corrigió
después). Tras el backfill inicial son unas 280 peticiones por jornada.

Formato de cada fichero (id de jugador -> partido):
    {"points": 10, "min": 90, "xg": 0.0, "xa": 0.0, "ss": 7.9,
     "c": {"minutesPlayed": [90, 2], "goalsAgainst": [0, 4], "saves": [4, 2], ...}}
"c" = componente de la puntuación -> [valor de la estadística, puntos que da];
solo los que no son cero. Si Marca no da desglose, "c" es null.

Uso:
    python player_stats.py
"""

import glob
import json
import os
import sys
import time

import client

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webapp", "data")
OUT_DIR = os.path.join(DATA_DIR, "player_stats")
REQUEST_DELAY_SECONDS = 0.4


def _json_field(data: dict, key: str) -> dict:
    try:
        value = json.loads(data.get(key) or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}  # sin datos llega "[]"


def _num(x: float) -> float | int:
    return int(x) if float(x).is_integer() else round(x, 3)


def compact(data: dict) -> dict:
    """De la respuesta de player-gameweek a lo que guarda la web."""
    stats = _json_field(data, "stats")
    components = {}
    for key, item in _json_field(data, "marca_stats_rating_detailed_filtered").items():
        value = item.get("value") or 0
        rating = float(item.get("rating") or 0)
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0
        if value or rating:
            components[key] = [_num(value), _num(rating)]
    return {
        "points": data.get("points"),
        "min": stats.get("minutesPlayed") or 0,
        "xg": round(stats.get("expectedGoals") or 0, 3),
        "xa": round(stats.get("expectedAssists") or 0, 3),
        "ss": data.get("rating_ss"),
        "c": components,
    }


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(payload.items(), key=lambda kv: int(kv[0]))), f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def pending() -> list[tuple[int, int, int]]:
    """(jornada, id jugador, puntos en su ficha) de lo que falta o ha cambiado."""
    stored = {}
    todo = []
    for path in glob.glob(os.path.join(DATA_DIR, "players", "*.json")):
        with open(path, encoding="utf-8") as f:
            detail = json.load(f)
        pid = detail["player"]["id"]
        for g in detail["points"]:
            points = g["points"]["points"]
            if points is None or g["points"].get("isLive"):
                continue
            n = g["number"]
            if n not in stored:
                stored[n] = load(os.path.join(OUT_DIR, f"{n}.json"))
            entry = stored[n].get(str(pid))
            if entry is None or entry.get("points") != points:
                todo.append((n, pid, points))
    return sorted(todo)


def main() -> None:
    with open(os.path.join(DATA_DIR, "gameweeks.json"), encoding="utf-8") as f:
        gameweek_ids = {g["number"]: g["id"] for g in json.load(f)}
    todo = pending()
    print(f"Desglose de puntos: {len(todo)} partidos de jugador por descargar", file=sys.stderr)
    files: dict[int, dict] = {}
    skipped = 0
    for i, (n, pid, points) in enumerate(todo, start=1):
        if n not in files:
            files[n] = load(os.path.join(OUT_DIR, f"{n}.json"))
        response = client.post_ajax("player-gameweek", {"id_gameweek": gameweek_ids[n], "id_player": pid})
        body = response.json()
        if body.get("status") == "ok" and body.get("data"):
            files[n][str(pid)] = compact(body["data"])
        else:
            # "No ha puntuado" (p.ej. un aplazado que Marca dio por jugado): se
            # apunta sin desglose para no volver a pedirlo mientras no cambie.
            files[n][str(pid)] = {"points": points, "c": None}
            skipped += 1
        if i % 100 == 0:
            for m, payload in files.items():
                save(os.path.join(OUT_DIR, f"{m}.json"), payload)
            print(f"  {i}/{len(todo)}", file=sys.stderr)
        time.sleep(REQUEST_DELAY_SECONDS)
    for n, payload in files.items():
        save(os.path.join(OUT_DIR, f"{n}.json"), payload)
    print(f"Listo: {len(todo) - skipped} guardados, {skipped} sin desglose.", file=sys.stderr)


if __name__ == "__main__":
    main()
