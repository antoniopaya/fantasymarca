#!/usr/bin/env bash
# Actualiza todos los datos de la app y la vuelve a publicar, ejecutando el
# refresco de GitHub Actions (refresh-data.yml) en ESTE ordenador.
#
# Por qué aquí y no en los servidores de GitHub: analiticafantasy.com
# bloquea (403) a los servidores de GitHub, así que sus alineaciones solo
# llegan si el refresco sale desde una conexión normal. Las credenciales de
# Marca siguen en los secrets del repo: no hace falta tenerlas en local.
#
# Qué hace:
#   1. La primera vez, descarga e instala el runner oficial de GitHub
#      Actions en ~/.local/share/fantasymarca-runner (comprobando su SHA-256).
#   2. Conecta el runner solo mientras dura el script (al terminar, o con
#      Ctrl+C, se desconecta): el repo es público y así nunca queda un
#      runner de esta máquina esperando trabajos.
#   3. Lanza refresh-data.yml con runner=local: datos de Marca, alineaciones
#      probables (futbolfantasy + analiticafantasy), modelo y commit.
#   4. Espera al despliegue en GitHub Pages y trae los cambios a este repo.
#
# Requisitos: git, gh (con `gh auth login` hecho), curl, tar, python3.
# Uso: ./actualizar.sh

set -euo pipefail

REPO="antoniopaya/fantasymarca"
LABEL="fantasymarca-local"
RUNNER_DIR="${FANTASYMARCA_RUNNER_DIR:-$HOME/.local/share/fantasymarca-runner}"
RUNNER_NAME="fantasymarca-$(hostname -s)"
SITE="https://antoniopaya.github.io/fantasymarca/"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

paso() { printf '\n\033[1;32m==>\033[0m %s\n' "$*"; }
aviso() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
fallo() {
  printf '\033[1;31mxx\033[0m %s\n' "$*" >&2
  exit 1
}

for cmd in git gh curl tar python3 sha256sum; do
  command -v "$cmd" >/dev/null || fallo "Falta '$cmd'. Instálalo y vuelve a probar."
done
gh auth status >/dev/null 2>&1 || fallo "gh no tiene sesión iniciada: ejecuta 'gh auth login'."

# --- 1. Instalar el runner (solo la primera vez) -----------------------------

instalar_runner() {
  paso "Instalando el runner de GitHub Actions en $RUNNER_DIR (solo la primera vez)"
  mkdir -p "$RUNNER_DIR"
  local version tarball url expected
  version="$(gh api repos/actions/runner/releases/latest -q .tag_name)"
  version="${version#v}"
  tarball="actions-runner-linux-x64-${version}.tar.gz"
  url="https://github.com/actions/runner/releases/download/v${version}/${tarball}"
  # Las notas de cada versión traen el SHA-256 de cada paquete.
  expected="$(gh api repos/actions/runner/releases/latest -q .body |
    sed -n 's/.*<!-- BEGIN SHA linux-x64 -->\([0-9a-f]\{64\}\)<!-- END SHA linux-x64 -->.*/\1/p')"
  [ -n "$expected" ] || fallo "No encuentro el SHA-256 oficial del runner $version."
  curl -fsSL -o "$RUNNER_DIR/$tarball" "$url"
  echo "$expected  $RUNNER_DIR/$tarball" | sha256sum -c --quiet - ||
    fallo "El SHA-256 del runner descargado no coincide: no se instala."
  tar -xzf "$RUNNER_DIR/$tarball" -C "$RUNNER_DIR"
  rm -f "$RUNNER_DIR/$tarball"

  local token
  token="$(gh api -X POST "repos/$REPO/actions/runners/registration-token" -q .token)"
  (cd "$RUNNER_DIR" && ./config.sh --unattended --replace \
    --url "https://github.com/$REPO" --token "$token" \
    --name "$RUNNER_NAME" --labels "$LABEL" --work _work >/dev/null)
  echo "Runner '$RUNNER_NAME' registrado."
}

[ -f "$RUNNER_DIR/.runner" ] || instalar_runner

# --- 2. Conectar el runner mientras dure el script ----------------------------

