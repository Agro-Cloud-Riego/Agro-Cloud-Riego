from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# BASE DE DATOS PROFESIONAL (Control independiente de Hidráulica y Movimiento)
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
        "timer_porcentaje": 0, # Detenido para mantenimiento
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
        
        # 1. Control de Bomba (Hidráulica)
        if parametro == "bomba":
            if valor == "encender":
                eq["bomba_activa"] = True
                eq["presion_bar"] = 2.4 if id_equipo == "PIVOT-P156" else 3.1
                eq["caudal_lh"] = 120000
            elif valor == "apagar":
                eq["bomba_activa"] = False
                eq["presion_bar"] = 0.0
                eq["caudal_lh"] = 0
                
        # 2. Control de Dirección (Tablero)
        elif parametro == "direccion":
            eq["direccion"] = valor.upper()
            
        # 3. Control de Velocidad / Parada de Avance (Timer)
        elif parametro == "timer":
            nuevo_timer = int(valor)
            if nuevo_timer < 0: nuevo_timer = 0
            if nuevo_timer > 100: nuevo_timer = 100
            eq["timer_porcentaje"] = nuevo_timer
            
            # IA Analítica: Si detiene el avance pero la bomba sigue prendida
            if nuevo_timer == 0 and eq["bomba_activa"]:
                eq["alerta_ia"] = "Mantenimiento: Equipo detenido aplicando lámina máxima en posición actual."
            else:
                eq["alerta_ia"] = "Operación normal regulada por telecontrol."

    return redirect(url_for('index', equipo=id_equipo))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)5000)
