from flask import Flask, render_template, jsonify
import random

app = Flask(__name__)

# Función para simular lecturas de sensores
def obtener_datos_simulados():
    return {
        "presion": round(random.uniform(2.0, 3.5), 1),  # Simula entre 2.0 y 3.5 Bar
        "angulo": random.randint(0, 360),              # Simula grados del Pivot
        "estado": "Regando" if random.random() > 0.2 else "Detenido"
    }

@app.route('/')
def index():
    # Enviamos los datos simulados a la página principal
    data = obtener_datos_simulados()
    return render_template('dashboard.html', data=data)

# Esta ruta será la que usaremos más adelante para actualizar la web 
# sin recargarla (vía AJAX/Fetch)
@app.route('/api/datos')
def api_datos():
    return jsonify(obtener_datos_simulados())

if __name__ == '__main__':
    app.run(debug=True)
