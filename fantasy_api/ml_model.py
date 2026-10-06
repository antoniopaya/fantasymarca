"""
Modelo de puntos esperados por jugador y jornada -> ../webapp/data/predicciones.json

Dos partes:
  1. P(juega): probabilidad de sumar puntos esa jornada (clasificación).
  2. Puntos si juega: regresión entrenada solo con las jornadas que jugó.
  Puntos esperados = P(juega) x puntos si juega.

Se prueban dos familias de modelos de scikit-learn y se queda la que mejor
valida (ver más abajo): lineal (logística + ridge, con imputación y
escalado; la mejor con pocas jornadas) y boosting (HistGradientBoosting
muy regularizado, que debería ir ganando cuando haya más temporada).

Cada fila es (jugador, jornada g) y sus variables se calculan SOLO con lo
que se sabía antes de g (jornadas anteriores, partidos ya jugados antes
del primero de g), para no hacer trampas con información del futuro:
posición, precio Fantástica, temporada pasada, medias/forma/titularidades
previas, goles y asistencias previas, fuerza del equipo y del rival
(puntos, goles a favor y en contra por partido) y si juega en casa.

Alineaciones probables (scrape_alineaciones.py): para la jornada a predecir
se combinan con P(juega) del modelo. Cuando haya al menos 2 jornadas con
alineaciones guardadas en alineaciones_hist/, la probabilidad de futbolfantasy
entra además como variable del modelo y aprende su peso sola.

Validación: "origen móvil". Para cada jornada k ya jugada (desde la 4), se
entrena con las anteriores y se predice k; se compara con dos referencias
(la media previa del jugador y la fórmula sencilla que usaba la web) en
error medio y en puntos reales de los 50 mejor predichos, que es lo que
importa para elegir jugadores. Los resultados van en el JSON y se muestran
en la web.

Uso:
    python ml_model.py
"""

import glob
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA_DIR = os.path.join(ROOT, "webapp", "data")
SHRINK = 3  # partidos "de media" con los que se encoge la fuerza de cada equipo
MIN_TRAIN_GW = 3  # jornadas mínimas de historia antes de validar
SEED = 0

FEATURES = [
    "position",
    "price",
    "ls_avg",
    "ls_points",
    "n_prev",
    "play_rate",
    "start_rate",
    "mean_played",
    "mean_all",
    "last1",
    "last3",
    "std_played",
    "goals_pg",
    "assists_pg",
    "team_ppg",
    "team_gf",
    "team_ga",
    "rival_ppg",
    "rival_gf",
    "rival_ga",
    "home",
]
FF_FEATURE = "ff_prob"


def load_json(*parts):
    with open(os.path.join(DATA_DIR, *parts), encoding="utf-8") as f:
        return json.load(f)


# --- Datos base -----------------------------------------------------------------


def load_matches():
    """Lista de partidos con jornada, equipos, goles, estado y fecha."""
    rows = []
    for path in glob.glob(os.path.join(DATA_DIR, "matches", "*.json")):
        gw = int(os.path.basename(path).split(".")[0])
        for m in load_json("matches", os.path.basename(path)):
            rows.append(
                {
                    "gw": gw,
                    "home": m["id_home"],
                    "away": m["id_away"],
                    "gh": m["goals_home"] if m["status"] == "played" else None,
                    "ga": m["goals_away"] if m["status"] == "played" else None,
                    "played": m["status"] == "played",
                    "ts": m["date"]["ts"],
                }
            )
    return pd.DataFrame(rows)


def team_strength_before(matches: pd.DataFrame, ts: float) -> dict:
    """Fuerza de cada equipo con los partidos jugados antes de `ts`."""
    done = matches[matches.played & (matches.ts < ts)]
    stats: dict[int, dict] = {}
    for team in set(matches.home) | set(matches.away):
        stats[team] = {"n": 0, "pts": 0, "gf": 0, "ga": 0}
    for m in done.itertuples():
        gh, ga = int(m.gh), int(m.ga)
        for team, f, a in ((m.home, gh, ga), (m.away, ga, gh)):
            s = stats[team]
            s["n"] += 1
            s["gf"] += f
            s["ga"] += a
            s["pts"] += 3 if f > a else 1 if f == a else 0
    total_n = sum(s["n"] for s in stats.values())
    avg_g = sum(s["gf"] for s in stats.values()) / total_n if total_n else 1.3
    avg_p = sum(s["pts"] for s in stats.values()) / total_n if total_n else 1.4
    return {
        t: {
            "ppg": (s["pts"] + SHRINK * avg_p) / (s["n"] + SHRINK),
            "gf": (s["gf"] + SHRINK * avg_g) / (s["n"] + SHRINK),
            "ga": (s["ga"] + SHRINK * avg_g) / (s["n"] + SHRINK),
        }
        for t, s in stats.items()
    }


