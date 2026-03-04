#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

CHART_IMG_BASE_URL="${CHART_IMG_BASE_URL:-https://api.chart-img.com}"
CHART_IMG_API_KEY="${CHART_IMG_API_KEY:-}"
CHART_IMG_TEST_AUTH_MODES="${CHART_IMG_TEST_AUTH_MODES:-x-api-key}"

if [[ -z "$CHART_IMG_API_KEY" ]]; then
  echo "ERROR: CHART_IMG_API_KEY is not set. Configure it in .env or environment."
  exit 1
fi

ARTIFACT_DIR="tmp/chart_img"
mkdir -p "$ARTIFACT_DIR"

BODY_ADV='{"symbol":"NASDAQ:AAPL","interval":"1D","theme":"dark","width":800,"height":600,"studies":[{"name":"Moving Average","input":{"length":20}},{"name":"Relative Strength Index","input":{"length":14}}]}'
BODY_MINI='{"symbol":"NASDAQ:AAPL","width":800,"height":600}'

V2_ADV_OK=0
V2_STORAGE_OK=0
V1_ROUTE_404_COUNT=0
LIMIT_HIT=0

probe() {
  local name="$1"
  local method="$2"
  local endpoint="$3"
  local body="$4"
  local auth="$5"
  local url="${CHART_IMG_BASE_URL%/}${endpoint}"
  local out_body out_head
  out_body="$(mktemp)"
  out_head="$(mktemp)"
  trap 'rm -f "$out_body" "$out_head"' RETURN

  if [[ "$auth" == "x-api-key" ]]; then
    curl -sS -m 40 -X "$method" "$url" \
      -H "x-api-key: $CHART_IMG_API_KEY" \
      -H "content-type: application/json" \
      -H "accept: image/png,application/json" \
      -d "$body" \
      -D "$out_head" \
      -o "$out_body" || true
  else
    curl -sS -m 40 -X "$method" "$url?key=$CHART_IMG_API_KEY" \
      -H "content-type: application/json" \
      -H "accept: image/png,application/json" \
      -d "$body" \
      -D "$out_head" \
      -o "$out_body" || true
  fi

  local status_line http_code content_type body_bytes preview
  status_line="$(head -n 1 "$out_head" | tr -d '\r')"
  http_code="$(awk 'NR==1{print $2}' "$out_head")"
  content_type="$(awk 'BEGIN{IGNORECASE=1}/^content-type:/{print $2; exit}' "$out_head" | tr -d '\r')"
  body_bytes="$(wc -c < "$out_body" | tr -d ' ')"
  preview="$(head -c 180 "$out_body" | tr '\n' ' ')"

  echo
  echo "[$name][$auth] $method $url"
  echo "status=${status_line:-N/A}"
  echo "content_type=${content_type:-unknown} body_bytes=${body_bytes}"
  echo "preview=${preview}"

  if [[ "$http_code" == "429" || "$preview" == *"Limit Exceeded"* || "$preview" == *"Too Many Requests"* ]]; then
    LIMIT_HIT=1
  fi

  if [[ "$http_code" == "200" && "$content_type" == image/* && "$name" == "v2-advanced" ]]; then
    V2_ADV_OK=1
    cp "$out_body" "$ARTIFACT_DIR/v2-advanced-${auth}.png"
    echo "saved_image=$ARTIFACT_DIR/v2-advanced-${auth}.png"
  fi

  if [[ "$http_code" == "200" && "$content_type" == application/json* && "$name" == "v2-advanced-storage" ]]; then
    V2_STORAGE_OK=1
    cp "$out_body" "$ARTIFACT_DIR/v2-advanced-storage-${auth}.json"
    echo "saved_json=$ARTIFACT_DIR/v2-advanced-storage-${auth}.json"
  fi

  if [[ "$name" == v1-* && "$http_code" == "404" ]]; then
    V1_ROUTE_404_COUNT=$((V1_ROUTE_404_COUNT + 1))
  fi
}

echo "== Chart-IMG preflight =="
curl -sS -m 30 \
  -H "x-api-key: $CHART_IMG_API_KEY" \
  -H "accept: application/json" \
  "${CHART_IMG_BASE_URL%/}/v3/tradingview/exchange/list" \
  -o "$ARTIFACT_DIR/v3-exchange-list.json"
echo "saved_json=$ARTIFACT_DIR/v3-exchange-list.json"

for auth in $CHART_IMG_TEST_AUTH_MODES; do
  probe "v2-advanced" "POST" "/v2/tradingview/advanced-chart" "$BODY_ADV" "$auth"
  probe "v2-advanced-storage" "POST" "/v2/tradingview/advanced-chart/storage" "$BODY_ADV" "$auth"
  probe "v1-advanced" "POST" "/v1/tradingview/advanced-chart" "$BODY_ADV" "$auth"
  probe "v1-advanced-storage" "POST" "/v1/tradingview/advanced-chart/storage" "$BODY_ADV" "$auth"
  probe "v1-mini" "POST" "/v1/tradingview/mini-chart" "$BODY_MINI" "$auth"
  probe "v1-mini-storage" "POST" "/v1/tradingview/mini-chart/storage" "$BODY_MINI" "$auth"
done

echo
echo "== Summary =="
echo "v2_advanced_ok=${V2_ADV_OK}"
echo "v2_storage_ok=${V2_STORAGE_OK}"
echo "v1_route_404_count=${V1_ROUTE_404_COUNT}"
echo "limit_hit=${LIMIT_HIT}"

if [[ "$V2_ADV_OK" -ne 1 ]]; then
  if [[ "$LIMIT_HIT" -eq 1 ]]; then
    echo "FATAL FLOW: Chart-IMG account limit/rate limit prevents V2 validation right now."
    exit 2
  fi
  echo "FATAL FLOW: V2 advanced endpoint did not return an image."
  exit 1
fi

echo "Completed Chart-IMG V1/V2 curl diagnostics."
