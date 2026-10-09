"""
scripts/memory_doctor.py

Repairs Seven's memory from the repository root:

    python scripts/memory_doctor.py            # report only
    python scripts/memory_doctor.py --fix      # clean poisoned legacy facts, reindex

Removes facts such as "User's name is What You" and "User said: ..." and
rebuilds the semantic index from the structured store.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="apply repairs")
    args = parser.parse_args()

    from memory import fact_service, facts_store
    print("Before:", fact_service.stats())
    if args.fix:
        print("Legacy migration:", fact_service.migrate_legacy())
        facts_store.meta_set("legacy_migration_v2", "done")
        print("Reindexed:", fact_service.reindex_pending(500))
        print("After:", fact_service.stats())
    else:
        print("Run with --fix to apply repairs.")


if __name__ == "__main__":
    main()
