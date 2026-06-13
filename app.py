from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'agroriego_secreto_cejasmardani'
DATABASE = 'agroriego_stock.db'

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

# --- CONFIGURACIÓN DE BASE DE DATOS (Stock 21 Permanente) ---
def conectar_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_db():
    """Crea la base de datos y el inventario inicial si no existe el archivo físico"""
    if not os.path.exists(DATABASE):
        conn = conectar_db()
        cursor = conn.cursor()
        
        # Tabla de Inventario
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventario (
                parte TEXT PRIMARY KEY,
                motor TEXT,
                categoria TEXT,
                item TEXT,
                ubicacion TEXT,
                minimo INTEGER,
                actual INTEGER
            )
        ''')
        
        # Tabla de Historial de Movimientos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT,
                parte TEXT,
                cantidad INTEGER,
                destino_origen TEXT,
                responsable TEXT,
                fecha TEXT
            )
        ''')
        
        # Lista real de repuestos del taller (Filtros, correas y sellos)
        repuestos_iniciales = [
            ("1R-0739", "Caterpillar", "Filtros", "Filtro de Aceite", "Estante A1", 2, 5),
            ("1R-0770", "Caterpillar", "Filtros", "Filtro Combustible / Trampa Agua", "Estante A1", 2, 1),
            ("106-3969", "Caterpillar", "Filtros", "Filtro Aire Primario", "Estante A2", 1, 2),
            ("504074043", "Iveco T5/T8", "Filtros", "Filtro de Aceite", "Estante B1", 3, 4),
            ("504107584", "Iveco T5/T8", "Filtros", "Filtro de Combustible", "Estante B1", 2, 2),
            ("504013423", "Iveco T5/T8", "Correas", "Correa Poly-V", "Estante B2", 2, 1),
            ("1174416", "Deutz 1013", "Filtros", "Filtro de Aceite", "Estante C1", 4, 6),
            ("1174423", "Deutz 1013", "Filtros", "Filtro de Combustible", "Estante C1", 3, 3),
            ("4272819", "Deutz 1013", "Repuestos", "Bomba de Pre-alimentación", "Caja Herramientas", 1, 0),
            ("1182313", "Deutz 1013 Powers", "Filtros", "Filtro Aire Reforzado", "Estante C2", 2, 2),
            ("Poliuretano", "Varios", "Bombas", "Goma de Acoplamiento", "Estante D1", 2, 3),
            ("Carburo Silicio", "Varios", "Bombas", "Sello Mecánico Cornell", "Estante D1", 2, 1)
        ]
        
        cursor.executemany('''
            INSERT OR IGNORE INTO inventario (parte, motor, categoria, item, ubicacion, minimo, actual)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', repuestos_iniciales)
        
        conn.commit()
        conn.close()

# --- RUTAS DE AUTENTICACIÓN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form.get('username')
        clave = request.form.get('password')
        if usuario in usuarios_sistema and usuarios_sistema[usuario] == clave:
            user = User(usuario)
            login_user(user)
            return redirect(url_for('index'))
        else:
            error = "Usuario o contraseña incorrectos."
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- PANEL PRINCIPAL (Monitoreo + Calculadora Integrada) ---
@app.route('/')
@login_required
def index():
    # Datos de telemetría simulados para los lotes y mapas reales
    equipos_riego = {
        "PIVOT-LOTE-A2": {
            "id": "PIVOT-LOTE-A2", "nombre_corto": "Lote A2", "tipo": "Pivot Central", "lote": "Lote A2 (156 Ha)",
            "posicion": "340°", "presion": "2.4 Bar", "caudal": "115.000 L/h", "estado": "DESCONECTADO", "senal": "-98 dBm",
            "lat": -25.0950, "lng": -64.1320, "hs_riego": 47.7, "hs_falla": 0.0, "hs_movimiento": 0.0, "hs_parado": 14.6,
            "ultima_lectura": "13/06/2026 a las 05:45 PM",
            "graficos_eje_x": ["10-06 00:00", "11-06 14:00", "12-06 08:00", "13-06 17:45"],
            "historial_presion": [0.0, 2.5, 2.4, 0.0], "historial_posicion": [180, 250, 340, 340], "historial_lamina": [0, 22.3, 22.3, 0]
        },
        "FRONTAL-F22": {
            "id": "FRONTAL-F22", "nombre_corto": "Frontal F22", "tipo": "Avance Frontal Lineal", "lote": "Cuadro Norte (210 Ha)",
            "posicion": "Cajón 4 de 12", "presion": "3.2 Bar", "caudal": "120.000 L/h", "estado": "MARCHA", "senal": "-85 dBm",
            "lat": -25.0833, "lng": -64.1167, "hs_riego": 72.3, "hs_falla": 1.1, "hs_movimiento": 5.4, "hs_parado": 8.2,
            "ultima_lectura": "13/06/2026 a las 05:50 PM",
            "graficos_eje_x": ["11-06 00:00", "13-06 17:50"], "historial_presion": [3.2, 3.2], "historial_posicion": [100, 450], "historial_lamina": [12.0, 12.0]
        }
    }
    
    ot_simuladas = [{"id": "OT-104", "tarea": "Engrase de towers 4 y 5 y revisión de alineación", "responsable": "Equipo Técnico", "prioridad": "Alta"}]
    
    id_solicitado = request.args.get('equipo', 'PIVOT-LOTE-A2')
    if id_solicitado not in equipos_riego: 
        id_solicitado = "PIVOT-LOTE-A2"
        
    return render_template('dashboard.html', data=equipos_riego[id_solicitado], todos_equipos=equipos_riego, ot=ot_simuladas, user=current_user)

# --- PANEL DE GESTIÓN DE STOCK 21 ---
@app.route('/stock', methods=['GET', 'POST'])
@login_required
def stock():
    conn = conectar_db()
    cursor = conn.cursor()

    if request.method == 'POST':
        tipo_accion = request.form.get('accion') 
        nro_parte = request.form.get('parte')
        cantidad = int(request.form.get('quantity', 0))
        responsable = request.form.get('responsable', 'Taller')
        destino_origen = request.form.get('destino_origen', '-')
        
        # Hora local Argentina (-3) para registrar los movimientos del taller
        fecha_local = (datetime.utcnow() - timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute("SELECT actual FROM inventario WHERE parte = ?", (nro_parte,))
        fila = cursor.fetchone()

        if fila and cantidad > 0:
            stock_actual = fila['actual']
            
            if tipo_accion == 'entrada':
                nuevo_stock = stock_actual + cantidad
                cursor.execute("UPDATE inventario SET actual = ? WHERE parte = ?", (nuevo_stock, nro_parte))
                cursor.execute('''
                    INSERT INTO movimientos (tipo, parte, cantidad, destino_origen, responsable, fecha)
                    VALUES ('entrada', ?, ?, ?, ?, ?)
                ''', (nro_parte, cantidad, destino_origen, responsable, fecha_local))
            
            elif tipo_accion == 'salida':
                if stock_actual >= cantidad:
                    nuevo_stock = stock_actual - cantidad
                    cursor.execute("UPDATE inventario SET actual = ? WHERE parte = ?", (nuevo_stock, nro_parte))
                    cursor.execute('''
                        INSERT INTO movimientos (tipo, parte, cantidad, destino_origen, responsable, fecha)
                        VALUES ('salida', ?, ?, ?, ?, ?)
                    ''', (nro_parte, cantidad, destino_origen, responsable, fecha_local))

            conn.commit()
            conn.close()
            return redirect(url_for('stock'))

    # Cargar listas completas ordenadas desde la base de datos
    cursor.execute("SELECT * FROM inventario")
    lista_inventario = cursor.fetchall()

    cursor.execute('''
        SELECT m.*, i.item, i.motor FROM movimientos m 
        JOIN inventario i ON m.parte = i.parte 
        WHERE m.tipo = 'entrada' ORDER BY m.id DESC LIMIT 10
    ''')
    entradas = cursor.fetchall()

    cursor.execute('''
        SELECT m.*, i.item, i.motor FROM movimientos m 
        JOIN inventario i ON m.parte = i.parte 
        WHERE m.tipo = 'salida' ORDER BY m.id DESC LIMIT 10
    ''')
    salidas = cursor.fetchall()

    conn.close()
    return render_template('stock.html', stock=lista_inventario, entradas=entradas, salidas=salidas, user=current_user)

if __name__ == '__main__':
    inicializar_db()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
