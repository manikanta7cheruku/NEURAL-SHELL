"""
=============================================================================
PROJECT SEVEN - backend/admin_server.py (Admin Analytics Dashboard)
Version: 1.0
=============================================================================
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import sqlite3
from datetime import datetime, timedelta
import os

app = FastAPI(title="Seven Admin Dashboard", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TELEMETRY_DB = "data/telemetry.db"

# =============================================================================
# ANALYTICS ENDPOINTS
# =============================================================================

@app.get("/api/stats/overview")
def get_overview():
    """Get high-level stats."""
    if not os.path.exists(TELEMETRY_DB):
        return {"total_downloads": 0, "active_7d": 0, "active_30d": 0, "new_this_week": 0, "retention_7d": 0, "retention_30d": 0, "free_users": 0, "pro_users": 0}
    
    conn = sqlite3.connect(TELEMETRY_DB)
    c = conn.cursor()
    
    # Total downloads
    c.execute("SELECT COUNT(*) FROM stats")
    total = c.fetchone()[0]
    
    if total == 0:
        conn.close()
        return {"total_downloads": 0, "active_7d": 0, "active_30d": 0, "new_this_week": 0, "retention_7d": 0, "retention_30d": 0, "free_users": 0, "pro_users": 0}
    
    # Active users (last 7 days)
    seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
    c.execute("SELECT COUNT(*) FROM stats WHERE last_seen >= ?", (seven_days_ago,))
    active_7d = c.fetchone()[0]
    
    # Active users (last 30 days)
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    c.execute("SELECT COUNT(*) FROM stats WHERE last_seen >= ?", (thirty_days_ago,))
    active_30d = c.fetchone()[0]
    
    # New this week
    c.execute("SELECT COUNT(*) FROM stats WHERE install_date >= ?", (seven_days_ago,))
    new_week = c.fetchone()[0]
    
    # License tier breakdown
    c.execute("SELECT COUNT(*) FROM stats WHERE license_tier = 'free' OR license_tier IS NULL")
    free_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM stats WHERE license_tier = 'pro'")
    pro_users = c.fetchone()[0]
    
    conn.close()
    
    return {
        "total_downloads": total,
        "active_7d": active_7d,
        "active_30d": active_30d,
        "new_this_week": new_week,
        "retention_7d": round((active_7d / total * 100) if total > 0 else 0, 1),
        "retention_30d": round((active_30d / total * 100) if total > 0 else 0, 1),
        "free_users": free_users,
        "pro_users": pro_users,
    }

@app.get("/api/stats/users")
def get_users(limit: int = 100):
    """Get user list with details."""
    if not os.path.exists(TELEMETRY_DB):
        return []
    
    conn = sqlite3.connect(TELEMETRY_DB)
    c = conn.cursor()
    
    c.execute("""
        SELECT device_id, country, active_hours, last_seen, email, install_date, license_tier
        FROM stats
        ORDER BY active_hours DESC
        LIMIT ?
    """, (limit,))
    
    users = []
    for row in c.fetchall():
        users.append({
            "device_id": row[0][:8] + "..." if row[0] else "—",
            "country": row[1] or "Unknown",
            "active_hours": round(row[2] or 0, 1),
            "last_seen": row[3] or "—",
            "email": row[4] if row[4] else "—",
            "install_date": row[5] or "—",
            "license_tier": row[6] if row[6] else "free",
        })
    
    conn.close()
    return users

@app.get("/api/stats/countries")
def get_countries():
    """Get user count by country."""
    if not os.path.exists(TELEMETRY_DB):
        return []
    
    conn = sqlite3.connect(TELEMETRY_DB)
    c = conn.cursor()
    
    c.execute("""
        SELECT country, COUNT(*) as count
        FROM stats
        GROUP BY country
        ORDER BY count DESC
    """)
    
    countries = [{"country": row[0] or "Unknown", "count": row[1]} for row in c.fetchall()]
    conn.close()
    return countries

@app.get("/api/stats/daily-active")
def get_daily_active():
    """Get daily active user count for last 30 days."""
    if not os.path.exists(TELEMETRY_DB):
        return []
    
    conn = sqlite3.connect(TELEMETRY_DB)
    c = conn.cursor()
    
    daily_data = []
    for i in range(30, -1, -1):
        date = (datetime.now() - timedelta(days=i)).date().isoformat()
        next_date = (datetime.now() - timedelta(days=i-1)).date().isoformat()
        
        c.execute("""
            SELECT COUNT(DISTINCT device_id) 
            FROM stats 
            WHERE DATE(last_seen) = ?
        """, (date,))
        
        count = c.fetchone()[0]
        daily_data.append({"date": date, "count": count})
    
    conn.close()
    return daily_data

# =============================================================================
# ADMIN DASHBOARD UI
# =============================================================================

@app.get("/", response_class=HTMLResponse)
def admin_dashboard():
    """HTML admin dashboard."""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Seven Admin Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', sans-serif; background: #09090b; color: #e4e4e7; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { font-size: 24px; margin-bottom: 20px; color: #6366f1; }
        h2 { font-size: 18px; margin: 30px 0 15px; color: #e4e4e7; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .card { background: #141418; border: 1px solid #23232a; border-radius: 8px; padding: 20px; }
        .card-title { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #71717a; margin-bottom: 10px; }
        .card-value { font-size: 28px; font-weight: 600; color: #e4e4e7; }
        .chart-container { background: #141418; border: 1px solid #23232a; border-radius: 8px; padding: 20px; margin-bottom: 30px; }
        table { width: 100%; border-collapse: collapse; background: #141418; border: 1px solid #23232a; border-radius: 8px; overflow: hidden; }
        th { background: #0c0c0f; padding: 12px; text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #71717a; border-bottom: 1px solid #23232a; }
        td { padding: 12px; font-size: 13px; border-bottom: 1px solid #23232a; }
        tr:last-child td { border-bottom: none; }
        .refresh { background: #6366f1; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; margin-bottom: 20px; }
        .refresh:hover { background: #5558e3; }
        .badge { padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 600; }
        .badge-free { background: #71717a; color: white; }
        .badge-pro { background: #6366f1; color: white; }
        .no-data { text-align: center; padding: 40px; color: #71717a; }
    </style>
</head>
<body>
    <div class="container">
        <h1>SEVEN ADMIN DASHBOARD</h1>
        <button class="refresh" onclick="loadStats()">Refresh</button>
        
        <div class="grid" id="stats-grid">
            <div class="no-data">Loading...</div>
        </div>
        
        <h2>Daily Active Users (Last 30 Days)</h2>
        <div class="chart-container">
            <canvas id="daily-chart" style="max-height: 300px;"></canvas>
        </div>
        
        <h2>Users</h2>
        <table id="users-table">
            <thead>
                <tr>
                    <th>Device ID</th>
                    <th>Country</th>
                    <th>Active Hours</th>
                    <th>License</th>
                    <th>Email</th>
                    <th>Last Seen</th>
                    <th>Installed</th>
                </tr>
            </thead>
            <tbody id="users-body">
                <tr><td colspan="7" class="no-data">Loading...</td></tr>
            </tbody>
        </table>
        
        <h2>Countries</h2>
        <table id="countries-table">
            <thead>
                <tr>
                    <th>Country</th>
                    <th>Users</th>
                </tr>
            </thead>
            <tbody id="countries-body">
                <tr><td colspan="2" class="no-data">Loading...</td></tr>
            </tbody>
        </table>
    </div>
    
    <script>
        let chartInstance = null;
        
        async function loadStats() {
            try {
                // Overview stats
                const overview = await fetch('/api/stats/overview').then(r => r.json());
                document.getElementById('stats-grid').innerHTML = `
                    <div class="card">
                        <div class="card-title">Total Downloads</div>
                        <div class="card-value">${overview.total_downloads}</div>
                    </div>
                    <div class="card">
                        <div class="card-title">Active (7d)</div>
                        <div class="card-value">${overview.active_7d} <span style="font-size: 14px; color: #71717a;">(${overview.retention_7d}%)</span></div>
                    </div>
                    <div class="card">
                        <div class="card-title">Active (30d)</div>
                        <div class="card-value">${overview.active_30d} <span style="font-size: 14px; color: #71717a;">(${overview.retention_30d}%)</span></div>
                    </div>
                    <div class="card">
                        <div class="card-title">New This Week</div>
                        <div class="card-value">${overview.new_this_week}</div>
                    </div>
                    <div class="card">
                        <div class="card-title">Free Users</div>
                        <div class="card-value">${overview.free_users}</div>
                    </div>
                    <div class="card">
                        <div class="card-title">Pro Users</div>
                        <div class="card-value" style="color: #6366f1;">${overview.pro_users}</div>
                    </div>
                `;
                
                // Users table
                const users = await fetch('/api/stats/users?limit=50').then(r => r.json());
                if (users.length === 0) {
                    document.getElementById('users-body').innerHTML = '<tr><td colspan="7" class="no-data">No users yet</td></tr>';
                } else {
                    document.getElementById('users-body').innerHTML = users.map(u => `
                        <tr>
                            <td style="font-family: monospace;">${u.device_id}</td>
                            <td>${u.country}</td>
                            <td>${u.active_hours}h</td>
                            <td><span class="badge badge-${u.license_tier}">${u.license_tier.toUpperCase()}</span></td>
                            <td style="font-size: 11px;">${u.email}</td>
                            <td style="font-size: 11px; color: #71717a;">${u.last_seen !== '—' ? new Date(u.last_seen).toLocaleString() : '—'}</td>
                            <td style="font-size: 11px; color: #71717a;">${u.install_date !== '—' ? new Date(u.install_date).toLocaleDateString() : '—'}</td>
                        </tr>
                    `).join('');
                }
                
                // Countries table
                const countries = await fetch('/api/stats/countries').then(r => r.json());
                if (countries.length === 0) {
                    document.getElementById('countries-body').innerHTML = '<tr><td colspan="2" class="no-data">No data yet</td></tr>';
                } else {
                    document.getElementById('countries-body').innerHTML = countries.map(c => `
                        <tr>
                            <td>${c.country}</td>
                            <td>${c.count}</td>
                        </tr>
                    `).join('');
                }
                
                // Daily active users chart
                const dailyData = await fetch('/api/stats/daily-active').then(r => r.json());
                
                if (chartInstance) {
                    chartInstance.destroy();
                }
                
                const ctx = document.getElementById('daily-chart').getContext('2d');
                chartInstance = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: dailyData.map(d => new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })),
                        datasets: [{
                            label: 'Active Users',
                            data: dailyData.map(d => d.count),
                            borderColor: '#6366f1',
                            backgroundColor: 'rgba(99, 102, 241, 0.1)',
                            tension: 0.4,
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: { color: '#71717a' },
                                grid: { color: '#23232a' }
                            },
                            x: {
                                ticks: { color: '#71717a', maxRotation: 45 },
                                grid: { display: false }
                            }
                        }
                    }
                });
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }
        
        loadStats();
    </script>
</body>
</html>
    """

# =============================================================================
# SERVER LAUNCHER
# =============================================================================

def start_admin_server():
    """Start admin dashboard server."""
    import uvicorn
    import threading
    
    def _run():
        uvicorn.run(app, host="127.0.0.1", port=8888, log_level="warning", access_log=False)
    
    thread = threading.Thread(target=_run, daemon=True, name="AdminServer")
    thread.start()
    print("[ADMIN] Dashboard available at http://localhost:8888")