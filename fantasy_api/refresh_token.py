"""
Refresca las credenciales de la API de Fantasy Marca.

No existe un endpoint dedicado a "refrescar token": cualquier llamada
autenticada, con el `refresh-token` guardado en auth_store.json, hace que el
servidor emita (via Set-Cookie) un nuevo access token y un refresh-token
rotado. Este script hace una llamada mínima solo para disparar esa rotación y
persistir el resultado en auth_store.json.

Uso:
    python refresh_token.py
"""

import sys

import auth_store
import client


def main() -> None:
    before = auth_store.load()["refresh_token"]

    try:
        client.call("players", id="33734", slug="abde-ezzalzouli", comments=0)
    except Exception as e:
        if "401" in str(e):
            print(
                "401 Unauthorized: el x-auth o el refresh-token guardados ya no son válidos.\n"
                "Hay que recapturarlos manualmente desde las DevTools del navegador y "
                "actualizarlos en auth_store.json.",
                file=sys.stderr,
            )
            sys.exit(1)
        raise

    after = auth_store.load()["refresh_token"]
    if after != before:
        print("Credenciales válidas. refresh-token rotado y guardado en auth_store.json.")
    else:
        print("Credenciales válidas. El servidor no ha devuelto un refresh-token nuevo (se mantiene el actual).")


if __name__ == "__main__":
    main()
