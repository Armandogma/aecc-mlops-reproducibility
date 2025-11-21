
import uvicorn
import httpx
import redis.asyncio as redis
import asyncio
import time
import json
import random  
import numpy as np
from scipy import stats
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel

#  Configuración
UMBRAL_INACTIVIDAD = 40 # Segundos para marcar un worker como ERROR
VENTANA_DRIFT = 50
NIVEL_SIGNIFICANCIA = 0.05

DATOS_ENTRENAMIENTO_REF = np.random.normal(loc=0.5, scale=0.1, size=1000)
buffer_datos_entrada = []

app = FastAPI(title="AECC Control Architecture")
redis_client = None
http_client = None  

class WorkerInfo(BaseModel):
    id_worker: str
    id_model: str
    version: float
    endpoint: str

@app.on_event("startup")
async def startup_event():
    global redis_client, http_client
    # 1. Conexión a Redis
    redis_client = redis.from_url("redis://localhost", decode_responses=True)
    try:
        await redis_client.ping()
        print("--> [INIT] Conectado a Redis (Tabla de Control)")
    except Exception as e:
        print(f"Error Redis: {e}")
    
    # 2. Cliente HTTP Global (CRÍTICO para 10k usuarios)
    # Limits ajustados para soportar alta concurrencia local
    limits = httpx.Limits(max_keepalive_connections=100, max_connections=200)
    http_client = httpx.AsyncClient(limits=limits, timeout=10.0)
    
    # 3. Tarea de fondo
    asyncio.create_task(watchdog_process())

@app.on_event("shutdown")
async def shutdown_event():
    if http_client:
        await http_client.aclose()

# Watchdog
async def watchdog_process():
    while True:
        try:
            if redis_client:
                async for key in redis_client.scan_iter("worker:*"):
                    data = await redis_client.hgetall(key)
                    if data and data.get("status") == "ACTIVE":
                        last_act = float(data.get("last_activity", 0))
                        if time.time() - last_act > UMBRAL_INACTIVIDAD:
                            await redis_client.hset(key, "status", "ERROR")
                            print(f"--> [WATCHDOG] Worker {data['id_worker']} marcado ERROR.")
        except Exception:
            pass
        await asyncio.sleep(5)

# Drift Detection 
def check_data_drift(new_value: float):
    global buffer_datos_entrada
    buffer_datos_entrada.append(new_value)
    if len(buffer_datos_entrada) >= VENTANA_DRIFT:
        statistic, p_value = stats.ks_2samp(DATOS_ENTRENAMIENTO_REF, buffer_datos_entrada)
        if p_value < NIVEL_SIGNIFICANCIA:
            print(f"*** ALERTA DE DRIFT (p={p_value:.4f}) ***")
        buffer_datos_entrada = []

 
async def find_best_worker(id_model: str):
    workers = []
    # Recolectar workers activos
    async for key in redis_client.scan_iter("worker:*"):
        w = await redis_client.hgetall(key)
        if w.get("id_model") == id_model and w.get("status") == "ACTIVE":
            workers.append(w)
    
    if not workers: return None
    
    
    random.shuffle(workers)
    
    # Algoritmo: Menor 'current_requests' (Least Connections) 
    return min(workers, key=lambda w: int(w.get("current_requests", 0)))

#  Endpoints 

@app.post("/register_worker")
async def register_worker(worker: WorkerInfo):
    print(f"--> Registrando nuevo worker: {worker.id_worker}")
    await redis_client.hset(f"worker:{worker.id_worker}", mapping={
        "id_worker": worker.id_worker,
        "id_model": worker.id_model,
        "version": worker.version,
        "endpoint": worker.endpoint,
        "status": "ACTIVE",
        "current_requests": 0,
        "avg_latency_ms": 0.0,
        "total_requests": 0,
        "errors": 0,
        "last_activity": time.time()
    })
    return {"status": "registered"}

@app.get("/")
def health_check():
    return {"system": "AECC Online"}

@app.post("/predict/{id_model}")
async def predict_proxy(id_model: str, request: Request, background_tasks: BackgroundTasks):
    # 1. Balanceo
    worker = await find_best_worker(id_model)
    if not worker:
        print("!!! ERROR: No hay workers disponibles")
        raise HTTPException(status_code=503, detail="No active workers")

    worker_key = f"worker:{worker['id_worker']}"
    
    
    try:
        body = await request.json()
        val = float(body.get("value", 0.5))
        background_tasks.add_task(check_data_drift, val)
    except:
        pass

    # 2. Actualizar Tabla (Incrementar Carga)
    await redis_client.hincrby(worker_key, "current_requests", 1)
    await redis_client.hset(worker_key, "last_activity", time.time())
    
    start_time = time.time()
    
    try:
        response = await http_client.post(f"{worker['endpoint']}/predict", json=await request.json())
        response.raise_for_status()
        data = response.json()
        
    except Exception as e:

        await redis_client.hset(worker_key, "status", "ERROR")
        await redis_client.hincrby(worker_key, "errors", 1)
        print(f"!!! Worker {worker['id_worker']} FALLÓ. Marcado como ERROR.")
        print(f"Error en worker {worker['id_worker']}: {e}")
        
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # 4. Decrementar Carga y guardar métricas
        duration_ms = (time.time() - start_time) * 1000
        await redis_client.hincrby(worker_key, "current_requests", -1)
        await redis_client.hincrby(worker_key, "total_requests", 1)
        await redis_client.hset(worker_key, "avg_latency_ms", f"{duration_ms:.2f}")

    return data

@app.get("/dashboard_data")
async def dashboard_data():
    workers = []
    if redis_client:
        async for key in redis_client.scan_iter("worker:*"):
            w = await redis_client.hgetall(key)
            # Conversiones de tipo
            w['current_requests'] = int(w.get('current_requests', 0))
            w['avg_latency_ms'] = float(w.get('avg_latency_ms', 0))
            w['total_requests'] = int(w.get('total_requests', 0))
            w['errors'] = int(w.get('errors', 0))
            workers.append(w)
    
    # ENVOLTURA MAGICA
    return {"data": workers}

@app.get("/stats_fig_3")
async def get_stats_fig_3():
    workers = await dashboard_data()
    return {w.get("id_worker"): int(w.get("total_requests", 0)) for w in workers}

if __name__ == "__main__":
    # Aumentamos workers de uvicorn para que el Control Module aguante más carga
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")