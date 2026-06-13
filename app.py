from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os

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

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('username')
        clave = request.form.get('password')
        if usuario in usuarios_sistema and usuarios_sistema[usuario] == clave:
            user = User(usuario)
            login_user(user)
            return redirect(url_for('index'))
    return '''
        <form method="post" style="background:#131c2e; color:white; padding:30px; border-radius:8px; max-width:300px; margin:100px auto; font-family:sans-serif;">
            <h2>AgroRiego Login</h2>
            <label>Usuario:</label><br><input type="text" name="username" style="width:100%; margin-bottom:10px;"><br>
            <label>Contraseña:</label><br><input type="password" name="password" style="width:100%; margin-bottom:10px;"><br>
            <button type="submit" style="background:#10b981; color:white; border:none; padding:8px 16px; border-radius:4px; cursor:pointer;">Entrar</button>
        </form>
    '''

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- TELEMETRÍA DE EQUIPOS ---
equipos_riego = {
    "PIVOT-LOTE-A2": {
        "id": "PIVOT-LOTE-A2", "nombre_corto": "Lote A2", "tipo": "Pivot Central", "lote": "Lote A2 (156 Ha)",
        "posicion": "340°", "presion": "2.4 Bar", "caudal": "115.000 L/h", "estado": "DESCONECTADO", "senal": "-98 dBm",
        "lat": -25.0950, "lng": -64.1320, "hs_riego": 47.7, "hs_falla": 0.0, "hs_movimiento": 0.0, "hs_parado": 14.6,
        "ultima_lectura": "09/06/2026 a las 10:14 AM",
        "graficos_eje_x": ["06-06 00:00", "06-06 14:00", "07-06 08:00", "07-06 22:00", "08-06 12:00", "09-06 02:00", "09-06 10:14"],
        "historial_presion": [0.0, 1.2, 2.5, 2.4, 1.8, 2.4, 0.0], "historial_posicion": [180, 220, 250, 250, 290, 340, 340],
        "historial_lamina": [0, 22.3, 22.3, 0, 15.5, 22.3, 0],
        "eventos": [{"fecha": "09/06/2026", "hora": "12:15 PM", "estado": "Desconectado", "badge": "badge-critico"}]
    },
    "FRONTAL-F22": {
        "id": "FRONTAL-F22", "nombre_corto": "Frontal F22", "tipo": "Avance Frontal Lineal", "lote": "Cuadro Norte (210 Ha)",
        "posicion": "Cajón 4 de 12", "presion": "3.2 Bar", "caudal": "120.000 L/h", "estado": "MARCHA", "senal": "-85 dBm",
        "lat": -25.0833, "lng": -64.1167, "hs_riego": 72.3, "hs_falla": 1.1, "hs_movimiento": 5.4, "hs_parado": 8.2,
        "ultima_lectura": "12/06/2026 a las 08:00 PM",
        "graficos_eje_x": ["10-06 00:00", "12-06 20:00"], "historial_presion": [3.2, 3.2], "historial_posicion": [100, 450], "historial_lamina": [12.0, 12.0],
        "eventos": [{"fecha": "12/06/2026", "hora": "06:15 PM", "estado": "Regando", "badge": "badge-marcha"}]
    }
}

ot_simuladas = [{"id": "OT-104", "tarea": "Engrase de towers 4 y 5", "responsable": "Téc. Mecánico", "prioridad": "Alta"}]


