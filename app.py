from flask import Flask, render_template, request, jsonify
import random

app = Flask(__name__)

# Base de datos en memoria (aquí se guardarán los datos que envíe el Arduino)
pivot_data = {
    "presion": 0.0,
    "angulo": 0,
    "estado": "Desconectado"
}

@app.route('/')
def index():
    return render_template('dashboard.html', data=pivot_data)

# RUTA PARA EL ARDUINO: El hardware llamará a esta dirección
@app.route('/api/telemetria', methods=['POST'])
def recibir_telemetria():
    global pivot_data
    datos_nuevos = request.json
    
    # Actualizamos los valores con lo que envía el microcontrolador
    pivot_data['presion'] = datos_nuevos.get('presion')
    pivot_data['angulo'] = datos_nuevos.get('angulo')
    pivot_data['estado'] = "Regando"
    
    return jsonify({"status": "Datos recibidos correctamente"}), 200

# RUTA PARA EL DASHBOARD: La web consulta aquí para actualizarse
@app.route('/api/obtener_datos')
def obtener_datos():
    return jsonify(pivot_data)

if __name__ == '__main__':
    app.run(debug=True)
