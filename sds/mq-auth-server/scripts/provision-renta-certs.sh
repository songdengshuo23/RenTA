#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CA_CERT="${1:-$HERE/../ca-server/certs/ca.crt}"
CA_KEY="${2:-$HERE/../ca-server/certs/ca.key}"
OUT="${3:-$HERE/certs}"
LEADER_AIC="${ACPS_MQ_LEADER_AIC:-1.2.156.3088.1.1.34C2.478BDF.3GF546.0JU4}"
PARTNER_AIC="${ACPS_MQ_PARTNER_AIC:-1.2.156.3088.1.1.34C2.478BDF.3GF547.0JUE}"

[[ -f "$CA_CERT" && -f "$CA_KEY" ]] || {
  echo "ACPs CA certificate or key is missing" >&2
  exit 1
}

mkdir -p "$OUT/partners"
install -m 0644 "$CA_CERT" "$OUT/acps-root-ca.pem"

issue_cert() {
  local name="$1"
  local common_name="$2"
  local usage="$3"
  local san="$4"
  local key="$OUT/${name}.key"
  local csr="$OUT/${name}.csr"
  local cert="$OUT/${name}.pem"
  local serial
  serial="$(openssl rand -hex 16)"

  openssl req -new -newkey rsa:3072 -nodes -sha256 \
    -subj "/CN=${common_name}" -keyout "$key" -out "$csr" >/dev/null 2>&1
  openssl x509 -req -sha256 -days 49 -set_serial "0x${serial}" \
    -CA "$CA_CERT" -CAkey "$CA_KEY" -in "$csr" -out "$cert" \
    -extfile <(printf '%s\n' \
      'basicConstraints=critical,CA:FALSE' \
      'keyUsage=critical,digitalSignature,keyEncipherment' \
      "extendedKeyUsage=${usage}" \
      "subjectAltName=${san}") >/dev/null 2>&1
  rm -f "$csr"
  chmod 0600 "$key"
  chmod 0644 "$cert"
}

issue_cert rabbitmq-server rabbitmq.local serverAuth "DNS:localhost,DNS:rabbitmq.local,IP:127.0.0.1"
issue_cert rabbitmq-client rabbitmq-auth-client clientAuth "URI:acps://rabbitmq-auth-client"
issue_cert server mq-auth.local serverAuth "DNS:localhost,DNS:mq-auth.local,IP:127.0.0.1"
issue_cert leader "$LEADER_AIC" clientAuth "URI:acps://${LEADER_AIC}"

partner_tmp="$OUT/stage6-partner"
issue_cert stage6-partner "$PARTNER_AIC" clientAuth "URI:acps://${PARTNER_AIC}"
mv "$partner_tmp.pem" "$OUT/partners/${PARTNER_AIC}.pem"
mv "$partner_tmp.key" "$OUT/partners/${PARTNER_AIC}.key"

openssl verify -CAfile "$OUT/acps-root-ca.pem" \
  "$OUT/rabbitmq-server.pem" "$OUT/rabbitmq-client.pem" "$OUT/server.pem" \
  "$OUT/leader.pem" "$OUT/partners/${PARTNER_AIC}.pem" >/dev/null

echo "issued_ca=$(openssl x509 -in "$OUT/acps-root-ca.pem" -noout -subject)"
echo "leader_aic=$LEADER_AIC"
echo "partner_aic=$PARTNER_AIC"
