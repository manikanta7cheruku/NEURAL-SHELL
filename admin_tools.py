"""
=============================================================================
PROJECT SEVEN - admin_tools.py (Admin License & Referral Manager)
INTERNAL USE ONLY — DO NOT DISTRIBUTE
=============================================================================
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta

def ensure_db():
    """Make sure database exists."""
    if not os.path.exists("data/license.db"):
        print("❌ No database found. Run Seven first to create it.")
        sys.exit(1)

def generate_license(email: str, tier: str = "ultimate", plan_type: str = "lifetime"):
    """Generate a license key."""
    import license as lic
    
    key = lic.create_license(email, tier, plan_type)
    
    if plan_type == "monthly":
        expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    elif plan_type == "yearly":
        expiry = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    else:
        expiry = "Never (Lifetime)"
    
    print("=" * 60)
    print(f"🎁 LICENSE GENERATED")
    print("=" * 60)
    print(f"Email:       {email}")
    print(f"Tier:        {tier.upper()}")
    print(f"Type:        {plan_type}")
    print(f"Expires:     {expiry}")
    print(f"License Key: {key}")
    print("=" * 60)
    print(f"\n📧 EMAIL TO SEND:")
    print("-" * 60)
    print(f"""
Subject: Your Seven {tier.upper()} License Key

Hi!

Here's your Seven {tier.upper()} license key:

License Key: {key}
Valid Until: {expiry}

To activate:
1. Open Seven
2. Go to Plans page
3. Paste the key and click Activate

Enjoy Seven!

