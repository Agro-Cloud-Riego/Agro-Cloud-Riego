from flask import Flask, render_template

app = Flask(__name__)

# Simulación de datos del Pivot
pivot_data = {
    "presion": 2.4,
    "angulo": 45,
    "estado": "Regando"
}

@app.route('/')
def index():
    return render_template('dashboard.html', data=pivot_data)

if __name__ == '__main__':
    app.run(debug=True)
