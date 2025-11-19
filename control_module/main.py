# control_module.py
import uvicorn
import httpx
import redis.asyncio as redis # Usamos redis asíncrono
import asyncio
import time
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

# --- Modelos de Datos (para validar la entrada) ---
class WorkerInfo(BaseModel):
    id_worker: str
    id_modelo: str
    version: float
    endpoint: str

# --- Configuración ---
app = FastAPI(title="Módulo de Control de ML (AECC)")
redis_client = None

@app.on_event("startup")
async def startup_event():
    global redis_client
    # Conecta a Redis (asegúrate de que Redis esté corriendo en localhost:6379)
    try:
        redis_client = redis.from_url("redis://localhost", decode_responses=True)
        await redis_client.ping()
        print("Conectado a Redis en localhost:6379")
    except Exception as e:
        print(f"*** ERROR CRÍTICO: No se pudo conectar a Redis en localhost:6379 ***")
        print(f"Asegúrate de que el contenedor de Redis esté corriendo (Fase 1).")
        print(f"Error: {e}")
        # exit() # Descomenta esto si quieres que falle si no hay Redis

# Cliente HTTP asíncrono para llamar a los workers
http_client = httpx.AsyncClient(timeout=10.0)


# --- Lógica de la Tabla de Control ---

async def get_all_workers():
    """Obtiene todos los workers de Redis."""
    if redis_client is None: return []
    workers = []
    # Usamos 'async for' para iterar sobre la "corriente" de llaves
    async for key in redis_client.scan_iter("worker:*"):
        worker_data = await redis_client.hgetall(key)
        if worker_data:
            workers.append(worker_data)
    return workers

@app.post("/register_worker")
async def register_worker(worker: WorkerInfo):
    """
    Endpoint para que los workers se registren (Sección 3.4 del artículo).
    Esto escribe en la Tabla de Control (Redis).
    """
    worker_key = f"worker:{worker.id_worker}"
    await redis_client.hset(worker_key, mapping={
        "id_worker": worker.id_worker,
        "id_modelo": worker.id_modelo,
        "version": worker.version,
        "endpoint": worker.endpoint,
        "estado": "ACTIVO",
        "solic_actuales": 0,
        "latencia_media_ms": 0,
        "total_solicitudes": 0, # Para Fig. 3
        "ultima_actividad": int(time.time())
    })
    return {"status": "registrado", "worker_id": worker.id_worker}

async def find_best_worker(id_modelo: str) -> dict | None:
    """
    IMPLEMENTACIÓN DEL BALANCEADOR (Sección 3.3 del artículo).
    Lógica: Menor número de solicitudes actuales.
    """
    all_workers = await get_all_workers()
    
    # Filtrar por modelo y estado
    valid_workers = [
        w for w in all_workers 
        if w.get("id_modelo") == id_modelo and w.get("estado") == "ACTIVO"
    ]
    
    if not valid_workers:
        return None
        
    # Encuentra el worker con menos solicitudes actuales (convirtiendo a int)
    best_worker = min(
        valid_workers, 
        key=lambda w: int(w.get("solic_actuales", 0))
    )
    return best_worker

# --- Endpoints Públicos ---

@app.post("/predict/{id_modelo}")
async def predict_load_balanced(id_modelo: str, request: Request):
    """
    Este es el API Gateway (Punto 1 de Arquitectura).
    """
    start_time = time.time()
    
    # 1. Encontrar el mejor worker
    worker = await find_best_worker(id_modelo)
    
    if not worker:
        # Si no hay workers, devolvemos el error 503 que viste.
        raise HTTPException(status_code=503, detail="No hay workers disponibles para este modelo")

    worker_key = f"worker:{worker['id_worker']}"
    worker_endpoint = worker['endpoint']

    try:
        # 2. Incrementar la carga en la Tabla de Control (Paso 5 del Flujo)
        await redis_client.hincrby(worker_key, "solic_actuales", 1)
        await redis_client.hset(worker_key, "ultima_actividad", int(time.time()))

        # 3. Reenviar la solicitud al worker
        req_data = await request.json()
        response = await http_client.post(f"{worker_endpoint}/predict", json=req_data)
        response.raise_for_status() # Lanza error si el worker falló (ej. 500)
        
        response_data = response.json()
        
    except Exception as e:
        # 4.a. Auto-corrección (Sección 3.4)
        await redis_client.hset(worker_key, "estado", "ERROR")
        raise HTTPException(status_code=500, detail=f"Error del Worker: {e}")
    
    finally:
        # 4.b. Decrementar la carga en la Tabla de Control (Paso 6 del Flujo)
        await redis_client.hincrby(worker_key, "solic_actuales", -1)

    # 5. Actualizar métricas (para monitoreo)
    latency_ms = (time.time() - start_time) * 1000
    await redis_client.hincrby(worker_key, "total_solicitudes", 1)
    await redis_client.hset(worker_key, "latencia_media_ms", f"{latency_ms:.2f}")

    return response_data

# --- Endpoints de Monitoreo (Para Figuras 3 y 4) ---

@app.get("/dashboard_data")
async def get_dashboard_data():
    """
    Este endpoint alimenta el dashboard de Grafana (Fig. 4).
    Devuelve el estado de toda la Tabla de Control.
    """
    workers = await get_all_workers()
    # Limpiar datos para que JSON los entienda
    for w in workers:
        w['version'] = float(w.get('version', 0))
        w['solic_actuales'] = int(w.get('solic_actuales', 0))
        w['latencia_media_ms'] = float(w.get('latencia_media_ms', 0))
        w['total_solicitudes'] = int(w.get('total_solicitudes', 0))
        w['ultima_actividad'] = int(w.get('ultima_actividad', 0))
    return workers

@app.get("/stats_fig_3")
async def get_stats_fig_3():
    """
    Datos específicos para generar la Figura 3.
    """
    workers = await get_all_workers()
    distribution = {
        w.get("id_worker"): int(w.get("total_solicitudes", 0))
        for w in workers if w.get("estado") == "ACTIVO"
    }
    return distribution

if __name__ == "__main__":
    # Inicia el Módulo de Control
    uvicorn.run(app, host="0.0.0.0", port=8000)