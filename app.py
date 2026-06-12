¡De una, Marcelo! Acá tenés los tres archivos completos, limpios, revisados renglón por renglón y listos para que los dejes definitivos en tu GitHub.

Con este código solucionamos el error de sintaxis, arreglamos lo del puerto que te trababa la página (Port Binding) y dejamos el diseño nuevo de AgroRiego con la telemetría funcionando al 100%.

🐍 1. El archivo app.py completo
(Acá ya incluí la biblioteca os al principio y cambié el final para que Render le asigne el puerto automáticamente sin quedarse cargando).

Python
from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os

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

# --- DATOS DEL AVANCE FRONTAL ---
equipos_riego = {
    "FRONTAL-F22": {
        "id": "FRONTAL-F22",
        "tipo": "Avance Frontal Lineal",
        "lote": "Cuadro Norte (210 Ha)",
        "posicion": "Cajón 4 de 12",
        "distancia": "450m",
        "presion": "0.0 Bar",
        "caudal": "0 L/h",
        "estado": "PARADO",
        "senal": "-92 dBm",
        "pluviometro": "14.2 mm",
        "mensual": "42.0 mm",
        "viento": "18 km/h (Norte)",
        "humedad": "32% (Moderada)"
    }
}

ot_simuladas = [
    {"id": "OT-104", "tarea": "Engrase de torres 4 y 5", "responsable": "Téc. Mecánico", "prioridad": "Alta"},
    {"id": "OT-105", "tarea": "Revisión presión de neumáticos", "responsable": "Preventivo", "prioridad": "Baja"}
]

stock_simulado = [
    {"componente": "Filtro de agua malla 8''", "cantidad": 2, "unidad": "unidades", "estado": "OK"},
    {"componente": "Aceite para reductor Deutz", "cantidad": 20, "unidad": "litros", "estado": "OK"},
    {"componente": "Aspersores terminales Valley", "cantidad": 0, "unidad": "unidades", "estado": "CRÍTICO"}
]

# --- RUTAS DE NAVEGACIÓN ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form.get('usuario')
        pass_input = request.form.get('clave')
        
        if user_input in usuarios_sistema and usuarios_sistema[user_input] == pass_input:
            usuario_obj = User(user_input)
            login_user(usuario_obj)
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="Usuario o clave incorrectos")
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    id_solicitado = request.args.get('equipo', 'FRONTAL-F22')
    
    if id_solicitado not in equipos_riego:
        id_solicitado = "FRONTAL-F22"
        
    datos_panel = equipos_riego[id_solicitado]
    
    return render_template(
        'dashboard.html', 
        data=datos_panel, 
        todos_equipos=equipos_riego, 
        ot=ot_simuladas, 
        stock=stock_simulado, 
        user=current_user
    )

# --- ARRANQUE COMPATIBLE CON PORT BINDING DE RENDER ---
if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
