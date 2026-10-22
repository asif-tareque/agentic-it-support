
import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="AI Infrastructure Copilot")

# SQLite database file
DB_PATH = Path(__file__).with_name("copilot.db")


# Connect to the database
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Create table and insert initial data
def init_db():
    with closing(get_connection()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                hostname TEXT PRIMARY KEY,
                cpu_usage REAL NOT NULL,
                memory_usage REAL NOT NULL,
                status TEXT NOT NULL
            )
        """)

        conn.executemany("""
            INSERT OR IGNORE INTO servers
            (hostname, cpu_usage, memory_usage, status)
            VALUES (?, ?, ?, ?)
        """, [
            ("web-server-01", 35, 60, "healthy"),
            ("database-server-01", 95, 88, "critical")
        ])

        conn.commit()


# Initialise the database for this learning project
init_db()


# Validate incoming metrics
class ServerMetrics(BaseModel):
    cpu_usage: float = Field(ge=0, le=100)
    memory_usage: float = Field(ge=0, le=100)


# Determine server status
def calculate_status(cpu, memory):
    if cpu >= 90 or memory >= 90:
        return "critical"
    elif cpu >= 70 or memory >= 75:
        return "warning"
    return "healthy"


# Read server data from SQLite
def fetch_servers():
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "SELECT * FROM servers"
        ).fetchall()
        return [dict(row) for row in rows]


@app.get("/")
def home():
    return {"message": "Infrastructure Copilot running"}


@app.get("/servers")
def get_servers():
    return fetch_servers()


@app.get("/incidents")
def get_incidents():
    incidents = []

    for server in fetch_servers():
        if server["status"] == "healthy":
            continue

        reasons = []

        if server["cpu_usage"] >= 70:
            reasons.append("High CPU usage")

        if server["memory_usage"] >= 75:
            reasons.append("High memory usage")

        incidents.append({
            "hostname": server["hostname"],
            "severity": server["status"],
            "reason": ", ".join(reasons)
        })

    return incidents


@app.patch("/servers/{hostname}/metrics")
def update_server_metrics(
    hostname: str,
    metrics: ServerMetrics
):
    status = calculate_status(
        metrics.cpu_usage,
        metrics.memory_usage
    )

    with closing(get_connection()) as conn:
        cursor = conn.execute("""
            UPDATE servers
            SET cpu_usage = ?,
                memory_usage = ?,
                status = ?
            WHERE hostname = ?
        """, (
            metrics.cpu_usage,
            metrics.memory_usage,
            status,
            hostname
        ))

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Server not found"
            )

        conn.commit()

    return {
        "message": "Metrics updated successfully",
        "server": {
            "hostname": hostname,
            "cpu_usage": metrics.cpu_usage,
            "memory_usage": metrics.memory_usage,
            "status": status
        }
    }