— Seven Team
""")
    print("=" * 60)
    return key


def list_licenses():
    """Show all active licenses."""
    import sqlite3
    import json
    
    ensure_db()
    
    conn = sqlite3.connect("data/license.db")
    c = conn.cursor()
    
    c.execute("""
        SELECT license_key, email, tier, plan_type, device_ids, created_at, expires_at
        FROM licenses
        WHERE is_active = 1
        ORDER BY created_at DESC
    """)
    
    rows = c.fetchall()
    conn.close()
    
    print("\n" + "=" * 80)
    print(f"ACTIVE LICENSES ({len(rows)} total)")
    print("=" * 80)
    
    if not rows:
        print("\nNo active licenses.")
    else:
        for row in rows:
            key, email, tier, plan_type, device_ids_json, created, expires = row
            device_ids = json.loads(device_ids_json) if device_ids_json else []
            
            print(f"\nKey:     {key}")
            print(f"Email:   {email}")
            print(f"Tier:    {tier.upper()} ({plan_type or 'N/A'})")
            print(f"Devices: {len(device_ids)}")
            print(f"Created: {created[:10] if created else 'N/A'}")
            print(f"Expires: {expires[:10] if expires else 'Never'}")
            print("-" * 80)


def revoke_license(license_key: str):
    """Deactivate a license key."""
    import sqlite3
    
    ensure_db()
    
    conn = sqlite3.connect("data/license.db")
    c = conn.cursor()
    
    c.execute("SELECT email FROM licenses WHERE license_key = ?", (license_key,))
    row = c.fetchone()
    
    if row:
        c.execute("UPDATE licenses SET is_active = 0 WHERE license_key = ?", (license_key,))
        conn.commit()
        print(f"✅ Revoked: {license_key}")
        print(f"   Email: {row[0]}")
    else:
        print(f"❌ Not found: {license_key}")
    
    conn.close()


def check_referrals():
    """Check pending and completed referrals."""
    import sqlite3
    
    ensure_db()
    
    conn = sqlite3.connect("data/license.db")
    c = conn.cursor()
    
    print("\n" + "=" * 70)
    print("REFERRAL STATUS")
    print("=" * 70)
    
    # Completed referrals
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
            print(f"\n  Command: python admin_tools.py reward {ref_email} {referrer_email}")
            print("-" * 70)
    else:
        print("\n✓ No completed referrals yet")
    
    # Almost complete
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
            mins = int(hours * 60)
            hrs = mins // 60
            mins = mins % 60
            time_str = f"{hrs}hr {mins}min" if hrs > 0 else f"{mins}min"
            print(f"  {ref_email}: {time_str} / 7hr")
            print(f"  Referred by: {referrer_email}")
            print("-" * 70)
    
    # All pending
    c.execute("""
        SELECT referred_email, usage_hours
        FROM referrals
        WHERE is_complete = 0
        ORDER BY usage_hours DESC
    """)
    
    all_pending = c.fetchall()
    
    print(f"\n📊 ALL PENDING ({len(all_pending)} total):")
    print("-" * 70)
    for ref_email, hours in all_pending:
        mins = int(hours * 60)
        hrs = mins // 60
        mins = mins % 60
        time_str = f"{hrs}hr {mins}min" if hrs > 0 else f"{mins}min"
        progress = min(100, int((hours / 7) * 100))
        bar = "█" * (progress // 10) + "░" * (10 - progress // 10)
        print(f"  {ref_email}: {time_str} [{bar}] {progress}%")
    
    conn.close()


def list_emails():
    """List all registered emails."""
    import sqlite3
    
    emails = set()
    
    if os.path.exists("data/license.db"):
        conn = sqlite3.connect("data/license.db")
        c = conn.cursor()
        
        for table, column in [("licenses", "email"), ("referrals", "referrer_email"), ("referrals", "referred_email")]:
            try:
                c.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL")
                for row in c.fetchall():
                    if row[0]:
                        emails.add(row[0])
            except:
                pass
        conn.close()
    
    if os.path.exists("data/telemetry.db"):
        conn = sqlite3.connect("data/telemetry.db")
        c = conn.cursor()
        try:
            c.execute("SELECT DISTINCT email FROM stats WHERE email IS NOT NULL")
            for row in c.fetchall():
                if row[0]:
                    emails.add(row[0])
        except:
            pass
        conn.close()
    
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


def show_usage():
    """Show usage time for all users."""
    import sqlite3
    
    ensure_db()
    
    conn = sqlite3.connect("data/license.db")
    c = conn.cursor()
    
    c.execute("""
        SELECT device_id, usage_hours, last_validated, license_key
        FROM activations
        ORDER BY usage_hours DESC
    """)
    
    rows = c.fetchall()
    conn.close()
    
    print("\n" + "=" * 70)
    print(f"USER USAGE TIME ({len(rows)} users)")
    print("=" * 70)
    
    if not rows:
        print("\nNo usage data yet.")
        return
    
    total_hours = 0
    for device_id, hours, last_seen, license_key in rows:
        total_hours += hours
        
        # Format time
        mins = int(hours * 60)
        hrs = mins // 60
        mins = mins % 60
        time_str = f"{hrs}hr {mins}min" if hrs > 0 else f"{mins}min"
        
        # Format device
        device_short = device_id[:8] + "..." if device_id and len(device_id) > 8 else device_id
        
        # License type
        lic_type = "FREE" if license_key == "FREE_USER" else license_key[:12] if license_key else "N/A"
        
        print(f"\nDevice:    {device_short}")
        print(f"Usage:     {time_str}")
        print(f"Last Seen: {last_seen[:16] if last_seen else 'N/A'}")
        print(f"License:   {lic_type}")
        print("-" * 70)
    
    # Total
    total_mins = int(total_hours * 60)
    total_hrs = total_mins // 60
    total_mins = total_mins % 60
    print(f"\n📊 TOTAL USAGE: {total_hrs}hr {total_mins}min across {len(rows)} users")


def send_referral_reward(referred_email: str, referrer_email: str):
    """Generate license keys for completed referral."""
    import license as lic
    
    pro_key = lic.generate_license_key("pro")
    ult_key = lic.generate_license_key("ultimate")
    expiry = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    print("\n" + "=" * 70)
    print("REFERRAL REWARD - LICENSE KEYS GENERATED")
    print("=" * 70)
    
    print(f"\n📧 EMAIL 1 - To: {referred_email}")
    print("-" * 70)
    print(f"""
Subject: Your Seven Pro Access is Ready! 🎉

Hi!

You've used Seven for 7 hours and unlocked Pro access FREE for 1 month!

License Key: {pro_key}
Valid Until: {expiry}

To activate:
1. Open Seven → Plans page
2. Paste the key → Click Activate

Enjoy!
— Seven Team
""")
    
    print(f"\n📧 EMAIL 2 - To: {referrer_email}")
    print("-" * 70)
    print(f"""
Subject: Your Friend Used Seven - You Got Ultimate Free! 🎁

Hi!

Your friend ({referred_email}) used Seven for 7 hours.
Here's Ultimate access FREE for 1 month!

License Key: {ult_key}
Valid Until: {expiry}

To activate:
1. Open Seven → Plans page
2. Paste the key → Click Activate

Share more to earn more!
— Seven Team
""")
    
    print("=" * 70)
    print(f"Pro Key (for {referred_email}):      {pro_key}")
    print(f"Ultimate Key (for {referrer_email}): {ult_key}")
    print("=" * 70)


def show_help():
    """Show all available commands."""
    print("""
