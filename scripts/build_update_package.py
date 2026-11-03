"""
scripts/build_update_package.py
After the installer is built: record what this release contains, and build the small "changed files only" update.

    python scripts/build_update_package.py                       record the manifest of this build (always run it)
    python scripts/build_update_package.py --prev 1.3.3          also build the patch for people on 1.3.3

Run it from the project root once `npm run build:installer` has finished. It reads dist-electron/win-unpacked (the files the
installer was made from) and the version in version.txt, and writes:

    release-manifests/manifest-<version>.json.gz     every file of this release with its SHA-256. KEEP IT: the next
                                                     release's patch is built by comparing against it. Commit it.
    dist-installer/SEVEN-Patch-<prev>-to-<version>.zip   only the files that changed since <prev>

and prints the values to paste into the admin dashboard (Updates, Publish, "Changed files only"). It refuses to continue
when the version on disk is not the version being released, which is how an update ends up installing and still being the old
version.
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend import update_package  # noqa: E402

MANIFESTS = os.path.join(ROOT, "release-manifests")


def read_version() -> str:
    with open(os.path.join(ROOT, "version.txt"), encoding="utf-8-sig") as f:
        return f.read().strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tree", default=os.path.join(ROOT, "dist-electron", "win-unpacked"), help="the build the installer was made from")
    ap.add_argument("--out", default=os.path.join(ROOT, "dist-installer"))
    ap.add_argument("--prev", help="the version the patch is for, for example 1.3.3 (its manifest must be in release-manifests/)")
    args = ap.parse_args()

    version = read_version()
    tree = os.path.abspath(args.tree)
    stamped = os.path.join(tree, "resources", "app", "version.txt")
    if not os.path.isfile(stamped):
        print(f"ERROR: {stamped} not found. Run `npm run build:installer` first.")
        return 1
    with open(stamped, encoding="utf-8-sig") as f:
        built = f.read().strip()
    if built != version:
        print(f"ERROR: the build folder says {built} but version.txt says {version}. Rebuild the installer after bumping the version.")
        return 1

    print(f"Hashing {tree} (a minute or two)...")
    manifest = update_package.build_manifest(tree, version)
    os.makedirs(MANIFESTS, exist_ok=True)
    manifest_path = os.path.join(MANIFESTS, f"manifest-{version}.json.gz")
    update_package.save_manifest(manifest, manifest_path)
    print(f"Manifest: {manifest_path} ({len(manifest['files'])} files). Keep it and commit it.")

    installer = os.path.join(args.out, f"SEVEN-Setup-{version}.exe")
    if os.path.isfile(installer):
        print(f"\nFull installer {os.path.basename(installer)}: {os.path.getsize(installer) / 1048576:.0f} MB")
        print(f"  SHA-256  {update_package.sha256_file(installer)}")

    if not args.prev:
        print("\nNo patch built (pass --prev <version> to build one).")
        return 0
    prev_path = os.path.join(MANIFESTS, f"manifest-{args.prev}.json.gz")
    if not os.path.isfile(prev_path):
        print(f"ERROR: {prev_path} not found. A patch needs the manifest recorded when {args.prev} was built.")
        return 1
    old = update_package.load_manifest(prev_path)
    os.makedirs(args.out, exist_ok=True)
    out_zip = os.path.join(args.out, f"SEVEN-Patch-{args.prev}-to-{version}.zip")
    meta = update_package.build_patch(tree, old, manifest, out_zip)
    print(f"\nPatch {os.path.basename(out_zip)}: {meta['size'] / 1048576:.1f} MB, {meta['files']} changed or new files, {meta['removed']} removed")
    print("\nPaste into the dashboard, Updates, Publish, Changed files only:")
    print(f"  Applies to version  {args.prev}")
    print(f"  Download link       (the https link where you upload {os.path.basename(out_zip)})")
    print(f"  SHA-256             {meta['sha256']}")
    print(f"  Size (MB)           {meta['size'] / 1048576:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
