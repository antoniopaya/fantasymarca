"""
Consulta el endpoint de equipos de Fantasy Marca (/ajax/sw/teams).

Uso:
    python get_team.py                  # usa los valores por defecto (id/slug de ejemplo)
    python get_team.py 14 rayo-vallecano

Ver client.py y auth_store.py para más detalles sobre autenticación y por qué
se usa curl_cffi en lugar de requests.
"""

import json
import os
import sys

import client

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def main() -> None:
    team_id = sys.argv[1] if len(sys.argv) > 1 else "14"
    slug = sys.argv[2] if len(sys.argv) > 2 else "rayo-vallecano"

    data = client.call("teams", id=team_id, slug=slug, comments=0)
    text = json.dumps(data, indent=2, ensure_ascii=False)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, f"team_{team_id}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    print(f"\nGuardado en {output_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
