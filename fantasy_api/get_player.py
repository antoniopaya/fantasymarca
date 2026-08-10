"""
Consulta el endpoint de jugadores de Fantasy Marca (/ajax/sw/players).

Uso:
    python get_player.py                # usa los valores por defecto (id/slug de ejemplo)
    python get_player.py 33734 abde-ezzalzouli

Ver client.py y auth_store.py para más detalles sobre autenticación y por qué
se usa curl_cffi en lugar de requests.
"""

import json
import os
import sys

import client

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def main() -> None:
    player_id = sys.argv[1] if len(sys.argv) > 1 else "33734"
    slug = sys.argv[2] if len(sys.argv) > 2 else "abde-ezzalzouli"

    data = client.call("players", id=player_id, slug=slug, comments=0)
    text = json.dumps(data, indent=2, ensure_ascii=False)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"player_{player_id}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    print(f"\nGuardado en {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
