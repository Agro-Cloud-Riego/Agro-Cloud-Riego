from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
import pandas as pd

app = Flask(__name__)
app.secret_key = 'agroriego_secreto_cejasmardani'

# --- CONFIGURACIÓN DE SEGURIDAD Y LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id

usuarios_sistema = {
    "marcelo": "agro2026"
}

@login_manager.user_loader
def load_user(user_id):
    if user_id in usuarios_sistema:
        return User(user_id)
    return None

# --- DATABASE MEJORADA CON HISTORIAL DE EVENTOS POR LOTE ---
equipos_riego = {
    "PIVOT-LOTE-A2": {
        "id": "PIVOT-LOTE-A2",
        "tipo": "Pivot Central",
        "lote": "Lote A2 (156 Ha)",
        "posicion": "Ángulo 340°",
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
        "eventos": [
            {"fecha": "09/06/2026", "hora": "12:15 PM", "estado": "Desconectado", "badge": "badge-critico"},
            {"fecha": "09/06/2026", "hora": "02:55 AM", "estado": "Apagado", "badge": "badge-parado"},
            {"fecha": "08/06/2026", "hora": "11:11 AM", "estado": "Regando", "badge": "badge-marcha"},
            {"fecha": "08/06/2026", "hora": "10:04 AM", "estado": "Apagado", "badge": "badge-parado"}
        ]
    },
    "FRONTAL-F22": {
        "id": "FRONTAL-F22",
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
        "eventos": [
            {"fecha": "12/06/2026", "hora": "06:15 PM", "estado": "Regando", "badge": "badge-marcha"},
            {"fecha": "11/06/2026", "hora": "04:30 AM", "estado": "Falla Presión", "badge": "badge-critico"},
            {"fecha": "10/06/2026", "hora": "01:11 PM", "estado": "Regando", "badge": "badge-marcha"}
        ]
    },
    "PIVOT-LOTE-B1": {
        "id": "PIVOT-LOTE-B1",
        "tipo": "Pivot Central",
        "lote": "Lote B1 (120 Ha)",
        "posicion": "Ángulo 45°",
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
        "eventos": [
            {"fecha": "11/06/2026", "hora": "08:00 AM", "estado": "Apagado Financio", "badge": "badge-parado"},
            {"fecha": "09/06/2026", "hora": "09:00 PM", "estado": "Regando", "badge": "badge-marcha"}
        ]
    }
}

ot_simuladas = [
    {"id": "OT-104", "tarea": "Engrase de towers 4 y 5", "responsable": "Téc. Mecánico", "prioridad": "Alta"},
    {"id": "OT-105", "tarea": "Revisión presión de neumáticos", "responsable": "Preventivo", "prioridad": "Baja"}
]

def cargar_stock_desde_ods():
    archivo_ods = "stockriego 21.ods"
    if os.path.exists(archivo_ods):
        try:
            df = pd.read_excel(archivo_ods, engine='odf')
            df.columns = df.columns.str.strip()
            lista_stock = []
            for _, fila in df.iterrows():
                componente = fila.get('Descripsion /Modelo')
                cantidad = fila.get('Stock Actual')
                estado_raw = fila.get('Stock Crítico', 'STOCK OK')
                if pd.isna(componente): continue
                estado_str = str(estado_raw).upper().strip()
                estado_final = "CRÍTICO" if "PEDIR" in estado_str or "URGENTE" in estado_str else "OK"
                lista_stock.append({
                    "componente": str(componente).strip(),
                    "cantidad": int(cantidad) if pd.notna(cantidad) else 0,
                    "unidad": "unidades",
                    "estado": estado_final
                })
            return lista_stock
        except Exception as e:
            print(f"Error procesando el archivo: {e}")
    return []

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form.get('usuario')
        pass_input = request.form.get('clave')
        if user_input in usuarios_sistema and usuarios_sistema[user_input] == pass_input:
            login_user(User(user_input))
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    id_solicitado = request.args.get('equipo', 'PIVOT-LOTE-A2')
    if id_solicitado not in equipos_riego:
        id_solicitado = "PIVOT-LOTE-A2"
    datos_panel = equipos_riego[id_solicitado]
    return render_template('dashboard.html', data=datos_panel, todos_equipos=equipos_riego, ot=ot_simuladas, user=current_user)

@app.route('/stock')
@login_required
def stock():
    return render_template('stock.html', stock=cargar_stock_desde_ods(), user=current_user)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
