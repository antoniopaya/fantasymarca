"""
Construye ../webapp/public/data/liga/<n>.json a partir de los PDFs de la liga
Fantástica (../data/Jornadas/*.pdf), uno por jornada.

Los PDFs son la exportación del Excel que lleva la liga (no tenemos el Excel):
una rejilla de fichas, una por participante, con este contenido de arriba abajo:

    [ganadas]  Nombre  [perdidas]
    11 filas "jugador  puntos"   (capitán con fondo amarillo y puntos ya doblados)
    total_anterior  puntos_jornada
    Total  total
    Dif.  Saldo  C               (C = cambios disponibles; en J1 no viene)

Se lee por coordenadas con pdfplumber, anclando cada ficha en su palabra "Total".

El PDF no trae ni id ni equipo de los jugadores, solo nombres abreviados
("Fermín L.", "Javi Hdez."). Para emparejarlos con el catálogo de Marca se
usan dos pistas: el parecido del nombre y que los puntos de cada aparición
coincidan con los que Marca dio a ese jugador en esa jornada (la liga puntúa
con los puntos de Marca). Lo que siga sin resolverse va a LIGA_ALIASES.

Uso:
    python build_liga.py
"""

import glob
import json
import os
import re
import sys

import pdfplumber

from name_matching import normalize_tokens, token_score

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PDF_DIR = os.path.join(ROOT, "data", "Jornadas")
DATA_DIR = os.path.join(ROOT, "webapp", "public", "data")
OUT_DIR = os.path.join(DATA_DIR, "liga")

BUDGET_MILLIONS = 180
MIN_NAME_SCORE = 0.7
NAME_SCORE_MARGIN = 0.15

# Nombre tal cual sale en el PDF -> id de fantasy.marca.com, para los casos
# que el emparejamiento automático no resuelve (o resuelve mal). None = jugador
# que ya no está en el catálogo de Marca (salió de LaLiga): se guarda sin id.
LIGA_ALIASES: dict[str, int | None] = {
    "Affengruber": None,
    "Oso": None,
}

NUM = re.compile(r"^-?\d+(,\d+)?$")


def to_number(text: str) -> float | int:
    return float(text.replace(",", ".")) if "," in text else int(text)


def is_yellow(color) -> bool:
    return isinstance(color, tuple) and len(color) == 3 and color[0] > 0.9 and color[1] > 0.9 and color[2] < 0.3


def group_lines(words: list[dict]) -> list[list[dict]]:
    lines: list[list[dict]] = []
    for w in sorted(words, key=lambda w: w["top"]):
        if lines and w["top"] - lines[-1][0]["top"] < 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def parse_card(anchor: dict, words: list[dict], yellow_rects: list[dict]) -> dict:
    x0 = anchor["x0"] - 6
    x1 = x0 + 72
    card_words = [
        w
        for w in words
        if x0 <= (w["x0"] + w["x1"]) / 2 < x1 and anchor["top"] - 175 < w["top"] < anchor["top"] + 30
    ]
    lines = group_lines(card_words)
    texts = [[w["text"].strip() for w in line] for line in lines]

    header_idx = next(
        i
        for i, t in enumerate(texts)
        if len(t) == 3 and NUM.match(t[0]) and NUM.match(t[2]) and not NUM.match(t[1])
    )
    won, participant, lost = texts[header_idx]

    players = []
    i = header_idx + 1
    while len(players) < 11:
        line = lines[i]
        name_words = [w for w in line if not NUM.match(w["text"].strip())]
        numbers = [w["text"].strip() for w in line if NUM.match(w["text"].strip())]
        if name_words:
            nw = name_words[0]
            captain = any(
                r["x0"] - 1 <= nw["x0"] and nw["x1"] <= r["x1"] + 1 and r["top"] - 1 <= nw["top"] and nw["bottom"] <= r["bottom"] + 1
                for r in yellow_rects
            )
            players.append(
                {
                    "name": " ".join(w["text"].strip() for w in name_words),
                    "points": to_number(numbers[-1]) if numbers else 0,
                    "captain": captain,
                }
            )
        i += 1

    # Tras el 11: "total_anterior puntos" y "Total total", en ese orden.
    prev_total, points, total = [to_number(x) for t in texts[i:] for x in t if NUM.match(x)][:3]

    # Última línea: Dif. / Saldo / C, asignados por columna porque C puede faltar.
    footer = {}
    for w in lines[-1]:
        if NUM.match(w["text"].strip()):
            offset = w["x0"] - anchor["x0"]
            key = "dif" if offset < 20 else "saldo" if offset < 45 else "changes"
            footer[key] = to_number(w["text"].strip())

    return {
        "participant": participant,
        "won": to_number(won),
        "lost": to_number(lost),
        "players": players,
        "points": points,
        "prev_total": prev_total,
        "total": total,
        "dif": footer.get("dif"),
        "saldo": footer.get("saldo"),
        "changes": footer.get("changes"),
    }


