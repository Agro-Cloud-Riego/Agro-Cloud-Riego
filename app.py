from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

# BASE DE DATOS EN MEMORIA (Estado actual de los equipos)
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
        "alerta_ia": "Normal - Presión estable en Cornell"
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
        "alerta_ia": "Estacionado - Listo para operar"
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
            
            if nuevo_timer == 0 and eq["bomba_activa"]:
                eq["alerta_ia"] = "Mantenimiento: Equipo detenido aplicando lámina máxima en posición actual."
            else:
                eq["alerta_ia"] = "Operación normal regulada por telecontrol."

    return redirect(url_for('index', equipo=id_equipo))

# ==========================================
#  RADAR DE TELEMETRÍA: ENCHUFE PARA ESP32
# ==========================================
@app.route('/api/telemetria', methods=['POST'])
def recibir_datos_campo():
    # El chip ESP32 va a mandar un paquete de datos por internet
    datos_recibidos = request.get_json()
    
    if not datos_recibidos or "id_equipo" not in datos_recibidos:
        return jsonify({"status": "error", "message": "Datos invalidos o falta id_equipo"}), 400
        
    id_eq = datos_recibidos["id_equipo"]
    
    # Si el equipo existe en nuestra lista, le actualizamos los valores con los del sensor real
    if id_eq in equipos:
        equipos[id_eq]["presion_bar"] = float(datos_recibidos.get("presion_bar", equipos[id_eq]["presion_bar"]))
        equipos[id_eq]["caudal_lh"] = int(datos_recibidos.get("caudal_lh", equipos[id_eq]["caudal_lh"]))
        equipos[id_eq]["angulo_actual"] = int(datos_recibidos.get("angulo_actual", equipos[id_eq]["angulo_actual"]))
        
        # Inteligencia Artificial Básica de Seguridad:
        # Si la bomba está activa pero la presión cae por debajo de 1.2 Bar, asumimos rotura o fuga
        if equipos[id_eq]["bomba_activa"] and equipos[id_eq]["presion_bar"] < 1.2:
            equipos[id_eq]["alerta_ia"] = "🚨 ALERTA IA: ¡Caída de presión crítica detectada! Posible rotura de caño o falla en bomba Cornell."
        else:
            equipos[id_eq]["alerta_ia"] = "Telemetría ONLINE — Sensores de campo transmitiendo correctamente."
            
        return jsonify({"status": "success", "message": "Telemetria actualizada en la nube"}), 200
    
    return jsonify({"status": "error", "message": "Equipo no registrado"}), 404
