import datetime
import random
from flask import Flask, jsonify, render_template, request

# ==========================================================
#   PLATAFORMA INTEGRAL: AGROFLOW AI (PROPIO & EN LA NUBE) v3.0
# ==========================================================

app = Flask(__name__)

# BASE DE DATOS EN MEMORIA (ESTADO REAL DEL PIVOT DE 156 HAS)
estado_pivot = {
    "id_equipo": "PIVOT-P156",
    "lote": "Lote A2",
    "bomba_activa": True,
    "presion_bar": 2.4,          
    "angulo_actual": 45,
    "direccion": "ADELANTE",
    "timer_porcentaje": 60,
    "hectareas_totales": 156.0,
    "hectareas_regadas": 19.5,
    "cultivo": "Soja de Primera"
}

# LINEA DE TIEMPO HISTORICA
historial_eventos = [
    {"hora": "09:15 AM", "evento": "REGANDO", "detalle": "Presion nominal optima en colector."},
    {"hora": "07:30 AM", "evento": "MOVIMIENTO", "detalle": "Avance automatico de tramos OK."},
    {"hora": "04:12 AM", "evento": "REGANDO", "detalle": "Equipo operando sin novedades en lote A2."},
    {"hora": "01:00 AM", "evento": "PARADA", "detalle": "Parada programada por temporizador fijo."}
]

registro_presion_ia = [2.4, 2.4, 2.3, 2.4, 2.3, 2.2, 2.0]

# 🧠 MOTOR DE INTELIGENCIA ARTIFICIAL
def analizar_con_ia():
    global registro_presion_ia
    if not estado_pivot["bomba_activa"]:
        return {"estado": "DORMIDO", "color": "#718096", "mensaje": "IA en espera: Bomba apagada."}
    
    p_actual = estado_pivot["presion_bar"]
    ultimas_cinco = registro_presion_ia[-5:]
    
    if p_actual < 1.2:
        return {"estado": "ALERTA CRITICA", "color": "#e74c3c", "mensaje": "IA detecta anomalia: Caida brusca de presion. Revisar canerias."}
    
    caida_gradual = all(ultimas_cinco[i] >= ultimas_cinco[i+1] for i in range(len(ultimas_cinco)-1))
    if caida_gradual and p_actual < 2.2:
        return {"estado": "PREDICCION PREVENTIVA", "color": "#f39c12", "mensaje": "IA detecta tendencia de caida lenta. Picos Nelson o filtros tapados."}
    
    return {"estado": "SISTEMA ESTABLE", "color": "#00bc8c", "mensaje": "IA: Flujo hidraulico optimo para el desarrollo del cultivo."}

# 📡 ENDPOINTS API
@app.route('/api/v1/telemetria', methods=['GET'])
def get_telemetria():
    return jsonify({"telemetria": estado_pivot, "ia": analizar_con_ia(), "linea_tiempo": historial_eventos})

@app.route('/api/v1/control', methods=['POST'])
def control_remoto():
    global registro_presion_ia
    data = request.json
    comando = data.get("comando")
    ahora = datetime.datetime.now().strftime("%H:%M %p")
    
    if comando == "ARRANCAR":
        estado_pivot["bomba_activa"] = True
        estado_pivot["presion_bar"] = 2.4
        historial_eventos.insert(0, {"hora": ahora, "evento": "REGANDO", "detalle": "Arranque remoto desde App celular."})
    elif comando == "PARAR":
        estado_pivot["bomba_activa"] = False
        estado_pivot["presion_bar"] = 0.0
        historial_eventos.insert(0, {"hora": ahora, "evento": "PARADA", "detalle": "Apagado remoto solicitado por operador."})
    elif comando == "AVANZAR":
        if estado_pivot["bomba_activa"]:
            estado_pivot["angulo_actual"] = (estado_pivot["angulo_actual"] + 10) % 360
            estado_pivot["hectareas_regadas"] = min(156.0, estado_pivot["hectareas_regadas"] + 1.2)
            historial_eventos.insert(0, {"hora": ahora, "evento": "MOVIMIENTO", "detalle": f"Avance manual. Angulo: {estado_pivot['angulo_actual']} grados."})
            if random.random() < 0.4:
                estado_pivot["presion_bar"] = round(max(0.8, estado_pivot["presion_bar"] - 0.4), 1)
                registro_presion_ia.append(estado_pivot["presion_bar"])
                
    if "lote" in data: estado_pivot["lote"] = data["lote"]
    if "cultivo" in data: estado_pivot["cultivo"] = data["cultivo"]
    if "timer" in data: estado_pivot["timer_porcentaje"] = int(data["timer"])
    
    return jsonify({"status": "ok"})

@app.route('/')
def vista_celular():
    # Aquí le estamos pasando el diccionario estado_pivot al HTML bajo el nombre 'data'
    return render_template('dashboard.html', data=estado_pivot)
