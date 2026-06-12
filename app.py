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

# --- FUNCIÓN INTELIGENTE PARA TU PLANILLA REAL ---
def cargar_stock_desde_ods():
    # Datos de respaldo por si el servidor no encuentra ningún archivo
    stock_respaldo = [
        {"componente": "Filtro de agua malla 8''", "cantidad": 2, "unidad": "unidades", "estado": "OK"},
        {"componente": "Aceite para reductor Deutz", "cantidad": 20, "unidad": "litros", "estado": "OK"},
        {"componente": "Aspersores terminales Valley", "cantidad": 0, "unidad": "unidades", "estado": "CRÍTICO"}
    ]
    
    # Escaneamos la carpeta del servidor buscando el archivo real de stock
    archivo_real = None
    for archivo in os.listdir('.'):
        nombre_minuscula = archivo.lower()
        if nombre_minuscula.startswith('stock') and (nombre_minuscula.endswith('.ods') or nombre_minuscula.endswith('.xlsx')):
            archivo_real = archivo
            print(f"¡Archivo de stock detectado en el servidor!: {archivo_real}")
            break

    if archivo_real:
        try:
            # Seleccionamos el motor correcto según el formato detectado
            if archivo_real.lower().endswith('.ods'):
                df = pd.read_excel(archivo_real, engine='odf')
            else:
                df = pd.read_excel(archivo_real)
            
            # Limpiamos los títulos de las columnas de espacios ocultos
            df.columns = df.columns.str.strip()
            
            lista_stock = []
            for _, fila in df.iterrows():
                # Mapeamos exactamente las columnas de tu foto de Calc
                componente = fila.get('Descripsion /Modelo')
                cantidad = fila.get('Stock Actual')
                estado_raw = fila.get('Stock Crítico', 'STOCK OK')
                
                # Si la fila no tiene componente, pasamos a la siguiente
                if pd.isna(componente):
                    continue
                
                # Sincronizamos las alertas de texto con los colores de tu diseño
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
            print(f"Error procesando el archivo {archivo_real}: {e}")
            return stock_respaldo
            
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
    
    # El sistema escanea y carga los datos reales de tu planilla
    stock_actualizado = cargar_stock_desde_ods()
    
    return render_template(
        'dashboard.html', 
        data=datos_panel, 
        todos_equipos=equipos_riego, 
        ot=ot_simuladas, 
        stock=stock_actualizado, 
        user=current_user
    )

# --- ARRANQUE EN RENDER ---
if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
