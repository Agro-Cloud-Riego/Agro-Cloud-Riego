from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

# BASE DE DATOS INDUSTRIAL AMPLIADA (Admite WiFi, LoRa y GPS)
equipos = {
    "PIVOT-P156": {
        "id_equipo": "PIVOT-P156",
        "tipo": "Pivot Central",
        "lote": "Lote A2",
        "bomba_activa": True,
        "presion_bar": 2.4,
        "angulo_actual": 45,
        "direccion": "ADELANTE",
        "timer_porcentaje": 60,
        "hectareas_totales": 156.0,
        "caudal_lh": 120000,
        "alerta_ia": "Normal - Presión estable en Cornell",
        # Nuevos campos del Ladrillo de Telemetría Avanzada:
        "modo_enlace": "WiFi / Celular",
        "latitud": -25.0451,
        "longitud": -64.1284,
        "rssi_dbm": -65  # Fuerza de la señal de radio
    },
    "FRONTAL-F22": {
        "id_equipo": "FRONTAL-F22",
        "tipo": "Frontal Lineal (22 Tramos)",
        "lote": "Lote Norte-B",
        "bomba_activa": False,
        "presion_bar": 0.0,
        "angulo_actual": 120, 
        "direccion": "REVERSA",
        "timer_porcentaje": 0, 
        "hectareas_totales": 210.0,
        "caudal_lh": 0,
        "alerta_ia": "Estacionado - Listo para operar",
        # Nuevos campos del Ladrillo de Telemetría Avanzada:
        "modo_enlace": "Enlace de Radio LoRa",
        "latitud": -25.0322,
        "longitud": -64.1115,
        "rssi_dbm": -92  # Señal lejana pero firme vía antena
    }
}

@app.route('/')
def index():
    id_seleccionado = request.args.get('equipo', 'PIVOT-P156')
    equipo = equipos.get(id_seleccionado, equipos["PIVOT-P156"])
    return render_template('dashboard.html', data=equipo, todos_equipos=equipos)

@app.route('/control/<id_equipo>/<parametro>/<valor>')
def control_avanzado(id_equipo, parametro, valor):
    if id_equipo in equipos:
        eq = equipos[id_equipo]
        if parametro == "bomba":
            if valor == "encender":
                eq["bomba_activa"] = True
                eq["presion_bar"] = 2.4 if id_equipo == "PIVOT-P156" else 3.1
                eq["caudal_lh"] = 120000
            elif valor == "apagar":
                eq["bomba_activa"] = False
                eq["presion_bar"] = 0.0
                eq["caudal_lh"] = 0
        elif parametro == "direccion":
            eq["direccion"] = valor.upper()
        elif parametro == "timer":
            try:
                nuevo_timer = int(valor)
            except ValueError:
                nuevo_timer = eq["timer_porcentaje"]
            if nuevo_timer < 0: nuevo_timer = 0
            if nuevo_timer > 100: nuevo_timer = 100
            eq["timer_porcentaje"] = nuevo_timer

    return redirect(url_for('index', equipo=id_equipo))

# =======================================================
#  API CENTRALIZADA: RECIBE WIFI, LORA Y TRAMAS GPS
# =======================================================
@app.route('/api/telemetria', methods=['POST'])
def recibir_datos_campo():
    datos = request.get_json()
    
    if not datos or "id_equipo" not in datos:
        return jsonify({"status": "error", "message": "Falta identificador"}), 400
        
    id_eq = datos["id_equipo"]
    
    if id_eq in equipos:
        # Actualizaciones básicas
        equipos[id_eq]["presion_bar"] = float(datos.get("presion_bar", equipos[id_eq]["presion_bar"]))
        equipos[id_eq]["caudal_lh"] = int(datos.get("caudal_lh", equipos[id_eq]["caudal_lh"]))
        equipos[id_eq]["angulo_actual"] = int(datos.get("angulo_actual", equipos[id_eq]["angulo_actual"]))
        
        # Nuevos datos satelitales y de radiofrecuencia que mandarán las placas
        equipos[id_eq]["modo_enlace"] = datos.get("modo_enlace", equipos[id_eq]["modo_enlace"])
        equipos[id_eq]["latitud"] = float(datos.get("latitud", equipos[id_eq]["latitud"]))
        equipos[id_eq]["longitud"] = float(datos.get("longitud", equipos[id_eq]["longitud"]))
        equipos[id_eq]["rssi_dbm"] = int(datos.get("rssi_dbm", equipos[id_eq]["rssi_dbm"]))
        
        # Inteligencia de Alertas de Campo
        if equipos[id_eq]["rssi_dbm"] < -110:
            equipos[id_eq]["alerta_ia"] = "⚠️ Señal de Radio Crítica. Antena LoRa posiblemente desalineada u obstruida."
        elif equipos[id_eq]["bomba_activa"] and equipos[id_eq]["presion_bar"] < 1.2:
            equipos[id_eq]["alerta_ia"] = "🚨 ¡Caída de presión! Posible rotura de pico o manguera de acople."
        else:
            equipos[id_eq]["alerta_ia"] = f"Datos recibidos vía {equipos[id_eq]['modo_enlace']} con éxito."
            
        return jsonify({"status": "success", "message": "Infraestructura actualizada"}), 200
    
    return jsonify({"status": "error", "message": "Dispositivo desconocido"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
