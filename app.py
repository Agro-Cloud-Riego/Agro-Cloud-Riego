from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.secret_key = 'agroflow_secreto_cejasmardani'

# --- CONFIGURACIÓN DE LOGIN ---
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

# --- DATOS REALES DEL PANEL ---
equipos = {
    "PIVOT-P156": {
        "id": "PIVOT-P156",
        "tipo": "Pivot Central Valley",
        "lote": "Lote Alfalfa - 156 Ha",
        "estado": "MARCHA",
        "presion": "3.8 Bar",
        "caudal": "140 m³/h",
        "posicion": "Ángulo 120°",
        "distancia": "🔄 Girando",
        "senal": "-72 dBm",
        "pluviometro": "5.0 mm",
        "mensual": "45.0 mm",
        "viento": "12 km/h",
        "humedad": "45%"
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

# --- RUTAS ---
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
    id_seleccionado = request.args.get('equipo', 'PIVOT-P156')
    if id_seleccionado not in equipos:
        id_seleccionado = "PIVOT-P156"
        
    return render_template(
        'dashboard.html', 
        data=equipos[id_seleccionado], 
        todos_equipos=equipos, 
        ot=ot_simuladas, 
        stock=stock_simulado, 
        user=current_user
    )

if __name__ == '__main__':
    app.run(debug=True)