def parse_pdf(path: str) -> tuple[int, list[dict]]:
    page = pdfplumber.open(path).pages[0]
    words = page.extract_words(keep_blank_chars=True)
    match = re.search(r"Jornada (\d+)", page.extract_text() or "")
    if not match:
        raise SystemExit(f"{path}: no encuentro el número de jornada en el PDF")
    yellow_rects = [r for r in page.rects if is_yellow(r.get("non_stroking_color"))]
    anchors = [w for w in words if w["text"].strip() == "Total"]
    return int(match.group(1)), [parse_card(a, words, yellow_rects) for a in anchors]


def validate(number: int, entries: list[dict]) -> list[str]:
    errors = []
    for e in entries:
        who = f"J{number} {e['participant']}"
        if len(e["players"]) != 11:
            errors.append(f"{who}: {len(e['players'])} jugadores")
        if sum(1 for p in e["players"] if p["captain"]) != 1:
            errors.append(f"{who}: no hay exactamente un capitán")
        if sum(p["points"] for p in e["players"]) != e["points"]:
            errors.append(f"{who}: la suma de los 11 no da los puntos de la jornada")
        if e["prev_total"] + e["points"] != e["total"]:
            errors.append(f"{who}: total anterior + jornada != total")
    return errors


def base_points(player: dict) -> float:
    if not player["captain"]:
        return player["points"]
    half = player["points"] / 2
    return int(half) if half == int(half) else half


class MarcaPoints:
    def __init__(self):
        self._cache: dict[int, dict[int, int]] = {}

    def get(self, player_id: int, gameweek: int) -> int:
        if player_id not in self._cache:
            with open(os.path.join(DATA_DIR, "players", f"{player_id}.json"), encoding="utf-8") as f:
                detail = json.load(f)
            self._cache[player_id] = {p["number"]: p["points"]["points"] for p in detail["points"]}
        # Sin dato en Marca = no jugó = 0 en la liga.
        return self._cache[player_id].get(gameweek) or 0


def match_names(appearances: dict[str, set[tuple[int, float]]], catalog: list[dict], prices: dict) -> tuple[dict, list[str]]:
    marca = MarcaPoints()
    catalog_tokens = [(p, normalize_tokens(p["name"])) for p in catalog]
    resolved: dict[str, int] = {}
    problems: list[str] = []

    for name, seen in sorted(appearances.items()):
        if name in LIGA_ALIASES:
            if LIGA_ALIASES[name] is not None:
                resolved[name] = LIGA_ALIASES[name]
            continue
        tokens = normalize_tokens(name)
        scored = [(token_score(tokens, c_tokens), p) for p, c_tokens in catalog_tokens]
        scored = [(s, p) for s, p in scored if s >= MIN_NAME_SCORE]
        if not scored:
            problems.append(f"{name}: sin candidatos en el catálogo")
            continue
        # El nombre manda; los puntos solo desempatan entre nombres casi igual de
        # parecidos ("Rodri", "Z. Romero"). Al revés, un "Ceballos" cualquiera que
        # coincidiera en puntos le ganaba a Dani Ceballos.
        top_score = max(s for s, _ in scored)
        ranked = []
        for score, p in scored:
            if score < top_score - NAME_SCORE_MARGIN:
                continue
            agree = sum(1 for gw, pts in seen if marca.get(p["id"], gw) == pts) / len(seen)
            ranked.append((agree, str(p["id"]) in prices, score, p))
        ranked.sort(key=lambda r: r[:3], reverse=True)

        best = ranked[0]
        if len(ranked) == 1:
            # Único candidato con nombre suficientemente parecido: los puntos del
            # PDF pueden diferir en 1 de los de Marca si Marca corrigió después.
            resolved[name] = best[3]["id"]
            continue
        tied = ranked[1][:2] == best[:2] and best[2] - ranked[1][2] < 0.05
        if best[0] < 0.5 or tied:
            options = ", ".join(f"{r[3]['name']} ({r[3]['id']}, {r[3]['team_name']})" for r in ranked[:3])
            problems.append(f"{name}: dudoso -> {options}")
            continue
        resolved[name] = best[3]["id"]
    return resolved, problems


