from flask import Flask, render_template

app = Flask(__name__)

# BASE DE DATOS EN MEMORIA
estado_pivot = {
    "id_equipo": "PIVOT-P156",
    "lote": "Lote A2",
    "bomba_activa": True,
    "presion_bar": 2.4,
    "angulo_actual": 45,
    "direccion": "ADELANTE",
    "timer_porcentaje": 60,
    "hectareas_totales": 156.0,
    "hectareas_regadas": 19.5
}

@app.route('/')
def vista_celular():
    # Enviamos el diccionario 'estado_pivot' al dashboard.html bajo el nombre 'data'
    return render_template('dashboard.html', data=estado_pivot)

if __name__ == '__main__':
    # Render necesita el host 0.0.0.0
    app.run(host='0.0.0.0', port=5000)
