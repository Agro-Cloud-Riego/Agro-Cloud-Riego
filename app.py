from flask import Flask, render_template, request, redirect, url_for, jsonify

app = Flask(__name__)

# BASE DE DATOS INDUSTRIAL CON CONSOLIDADO DE TELEMETRÍA
equipos = {
    "PIVOT-A2": {
        "id_equipo": "PIVOT-A2",
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
        "ultima_conexion": "Justo ahora",
        "motor_modelo": "Deutz 1013 / Bomba Cornell 6h",
        "motor_horas": 218,
        "motor_proximo_service": 250,
        "motor_temperatura": "82 oC",
        "motor_presion_aceite": "4.2 Bar",
        "riego_semanal_mm": 25.4,
        "eficiencia_sistema": 88
    },
    "FRONTAL-PE18": {
        "id_equipo": "FRONTAL-PE18",
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
        "ultima_conexion": "Hace 2 min",
        "motor_modelo": "Caterpillar C7 / Bomba Cornell 10 RB",
        "motor_horas": 485,
        "motor_proximo_service": 500,
        "motor_temperatura": "24 oC",
        "motor_presion_aceite": "0.0 Bar",
        "riego_semanal_mm": 18.0,
        "eficiencia_sistema": 92
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
    "temperatura": "26.4 oC",
    "lluvia_semanal_mm": 15.0
}

ordenes_trabajo = [
    {"id": "OT-104", "equipo": "PIVOT-A2", "tarea": "Cambio de aceite de reductoras en torre 4 y 5", "responsable": "Mecánicos", "prioridad": "Alta"},
    {"id": "OT-105", "equipo": "FRONTAL-F22", "tarea": "Revisión de alineación de tramos", "responsable": "Electricista", "prioridad": "Media"}
]

historial_eventos = [
    {"hora": "15:34", "equipo": "SISTEMA", "evento": "Reinicio de Gateway LoRa Estación Base", "tipo": "info"},
    {"hora": "14:12", "equipo": "PIVOT-A2", "evento": "Bomba de Presión (Cornell/Deutz) Encendida con éxito", "tipo": "marcha"},
    {"hora": "11:50", "equipo": "METEO", "evento": "Alerta: Pluviómetro superó los 14mm diarios", "tipo": "alerta"},
    {"hora": "09:15", "equipo": "FRONTAL-PE18", "evento": "Parada técnica: Revisión preventiva de alineación en tramos", "tipo": "parado"},
    {"hora": "06:00", "equipo": "SISTEMA", "evento": "Reporte automático matutino generado y enviado a pañol", "tipo": "info"}
]

@app.route('/')
def index():
    id_seleccionado = request.args.get('equipo', 'PIVOT-A2')
    equipo = equipos.get(id_seleccionado, equipos["PIVOT-A2"])
    
    horas_actuales = equipo["motor_horas"]
    horas_limite = equipo["motor_proximo_service"]
    porcentaje_uso = min(int((horas_actuales / horas_limite) * 100), 100)
    horas_restantes = max(horas_limite - horas_actuales, 0)

    lluvia_s = meteorologia["lluvia_semanal_mm"]
    riego_s = equipo["riego_semanal_mm"]
    agua_total_lote = lluvia_s + riego_s

    return render_template(
        'dashboard.html', 
        data=equipo, 
        todos_equipos=equipos, 
        stock=inventario, 
        clima=meteorologia, 
        ot=ordenes_trabajo,
        eventos=historial_eventos,
        mantenimiento={
            "porcentaje": porcentaje_uso,
            "restantes": horas_restantes
        },
        hidrologia={
            "agua_total": agua_total_lote,
            "porcentaje_riego": int((riego_s / agua_total_lote) * 100) if agua_total_lote > 0 else 0,
            "porcentaje_lluvia": int((lluvia_s / agua_total_lote) * 100) if agua_total_lote > 0 else 0
        }
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
