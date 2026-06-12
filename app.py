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

# --- FUNCIÓN PARA CARGAR STOCK DESDE EL ARCHIVO ODS ---
def cargar_stock_desde_ods():
    archivo_ods = "stockriego 21.ods"
    
    # Datos de respaldo por si el archivo no se encuentra en el servidor
    stock_respaldo = [
        {"componente": "Filtro de agua malla 8''", "cantidad": 2, "unidad": "unidades", "estado": "OK"},
        {"componente": "Aceite para reductor Deutz", "cantidad": 20, "unidad": "litros", "estado": "OK"},
        {"componente": "Aspersores terminales Valley", "cantidad": 0, "unidad": "unidades", "estado": "CRÍTICO"}
    ]
    
    if os.path.exists(archivo_ods):
        try:
            # Lee la primera hoja del archivo ODS
            df = pd.read_excel(archivo_ods, engine='odf')
            
            # Limpiamos los nombres de las columnas por si tienen espacios
            df.columns = df.columns.str.strip()
            
            # Estructuramos la lista para que la lea el HTML
            lista_stock = []
            for _, fila in df.iterrows():
                # Reemplazá 'Insumo', 'Stock Disp.' y 'Estado' por los nombres exactos de tus columnas si difieren
                componente = fila.get('Insumo', fila.iloc[0])
                cantidad = fila.get('Stock Disp.', fila.iloc[1])
                estado = fila.get('Estado', 'OK')
                
                lista_stock.append({
                    "componente": str(componente),
                    "cantidad": str(cantidad),
                    "unidad": "", # Dejamos vacío o lo acoplamos si tenés columna de unidades
                    "estado": str(estado).upper()
                })
            return lista_stock
        except Exception as e:
            print(f"Error al leer el archivo ODS, usando respaldo: {e}")
            return stock_respaldo
    else:
        return stock_respaldo

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
    
    # Cargamos el stock dinámico desde tu archivo de Calc
    stock_actualizado = cargar_stock_desde_ods()
    
    return render_template(
        'dashboard.html', 
        data=datos_panel, 
        todos_equipos=equipos_riego, 
        ot=ot_simuladas, 
        stock=stock_actualizado, 
        user=current_user
    )

# --- ARRANQUE COMPATIBLE CON PORT BINDING DE RENDER ---
if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
