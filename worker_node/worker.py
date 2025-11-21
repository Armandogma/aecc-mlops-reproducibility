# worker.py
import uvicorn
import httpx
import os
import time
import random
from fastapi import FastAPI, Request

app = FastAPI()

# Variables de entorno (Docker)
WORKER_ID = os.getenv("WORKER_ID", f"w-{random.randint(100,999)}")
CONTROL_URL = os.getenv("CONTROL_MODULE_URL", "http://localhost:8000")
MY_ENDPOINT = os.getenv("WORKER_ENDPOINT", "http://localhost:8001")

@app.on_event("startup")
async def register():
    # Esperar un poco a que Redis/Control suban
    time.sleep(3) 
    async with httpx.AsyncClient() as client:
        try:
            # Registro alineado con Table I 
            resp = await client.post(f"{CONTROL_URL}/register_worker", json={
                "id_worker": WORKER_ID,
                "id_model": "modelo_fraude",
                "version": 1.2,
                "endpoint": MY_ENDPOINT
            })
            print(f"Worker {WORKER_ID} registrado: {resp.status_code}")
        except Exception as e:
            print(f"Fallo al registrar {WORKER_ID}: {e}")

@app.post("/predict")
async def predict(request: Request):
    # Simular inferencia (Random Forest)
    time.sleep(random.uniform(0.05, 0.2)) # Latencia simulada
    return {
        "prediction": random.choice([0, 1]), # 0: Legit, 1: Fraude
        "worker": WORKER_ID
    }