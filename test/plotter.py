# plotter.py (VERSIÓN CORREGIDA PARA LEER HTML)
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import os
import json
import re  # Importamos la librería para buscar texto

sns.set_theme(style="whitegrid")

def parse_locust_report(html_file):
    """
    Esta nueva función abre el reporte HTML de Locust,
    busca el JSON de datos y extrae el historial.
    """
    print(f"Procesando el reporte: {html_file}")
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Usamos una expresión regular para encontrar el JSON gigante
        # que Locust guarda dentro del HTML
        match = re.search(r'var report = (\{.*\});', content)
        if not match:
            print(f"Error: No se pudo encontrar el JSON 'var report' en {html_file}")
            return None
        
        data = json.loads(match.group(1))
        
        # Extraer el historial de datos
        history = data.get("history")
        if not history:
            print(f"Error: No se encontró 'history' en el JSON de {html_file}")
            return None
            
        # Convertir el historial a un DataFrame de pandas
        df = pd.DataFrame(history)
        
        # Asegurarnos de que las columnas que necesitamos existan
        if 'user_count' not in df.columns or 'response_time_percentile_0.5' not in df.columns:
            print(f"Error: El historial en {html_file} no tiene 'user_count' o 'response_time_percentile_0.5'")
            return None
        
        print(f"Se procesó {html_file} exitosamente.")
        return df
        
    except FileNotFoundError:
        print(f"Error: No se encontró el archivo de reporte {html_file}")
        return None
    except Exception as e:
        print(f"Error al procesar {html_file}: {e}")
        return None

def plot_fig_2(report_con_balanceo, report_sin_balanceo):
    """
    Genera la Figura 2: Latencia vs. Concurrencia (desde los Reportes HTML)
    """
    print("Generando Figura 2: Latencia vs. Concurrencia")
    
    df_con = parse_locust_report(report_con_balanceo)
    df_sin = parse_locust_report(report_sin_balanceo)
    
    if df_con is None or df_sin is None:
        print("No se pudieron procesar los archivos de reporte. No se generará la Figura 2.")
        return

    plt.figure(figsize=(10, 6))

    # El 'user_count' es lo que queremos en el eje X
    # 'response_time_percentile_0.5' es el percentil 50 (Mediana)
    plt.plot(df_con['user_count'], df_con['response_time_percentile_0.5'], 
             label='Propuesta AECC (Mediana Resp.)', color='blue', marker='o', markersize=4, alpha=0.7)
    
    plt.plot(df_sin['user_count'], df_sin['response_time_percentile_0.5'], 
             label='Despliegue Estático (Mediana Resp.)', color='red', marker='x', markersize=4, alpha=0.7)
    
    plt.title('Rendimiento del Sistema bajo Carga Concurrente')
    plt.xlabel('Usuarios Concurrentes')
    plt.ylabel('Tiempo de Respuesta (Mediana) (ms)')
    plt.legend()
    plt.ylim(bottom=0) # Empezar en 0
    plt.xlim(left=0)
    plt.savefig('latencia.png', dpi=300, bbox_inches='tight')
    print("Figura 'latencia.png' guardada.")

def plot_fig_3(control_module_url):
    """
    Genera la Figura 3: Distribución de Carga (desde la API de stats)
    Esta función no cambia, sigue llamando a tu Módulo de Control.
    """
    print("Generando Figura 3: Distribución de Carga")
    try:
        response = requests.get(f"{control_module_url}/stats_fig_3")
        response.raise_for_status()
        data = response.json()
        
        if not data:
            print("No se recibieron datos de 'stats_fig_3'. ¿Están los workers registrados?")
            return

        workers = list(data.keys())
        solicitudes = list(data.values())
        
        plt.figure(figsize=(8, 5))
        sns.barplot(x=workers, y=solicitudes, palette="viridis")
        
        plt.title('Distribución de Solicitudes (4 Workers)')
        plt.xlabel('ID del Worker')
        plt.ylabel('Número Total de Solicitudes Procesadas')
        plt.savefig('distribucion.png', dpi=300, bbox_inches='tight')
        print("Figura 'distribucion.png' guardada.")
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener datos de stats_fig_3: {e}")
        return

# --- Ejecutar los gráficos ---
if __name__ == "__main__":
    # 1. Genera la Fig 2 (Asegúrate de tener los .html)
    plot_fig_2(
        report_con_balanceo="con_balanceo.html", 
        report_sin_balanceo="sin_balanceo.html"
    )
    
    # 2. Genera la Fig 3 (Asegúrate de que el Módulo de Control esté corriendo)
    plot_fig_3(control_module_url="http://localhost:8000")