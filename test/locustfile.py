# locustfile.py
from locust import HttpUser, task, between

class MLUser(HttpUser):
    # El usuario simulado espera entre 0.5 y 1 segundo entre cada solicitud
    wait_time = between(0.5, 1.0)
    
    @task
    def call_predict(self):
        # Llama al Módulo de Control (el balanceador), no al worker
        self.client.post(
            "/predict/modelo_fraude", # Asegúrate de que 'modelo_fraude' coincida
            json={"data": "datos_del_usuario_simulado"}
        )