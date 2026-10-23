import os
import sqlite3

appdata = os.environ.get('APPDATA', '')
db_path = os.path.join(appdata, 'SEVEN', 'data', 'telemetry.db')

print(f"DB path: {db_path}")
print(f"Exists: {os.path.exists(db_path)}")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    print("\n=== STATS TABLE ===")
    c.execute("SELECT device_id, email, active_hours, last_seen FROM stats")
    rows = c.fetchall()
    if rows:
        for row in rows:
            print(f"Device: {row[0][:8]}... | Email: {row[1]} | Hours: {round(row[2],4)} | Last: {row[3]}")
    else:
        print("EMPTY - no rows in stats table")
    
    print("\n=== DAILY USAGE ===")
    c.execute("SELECT date, hours FROM daily_usage ORDER BY date DESC LIMIT 14")
    rows = c.fetchall()
    if rows:
        for row in rows:
            mins = int(row[1] * 60)
            print(f"Date: {row[0]} | Hours: {row[1]:.4f} | Minutes: {mins}")
    else:
        print("EMPTY - no rows in daily_usage table")
    
    print("\n=== ALL TABLES ===")
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print(c.fetchall())
    
    conn.close()