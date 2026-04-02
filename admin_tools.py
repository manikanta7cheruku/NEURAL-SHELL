"""
=============================================================================
PROJECT SEVEN - admin_tools.py (Admin License Generator)
INTERNAL USE ONLY — DO NOT DISTRIBUTE
=============================================================================
"""

import license as lic

def generate_free_key(email: str, tier: str = "ultimate", plan_type: str = "lifetime"):
    """
    Generate a FREE license key for friends/family.
    
    Args:
        email: Recipient's email
        tier: "pro" or "ultimate"
        plan_type: "monthly", "yearly", or "lifetime"
    
    Returns:
        License key string
    """
    key = lic.create_license(email, tier, plan_type)
    
    print("=" * 60)
    print(f"🎁 FREE LICENSE GENERATED")
    print("=" * 60)
    print(f"Email:       {email}")
    print(f"Tier:        {tier.upper()}")
    print(f"Type:        {plan_type}")
    print(f"License Key: {key}")
    print("=" * 60)
    print("\nShare this key with the user:")
    print(f"  {key}")
    print("\nThey should:")
    print("  1. Open Seven → Plans page")
    print("  2. Enter this key in 'Activate License Key'")
    print("  3. Click Activate")
    print("=" * 60)
    
    return key


def list_all_licenses():
    """Show all active licenses."""
    import sqlite3
    import json
    
    conn = sqlite3.connect("data/license.db")
    c = conn.cursor()
    
    c.execute("""
        SELECT license_key, email, tier, plan_type, device_ids, created_at, expires_at
        FROM licenses
        WHERE is_active = 1
        ORDER BY created_at DESC
    """)
    
    print("\n" + "=" * 80)
    print("ACTIVE LICENSES")
    print("=" * 80)
    
    for row in c.fetchall():
        key, email, tier, plan_type, device_ids_json, created, expires = row
        device_ids = json.loads(device_ids_json) if device_ids_json else []
        
        print(f"\nKey:     {key}")
        print(f"Email:   {email}")
        print(f"Tier:    {tier.upper()} ({plan_type})")
        print(f"Devices: {len(device_ids)}")
        print(f"Created: {created[:10]}")
        print(f"Expires: {expires[:10] if expires else 'Never'}")
        print("-" * 80)
    
    conn.close()


def revoke_license(license_key: str):
    """Deactivate a license key."""
    import sqlite3
    
    conn = sqlite3.connect("data/license.db")
    c = conn.cursor()
    
    c.execute("UPDATE licenses SET is_active = 0 WHERE license_key = ?", (license_key,))
    
    if c.rowcount > 0:
        print(f"✅ Revoked: {license_key}")
    else:
        print(f"❌ Not found: {license_key}")
    
    conn.commit()
    conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python admin_tools.py gen <email> [tier] [plan_type]")
        print("  python admin_tools.py list")
        print("  python admin_tools.py revoke <key>")
        print("\nExamples:")
        print("  python admin_tools.py gen friend@gmail.com ultimate lifetime")
        print("  python admin_tools.py gen relative@gmail.com pro yearly")
        print("  python admin_tools.py list")
        print("  python admin_tools.py revoke VII-A3F9-B2E7-C1D4")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "gen":
        email = sys.argv[2]
        tier = sys.argv[3] if len(sys.argv) > 3 else "ultimate"
        plan_type = sys.argv[4] if len(sys.argv) > 4 else "lifetime"
        generate_free_key(email, tier, plan_type)
    
    elif cmd == "list":
        list_all_licenses()
    
    elif cmd == "revoke":
        key = sys.argv[2]
        revoke_license(key)
    
    else:
        print(f"Unknown command: {cmd}")