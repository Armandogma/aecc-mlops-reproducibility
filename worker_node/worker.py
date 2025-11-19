# worker.py
import uvicorn
import httpx
import random
import time
import os
import asyncio # Usamos asyncio para la simulación
from fastapi import FastAPI, Request

app = FastAPI()

# --- Configuración del Worker ---
# Leemos las variables de entorno que Docker nos dará
WORKER_ID = os.getenv("WORKER_ID", f"worker_local_{random.randint(1000, 9999)}")
CONTROL_MODULE_URL = os.getenv("CONTROL_MODULE_URL", "http://localhost:8000")
WORKER_ENDPOINT = os.getenv("WORKER_ENDPOINT", "http://localhost:8001")
MODELO_ID = "modelo_fraude" # Recuerda cambiar esto por el nombre de tu modelo real
VERSION = 1.2

@app.on_event("startup")
async def register_worker():
    """
    Al iniciar, este worker se registra a sí mismo en la Tabla de Control.
    """
    print(f"Iniciando {WORKER_ID} ({MODELO_ID} v{VERSION})... registrando en {CONTROL_MODULE_URL}")
    async with httpx.AsyncClient() as client:
        try:
            await client.post(f"{CONTROL_MODULE_URL}/register_worker", json={
                "id_worker": WORKER_ID,
                "id_modelo": MODELO_ID,
                "version": VERSION,
                "endpoint": WORKER_ENDPOINT
            })
            print(f"Worker {WORKER_ID} registrado exitosamente.")
        except httpx.ConnectError:
            print(f"ERROR: No se pudo conectar al Módulo de Control en {CONTROL_MODULE_URL}")
            print("Asegúrate de que 'control_module.py' esté corriendo.")

@app.post("/predict")
async def predict(request: Request):
    """
    Simula una predicción de ML.
    """
    # Simula el tiempo que tarda un modelo en procesar (entre 100ms y 500ms)
    processing_time = random.uniform(0.1, 0.5) 
    await asyncio.sleep(processing_time) # Usamos asyncio.sleep (no bloqueante)
    
    return {
        "prediction": "ok", 
        "processed_by": WORKER_ID,
        "processing_time_ms": processing_time * 1000
    }

@app.get("/health")
def health_check():
    """Endpoint simple para que el Módulo de Control verifique si está vivo."""
    return {"status": "alive", "worker_id": WORKER_ID}