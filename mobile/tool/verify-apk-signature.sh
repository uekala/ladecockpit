#!/usr/bin/env bash
# Prints the signing certificate of an APK and, if ANDROID_SIGNING_CERT_SHA256
# is set (repository variable, not a secret), fails when it does not match.
# This guarantees that every release is signed with the same key, so Android
# accepts it as an update of the installed app.
set -euo pipefail

APK="${1:?Pfad zur APK fehlt}"
APKSIGNER="$(find "${ANDROID_HOME:?ANDROID_HOME fehlt}/build-tools" -type f -name apksigner | sort -V | tail -n 1)"
if [[ -z "$APKSIGNER" ]]; then
  echo "::error::apksigner nicht gefunden"
  exit 1
fi

"$APKSIGNER" verify --verbose "$APK" >/dev/null
CERTS="$("$APKSIGNER" verify --print-certs "$APK")"
FINGERPRINT="$(printf '%s\n' "$CERTS" | sed -n 's/.*certificate SHA-256 digest: //p' | head -n 1 | tr -d ':' | tr '[:lower:]' '[:upper:]')"
SUBJECT="$(printf '%s\n' "$CERTS" | sed -n 's/.*certificate DN: //p' | head -n 1)"

if [[ -z "$FINGERPRINT" ]]; then
  echo "::error::Kein Signaturzertifikat in $APK gefunden"
  exit 1
fi
if [[ "$SUBJECT" == *"Android Debug"* ]]; then
  echo "::error::Die APK ist mit einem Debug-Schlüssel signiert und lässt sich nicht als Update installieren"
  exit 1
fi

EXPECTED="$(printf '%s' "${ANDROID_SIGNING_CERT_SHA256:-}" | tr -d ': ' | tr '[:lower:]' '[:upper:]')"
if [[ -n "$EXPECTED" && "$EXPECTED" != "$FINGERPRINT" ]]; then
  echo "::error::Signaturzertifikat $FINGERPRINT entspricht nicht dem erwarteten $EXPECTED"
  exit 1
fi

echo "Signatur: $SUBJECT"
echo "SHA-256: $FINGERPRINT"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  {
    echo "### Android-Signatur"
    echo ""
    echo "- Zertifikat: \`$SUBJECT\`"
    echo "- SHA-256: \`$FINGERPRINT\`"
    if [[ -z "$EXPECTED" ]]; then
      echo "- Hinweis: Repository-Variable \`ANDROID_SIGNING_CERT_SHA256\` ist nicht gesetzt; der Abgleich mit dem erwarteten Zertifikat wurde übersprungen."
    else
      echo "- Abgleich mit \`ANDROID_SIGNING_CERT_SHA256\`: ok"
    fi
  } >> "$GITHUB_STEP_SUMMARY"
fi
