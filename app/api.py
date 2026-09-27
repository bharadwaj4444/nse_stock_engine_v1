from fastapi import FastAPI
from sqlalchemy import text
from app.db import engine

app = FastAPI(title="NSE Stock Engine V1")

@app.get("/health")
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}

@app.get("/")
def root():
    return {
        "service": "nse-stock-engine",
        "version": "0.1.0",
        "endpoints": ["/health"]
    }
