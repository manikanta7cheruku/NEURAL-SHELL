"""
scripts/build_app_manifest.py

Regenerates brain_modules/data/app_map.json from frontend/src so Seven always
knows the real screens, controls and descriptions. Wired into the frontend
build (npm run build:manifest) and also refreshed automatically at startup in
a development checkout.

    python scripts/build_app_manifest.py [--src frontend/src]
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.join(ROOT, "frontend", "src"))
    args = ap.parse_args()
    from brain_modules import app_map
    if not os.path.isfile(os.path.join(args.src, "App.jsx")):
        print(f"App.jsx not found under {args.src}")
        return 1
    data = app_map.build(args.src)
    app_map.write(data)
    print(f"app map written: {len(data['pages'])} pages, "
          f"{sum(len(p['controls']) for p in data['pages'])} controls -> {app_map.DATA_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
