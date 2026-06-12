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

# --- FUNCIÓN DETECTIVE PARA VER QUÉ HAY EN EL SERVIDOR ---
def cargar_stock_desde_ods():
    # Buscamos el archivo de stock
    archivo_real = None
    archivos_encontrados = os.listdir('.')
    
    for archivo in archivos_encontrados:
        nombre_minuscula = archivo.lower()
        if nombre_minuscula.startswith('stock') and (nombre_minuscula.endswith('.ods') or nombre_minuscula.endswith('.xlsx')):
            archivo_real = archivo
            break

    # SI ENCUENTRA EL ARCHIVO, LO PROCESA
    if archivo_real:
        try:
            if archivo_real.lower().endswith('.ods'):
                df = pd.read_excel(archivo_real, engine='odf')
            else:
                df = pd.read_excel(archivo_real)
            
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
            # Si falla al leerlo, nos avisa en la tabla el error
            return [{"componente": f"⚠️ Error al leer archivo: {archivo_real}", "cantidad": str(e), "unidad": "", "estado": "CRÍTICO"}]
            
    # SI NO ENCUENTRA EL ARCHIVO, EN LUGAR DEL RESPALDO, NOS MUESTRA QUÉ ARCHIVOS HAY
    lista_diagnostico = []
    for f in archivos_encontrados:
        # Filtramos archivos ocultos del sistema para no llenar la pantalla
        if not f.startswith('.'):
            lista_diagnostico.append({
                "componente": f"📁 Archivo en servidor: {f}",
                "cantidad": "Visible",
                "unidad": "",
                "estado": "OK"
            })
            
    if len(lista_diagnostico) == 0:
        return [{"componente": "❌ Servidor vacío (No se ven archivos)", "cantidad": 0, "unidad": "", "estado": "CRÍTICO"}]
        
    return lista_diagnostico

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
    
    stock_actualizado = cargar_stock_desde_ods()
    
    return render_template(
        'dashboard.html', 
        data=datos_panel, 
        todos_equipos=equipos_riego, 
        ot=ot_simuladas, 
        stock=stock_actualizado, 
        user=current_user
    )

if __name__ == '__main__':
    puerto = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=puerto)