# --- BASE DE DATOS INVENTARIO REAL (STOCK 21) ---
# Usamos un diccionario indexado por Nro. de Parte para buscar y actualizar rápido
inventario_repuestos = {
    "1R-0739": {"motor": "Caterpillar", "categoria": "Filtros", "item": "Filtro de Aceite", "parte": "1R-0739", "actual": 5, "minimo": 2, "ubicacion": "Estante A1"},
    "1R-0770": {"motor": "Caterpillar", "categoria": "Filtros", "item": "Filtro Combustible / Trampa Agua", "parte": "1R-0770", "actual": 1, "minimo": 2, "ubicacion": "Estante A1"},
    "106-3969": {"motor": "Caterpillar", "categoria": "Filtros", "item": "Filtro Aire Primario", "parte": "106-3969", "actual": 2, "minimo": 1, "ubicacion": "Estante A2"},
    "504074043": {"motor": "Iveco T5/T8", "categoria": "Filtros", "item": "Filtro de Aceite", "parte": "504074043", "actual": 4, "minimo": 3, "ubicacion": "Estante B1"},
    "504107584": {"motor": "Iveco T5/T8", "categoria": "Filtros", "item": "Filtro de Combustible", "parte": "504107584", "actual": 2, "minimo": 2, "ubicacion": "Estante B1"},
    "504013423": {"motor": "Iveco T5/T8", "categoria": "Correas", "item": "Correa Poly-V", "parte": "504013423", "actual": 1, "minimo": 2, "ubicacion": "Estante B2"},
    "1174416": {"motor": "Deutz 1013", "categoria": "Filtros", "item": "Filtro de Aceite", "parte": "1174416", "actual": 6, "minimo": 4, "ubicacion": "Estante C1"},
    "1174423": {"motor": "Deutz 1013", "categoria": "Filtros", "item": "Filtro de Combustible", "parte": "1174423", "actual": 3, "minimo": 3, "ubicacion": "Estante C1"},
    "4272819": {"motor": "Deutz 1013", "categoria": "Repuestos", "item": "Bomba de Pre-alimentación", "parte": "4272819", "actual": 0, "minimo": 1, "ubicacion": "Caja Herramientas"},
    "1182313": {"motor": "Deutz 1013 Powers", "categoria": "Filtros", "item": "Filtro Aire Reforzado", "parte": "1182313", "actual": 2, "minimo": 2, "ubicacion": "Estante C2"},
    "Poliuretano": {"motor": "Varios", "categoria": "Bombas", "item": "Goma de Acoplamiento", "parte": "Poliuretano", "actual": 3, "minimo": 2, "ubicacion": "Estante D1"},
    "Carburo Silicio": {"motor": "Varios", "categoria": "Bombas", "item": "Sello Mecánico Cornell", "parte": "Carburo Silicio", "actual": 1, "minimo": 2, "ubicacion": "Estante D1"}
}

# Historiales para las otras pestañas
historial_entradas = []
historial_salidas = []

@app.route('/')
@login_required
def index():
    id_solicitado = request.args.get('equipo', 'PIVOT-LOTE-A2')
    if id_solicitado not in equipos_riego: id_solicitado = "PIVOT-LOTE-A2"
    return render_template('dashboard.html', data=equipos_riego[id_solicitado], todos_equipos=equipos_riego, ot=ot_simuladas, user=current_user)


# --- RUTA DE STOCK INTERACTIVA ---
@app.route('/stock', methods=['GET', 'POST'])
@login_required
def stock():
    if request.method == 'POST':
        tipo_accion = request.form.get('accion') # 'entrada' o 'salida'
        nro_parte = request.form.get('parte')
        cantidad = int(request.form.get('cantidad', 0))
        responsable = request.form.get('responsable', 'Taller')
        destino_origen = request.form.get('destino_origen', '-')

        if nro_parte in inventario_repuestos and cantidad > 0:
            item = inventario_repuestos[nro_parte]
            
            if tipo_accion == 'entrada':
                item['actual'] += cantidad
                historial_entradas.insert(0, {
                    "parte": nro_parte, "item": item['item'], "motor": item['motor'],
                    "cantidad": cantidad, "origen": destino_origen, "responsable": responsable
                })
            
            elif tipo_accion == 'salida':
                if item['actual'] >= cantidad:
                    item['actual'] -= cantidad
                    historial_salidas.insert(0, {
                        "parte": nro_parte, "item": item['item'], "motor": item['motor'],
                        "cantidad": cantidad, "destino": destino_origen, "responsable": responsable
                    })
                else:
                    # Si no hay suficiente stock, no hace el descuento
                    pass

            return redirect(url_for('stock'))

    # Pasamos las listas ordenadas para la interfaz de las 3 pestañas
    lista_inventario = list(inventario_repuestos.values())
    return render_template('stock.html', stock=lista_inventario, entradas=historial_entradas, salidas=historial_salidas, user=current_user)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