def load_players(current_season: str):
    catalog = load_json("players.json")
    prices = load_json("precios_fantastica.json")
    players = []
    for p in catalog:
        try:
            detail = load_json("players", f"{p['id']}.json")
        except FileNotFoundError:
            continue
        last = next((h for h in detail["points_history"] if h["season"] != current_season), None)
        players.append(
            {
                "id": p["id"],
                "team": p["id_team"],
                "position": p["position"],
                "price": prices.get(str(p["id"])),
                "status": detail["player"]["status"],
                "ls_avg": last["avg"] if last else np.nan,
                "ls_points": last["points"] if last else np.nan,
                "gws": {
                    g["number"]: {
                        "points": g["points"]["points"],
                        "team_played": g.get("teamPlayed"),
                        "events": g.get("events") or [],
                    }
                    for g in detail["points"]
                },
            }
        )
    return players


def load_ff_history() -> dict[int, dict[int, int]]:
    """jornada -> {id Marca: probabilidad de titular (0-100)}."""
    out: dict[int, dict[int, int]] = {}
    for path in glob.glob(os.path.join(DATA_DIR, "alineaciones_hist", "*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("jornada"):
            continue
        out[data["jornada"]] = {
            p["id"]: p["prob"] for team in data["teams"].values() for p in team if p.get("id") is not None
        }
    return out


# --- Variables ------------------------------------------------------------------


def player_history_features(pl: dict, gw: int) -> dict:
    prev = [pl["gws"][g] for g in sorted(pl["gws"]) if g < gw and pl["gws"][g]["team_played"]]
    played = [g for g in prev if g["points"] is not None]
    pts_all = [g["points"] or 0 for g in prev]
    pts_played = [g["points"] for g in played]
    started = [g for g in played if "sub_in" not in g["events"]]
    goals = sum(g["events"].count("goal") for g in played)
    assists = sum(g["events"].count("assist") for g in played)
    n = len(prev)
    return {
        "n_prev": n,
        "play_rate": len(played) / n if n else np.nan,
        "start_rate": len(started) / n if n else np.nan,
        "mean_played": float(np.mean(pts_played)) if pts_played else np.nan,
        "mean_all": float(np.mean(pts_all)) if pts_all else np.nan,
        "last1": pts_all[-1] if pts_all else np.nan,
        "last3": float(np.sum(pts_all[-3:])) if pts_all else np.nan,
        "std_played": float(np.std(pts_played)) if len(pts_played) > 1 else np.nan,
        "goals_pg": goals / len(played) if played else np.nan,
        "assists_pg": assists / len(played) if played else np.nan,
    }


def build_rows(players, matches, gws, ff_hist):
    rows = []
    for gw in gws:
        gw_matches = matches[matches.gw == gw]
        if gw_matches.empty:
            continue
        strength = team_strength_before(matches, gw_matches.ts.min())
        fixture = {}
        for m in gw_matches.itertuples():
            fixture[m.home] = (m.away, 1, m.played)
            fixture[m.away] = (m.home, 0, m.played)
        for pl in players:
            if pl["team"] not in fixture:
                continue  # su equipo no juega (o el partido está aplazado)
            rival, home, _ = fixture[pl["team"]]
            target = pl["gws"].get(gw, {})
            row = {
                "id": pl["id"],
                "gw": gw,
                "position": pl["position"],
                "price": pl["price"] if pl["price"] is not None else np.nan,
                "ls_avg": pl["ls_avg"],
                "ls_points": pl["ls_points"],
                **player_history_features(pl, gw),
                "team_ppg": strength[pl["team"]]["ppg"],
                "team_gf": strength[pl["team"]]["gf"],
                "team_ga": strength[pl["team"]]["ga"],
                "rival_ppg": strength[rival]["ppg"],
                "rival_gf": strength[rival]["gf"],
                "rival_ga": strength[rival]["ga"],
                "home": home,
                FF_FEATURE: ff_hist.get(gw, {}).get(pl["id"], np.nan),
                "team_played": bool(target.get("team_played")),
                "y_points": target.get("points"),
            }
            rows.append(row)
    df = pd.DataFrame(rows)
    df["y_played"] = df.y_points.notna()
    df["y_total"] = df.y_points.fillna(0)
    return df


# --- Modelos y referencias -------------------------------------------------------


def _linear(model):
    return make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(), model)


MODEL_FAMILIES = {
    "lineal": (
        lambda: _linear(LogisticRegression(C=0.3, max_iter=2000)),
        lambda: _linear(Ridge(alpha=10)),
    ),
    "boosting": (
        lambda: HistGradientBoostingClassifier(
            max_iter=120, learning_rate=0.04, max_depth=3, min_samples_leaf=40, l2_regularization=2.0, random_state=SEED
        ),
        lambda: HistGradientBoostingRegressor(
            max_iter=150, learning_rate=0.04, max_depth=3, min_samples_leaf=40, l2_regularization=2.0, random_state=SEED
        ),
    ),
}


def fit(train: pd.DataFrame, features: list[str], family: str):
    make_clf, make_reg = MODEL_FAMILIES[family]
    clf = make_clf().fit(train[features], train.y_played)
    played = train[train.y_played]
    reg = make_reg().fit(played[features], played.y_points)
    return clf, reg


def predict(models, df: pd.DataFrame, features: list[str]):
    clf, reg = models
    p_play = clf.predict_proba(df[features])[:, 1]
    if_plays = np.clip(reg.predict(df[features]), -2, None)
    return p_play, if_plays


def baseline_mean(df):
    return df.mean_all.fillna(df.ls_avg * 0.5).fillna(0).to_numpy()


def baseline_formula(df):
    """La fórmula que usaba la web: 0.6 media + 0.4 forma, ajustada por rival y casa."""
    base = 0.6 * df.mean_played.fillna(df.ls_avg).fillna(0) + 0.4 * (df.last3.fillna(0) / 3)
    rel = np.where(df.position <= 2, df.rival_gf, 2.6 - df.rival_ga)
    factor = 1 - 0.25 * (rel - np.nanmean(rel)) / (np.nanstd(rel) or 1)
    return (base * np.clip(factor, 0.75, 1.25) * np.where(df.home == 1, 1.05, 0.95)).to_numpy()


def evaluate(df: pd.DataFrame, features: list[str]):
    results = []
    played_gws = sorted(df[df.team_played].gw.unique())
    for k in played_gws:
        train = df[(df.gw < k) & df.team_played]
        test = df[(df.gw == k) & df.team_played]
        if train.gw.nunique() < MIN_TRAIN_GW or test.empty:
            continue
        preds = {}
        for family in MODEL_FAMILIES:
            p, s = predict(fit(train, features, family), test, features)
            preds[family] = p * s
        preds["media_previa"] = baseline_mean(test)
        preds["formula_web"] = baseline_formula(test)
        y = test.y_total.to_numpy()
        row = {"jornada": int(k), "n": int(len(test))}
        for name, pred in preds.items():
            top = np.argsort(-pred)[:50]
            row[name] = {
                "mae": round(float(np.mean(np.abs(pred - y))), 3),
                "top50": round(float(np.mean(y[top])), 2),
            }
        results.append(row)
    return results


def summarize(results):
    if not results:
        return {}
    out = {}
    for name in (*MODEL_FAMILIES, "media_previa", "formula_web"):
        out[name] = {
            "mae": round(float(np.mean([r[name]["mae"] for r in results])), 3),
            "top50": round(float(np.mean([r[name]["top50"] for r in results])), 2),
        }
    return out


def blend_with_lineups(p_model: np.ndarray, ff_prob: np.ndarray) -> np.ndarray:
    """Mientras el modelo no tenga historia de alineaciones para aprender su
    peso: 70% futbolfantasy (sabe de lesiones y rotaciones de esta semana),
    30% lo que dice la historia del jugador. Un 0% de futbolfantasy (baja,
    descartado) manda casi del todo."""
    ff = ff_prob / 100
    blended = 0.7 * ff + 0.3 * p_model
    blended = np.where(ff_prob == 0, 0.03, blended)
    return np.where(np.isnan(ff_prob), p_model, blended)


def main() -> None:
    gameweeks = load_json("gameweeks.json")
    season = gameweeks[0]["season"]
    matches = load_matches()

    # Próxima jornada: la primera con partidos pendientes (igual que la web,
    # sin contar aplazados de jornadas anteriores).
    pending = matches[~matches.played]
    next_gw = int(pending.gw.min()) if not pending.empty else int(matches.gw.max())
    later = pending[pending.gw > next_gw]
    if not later.empty:
        stragglers = pending[(pending.gw == next_gw) & (pending.ts > later.ts.min())]
        if len(stragglers) == len(pending[pending.gw == next_gw]):
            next_gw = int(later.gw.min())

    players = load_players(season)
    ff_hist = load_ff_history()
    try:
        lineups = load_json("alineaciones.json")
    except FileNotFoundError:
        lineups = None
    ff_now = {}
    if lineups and lineups.get("jornada") == next_gw:
        ff_now = {p["id"]: p for team in lineups["teams"].values() for p in team if p.get("id") is not None}
        ff_hist.setdefault(next_gw, {pid: p["prob"] for pid, p in ff_now.items()})

    df = build_rows(players, matches, range(1, next_gw + 1), ff_hist)
    history_gws = df[(df.gw < next_gw) & df[FF_FEATURE].notna()].gw.nunique()
    use_ff_feature = history_gws >= 2
    features = FEATURES + ([FF_FEATURE] if use_ff_feature else [])
    print(
        f"Filas: {len(df)} · jornada a predecir: {next_gw} · "
        f"alineaciones como variable: {'sí' if use_ff_feature else f'no ({history_gws} jornadas de historia)'}",
        file=sys.stderr,
    )

    validation = evaluate(df, features)
    summary = summarize(validation)
    # Se queda la familia con menor error medio en la validación.
    family = min(MODEL_FAMILIES, key=lambda f: summary[f]["mae"]) if summary else "lineal"
    for name, m in summary.items():
        print(f"  {name:13} MAE {m['mae']:.3f} · top-50 {m['top50']:.2f}", file=sys.stderr)
    print(f"  -> modelo elegido: {family}", file=sys.stderr)

    train = df[(df.gw < next_gw) & df.team_played]
    target = df[df.gw == next_gw].copy()
    models = fit(train, features, family)
    p_model, if_plays = predict(models, target, features)
    target["p_model"] = p_model
    target["if_plays"] = if_plays
    ff_prob = target["id"].map(lambda i: ff_now[i]["prob"] if i in ff_now else np.nan).to_numpy(dtype=float)
    status = target["id"].map({p["id"]: p["status"] for p in players})
    p_play = p_model if use_ff_feature else blend_with_lineups(p_model, ff_prob)
    # Sin dato de futbolfantasy, el estado de Marca (lesión/sanción) manda.
    out_status = status.isin(["injury", "red", "other"]).to_numpy() & np.isnan(ff_prob)
    p_play = np.where(out_status, 0.0, p_play)
    p_play = np.where(status.eq("doubt").to_numpy() & np.isnan(ff_prob), p_play * 0.5, p_play)
    target["p_play"] = p_play
    target["xp"] = p_play * target["if_plays"]

    players_out = {}
    for r in target.itertuples():
        ff = ff_now.get(r.id)
        players_out[str(r.id)] = {
            "xp": round(float(r.xp), 2),
            "p_play": round(float(r.p_play), 3),
            "if_plays": round(float(r.if_plays), 2),
            "ff_prob": ff["prob"] if ff else None,
            "ff_status": ff["status"] if ff else None,
        }

    payload = {
        "jornada": next_gw,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "model": family,
        "n_train": int(len(train)),
        "train_gameweeks": int(train.gw.nunique()),
        "uses_lineups_as_feature": use_ff_feature,
        "lineups_jornada": lineups.get("jornada") if lineups else None,
        "validation": validation,
        "validation_summary": summary,
        "players": players_out,
    }
    with open(os.path.join(DATA_DIR, "predicciones.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)
        f.write("\n")

    top = target.sort_values("xp", ascending=False).head(10)
    names = {p["id"]: p["name"] for p in load_json("players.json")}
    print(f"\nPredicciones de la J{next_gw}: {len(players_out)} jugadores. Top 10:", file=sys.stderr)
    for r in top.itertuples():
        ff = ff_now.get(r.id)
        print(
            f"  {names.get(r.id, r.id):24} xp {r.xp:5.2f} = P {r.p_play:.2f} x {r.if_plays:5.2f}"
            f"  (ff {ff['prob'] if ff else '-'}%)",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
