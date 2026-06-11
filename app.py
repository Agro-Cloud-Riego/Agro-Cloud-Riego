from flask import Flask, render_template, request, redirect, url_for, jsonify, send_file
import os

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
        "modo_enlace": "WiFi / Celular",
        "latitud": -25.0451,
        "longitud": -64.1284,
        "rssi_dbm": -65
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
        "modo_enlace": "Enlace de Radio LoRa",
        "latitud": -25.0322,
        "longitud": -64.1115,
        "rssi_dbm": -92
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

@app.route('/api/telemetria', methods=['POST'])
def recibir_datos_campo():
    datos = request.get_json()
    if not datos or "id_equipo" not in datos:
        return jsonify({"status": "error", "message": "Falta identificador"}), 400
    id_eq = datos["id_equipo"]
    if id_eq in equipos:
        equipos[id_eq]["presion_bar"] = float(datos.get("presion_bar", equipos[id_eq]["presion_bar"]))
        equipos[id_eq]["caudal_lh"] = int(datos.get("caudal_lh", equipos[id_eq]["caudal_lh"]))
        equipos[id_eq]["angulo_actual"] = int(datos.get("angulo_actual", equipos[id_eq]["angulo_actual"]))
        equipos[id_eq]["modo_enlace"] = datos.get("modo_enlace", equipos[id_eq]["modo_enlace"])
        equipos[id_eq]["latitud"] = float(datos.get("latitud", equipos[id_eq]["latitud"]))
        equipos[id_eq]["longitud"] = float(datos.get("longitud", equipos[id_eq]["longitud"]))
        equipos[id_eq]["rssi_dbm"] = int(datos.get("rssi_dbm", equipos[id_eq]["rssi_dbm"]))
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 404

# ─── NUEVA RUTA PARA DESCARGAR EL MANUAL TÉCNICO DIRECTO ───
@app.route('/descargar-manual')
def descargar_manual():
    # Creamos un archivo de texto con toda la ingeniería de pines detallada
    ruta_archivo = "Manual_Pines_ESP32_AgroFlow.txt"
    with open(ruta_archivo, "w", encoding="utf-8") as f:
        f.write("=========================================================\n")
        f.write("   AGROFLOW AI PRO - PLAN DE ARQUITECTURA DE CAMPO\n")
        f.write("=========================================================\n\n")
        f.write("1. ASIGNACIÓN DE PINES FÍSICOS EN EL CHIP ESP32:\n")
        f.write("---------------------------------------------------------\n")
        f.write(" * Transductor de Presión (Bomba/Tramo): Pin GPIO 34 (Analog In)\n")
        f.write(" * Caudalímetro (Conteo de Pulsos):     Pin GPIO 25 (Digital In)\n")
        f.write(" * Módulo GPS Neo-6M (Línea Frontal):   Pin GPIO 16 (RX2) y GPIO 17 (TX2)\n")
        f.write(" * Módulo Radio LoRa SX1276 (Antena):   Pines SPI Estándar:\n")
        f.write("                                        - SS/CS:   GPIO 5\n")
        f.write("                                        - SCK:     GPIO 18\n")
        f.write("                                        - MISO:    GPIO 19\n")
        f.write("                                        - MOSI:    GPIO 23\n\n")
        f.write("2. CÁLCULO DE CAUDAL ESTIMADO (Mecánica de Fluidos):\n")
        f.write("---------------------------------------------------------\n")
        f.write(" Ecuación fundamental: Q = K * raiz(Delta_P)\n")
        f.write(" Donde Q es el caudal en L/h y P es la presión en Bar leída por el sensor.\n\n")
        f.write("3. RECOMENDACIÓN DE SEGURIDAD ELÉCTRICA EN EL CAMPO:\n")
        f.write("---------------------------------------------------------\n")
        f.write(" Instalar filtros de supresión de picos transitorios (TVS) o diodos zener\n")
        f.write(" en la entrada de 12V/24V del tablero para proteger el microcontrolador\n")
        f.write(" contra descargas y rayos en las tormentas de verano.\n")
    
    return send_file(ruta_archivo, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
