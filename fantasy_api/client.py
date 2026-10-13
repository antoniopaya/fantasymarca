"""
Cliente HTTP compartido para los endpoints /ajax/sw/* (y algún /ajax/*) de Fantasy Marca.

Usa `curl_cffi` (no `requests` normal) porque Cloudflare bloquea con 403 las
peticiones que no imitan la huella TLS de un navegador real, aunque los
headers sean idénticos a los de Chrome.

Autenticación (comprobado empíricamente quitando cabeceras/cookies una a una):
lo único que la API exige es el header `x-auth` y la cookie `refresh-token`.
El resto de cookies capturadas en el navegador (analítica, marketing,
`cf_clearance`, `token` de acceso, paywall, etc.) no son necesarias. Las
credenciales viven en auth_store.json; cada llamada persiste el
refresh-token rotado que devuelve el servidor.
"""

from curl_cffi import requests

import auth_store

BASE_URL = "https://fantasy.marca.com/ajax/sw"


def post(endpoint: str, payload: dict) -> dict:
    """Llama a /ajax/sw/<endpoint> con un payload de formulario arbitrario."""
    url = f"{BASE_URL}/{endpoint}"

    response = requests.post(url, headers=auth_store.headers(), data=payload, impersonate="chrome")
    response.raise_for_status()
    auth_store.update_from_response(response)
    return response.json()


def post_ajax(path: str, payload: dict) -> requests.Response:
    """Llama a /ajax/<path> (fuera de /sw, p.ej. player-gameweek). Devuelve la
    respuesta sin comprobar el código: algunos endpoints responden 400 con un
    mensaje normal ("El jugador no ha puntuado esta jornada")."""
    headers = auth_store.headers() | {"origin": "https://fantasy.marca.com", "referer": "https://fantasy.marca.com/feed"}
    response = requests.post(f"https://fantasy.marca.com/ajax/{path}", headers=headers, data=payload, impersonate="chrome")
    if response.status_code >= 500 or response.status_code in (401, 403):
        response.raise_for_status()
    auth_store.update_from_response(response)
    return response


def call(endpoint: str, id, slug, comments: int = 0) -> dict:
    """Llama a /ajax/sw/<endpoint> con el payload {post, id, slug, comments}."""
    return post(endpoint, {"post": endpoint, "id": id, "slug": slug, "comments": comments})
