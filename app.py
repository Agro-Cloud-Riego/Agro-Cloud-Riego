from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# BASE DE DATOS MULTI-EQUIPO (Aquí conviven Pivots y Frontales)
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
        "angulo_actual": 0, # En frontales representa metros avanzados o posición
        "direccion": "REVERSA",
        "timer_porcentaje": 80,
        "hectareas_totales": 210.0,
        "caudal_lh": 0,
        "alerta_ia": "Apagado - Esperando ventana de riego según NDVI"
    }
}

@app.route('/')
def index():
    # Por defecto, si no elige ninguno, mostramos el Pivot
    id_seleccionado = request.args.get('equipo', 'PIVOT-P156')
    equipo = equipos.get(id_seleccionado, equipos["PIVOT-P156"])
    return render_template('dashboard.html', data=equipo, todos_equipos=equipos)

@app.route('/control/<id_equipo>/<accion>')
def control_bomba(id_equipo, accion):
    if id_equipo in equipos:
        if accion == "arrancar":
            equipos[id_equipo]["bomba_activa"] = True
            equipos[id_equipo]["presion_bar"] = 2.4 if id_equipo == "PIVOT-P156" else 3.1
            equipos[id_equipo]["caudal_lh"] = 120000
            equipos[id_equipo]["alerta_ia"] = "Bomba encendida por telecontrol."
        elif accion == "parar":
            equipos[id_equipo]["bomba_activa"] = False
            equipos[id_equipo]["presion_bar"] = 0.0
            equipos[id_equipo]["caudal_lh"] = 0
            equipos[id_equipo]["alerta_ia"] = "Apagado manual a distancia."
            
    return redirect(url_for('index', equipo=id_equipo))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
