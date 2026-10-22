# Patches

All small edits to files that are not replaced are applied by `python scripts/apply_patches.py --apply`
(dry run without `--apply`). The exact edits are listed in that script's `PATCHES` table; it is idempotent,
keeps CRLF line endings and refuses to write a file when an expected line is not found.
