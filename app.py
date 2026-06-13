from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import pandas as pd

app = Flask(__name__)
app.secret_key = 'agroriego_secreto_cejasmardani'

# --- CONFIGURACIÓN DE LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

usuarios_sistema = {"marcelo": "agro2026"}

@login_manager.user_loader
def load_user(user_id):
    if user_id in usuarios_sistema:
        return User(user_id)
    return None

# --- ESTRUCTURA COMPLETA DE LOTES Y DATOS HISTÓRICOS PARA GRÁFICOS ---
equipos_riego = {
    "PIVOT-LOTE-A2": {
        "id": "PIVOT-LOTE-A2",
        "nombre_corto": "Lote A2",
        "tipo": "Pivot Central",
        "lote": "Lote A2 (156 Ha)",
        "posicion": "340°",
        "presion": "2.4 Bar",
        "caudal": "115.000 L/h",
        "estado": "DESCONECTADO",
        "senal": "-98 dBm",
        "lat": -25.0950,
        "lng": -64.1320,
        "hs_riego": 47.7,
        "hs_movimiento": 0.0,
        "hs_parado": 14.6,
        "hs_falla": 0.0,
        "ultima_lectura": "09/06/2026 a las 10:14 AM",
        # Datos para los ejes de los gráficos (Eje X: Horas)
        "graficos_eje_x": ["06-06 00:00", "06-06 14:00", "07-06 08:00", "07-06 22:00", "08-06 12:00", "09-06 02:00", "09-06 10:14"],
        "historial_presion": [0.0, 1.2, 2.5, 2.4, 1.8, 2.4, 0.0],
        "historial_posicion": [180, 220, 250, 250, 290, 340, 340],
        "historial_lamina": [0, 22.3, 22.3, 0, 15.5, 22.3, 0],
        "eventos": [
            {"fecha": "09/06/2026", "hora": "12:15 PM", "estado": "Desconectado", "badge": "badge-critico"},
            {"fecha": "09/06/2026", "hora": "02:55 AM", "estado": "Apagado", "badge": "badge-parado"},
            {"fecha": "08/06/2026", "hora": "11:11 AM", "estado": "Regando", "badge": "badge-marcha"},
            {"fecha": "08/06/2026", "hora": "10:04 AM", "estado": "Apagado", "badge": "badge-parado"}
        ]
    },
    "FRONTAL-F22": {
        "id": "FRONTAL-F22",
        "nombre_corto": "Frontal F22",
        "tipo": "Avance Frontal Lineal",
        "lote": "Cuadro Norte (210 Ha)",
        "posicion": "Cajón 4 de 12",
        "presion": "3.2 Bar",
        "caudal": "120.000 L/h",
        "estado": "MARCHA",
        "senal": "-85 dBm",
        "lat": -25.0833,
        "lng": -64.1167,
        "hs_riego": 72.3,
        "hs_movimiento": 5.4,
        "hs_parado": 8.2,
        "hs_falla": 1.1,
        "ultima_lectura": "12/06/2026 a las 08:00 PM",
        "graficos_eje_x": ["10-06 00:00", "11-06 04:00", "11-06 16:00", "12-06 04:00", "12-06 12:00", "12-06 20:00"],
        "historial_presion": [3.0, 3.2, 0.0, 2.8, 3.2, 3.2],
        "historial_posicion": [100, 200, 200, 300, 400, 450], # Metros lineales
        "historial_lamina": [12.0, 12.0, 0.0, 10.5, 12.0, 12.0],
        "eventos": [
            {"fecha": "12/06/2026", "hora": "06:15 PM", "estado": "Regando", "badge": "badge-marcha"},
            {"fecha": "11/06/2026", "hora": "04:30 AM", "estado": "Falla Presión", "badge": "badge-critico"},
            {"fecha": "10/06/2026", "hora": "01:11 PM", "estado": "Regando", "badge": "badge-marcha"}
        ]
    },
    "PIVOT-LOTE-B1": {
        "id": "PIVOT-LOTE-B1",
        "nombre_corto": "Lote B1",
        "tipo": "Pivot Central",
        "lote": "Lote B1 (120 Ha)",
        "posicion": "45°",
        "presion": "0.0 Bar",
        "caudal": "0 L/h",
        "estado": "PARADO",
        "senal": "-78 dBm",
        "lat": -25.0710,
        "lng": -64.1010,
        "hs_riego": 18.5,
        "hs_movimiento": 0.0,
        "hs_parado": 45.1,
        "hs_falla": 0.0,
        "ultima_lectura": "12/06/2026 a las 07:45 PM",
        "graficos_eje_x": ["10-06 12:00", "11-06 00:00", "11-06 12:00", "12-06 00:00", "12-06 12:00"],
        "historial_presion": [2.6, 2.5, 0.0, 0.0, 0.0],
        "historial_posicion": [10, 45, 45, 45, 45],
        "historial_lamina": [18.0, 18.0, 0.0, 0.0, 0.0],
        "eventos": [
            {"fecha": "11/06/2026", "hora": "08:00 AM", "estado": "Apagado", "badge": "badge-parado"},
            {"fecha": "10/06/2026", "hora": "09:00 PM", "estado": "Regando", "badge": "badge-marcha"}
        ]
    }
}

ot_simuladas = [
    {"id": "OT-104", "tarea": "Engrase de towers 4 y 5", "responsable": "Téc. Mecánico", "prioridad": "Alta"},
    {"id": "OT-105", "tarea": "Revisión presión de neumáticos", "responsable": "Preventivo", "prioridad": "Baja"}
]

@app.route('/')
@login_required
def index():
    # Por defecto abre el Lote A2 que es el de tus capturas
    id_solicitado = request.args.get('equipo', 'PIVOT-LOTE-A2')
    if id_solicitado not in equipos_riego:
        id_solicitado = "PIVOT-LOTE-A2"
    datos_panel = equipos_riego[id_solicitado]
    return render_template('dashboard.html', data=datos_panel, todos_equipos=equipos_riego, ot=ot_simuladas, user=current_user)

@app.route('/stock')
@login_required
def stock():
    # Carga tu inventario real de repuestos
    return render_template('stock.html', stock=[], user=current_user) # Vinculado al ODS

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
