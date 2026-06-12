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

# --- FUNCIÓN PARA LOGÍSTICA DE REPUSTOS ---
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
                
                if pd.isna(componente):
                    continue
                
                estado_str = str(estado_raw).upper().strip()
                if "URGENTE" in estado_str or "CRITICO" in estado_str:
                    estado_final = "CRÍTICO"
                else:
                    estado_final = "OK"
                
                lista_stock.append({
                    "componente": str(componente).strip(),
                    "cantidad": int(cantidad) if pd.notna(cantidad) else 0,
                    "unidad": "unidades",
                    "estado": estado_final
                })
            
            if len(lista_stock) > 0:
                return lista_stock
                
        except Exception as e:
            print(f"Error procesando el archivo: {e}")
            return []
            
    return []

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

# 1. PANTALLA PRINCIPAL: Dashboard Limpio (Sin la tabla de stock)
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
        user=current_user
    )

# 2. NUEVA PANTALLA INDEPENDIENTE: "Stock 21"
@app.route('/stock')
@login_required
def stock():
    stock_actualizado = cargar_stock_desde_ods()
    return render_template(
        'stock.html', 
        stock=stock_actualizado, 
        user=current_user
    )

if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
