from flask import Flask, render_template, request, redirect, url_for, jsonify, session

app = Flask(__name__)
# Esta clave secreta encripta las sesiones para que no puedan saltearse el login
app.secret_key = 'sector_riego_salta_2026'

# Lista de usuarios autorizados que van a poder ver la plataforma
USUARIOS_VALIDOS = {
    "marcelo@agroflow.com": "riego2026",
    "admin": "1234"
}

# BASE DE DATOS INDUSTRIAL (Mantiene exactamente tus mismos datos de telemetría)
equipos = {
    "PIVOT-P156": {
        "id_equipo": "PIVOT-P156",
        "tipo": "Pivot Central",
        "lote": "Lote Alfalfa (156 Ha)",
        "estado_marcha": "OPERANDO",
        "presion_bar": 2.4,
        "caudal_lh": 120000,
        "tipo_geometria": "circular",
        "angulo_actual": 145,
        "hectareas_regadas": 62.5,
        "velocidad_avance": "1.2 m/h",
        "modo_enlace": "WiFi Rural (Puesto)",
        "rssi_dbm": -68,
        "ultima_conexion": "Justo ahora"
    },
    "FRONTAL-F22": {
        "id_equipo": "FRONTAL-F22",
        "tipo": "Avance Frontal Lineal",
        "lote": "Cuadro Norte (210 Ha)",
        "estado_marcha": "PARADO",
        "presion_bar": 0.0,
        "caudal_lh": 0,
        "tipo_geometria": "lineal",
        "cajon_actual": 4,
        "cajones_totales": 12,
        "metros_recorridos": 450,
        "modo_enlace": "Radio LoRa (Antena Base)",
        "rssi_dbm": -92,
        "ultima_conexion": "Hace 2 min"
    }
}

inventario = [
    {"componente": "Aceite de Transmisión (SAE 50)", "cantidad": 45, "unidad": "Litros", "estado": "OK"},
    {"componente": "Caja de Engranajes (Gearbox)", "cantidad": 3, "unidad": "Unidades", "estado": "CRÍTICO"},
    {"componente": "Picos Aspersores (Boquillas 3/4)", "cantidad": 120, "unidad": "Unidades", "estado": "OK"},
    {"componente": "Neumático de Pivot 11.2x38", "cantidad": 2, "unidad": "Unidades", "estado": "BAJO"}
]

meteorologia = {
    "pluviometria_hoy": 14.2,
    "pluviometria_acumulada_mes": 42.0,
    "velocidad_viento": "18 km/h (Norte)",
    "humedad_suelo": "32% (Moderada)",
    "temperatura": "26.4 oC"
}

ordenes_trabajo = [
    {"id": "OT-104", "equipo": "PIVOT-P156", "tarea": "Cambio de aceite de reductoras en torre 4 y 5", "responsable": "Mecánicos", "prioridad": "Alta"},
    {"id": "OT-105", "equipo": "FRONTAL-F22", "tarea": "Revisión de alineación de tramos", "responsable": "Electricista", "prioridad": "Media"}
]

# NUEVA RUTA: Maneja exclusivamente la pantalla de inicio de sesión
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('username')
        clave = request.form.get('password')
        
        # Comprobar si las credenciales coinciden
        if usuario in USUARIOS_VALIDOS and USUARIOS_VALIDOS[usuario] == clave:
            session['usuario_autenticado'] = usuario  # Guarda la sesión activa
            return redirect(url_for('index'))  # Lo deja pasar al dashboard
            
        return render_template('login.html', error="Usuario o contraseña incorrectos")
        
    return render_template('login.html')

# RUTA PRINCIPAL (Protegida)
@app.route('/')
def index():
    # SI NO INICIÓ SESIÓN: Lo rebota automáticamente al login sin cargar el dashboard
    if 'usuario_autenticado' not in session:
        return redirect(url_for('login'))
        
    # SI INICIÓ SESIÓN: Ejecuta tu código de siempre de manera transparente
    id_seleccionado = request.args.get('equipo', 'PIVOT-P156')
    equipo = equipos.get(id_seleccionado, equipos["PIVOT-P156"])
    return render_template(
        'dashboard.html', 
        data=equipo, 
        todos_equipos=equipos, 
        stock=inventario, 
        clima=meteorologia, 
        ot=ordenes_trabajo
    )

@app.route('/api/telemetria', methods=['POST'])
def recibir_datos():
    datos = request.get_json()
    if not datos or "id_equipo" not in datos:
        return jsonify({"status": "error"}), 400
    
    id_eq = datos["id_equipo"]
    if id_eq in equipos:
        equipos[id_eq]["presion_bar"] = float(datos.get("presion_bar", equipos[id_eq]["presion_bar"]))
        equipos[id_eq]["caudal_lh"] = int(datos.get("caudal_lh", equipos[id_eq]["caudal_lh"]))
        if equipos[id_eq]["tipo_geometria"] == "circular":
            equipos[id_eq]["angulo_actual"] = int(datos.get("angulo_actual", equipos[id_eq]["angulo_actual"]))
        else:
            equipos[id_eq]["cajon_actual"] = int(datos.get("cajon_actual", equipos[id_eq]["cajon_actual"]))
        equipos[id_eq]["rssi_dbm"] = int(datos.get("rssi_dbm", equipos[id_eq]["rssi_dbm"]))
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error"}), 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)