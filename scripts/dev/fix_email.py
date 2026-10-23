import sqlite3
import os

# Read email from file
email = None
if os.path.exists("data/email.txt"):
    with open("data/email.txt", "r") as f:
        email = f.read().strip()

if not email:
    email = input("Enter your email: ").strip()
    # Save it
    os.makedirs("data", exist_ok=True)
    with open("data/email.txt", "w") as f:
        f.write(email)

# Read device ID
device_id = None
if os.path.exists("data/device_id.txt"):
    with open("data/device_id.txt", "r") as f:
        device_id = f.read().strip()

if not device_id:
    print("❌ Device ID not found. Run Seven first.")
    exit()

print(f"Device ID: {device_id[:12]}...")
print(f"Email: {email}")

# Update telemetry.db
if os.path.exists("data/telemetry.db"):
    conn = sqlite3.connect("data/telemetry.db")
    c = conn.cursor()
    
    c.execute("UPDATE stats SET email = ? WHERE device_id = ?", (email, device_id))
    
    rows_updated = c.rowcount
    conn.commit()
    conn.close()
    
    print(f"✓ Updated {rows_updated} row(s) in telemetry.db")
else:
    print("⚠️  telemetry.db not found")

# Update license.db (activations table)
if os.path.exists("data/license.db"):
    conn = sqlite3.connect("data/license.db")
    c = conn.cursor()
    
    # Check if activations table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='activations'")
    if c.fetchone():
        # Add email column if it doesn't exist
        try:
            c.execute("ALTER TABLE activations ADD COLUMN email TEXT")
            print("✓ Added email column to activations table")
        except:
            pass  # Column already exists
        
        c.execute("UPDATE activations SET email = ? WHERE device_id = ?", (email, device_id))
        
        rows_updated = c.rowcount
        conn.commit()
        print(f"✓ Updated {rows_updated} row(s) in license.db")
    
    conn.close()
else:
    print("⚠️  license.db not found")

print("\n✅ Email linking complete!")
print(f"\nNow run: python admin_tools.py usage {email}")