╔═══════════════════════════════════════════════════════════════════════════╗
║                         SEVEN ADMIN TOOLS                                  ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  LICENSE COMMANDS                                                         ║
║  ────────────────────────────────────────────────────────────────────     ║
║                                                                           ║
║  gen <email> <tier> <type>    Generate license key                        ║
║      tiers: pro, ultimate                                                 ║
║      types: monthly, yearly, lifetime                                     ║
║                                                                           ║
║      Examples:                                                            ║
║        python admin_tools.py gen user@email.com pro monthly               ║
║        python admin_tools.py gen user@email.com ultimate lifetime         ║
║                                                                           ║
║  pro <email>                  Quick: Pro 1-month key                      ║
║      Example: python admin_tools.py pro friend@gmail.com                  ║
║                                                                           ║
║  ultimate <email>             Quick: Ultimate 1-month key                 ║
║      Example: python admin_tools.py ultimate vip@gmail.com                ║
║                                                                           ║
║  list                         Show all active licenses                    ║
║      Example: python admin_tools.py list                                  ║
║                                                                           ║
║  revoke <key>                 Deactivate a license                        ║
║      Example: python admin_tools.py revoke VII-XXXX-XXXX-XXXX             ║
║                                                                           ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  REFERRAL COMMANDS                                                        ║
║  ────────────────────────────────────────────────────────────────────     ║
║                                                                           ║
║  referrals                    Check all referral status                   ║
║      Shows: Completed, Almost complete, All pending                       ║
║      Example: python admin_tools.py referrals                             ║
║                                                                           ║
║  reward <referred> <referrer> Generate reward keys for completed referral ║
║      Example: python admin_tools.py reward friend@email.com you@email.com ║
║                                                                           ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  USER COMMANDS                                                            ║
║  ────────────────────────────────────────────────────────────────────     ║
║                                                                           ║
║  emails                       List all registered emails                  ║
║      Example: python admin_tools.py emails                                ║
║                                                                           ║
║  usage                        Show usage time for all users               ║
║      Example: python admin_tools.py usage                                 ║
║                                                                           ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  DAILY WORKFLOW                                                           ║
║  ────────────────────────────────────────────────────────────────────     ║
║                                                                           ║
║  1. Check referrals:   python admin_tools.py referrals                    ║
║  2. Check usage:       python admin_tools.py usage                        ║
║  3. Send rewards:      python admin_tools.py reward <email1> <email2>     ║
║  4. Copy emails and send via Gmail                                        ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        show_help()
        sys.exit(0)
    
    cmd = sys.argv[1].lower()
    
    if cmd == "help" or cmd == "-h" or cmd == "--help":
        show_help()
    
    elif cmd == "gen":
        if len(sys.argv) < 3:
            print("Usage: python admin_tools.py gen <email> [tier] [plan]")
            print("Example: python admin_tools.py gen user@email.com pro monthly")
            sys.exit(1)
        email = sys.argv[2]
        tier = sys.argv[3] if len(sys.argv) > 3 else "ultimate"
        plan = sys.argv[4] if len(sys.argv) > 4 else "lifetime"
        generate_license(email, tier, plan)
    
    elif cmd == "pro":
        if len(sys.argv) < 3:
            print("Usage: python admin_tools.py pro <email>")
            sys.exit(1)
        generate_license(sys.argv[2], "pro", "monthly")
    
    elif cmd == "ultimate":
        if len(sys.argv) < 3:
            print("Usage: python admin_tools.py ultimate <email>")
            sys.exit(1)
        generate_license(sys.argv[2], "ultimate", "monthly")
    
    elif cmd == "list":
        list_licenses()
    
    elif cmd == "revoke":
        if len(sys.argv) < 3:
            print("Usage: python admin_tools.py revoke <license_key>")
            sys.exit(1)
        revoke_license(sys.argv[2])
    
    elif cmd == "referrals":
        check_referrals()
    
    elif cmd == "emails":
        list_emails()
    
    elif cmd == "usage":
        show_usage()
    
    elif cmd == "reward":
        if len(sys.argv) < 4:
            print("Usage: python admin_tools.py reward <referred_email> <referrer_email>")
            sys.exit(1)
        send_referral_reward(sys.argv[2], sys.argv[3])
    
    else:
        print(f"❌ Unknown command: {cmd}")
        print("Run 'python admin_tools.py help' for usage")