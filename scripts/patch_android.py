#!/usr/bin/env python3
"""
Post-build step for the Android package.

buildozer/python-for-android generates the Gradle project under
``.buildozer/android/platform/build-*/dists/*``.  This script merges the pieces
that buildozer does not handle automatically:

* ``res/xml/accessibility_service_config.xml``
* extra strings used by the service
* the ``<service>`` / ``<receiver>`` entries in AndroidManifest.xml

Run it after ``buildozer android debug`` and then build once more:

    buildozer android debug
    python scripts/patch_android.py
    buildozer android debug
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android"


def find_dist() -> Path:
    base = ROOT / ".buildozer" / "android" / "platform"
    if not base.is_dir():
        sys.exit("未找到 .buildozer 目录，请先运行 buildozer android debug")
    candidates = sorted(base.glob("build-*/dists/*/src/main/AndroidManifest.xml"))
    if not candidates:
        sys.exit("未找到生成的 AndroidManifest.xml，请先运行 buildozer android debug")
    return candidates[-1].parents[2]


def copy_resources(dist: Path) -> None:
    res = dist / "src" / "main" / "res"

    xml_src = ANDROID / "res" / "xml" / "accessibility_service_config.xml"
    xml_dst_dir = res / "xml"
    xml_dst_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(xml_src, xml_dst_dir / xml_src.name)
    print(f"  copied {xml_src.name} -> {xml_dst_dir}")

    values_dir = res / "values"
    values_dir.mkdir(parents=True, exist_ok=True)
    strings_dst = values_dir / "strings.xml"
    extra = (ANDROID / "src" / "main" / "res" / "values" / "strings.xml").read_text(
        encoding="utf-8"
    )
    extra_items = re.findall(r"<string .*?</string>", extra, flags=re.S)

    if strings_dst.exists():
        current = strings_dst.read_text(encoding="utf-8")
    else:
        current = '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n</resources>\n'

    additions = [item for item in extra_items
                 if f'name="{re.search(chr(34) + r"(.+?)" + chr(34), item).group(1)}"' not in current]
    if additions:
        current = current.replace(
            "</resources>", "\n    ".join(additions) + "\n</resources>"
        )
        strings_dst.write_text(current, encoding="utf-8")
        print(f"  merged {len(additions)} string(s) into {strings_dst}")


def copy_java(dist: Path) -> None:
    src = ANDROID / "src" / "main" / "java" / "com" / "autoaccount"
    dst = dist / "src" / "main" / "java" / "com" / "autoaccount"
    dst.mkdir(parents=True, exist_ok=True)
    for path in src.glob("*.java"):
        shutil.copy2(path, dst / path.name)
    print(f"  copied {len(list(src.glob('*.java')))} java file(s) -> {dst}")


def patch_manifest(dist: Path) -> None:
    manifest = dist / "src" / "main" / "AndroidManifest.xml"
    text = manifest.read_text(encoding="utf-8")

    snippet = (ANDROID / "res" / "extra_application.xml").read_text(encoding="utf-8")
    snippet = re.sub(r"<!--.*?-->", "", snippet, flags=re.S).strip()

    if "AutoAccountAccessibilityService" in text:
        print("  manifest already patched")
        return
    if "</application>" not in text:
        sys.exit("AndroidManifest.xml 中缺少 </application>，无法打补丁")

    text = text.replace("</application>", f"\n{snippet}\n    </application>")
    manifest.write_text(text, encoding="utf-8")
    print(f"  patched {manifest}")


def main() -> None:
    dist = find_dist()
    print(f"生成目录: {dist}")
    copy_java(dist)
    copy_resources(dist)
    patch_manifest(dist)
    print("\n完成，重新运行 buildozer android debug 生成包含无障碍服务的 APK。")


if __name__ == "__main__":
    main()
