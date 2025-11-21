from locust import HttpUser, task, between
import random

class MLUser(HttpUser):
    wait_time = between(0.5, 1.0)

    @task
    def predict_fraud(self):
        # Enviamos "value" para alimentar el algoritmo de Drift Detection
        val = random.gauss(0.5, 0.1) # Datos normales
        
        # De vez en cuando enviamos datos "malos" para provocar Drift
        if random.random() > 0.95: 
            val = random.gauss(0.9, 0.2) # Datos desviados (Drift)

        self.client.post("/predict/modelo_fraude", json={
            "data": "vector_x",
            "value": val 
        })