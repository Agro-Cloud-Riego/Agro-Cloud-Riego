from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Base de datos global
equipo_data = {
    "tipo": "Pivot", # Puede ser "Pivot" o "Frontal"
    "presion": 0.0,
    "posicion": 0, # Grados para Pivot, Metros para Frontal
    "estado": "Desconectado"
}

@app.route('/')
def index():
    return render_template('dashboard.html', data=equipo_data)

@app.route('/api/telemetria', methods=['POST'])
def recibir_telemetria():
    global equipo_data
    datos = request.json
    # Actualizamos con lo que venga del hardware
    equipo_data.update(datos)
    return jsonify({"status": "Recibido"}), 200
