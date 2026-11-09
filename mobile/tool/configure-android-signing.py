#!/usr/bin/env python3
"""Sign Android release builds with one persistent upload key.

Android only installs an update over an existing app if both are signed with
the same key. CI regenerates the Android project with `flutter create`, which
signs release builds with the runner's throwaway debug key, so every build had
a different signature. This script switches the release build to a persistent
key that lives only in GitHub Actions secrets.

Run it after `flutter create`, from the Flutter app directory:

    python3 tool/configure-android-signing.py [--required]

Environment variables (GitHub Actions secrets):
    ANDROID_KEYSTORE_BASE64    base64 of the upload keystore (.jks)
    ANDROID_KEYSTORE_PASSWORD  keystore password
    ANDROID_KEY_ALIAS          key alias
    ANDROID_KEY_PASSWORD       key password

Passwords are never written to disk: Gradle reads them from the environment.
In GitHub Actions the step output `signed` is set to `true` or `false`.
The keystore is written to android/app/release-upload.jks (mode 0600, ignored
by git) and should be deleted after the build.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import os
import sys
from pathlib import Path

REQUIRED = (
    "ANDROID_KEYSTORE_BASE64",
    "ANDROID_KEYSTORE_PASSWORD",
    "ANDROID_KEY_ALIAS",
    "ANDROID_KEY_PASSWORD",
)
KEYSTORE_NAME = "release-upload.jks"
DEBUG_SIGNING = 'signingConfig = signingConfigs.getByName("debug")'
RELEASE_SIGNING = 'signingConfig = signingConfigs.getByName("release")'
SIGNING_BLOCK = """    signingConfigs {
        create("release") {
            // Persistent upload key; passwords come from the environment only.
            storeFile = file(System.getenv("ANDROID_KEYSTORE_PATH") ?: "release-upload.jks")
            storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
            keyAlias = System.getenv("ANDROID_KEY_ALIAS")
            keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
        }
    }

"""


class SigningError(RuntimeError):
    pass


def patch_gradle(text: str) -> str:
    """Add the release signing config to a Flutter-generated build.gradle.kts."""
    if 'create("release")' not in text:
        marker = "android {\n"
        if marker not in text:
            raise SigningError("android-Block in build.gradle.kts nicht gefunden")
        text = text.replace(marker, marker + SIGNING_BLOCK, 1)
    if DEBUG_SIGNING in text:
        text = text.replace(DEBUG_SIGNING, RELEASE_SIGNING)
    if RELEASE_SIGNING not in text:
        raise SigningError("signingConfig der Release-Variante nicht gefunden")
    return text


def write_keystore(encoded: str, target: Path) -> None:
    try:
        data = base64.b64decode("".join(encoded.split()), validate=True)
    except (binascii.Error, ValueError) as err:
        raise SigningError("ANDROID_KEYSTORE_BASE64 ist kein gültiges Base64") from err
    if len(data) < 64:
        raise SigningError("ANDROID_KEYSTORE_BASE64 enthält keinen Keystore")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def configure(app_dir: Path, env: dict[str, str], required: bool) -> bool:
    missing = [name for name in REQUIRED if not env.get(name)]
    if missing:
        if required:
            raise SigningError("Fehlende GitHub-Actions-Secrets: " + ", ".join(missing))
        print("::notice::Kein Release-Schlüssel hinterlegt – Signatur wird nicht eingerichtet.")
        return False
    gradle = app_dir / "android" / "app" / "build.gradle.kts"
    if not gradle.is_file():
        raise SigningError(f"{gradle} fehlt – zuerst flutter create ausführen")
    write_keystore(env["ANDROID_KEYSTORE_BASE64"], gradle.parent / KEYSTORE_NAME)
    gradle.write_text(patch_gradle(gradle.read_text(encoding="utf-8")), encoding="utf-8")
    print("Release-Signatur mit dem dauerhaften Upload-Schlüssel eingerichtet.")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Android-Release-Signatur einrichten")
    parser.add_argument("--app-dir", default=".", help="Flutter-App-Verzeichnis")
    parser.add_argument(
        "--required", action="store_true", help="Abbrechen, wenn ein Secret fehlt"
    )
    args = parser.parse_args(argv)
    try:
        signed = configure(Path(args.app_dir), dict(os.environ), args.required)
    except SigningError as err:
        print(f"::error::{err}", file=sys.stderr)
        return 1
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"signed={'true' if signed else 'false'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
