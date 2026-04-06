"""
=============================================================================
PROJECT SEVEN - admin_tools.py (Admin License & Referral Manager)
INTERNAL USE ONLY — DO NOT DISTRIBUTE
=============================================================================
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import license as lic

def generate_free_key(email: str, tier: str = "ultimate", plan_type: str = "lifetime"):
    """Generate a FREE license key."""
    key = lic.create_license(email, tier, plan_type)
    
    print("=" * 60)
    print(f"🎁 LICENSE GENERATED")
    print("=" * 60)
    print(f"Email:       {email}")
    print(f"Tier:        {tier.upper()}")
    print(f"Type:        {plan_type}")
    print(f"License Key: {key}")
    print("=" * 60)
    print(f"\nSend this to {email}:")
    print(f"  {key}")
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
        print(f"Created: {created[:10] if created else 'N/A'}")
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


def check_referrals():
    """Check pending and completed referrals."""
    import sqlite3
    
    conn = sqlite3.connect("data/license.db")
    c = conn.cursor()
    
    print("\n" + "=" * 70)
    print("REFERRAL STATUS")
    print("=" * 70)
    
    # Recently completed (need to send license)
    c.execute("""
        SELECT r.referred_email, r.referrer_email, r.completed_at, r.usage_hours
        FROM referrals r
        WHERE r.is_complete = 1 
        ORDER BY r.completed_at DESC
        LIMIT 20
    """)
    
    completed = c.fetchall()
    
    if completed:
        print("\n🎉 COMPLETED (Send license keys!):")
        print("-" * 70)
        for ref_email, referrer_email, completed_at, hours in completed:
            print(f"  Completed: {completed_at[:16] if completed_at else 'N/A'}")
            print(f"  Referred:  {ref_email} → Send PRO 1-month")
            print(f"  Referrer:  {referrer_email} → Send ULTIMATE 1-month")
            print("-" * 70)
    else:
        print("\n✓ No completed referrals yet")
    
    # Almost complete (>5 hours)
    c.execute("""
        SELECT r.referred_email, r.referrer_email, r.usage_hours
        FROM referrals r
        WHERE r.is_complete = 0 
        AND r.usage_hours >= 3
        ORDER BY r.usage_hours DESC
    """)
    
    almost = c.fetchall()
    
    if almost:
        print("\n⏳ ALMOST COMPLETE (3+ hours):")
        print("-" * 70)
        for ref_email, referrer_email, hours in almost:
            remaining = 7 - hours
            mins = int((hours % 1) * 60)
            hrs = int(hours)
            time_str = f"{hrs}hr {mins}min" if hrs > 0 else f"{mins}min"
            print(f"  {ref_email}: {time_str} / 7hr ({round(remaining, 1)}hr left)")
            print(f"  Referred by: {referrer_email}")
            print("-" * 70)
    
    # All pending
    c.execute("""
        SELECT referred_email, referrer_email, usage_hours, created_at
        FROM referrals
        WHERE is_complete = 0
        ORDER BY usage_hours DESC
    """)
    
    all_pending = c.fetchall()
    
    print(f"\n📊 ALL PENDING REFERRALS ({len(all_pending)} total):")
    print("-" * 70)
    for ref_email, referrer_email, hours, created in all_pending:
        mins = int((hours % 1) * 60)
        hrs = int(hours)
        time_str = f"{hrs}hr {mins}min" if hrs > 0 else f"{mins}min"
        print(f"  {ref_email}: {time_str}")
    
    conn.close()


def list_emails():
    """List all registered emails."""
    import sqlite3
    
    emails = set()
    
    # From license db
    try:
        conn = sqlite3.connect("data/license.db")
        c = conn.cursor()
        
        c.execute("SELECT DISTINCT email FROM licenses WHERE email IS NOT NULL")
        for row in c.fetchall():
            if row[0]:
                emails.add(row[0])
        
        c.execute("SELECT DISTINCT referrer_email FROM referrals WHERE referrer_email IS NOT NULL")
        for row in c.fetchall():
            if row[0]:
                emails.add(row[0])
        
        c.execute("SELECT DISTINCT referred_email FROM referrals WHERE referred_email IS NOT NULL")
        for row in c.fetchall():
            if row[0]:
                emails.add(row[0])
        
        conn.close()
    except:
        pass
    
    # From telemetry
    try:
        conn = sqlite3.connect("data/telemetry.db")
        c = conn.cursor()
        c.execute("SELECT DISTINCT email FROM stats WHERE email IS NOT NULL")
        for row in c.fetchall():
            if row[0]:
                emails.add(row[0])
        conn.close()
    except:
        pass
    
    # From email file
    if os.path.exists("data/email.txt"):
        with open("data/email.txt", "r") as f:
            email = f.read().strip()
            if email:
                emails.add(email)
    
    print("\n" + "=" * 50)
    print(f"ALL REGISTERED EMAILS ({len(emails)} total)")
    print("=" * 50)
    for email in sorted(emails):
        print(f"  {email}")
    print("=" * 50)


def send_referral_reward(referred_email: str, referrer_email: str):
    """Generate and display license keys for completed referral."""
    print("\n" + "=" * 70)
    print("REFERRAL REWARD - LICENSE KEYS")
    print("=" * 70)
    
    # Pro 1-month for referred user
    from datetime import datetime, timedelta
    
    pro_key = lic.generate_license_key("pro")
    ult_key = lic.generate_license_key("ultimate")
    
    # Calculate expiry (1 month from now)
    expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    print(f"\n📧 EMAIL 1 - To: {referred_email}")
    print("-" * 70)
    print(f"""
Subject: Your Seven Pro Access is Ready! 🎉

Hi!

Congratulations! You've used Seven for 7 hours and unlocked Pro access FREE for 1 month!

Your License Key: {pro_key}
Valid Until: {expiry}

To activate:
1. Open Seven
2. Go to Plans page  
3. Paste the key and click Activate

Enjoy unlimited schedules, knowledge files, and more!

— Seven Team
""")
    
    print(f"\n📧 EMAIL 2 - To: {referrer_email}")
    print("-" * 70)
    print(f"""
Subject: Your Friend Used Seven - You Got Ultimate Free! 🎁

Hi!

Great news! Your friend {referred_email} used Seven for 7 hours.

As a thank you, here's Ultimate access FREE for 1 month!

Your License Key: {ult_key}
Valid Until: {expiry}

To activate:
1. Open Seven
2. Go to Plans page
3. Paste the key and click Activate

Keep sharing to earn more rewards!

— Seven Team
""")
    print("=" * 70)
    print(f"\nKeys generated:")
    print(f"  Pro (for {referred_email}): {pro_key}")
    print(f"  Ultimate (for {referrer_email}): {ult_key}")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""
SEVEN ADMIN TOOLS
=================

Usage:
  python admin_tools.py gen <email> [tier] [plan_type]
  python admin_tools.py list
  python admin_tools.py revoke <key>
  python admin_tools.py referrals
  python admin_tools.py emails
  python admin_tools.py reward <referred_email> <referrer_email>

Examples:
  python admin_tools.py gen friend@gmail.com ultimate lifetime
  python admin_tools.py gen user@email.com pro monthly
  python admin_tools.py referrals
  python admin_tools.py emails
  python admin_tools.py reward friend@gmail.com referrer@gmail.com
        """)
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
    
    elif cmd == "referrals":
        check_referrals()
    
    elif cmd == "emails":
        list_emails()
    
    elif cmd == "reward":
        referred = sys.argv[2]
        referrer = sys.argv[3]
        send_referral_reward(referred, referrer)
    
    else:
        print(f"Unknown command: {cmd}")