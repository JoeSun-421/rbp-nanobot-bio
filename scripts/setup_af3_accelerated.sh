#!/usr/bin/env bash
# Accelerate AF3 *conda env* install without modifying rhobind_agent_delivery.
#
# - Never writes under DELIVERY_ROOT (read-only use of setup_af3.sh / af3_env.yml)
# - Uses pip mirror + aria2c for wheel downloads when available
# - Re-pins jax/triton to versions declared in delivery af3_env.yml (jax 0.4.34 / triton 3.1.0)
#
# Usage:
#   source nanobot-bio/scripts/activate_env.sh   # optional; sets DELIVERY_ROOT
#   bash nanobot-bio/scripts/setup_af3_accelerated.sh
set -euo pipefail

_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_AGENT_ROOT="$(cd "$_SCRIPT_DIR/.." && pwd)"
_BIO_ROOT="$(cd "${BIO_ROOT:-$_AGENT_ROOT/..}" && pwd)"
DELIVERY_ROOT="${DELIVERY_ROOT:-$_BIO_ROOT/rhobind_agent_delivery}"
AF3_DIR="${AF3_DIR:-$DELIVERY_ROOT/agent/third_party/alphafold3}"
YML="$AF3_DIR/af3_env.yml"
PIP_INDEX="${PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
PIP_HOST="${PIP_TRUSTED_HOST:-pypi.tuna.tsinghua.edu.cn}"
WHEEL_CACHE="${AF3_WHEEL_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/af3-wheel-cache}"

echo "[af3-fast] DELIVERY_ROOT=$DELIVERY_ROOT (read-only)"
echo "[af3-fast] AF3_DIR=$AF3_DIR"
echo "[af3-fast] PIP_INDEX=$PIP_INDEX"
echo "[af3-fast] WHEEL_CACHE=$WHEEL_CACHE"

if [[ ! -f "$YML" ]]; then
  echo "ERROR: missing $YML" >&2
  exit 1
fi
if [[ ! -f "$DELIVERY_ROOT/agent/setup_af3.sh" ]]; then
  echo "ERROR: missing delivery setup_af3.sh" >&2
  exit 1
fi
command -v conda >/dev/null || { echo "ERROR: conda required" >&2; exit 1; }

# 1) Create / refresh env via delivery script (it only creates env + pip -e + ccd copy)
echo "[af3-fast] 1/4 run delivery setup_af3.sh (no edits to delivery) ..."
# shellcheck disable=SC1091
source "$DELIVERY_ROOT/agent/setup.sh"
bash "$DELIVERY_ROOT/agent/setup_af3.sh"

AF3_PY="$(conda run -n af3 which python)"
echo "[af3-fast] AF3_PYTHON=$AF3_PY"

# 2) Extract pinned pip deps from af3_env.yml (read-only parse)
echo "[af3-fast] 2/4 parse pinned pip deps from af3_env.yml ..."
mapfile -t PINS < <(python - <<PY
from pathlib import Path
pins = []
in_pip = False
for line in Path(r"$YML").read_text().splitlines():
    s = line.strip()
    if s.startswith("- pip:"):
        in_pip = True
        continue
    if in_pip:
        if s.startswith("- ") and "==" in s:
            pins.append(s[2:].strip())
        elif s and not s.startswith("-") and not s.startswith("#"):
            break
for p in pins:
    print(p)
PY
)
echo "[af3-fast]   ${#PINS[@]} pins (e.g. ${PINS[0]:-none} …)"

# 3) Prefetch wheels with aria2 when possible, then pip install --no-deps
mkdir -p "$WHEEL_CACHE"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_DEFAULT_TIMEOUT=120

_pip() {
  "$AF3_PY" -m pip "$@"
}

echo "[af3-fast] 3/4 re-pin jax/triton stack (fixes Triton int32 / jax 0.6 mismatch) ..."
# Prefer mirror; fall back to PyPI
_pip install -U pip setuptools wheel \
  -i "$PIP_INDEX" --trusted-host "$PIP_HOST" -q || true

# Download wheels into cache (aria2 parallel when URL list available)
REQ_FILE="$(mktemp)"
printf '%s\n' "${PINS[@]}" > "$REQ_FILE"
if command -v aria2c >/dev/null 2>&1; then
  echo "[af3-fast]   prefetch via pip download + aria2-friendly cache dir ..."
  # pip download fills WHEEL_CACHE; aria2 used for any http(s) we can list
  _pip download -r "$REQ_FILE" -d "$WHEEL_CACHE" \
    -i "$PIP_INDEX" --trusted-host "$PIP_HOST" \
    --dest "$WHEEL_CACHE" 2>/tmp/af3_pip_download.log || \
  _pip download -r "$REQ_FILE" -d "$WHEEL_CACHE" 2>>/tmp/af3_pip_download.log || true
  # Also aria2 any .whl URLs pip reported (best-effort)
  if grep -Eo 'https?://[^ ]+\.whl' /tmp/af3_pip_download.log >/tmp/af3_whl_urls.txt 2>/dev/null; then
    if [[ -s /tmp/af3_whl_urls.txt ]]; then
      aria2c -c -x 16 -s 16 -j 8 -d "$WHEEL_CACHE" -i /tmp/af3_whl_urls.txt || true
    fi
  fi
  _pip install --no-deps --no-index --find-links="$WHEEL_CACHE" -r "$REQ_FILE" \
    || _pip install --no-deps -r "$REQ_FILE" -i "$PIP_INDEX" --trusted-host "$PIP_HOST" \
    || _pip install --no-deps -r "$REQ_FILE"
else
  echo "[af3-fast]   aria2c not found — pip mirror only"
  _pip install --no-deps -r "$REQ_FILE" -i "$PIP_INDEX" --trusted-host "$PIP_HOST" \
    || _pip install --no-deps -r "$REQ_FILE"
fi
rm -f "$REQ_FILE"

# Ensure editable alphafold3 still points at delivery tree (no file edits)
echo "[af3-fast]   ensure alphafold3 editable install ..."
_pip install --no-deps -e "$AF3_DIR" -q

# 4) Verify import + versions
echo "[af3-fast] 4/4 verify ..."
"$AF3_PY" - <<'PY'
import jax, triton
print("jax", jax.__version__, "devices", jax.devices())
print("triton", triton.__version__)
import alphafold3
from alphafold3.common import folding_input
print("alphafold3 OK", alphafold3.__file__)
assert jax.__version__.startswith("0.4."), f"want jax 0.4.x, got {jax.__version__}"
assert triton.__version__.startswith("3.1."), f"want triton 3.1.x, got {triton.__version__}"
print("pin check OK")
PY

# Persist AF3_PYTHON into agent .env without touching delivery
ENVF="$_AGENT_ROOT/.env"
if [[ -f "$ENVF" ]]; then
  if grep -q '^AF3_PYTHON=' "$ENVF"; then
    sed -i "s|^AF3_PYTHON=.*|AF3_PYTHON=$AF3_PY|" "$ENVF"
  else
    echo "AF3_PYTHON=$AF3_PY" >> "$ENVF"
  fi
  echo "[af3-fast] updated $ENVF AF3_PYTHON"
fi

echo
echo "[af3-fast] DONE. Smoke (optional, GPU):"
echo "  conda run -n af3 python $DELIVERY_ROOT/agent/tools/structure/structure_predict_af3.py --json '{\"sequence\":\"MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG\",\"name\":\"ubq\"}'"
echo "  (delivery files were not modified)"
