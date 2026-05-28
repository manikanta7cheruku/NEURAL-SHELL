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

SERVER_URL = "https://seven-server-u2rp.onrender.com"


def generate_license(email: str, tier: str = "ultimate",
                     plan_type: str = "lifetime", custom_key: str = None):
    """
    Generate a license key and save to Render PostgreSQL server.
    Works on ANY machine — not just developer machine.

    custom_key examples:
      LAUNCH-2025   → VII-LAUNCH-2025
      BETA-FRIEND   → VII-BETA-FRIEND
    """
    import requests
    import license as lic

    # Build the key
    built_key = lic.generate_license_key(tier, custom=custom_key)

    # Calculate expiry
    if plan_type == "monthly":
        expires_at   = (datetime.now() + timedelta(days=30)).isoformat()
        expiry_print = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    elif plan_type == "yearly":
        expires_at   = (datetime.now() + timedelta(days=365)).isoformat()
        expiry_print = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")
    else:
        expires_at   = None
        expiry_print = "Never (Lifetime)"

    # ── Save to server (PostgreSQL — works on any machine) ──
    server_ok = False
    try:
        r = requests.post(
            f"{SERVER_URL}/admin/license/create",
            json={
                "license_key": built_key,
                "email":       email,
                "tier":        tier,
                "plan_type":   plan_type,
                "expires_at":  expires_at
            },
            timeout=15
        )
        if r.status_code == 200:
            server_ok = True
            print(f"✅ Key saved to server (PostgreSQL)")
        else:
            print(f"⚠️  Server returned {r.status_code}: {r.text}")
    except Exception as e:
        print(f"⚠️  Could not reach server: {e}")
        print(f"   Key NOT saved to server. User cannot activate on other machines.")

    # ── Also save locally as backup ──
    try:
        lic.create_license(email, tier, plan_type, custom_key=custom_key)
        print(f"✅ Key saved locally  (this machine only)")
    except Exception as e:
        print(f"   Local save skipped: {e}")

    print()
    print("=" * 60)
    print(f"🎁 LICENSE GENERATED")
    print("=" * 60)
    print(f"Email:       {email}")
    print(f"Tier:        {tier.upper()}")
    print(f"Type:        {plan_type}")
    print(f"Expires:     {expiry_print}")
    print(f"License Key: {built_key}")
    print(f"Server:      {'✅ Saved (works anywhere)' if server_ok else '❌ Not saved (local only)'}")
    print("=" * 60)
    print(f"\n📧 EMAIL TO SEND:")
    print("-" * 60)
    print(f"""
Subject: Your Seven {tier.upper()} License Key

Hi!

Here's your Seven {tier.upper()} license key:

  {built_key}

Valid Until: {expiry_print}

To activate:
1. Open Seven
2. Go to Plans page
3. Paste the key → click Activate

Enjoy Seven!
— Manikanta
""")
    print("=" * 60)
    return built_key


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
    """Check pending and completed referrals from server."""
    import requests

    SERVER_URL = "https://seven-server-u2rp.onrender.com"

    print("\n" + "=" * 70)
    print("REFERRAL STATUS (from server)")
    print("=" * 70)

    try:
        # Get all referrals from server
        r = requests.get(f"{SERVER_URL}/admin/referrals", timeout=10)
        refs = r.json()

        # Get pending rewards
        p = requests.get(f"{SERVER_URL}/admin/rewards/pending", timeout=10)
        pending_rewards = p.json()

        if pending_rewards:
            print(f"\n🎉 COMPLETED — SEND KEYS NOW ({len(pending_rewards)}):")
            print("-" * 70)
            for pr in pending_rewards:
                print(f"  Referrer: {pr['referrer']} → Send ULTIMATE 1-month")
                print(f"  Referred: {pr['referred']} → Send PRO 1-month")
                print(f"\n  Command:")
                print(f"  python admin_tools.py reward {pr['referred']} {pr['referrer']}")
                print("-" * 70)
        else:
            print("\n✓ No pending rewards")

        # Show all referrals
        in_progress = [r for r in refs if not r['complete']]
        completed   = [r for r in refs if r['complete']]

        if in_progress:
            print(f"\n⏳ IN PROGRESS ({len(in_progress)}):")
            print("-" * 70)
            for ref in in_progress:
                hours = ref['hours']
                pct   = min(100, int((hours / 7) * 100))
                bar   = "█" * (pct // 10) + "░" * (10 - pct // 10)
                print(f"  Referrer: {ref['referrer'] or '—'}")
                print(f"  Referred: {ref['referred'] or '—'}")
                print(f"  Progress: {hours}h/7h [{bar}] {pct}%")
                print("-" * 70)

        if completed:
            print(f"\n✅ COMPLETED ({len(completed)}):")
            print("-" * 70)
            for ref in completed:
                sent = "SENT" if ref['reward_sent'] else "PENDING"
                print(f"  {ref['referrer']} → {ref['referred']} [{sent}]")
            print("-" * 70)

        print(f"\n📊 TOTAL: {len(refs)} referrals | "
              f"{len(completed)} completed | "
              f"{len(in_progress)} in progress")

    except Exception as e:
        print(f"❌ Could not reach server: {e}")
        print("Check your internet connection or server URL")

    print("=" * 70)


def check_referrals_local():
    """Check referrals from local SQLite (fallback)."""
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


def show_usage(email_filter=None):
    """Show usage time for all users or specific email."""
    import sqlite3
    
    # Check both databases
    license_db_exists = os.path.exists("data/license.db")
    telemetry_db_exists = os.path.exists("data/telemetry.db")
    
    if not license_db_exists and not telemetry_db_exists:
        print("\n❌ No usage data found. Databases don't exist yet.")
        return
    
    all_usage = {}
    
    # Collect from LICENSE database (activations table)
    if license_db_exists:
        conn = sqlite3.connect("data/license.db")
        c = conn.cursor()
        
        c.execute("""
            SELECT device_id, usage_hours, last_validated, license_key
            FROM activations
        """)
        
        for row in c.fetchall():
            device_id, hours, last_seen, license_key = row
            if device_id not in all_usage:
                all_usage[device_id] = {
                    'hours': hours or 0,
                    'last_seen': last_seen,
                    'license': license_key,
                    'email': None
                }
        conn.close()
    
    # Collect from TELEMETRY database (has email)
    if telemetry_db_exists:
        conn = sqlite3.connect("data/telemetry.db")
        c = conn.cursor()
        
        c.execute("""
            SELECT device_id, active_hours, last_seen, email
            FROM stats
        """)
        
        for row in c.fetchall():
            device_id, hours, last_seen, email = row
            if device_id in all_usage:
                # Merge data (telemetry has email)
                all_usage[device_id]['email'] = email
                # Use the higher hours count
                all_usage[device_id]['hours'] = max(all_usage[device_id]['hours'], hours or 0)
            else:
                all_usage[device_id] = {
                    'hours': hours or 0,
                    'last_seen': last_seen,
                    'license': 'FREE_USER',
                    'email': email
                }
        conn.close()
    
    # Filter by email if provided
    if email_filter:
        all_usage = {k: v for k, v in all_usage.items() if v['email'] and email_filter.lower() in v['email'].lower()}
    
    # Sort by usage hours (descending)
    sorted_usage = sorted(all_usage.items(), key=lambda x: x[1]['hours'], reverse=True)
    
    print("\n" + "=" * 90)
    if email_filter:
        print(f"USAGE TIME FOR: {email_filter} ({len(sorted_usage)} match{'es' if len(sorted_usage) != 1 else ''})")
    else:
        print(f"USER USAGE TIME ({len(sorted_usage)} user{'s' if len(sorted_usage) != 1 else ''})")
    print("=" * 90)
    
    if not sorted_usage:
        if email_filter:
            print(f"\n❌ No usage data found for email: {email_filter}")
        else:
            print("\n⚠️  No usage data yet. Users need to interact with Seven first.")
        return
    
    total_hours = 0
    for device_id, data in sorted_usage:
        hours = data['hours']
        total_hours += hours
        
        # Format time
        if hours < 1:
            mins = int(hours * 60)
            time_str = f"{mins} min"
        else:
            hrs = int(hours)
            mins = int((hours - hrs) * 60)
            time_str = f"{hrs}h {mins}m" if mins > 0 else f"{hrs}h"
        
        # Format device
        device_short = device_id[:12] + "..." if len(device_id) > 12 else device_id
        
        # License type
        lic = data['license']
        if lic == "FREE_USER":
            lic_display = "FREE"
        elif lic and lic.startswith("VII-"):
            lic_display = lic[:16] + "..."
        else:
            lic_display = lic or "N/A"
        
        # Email
        email = data['email'] or "—"
        
        # Last seen
        last_seen = data['last_seen']
        if last_seen:
            try:
                dt = datetime.fromisoformat(last_seen)
                last_seen_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                last_seen_str = last_seen[:16]
        else:
            last_seen_str = "—"
        
        print(f"\n📧 Email:     {email}")
        print(f"   Device:    {device_short}")
        print(f"   ⏱️  Usage:    {time_str}")
        print(f"   Last Seen: {last_seen_str}")
        print(f"   License:   {lic_display}")
        print("-" * 90)
    
    # Total summary
    if total_hours < 1:
        total_mins = int(total_hours * 60)
        total_str = f"{total_mins} min"
    else:
        total_hrs = int(total_hours)
        total_mins = int((total_hours - total_hrs) * 60)
        total_str = f"{total_hrs}h {total_mins}m" if total_mins > 0 else f"{total_hrs}h"
    
    print(f"\n📊 TOTAL USAGE: {total_str} across {len(sorted_usage)} user{'s' if len(sorted_usage) != 1 else ''}")
    print("=" * 90)


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


def demote_user(email_or_key: str):
    """
    Remove plan from user. Reverts to free tier.
    Can pass email or license key.
    """
    import sqlite3

    ensure_db()
    conn = sqlite3.connect("data/license.db")
    c    = conn.cursor()

    # Find by key or email
    if email_or_key.startswith("VII-"):
        c.execute("SELECT license_key, email, tier FROM licenses WHERE license_key = ?",
                  (email_or_key,))
    else:
        c.execute("SELECT license_key, email, tier FROM licenses WHERE email = ? AND is_active = 1",
                  (email_or_key,))

    row = c.fetchone()
    if not row:
        print(f"No active license found for: {email_or_key}")
        conn.close()
        return

    key, email, tier = row

    # Deactivate
    c.execute("UPDATE licenses SET is_active = 0 WHERE license_key = ?", (key,))
    # Remove device activations
    c.execute("DELETE FROM activations WHERE license_key = ?", (key,))
    conn.commit()
    conn.close()

    print("=" * 50)
    print(f"PLAN REMOVED")
    print("=" * 50)
    print(f"Email:  {email}")
    print(f"Key:    {key}")
    print(f"Was:    {tier.upper()}")
    print(f"Now:    FREE")
    print("=" * 50)
    print("User will see FREE tier on next app restart.")


def force_update(version, download_url, size_mb=0, changelog=""):
    """
    Force Seven to show update available WITHOUT server.
    Use when Render server is down.
    Creates a local update state file that Seven reads.
    
    Usage:
      python admin_tools.py update 1.2.0 https://github.com/.../SEVEN.Setup.1.2.0.exe
    """
    import json
    import os

    # Write update info to a file Seven checks on startup
    update_info = {
        "update_available":  True,
        "version":           version,
        "download_url":      download_url,
        "size_mb":           float(size_mb),
        "changelog":         [changelog] if changelog else [f"Seven {version} update"],
        "target_tier":       "all",
        "is_critical":       False,
        "download_mode":     "manual",
        "auto_deliver":      True,
        "published_at":      __import__('datetime').datetime.now().isoformat(),
        "source":            "local_override"
    }

    # Save to APPDATA so Seven reads it
    app_data = os.path.join(os.environ.get("APPDATA", ""), "SEVEN")
    os.makedirs(app_data, exist_ok=True)
    override_path = os.path.join(app_data, "update_override.json")

    with open(override_path, "w", encoding="utf-8") as f:
        json.dump(update_info, f, indent=2)

    print("=" * 60)
    print(f"UPDATE OVERRIDE SAVED")
    print("=" * 60)
    print(f"Version:  {version}")
    print(f"URL:      {download_url}")
    print(f"File:     {override_path}")
    print()
    print("Restart Seven — update banner will appear immediately.")
    print("No server needed.")
    print("=" * 60)


def clear_update_override():
    """Remove local update override."""
    import os
    path = os.path.join(os.environ.get("APPDATA",""), "SEVEN", "update_override.json")
    if os.path.exists(path):
        os.remove(path)
        print("Update override cleared.")
    else:
        print("No override found.")


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
║  usage                        Show usage time for ALL users               ║
║      Example: python admin_tools.py usage                                 ║
║                                                                           ║
║  usage <email>                Show usage time for SPECIFIC user           ║
║      Example: python admin_tools.py usage jacksonnote@gmail.com           ║
║                                                                           ║
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
            print("Usage: python admin_tools.py gen <email> [tier] [plan] [custom-key]")
            print()
            print("Examples:")
            print("  python admin_tools.py gen user@email.com pro monthly")
            print("  python admin_tools.py gen user@email.com ultimate lifetime")
            print("  python admin_tools.py gen user@email.com ultimate monthly LAUNCH-2025")
            print("  python admin_tools.py gen user@email.com ultimate lifetime VIP-MANIKANTA")
            print("  python admin_tools.py gen user@email.com pro monthly BETA-FRIEND")
            sys.exit(1)
        email      = sys.argv[2]
        tier       = sys.argv[3] if len(sys.argv) > 3 else "ultimate"
        plan       = sys.argv[4] if len(sys.argv) > 4 else "lifetime"
        custom_key = sys.argv[5] if len(sys.argv) > 5 else None
        generate_license(email, tier, plan, custom_key=custom_key)

    elif cmd == "custom":
        """
        Generate a custom key without needing email.
        Anyone who has the key can activate it.
        
        Usage:
          python admin_tools.py custom LAUNCH-2025
          python admin_tools.py custom BETA-FRIEND pro monthly
          python admin_tools.py custom EARLYBIRD ultimate yearly
          python admin_tools.py custom VIP-MK ultimate lifetime
        """
        if len(sys.argv) < 3:
            print("Usage: python admin_tools.py custom <key-name> [tier] [plan]")
            print()
            print("Examples:")
            print("  python admin_tools.py custom LAUNCH-2025")
            print("  python admin_tools.py custom BETA-FRIEND pro monthly")
            print("  python admin_tools.py custom EARLYBIRD ultimate yearly")
            print("  python admin_tools.py custom VIP-MK ultimate lifetime")
            sys.exit(1)
        custom_key = sys.argv[2]
        tier       = sys.argv[3] if len(sys.argv) > 3 else "ultimate"
        plan       = sys.argv[4] if len(sys.argv) > 4 else "lifetime"
        # Use generic placeholder — no email needed
        email      = f"key-{custom_key.lower()}@seven.app"
        generate_license(email, tier, plan, custom_key=custom_key)
    
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

    elif cmd == "demote":
        if len(sys.argv) < 3:
            print("Usage: python admin_tools.py demote <email or license_key>")
            print("Example: python admin_tools.py demote friend@gmail.com")
            print("Example: python admin_tools.py demote VII-XXXX-XXXX-XXXX")
            sys.exit(1)
        demote_user(sys.argv[2])
    
    elif cmd == "referrals":
        check_referrals()
    
    elif cmd == "emails":
        list_emails()
    
    elif cmd == "usage":
        if len(sys.argv) >= 3:
            # Specific user by email
            show_usage(email_filter=sys.argv[2])
        else:
            # All users
            show_usage()
    
    elif cmd == "reward":
        if len(sys.argv) < 4:
            print("Usage: python admin_tools.py reward <referred_email> <referrer_email>")
            sys.exit(1)
        send_referral_reward(sys.argv[2], sys.argv[3])

    elif cmd == "update":
        if len(sys.argv) < 4:
            print("Usage: python admin_tools.py update <version> <download_url> [size_mb] [changelog]")
            print()
            print("Example:")
            print("  python admin_tools.py update 1.2.0 https://github.com/.../SEVEN.Setup.1.2.0.exe 145")
            sys.exit(1)
        version      = sys.argv[2]
        url          = sys.argv[3]
        size         = sys.argv[4] if len(sys.argv) > 4 else "0"
        changelog    = sys.argv[5] if len(sys.argv) > 5 else ""
        force_update(version, url, size, changelog)

    elif cmd == "clear-update":
        clear_update_override()
    
    else:
        print(f"❌ Unknown command: {cmd}")
        print("Run 'python admin_tools.py help' for usage")