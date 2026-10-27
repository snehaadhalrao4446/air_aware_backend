import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


DB_PATH = Path(__file__).with_name("air_quality.db")

app = FastAPI(title="Hyperlocal Air Quality API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://air-aware-kj8z.vercel.app",
],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def connect_db():
    if not DB_PATH.exists():
        raise RuntimeError(f"Database file not found: {DB_PATH}")
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


@app.get("/")
def home():
    return {"message": "Air Quality API is running"}


@app.get("/locations")
def get_locations():
    with closing(connect_db()) as connection:
        rows = connection.execute(
            "SELECT DISTINCT location FROM air_quality ORDER BY location"
        ).fetchall()
    return [row[0] for row in rows]


@app.get("/readings")
def get_readings(location: str):
    with closing(connect_db()) as connection:
        rows = connection.execute(
            "SELECT * FROM air_quality WHERE LOWER(location) = LOWER(?) ORDER BY time",
            (location,),
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Location not found")
    return [dict(row) for row in rows]


@app.get("/summary")
def get_summary(location: str):
    pollutants = (
        "pm2_5",
        "pm10",
        "nitrogen_dioxide",
        "ozone",
        "sulphur_dioxide",
        "carbon_monoxide",
        "us_aqi",
    )
    with closing(connect_db()) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(air_quality)").fetchall()
        }
        available = [column for column in pollutants if column in columns]
        if not available:
            raise HTTPException(status_code=500, detail="No pollutant columns found")
        expressions = ", ".join(f'AVG("{column}") AS "{column}"' for column in available)
        row = connection.execute(
            f"SELECT COUNT(*) AS total_readings, {expressions} "
            "FROM air_quality WHERE LOWER(location) = LOWER(?)",
            (location,),
        ).fetchone()
    if row["total_readings"] == 0:
        raise HTTPException(status_code=404, detail="Location not found")
    averages = {
        column: round(row[column], 2) if row[column] is not None else None
        for column in available
    }
    return {
        "location": location,
        "total_readings": row["total_readings"],
        "averages": averages,
    }
