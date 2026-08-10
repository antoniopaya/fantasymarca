"""
Almacén compartido de credenciales para la API de Fantasy Marca.

Guarda `x_auth` y `refresh_token` en auth_store.json. Cada vez que se hace una
llamada autenticada, el servidor devuelve (via Set-Cookie) un refresh_token
"rotado". No es obligatorio guardarlo (el valor original capturado en el
navegador sigue funcionando indefinidamente, Max-Age ~100 años), pero
persistir el más reciente es la práctica más robusta por si en algún momento
el servidor empieza a invalidar los valores antiguos tras rotarlos.
"""

import json
import os

STORE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_store.json")


def load() -> dict:
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save(x_auth: str, refresh_token: str) -> None:
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump({"x_auth": x_auth, "refresh_token": refresh_token}, f, indent=2)
        f.write("\n")


def headers() -> dict:
    creds = load()
    return {
        "x-auth": creds["x_auth"],
        "x-requested-with": "XMLHttpRequest",
        "cookie": f"refresh-token={creds['refresh_token']}",
    }


def update_from_response(response) -> None:
    """Si la respuesta trae un refresh-token rotado, lo persiste."""
    new_refresh_token = response.cookies.get("refresh-token")
    if new_refresh_token:
        creds = load()
        save(creds["x_auth"], new_refresh_token)