def check_saldo(number: int, entries: list[dict], prices: dict) -> list[str]:
    warnings = []
    for e in entries:
        if e["saldo"] is None or any(p["id"] is None for p in e["players"]):
            continue
        spent = [prices.get(str(p["id"])) for p in e["players"]]
        if None in spent:
            continue
        if BUDGET_MILLIONS - sum(spent) != e["saldo"]:
            warnings.append(
                f"J{number} {e['participant']}: 180 - precios = {BUDGET_MILLIONS - sum(spent)}, el PDF dice saldo {e['saldo']}"
            )
    return warnings


def write_json(path: str, payload) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main() -> None:
    with open(os.path.join(DATA_DIR, "players.json"), encoding="utf-8") as f:
        catalog = json.load(f)
    with open(os.path.join(DATA_DIR, "precios_fantastica.json"), encoding="utf-8") as f:
        prices = json.load(f)

    jornadas: dict[int, list[dict]] = {}
    for path in sorted(glob.glob(os.path.join(PDF_DIR, "*.pdf"))):
        number, entries = parse_pdf(path)
        if number in jornadas:
            raise SystemExit(f"Jornada {number} repetida ({path})")
        jornadas[number] = entries
        print(f"  {os.path.basename(path)}: jornada {number}, {len(entries)} participantes", file=sys.stderr)

    errors = [err for n, entries in jornadas.items() for err in validate(n, entries)]
    if errors:
        raise SystemExit("PDFs con datos incoherentes:\n  " + "\n  ".join(errors))

    appearances: dict[str, set[tuple[int, float]]] = {}
    for n, entries in jornadas.items():
        for e in entries:
            for p in e["players"]:
                appearances.setdefault(p["name"], set()).add((n, base_points(p)))

    resolved, problems = match_names(appearances, catalog, prices)
    for entries in jornadas.values():
        for e in entries:
            for p in e["players"]:
                p["id"] = resolved.get(p["name"])
                # El PDF muestra los puntos del capitán ya doblados; se guardan los base.
                p["points"] = base_points(p)

    warnings = [w for n, entries in jornadas.items() for w in check_saldo(n, entries, prices)]

    for n, entries in sorted(jornadas.items()):
        entries.sort(key=lambda e: -e["total"])
        players_out = [
            {**e, "players": [{"id": p["id"], "name": p["name"], "points": p["points"], "captain": p["captain"]} for p in e["players"]]}
            for e in entries
        ]
        write_json(os.path.join(OUT_DIR, f"{n}.json"), {"number": n, "entries": players_out})

    print(
        f"\nListo: {len(jornadas)} jornadas, {len(resolved)}/{len(appearances)} nombres emparejados "
        f"({sum(1 for v in LIGA_ALIASES.values() if v is None)} sin id a propósito).",
        file=sys.stderr,
    )
    if problems:
        print(f"\n{len(problems)} nombres sin resolver (añádelos a LIGA_ALIASES):", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
    if warnings:
        print(f"\n{len(warnings)} fichas cuyo saldo no cuadra con los precios Fantástica:", file=sys.stderr)
        for w in warnings:
            print(f"  {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
