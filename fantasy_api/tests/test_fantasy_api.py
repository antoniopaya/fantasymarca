"""Tests de lo que se puede probar sin red ni credenciales."""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import client  # noqa: E402
import main  # noqa: E402
import ml_model  # noqa: E402
import name_matching  # noqa: E402


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(client.time, "sleep", lambda _s: None)


def _fake_post(outcomes):
    calls = []

    def post(url, headers, data, impersonate):
        calls.append(url)
        outcome = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)

    return post, calls


def test_reintenta_tras_un_corte_de_conexion(monkeypatch):
    post, calls = _fake_post([client.requests.exceptions.ConnectionError("reset"), 200])
    monkeypatch.setattr(client.requests, "post", post)
    assert client._send("u", {}, {}).status_code == 200
    assert len(calls) == 2


def test_reintenta_los_5xx_y_acaba_devolviendo_el_ultimo(monkeypatch):
    post, calls = _fake_post([503])
    monkeypatch.setattr(client.requests, "post", post)
    assert client._send("u", {}, {}).status_code == 503
    assert len(calls) == client.RETRIES + 1


def test_no_reintenta_un_403(monkeypatch):
    post, calls = _fake_post([403])
    monkeypatch.setattr(client.requests, "post", post)
    assert client._send("u", {}, {}).status_code == 403
    assert len(calls) == 1


def test_si_siempre_se_corta_la_conexion_lanza_el_error(monkeypatch):
    post, calls = _fake_post([client.requests.exceptions.ConnectionError("reset")])
    monkeypatch.setattr(client.requests, "post", post)
    with pytest.raises(client.requests.exceptions.ConnectionError):
        client._send("u", {}, {})
    assert len(calls) == client.RETRIES + 1


def test_borra_solo_las_fichas_huerfanas(tmp_path, monkeypatch):
    folder = tmp_path / "players"
    folder.mkdir()
    for name in ("1.json", "2.json", "3.json", "notas.txt"):
        (folder / name).write_text("{}")
    monkeypatch.setattr(main, "WEBAPP_DATA_DIR", str(tmp_path))
    main.remove_orphan_players({1, 3})
    assert sorted(os.listdir(folder)) == ["1.json", "3.json", "notas.txt"]


def test_margen_crece_con_la_duda_de_jugar():
    pos = pd.Series([3, 3, 3])
    sd = {1: 3.0, 2: 3.0, 3: 3.0, 4: 3.0}
    fijo, dudoso, baja = ml_model.spread(np.array([0.99, 0.5, 0.0]), np.array([6.0, 6.0, 6.0]), pos, sd)
    assert dudoso > fijo > 0
    assert baja == 0  # quien seguro no juega no tiene margen


def test_margen_de_quien_juega_seguro_es_el_de_su_posicion():
    out = ml_model.spread(np.array([1.0]), np.array([5.0]), pd.Series([4]), {1: 2.0, 2: 2.0, 3: 2.0, 4: 3.5})
    assert out[0] == pytest.approx(3.5)


def test_residual_sd_usa_la_media_cuando_faltan_datos():
    residuals = {1: [1.0] * 40 + [-1.0] * 40, 2: [5.0, -5.0]}
    sd = ml_model.residual_sd(residuals)
    assert sd[1] == pytest.approx(1.0)
    assert sd[2] == sd[3] == sd[4] == pytest.approx(np.std(residuals[1] + residuals[2]))


@pytest.mark.parametrize(
    "excel, catalog, expected_best",
    [
        (["fermin", "l."], ["fermin", "lopez"], True),
        (["javi", "hdez."], ["javi", "hernandez"], True),
        (["javi", "hdez"], ["unai", "simon"], False),
    ],
)
def test_emparejado_de_nombres(excel, catalog, expected_best):
    score = name_matching.token_score(name_matching.normalize_tokens(" ".join(excel)), catalog)
    assert (score >= 0.8) is expected_best


def test_normaliza_abreviaturas_y_tildes():
    assert name_matching.normalize_tokens("Fermín L.") == ["fermin", "l"]
    assert name_matching.normalize_tokens("Javi Hdez.") == ["javi", "hernandez"]


def test_calibracion_del_margen_cubre_lo_pedido():
    rng = np.random.default_rng(0)
    n = 4000
    position = np.full(n, 3)
    p_play = np.full(n, 0.9)
    if_plays = np.full(n, 5.0)
    y = np.where(rng.random(n) < 0.9, 5.0 + rng.normal(0, 3.0, n), 0.0)
    sd_by_pos = {1: 3.0, 2: 3.0, 3: 3.0, 4: 3.0}
    scale = ml_model.calibrate_spread([(position, y, p_play, if_plays)], sd_by_pos, coverage=0.68)
    sd = scale * ml_model.spread(p_play, if_plays, pd.Series(position), sd_by_pos)
    covered = float(np.mean(np.abs(y - p_play * if_plays) <= sd))
    assert covered == pytest.approx(0.68, abs=0.02)
