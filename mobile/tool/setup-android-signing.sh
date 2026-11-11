#!/usr/bin/env bash
# Creates (or reuses) the Android upload key ON YOUR COMPUTER and stores it as
# GitHub Actions secrets of one repository. Run it locally, never in CI.
#
#   bash setup-android-signing.sh <owner/repo> [keystore-file] [alias]
#
# Needs: keytool (from a JDK, e.g. Android Studio's), gh (logged in), base64.
# On Windows use Git Bash or WSL.
#
# The keystore and its password never leave your computer except as encrypted
# GitHub secrets. Keep the keystore file and the password safe: without them no
# further app updates are possible. The script refuses to replace an existing
# key in the repository (that would break updates for installed apps).
set -euo pipefail

REPO="${1:?Aufruf: setup-android-signing.sh <owner/repo> [keystore-datei] [alias]}"
KEYSTORE="${2:-${REPO##*/}-upload.jks}"
ALIAS="${3:-upload}"

fail() { echo "Fehler: $*" >&2; exit 1; }

for tool in keytool gh base64; do
  command -v "$tool" >/dev/null 2>&1 || fail "$tool nicht gefunden"
done
gh auth status >/dev/null 2>&1 || fail "gh ist nicht angemeldet (gh auth login)"
gh repo view "$REPO" >/dev/null 2>&1 || fail "Repository $REPO nicht erreichbar"

# Erst die Abfrage selbst absichern: Ein API-/Berechtigungsfehler darf nicht wie
# eine leere Secret-Liste behandelt werden, sonst könnte ein neuer Schlüssel
# erzeugt und über den vorhandenen Update-Schlüssel geschrieben werden.
SECRET_LIST="$(gh secret list --repo "$REPO")" \\
  || fail "GitHub-Secrets für $REPO konnten nicht sicher abgefragt werden; abgebrochen."
if printf '%s\\n' "$SECRET_LIST" | awk '{print $1}' | grep -qx ANDROID_KEYSTORE_BASE64; then
  fail "$REPO hat bereits einen Signaturschlüssel. Ein neuer Schlüssel würde Updates installierter Apps verhindern; abgebrochen."
fi

read -r -s -p "Keystore-Passwort (mindestens 8 Zeichen): " STORE_PASS; echo
[[ ${#STORE_PASS} -ge 8 ]] || fail "Passwort zu kurz"
export STORE_PASS

if [[ -f "$KEYSTORE" ]]; then
  echo "Vorhandener Keystore $KEYSTORE wird verwendet."
  keytool -list -keystore "$KEYSTORE" -alias "$ALIAS" -storepass:env STORE_PASS >/dev/null 2>&1 \
    || fail "Keystore lässt sich mit diesem Passwort und Alias $ALIAS nicht öffnen"
else
  read -r -s -p "Passwort wiederholen: " CONFIRM; echo
  [[ "$STORE_PASS" == "$CONFIRM" ]] || fail "Passwörter stimmen nicht überein"
  umask 077
  keytool -genkeypair -noprompt \
    -keystore "$KEYSTORE" -storetype PKCS12 \
    -alias "$ALIAS" -keyalg RSA -keysize 4096 -validity 10000 \
    -dname "CN=${REPO##*/} Android Upload Key" \
    -storepass:env STORE_PASS -keypass:env STORE_PASS >/dev/null 2>&1 \
    || fail "keytool konnte den Schlüssel nicht erzeugen"
  echo "Neuer Keystore: $KEYSTORE"
fi

FINGERPRINT="$(keytool -list -v -keystore "$KEYSTORE" -alias "$ALIAS" -storepass:env STORE_PASS 2>/dev/null \
  | sed -n 's/^[[:space:]]*SHA256: //p' | head -n 1)"
[[ -n "$FINGERPRINT" ]] || fail "Fingerabdruck nicht lesbar"

base64 < "$KEYSTORE" | tr -d '\r\n' | gh secret set ANDROID_KEYSTORE_BASE64 --repo "$REPO"
printf '%s' "$STORE_PASS" | gh secret set ANDROID_KEYSTORE_PASSWORD --repo "$REPO"
printf '%s' "$ALIAS" | gh secret set ANDROID_KEY_ALIAS --repo "$REPO"
# PKCS12 keystores use one password for the store and the key.
printf '%s' "$STORE_PASS" | gh secret set ANDROID_KEY_PASSWORD --repo "$REPO"
gh variable set ANDROID_SIGNING_CERT_SHA256 --repo "$REPO" --body "$FINGERPRINT"
unset STORE_PASS CONFIRM

cat <<EOF

Fertig für $REPO:
  Secrets: ANDROID_KEYSTORE_BASE64, ANDROID_KEYSTORE_PASSWORD, ANDROID_KEY_ALIAS, ANDROID_KEY_PASSWORD
  Variable: ANDROID_SIGNING_CERT_SHA256 = $FINGERPRINT

Jetzt sichern (ohne beides sind keine Updates mehr möglich):
  - $KEYSTORE (z. B. Passwortmanager und eine Offline-Kopie)
  - das Keystore-Passwort
Den Keystore nie ins Repository legen und nie in einen Chat kopieren.
EOF