RUNNER_PID=""
desconectar() {
  if [ -n "$RUNNER_PID" ] && kill -0 "$RUNNER_PID" 2>/dev/null; then
    paso "Desconectando el runner"
    # run.sh lanza el Runner.Listener en su propio grupo de procesos.
    kill -TERM -- "-$RUNNER_PID" 2>/dev/null || kill -TERM "$RUNNER_PID" 2>/dev/null || true
    wait "$RUNNER_PID" 2>/dev/null || true
  fi
}
trap desconectar EXIT
trap 'desconectar; exit 130' INT TERM

estado_runner() {
  gh api "repos/$REPO/actions/runners" \
    -q ".runners[] | select(.name == \"$RUNNER_NAME\") | .status" 2>/dev/null
}

if [ "$(estado_runner)" = "online" ]; then
  aviso "El runner ya estaba conectado (otro ./actualizar.sh en marcha?); se usa ese."
else
  paso "Conectando el runner de este ordenador"
  setsid "$RUNNER_DIR/run.sh" >"$RUNNER_DIR/runner.log" 2>&1 &
  RUNNER_PID=$!
  for _ in $(seq 1 30); do
    [ "$(estado_runner)" = "online" ] && break
    kill -0 "$RUNNER_PID" 2>/dev/null || fallo "El runner se ha cerrado; mira $RUNNER_DIR/runner.log"
    sleep 2
  done
  [ "$(estado_runner)" = "online" ] || fallo "El runner no llega a conectarse; mira $RUNNER_DIR/runner.log"
fi

# --- 3. Lanzar el refresco ---------------------------------------------------------

ultimo_run() { # $1 = workflow; id del run más reciente lanzado a mano después de $DESDE
  gh run list --repo "$REPO" --workflow "$1" --event workflow_dispatch --limit 5 \
    --json databaseId,createdAt \
    -q "[.[] | select(.createdAt >= \"$DESDE\")] | first | .databaseId // empty"
}

paso "Lanzando el refresco de datos (Marca, alineaciones, modelo)"
DESDE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
gh workflow run refresh-data.yml --repo "$REPO" --ref main -f runner=local -f force_deploy=true >/dev/null
RUN_ID=""
for _ in $(seq 1 30); do
  RUN_ID="$(ultimo_run refresh-data.yml)"
  [ -n "$RUN_ID" ] && break
  sleep 2
done
[ -n "$RUN_ID" ] || fallo "No encuentro el refresco que acabo de lanzar."
echo "En marcha (unos 6 minutos): https://github.com/$REPO/actions/runs/$RUN_ID"
gh run watch "$RUN_ID" --repo "$REPO" --exit-status --interval 15 >/dev/null 2>&1 ||
  fallo "El refresco ha fallado: https://github.com/$REPO/actions/runs/$RUN_ID"

gh run view "$RUN_ID" --repo "$REPO" --log 2>/dev/null |
  grep -E "futbolfantasy:|analiticafantasy:|Listo: jornada|modelo elegido" |
  sed 's/^.*Z //' || true

# Ya no hace falta el runner: el despliegue va en los servidores de GitHub.
desconectar
RUNNER_PID=""

# --- 4. Esperar al despliegue ------------------------------------------------------

paso "Esperando al despliegue en GitHub Pages"
DEPLOY_ID=""
for _ in $(seq 1 30); do
  DEPLOY_ID="$(ultimo_run deploy.yml)"
  [ -n "$DEPLOY_ID" ] && break
  sleep 2
done
if [ -n "$DEPLOY_ID" ]; then
  gh run watch "$DEPLOY_ID" --repo "$REPO" --exit-status --interval 10 >/dev/null 2>&1 ||
    fallo "El despliegue ha fallado: https://github.com/$REPO/actions/runs/$DEPLOY_ID"
else
  aviso "No he visto el despliegue; puede que no hubiera cambios que publicar."
fi

paso "Trayendo los datos nuevos a $REPO_DIR"
if git -C "$REPO_DIR" diff --quiet && git -C "$REPO_DIR" diff --cached --quiet; then
  git -C "$REPO_DIR" pull --ff-only -q && git -C "$REPO_DIR" log --oneline -1
else
  aviso "Tienes cambios sin guardar en el repo: no hago git pull (hazlo tú cuando quieras)."
fi

paso "Listo: $SITE"
echo "En la app instalada saldrá 'Hay datos nuevos · Recargar'."
