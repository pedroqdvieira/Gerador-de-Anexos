import sys
import os
import threading
import webbrowser
from datetime import timedelta


def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)


import logging
from flask import Flask, redirect, url_for, session, render_template, request
from database import init_db, USE_POSTGRES
from routes.pessoas import pessoas_bp
from routes.empresas import empresas_bp
from routes.contratos import contratos_bp
from routes.anexos import anexos_bp
from routes.auth import auth_bp, login_required

app = Flask(
    __name__,
    template_folder=resource_path('templates'),
    static_folder=resource_path('static')
)

# ── Logging ───────────────────────────────────────────────────────────────────
_log_level = logging.DEBUG if os.environ.get('FLASK_DEBUG') else logging.INFO
logging.basicConfig(
    level=_log_level,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)
# Em produção, defina SECRET_KEY como variável de ambiente no Railway.
# Localmente, gera uma chave aleatória por sessão (não persiste entre reinicios).
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    import secrets as _secrets_mod
    _secret = _secrets_mod.token_hex(32)
app.secret_key = _secret
app.permanent_session_lifetime = timedelta(hours=8)

@app.template_filter('databr')
def databr_filter(value):
    if value and len(str(value)) == 10 and str(value)[4] == '-':
        p = str(value).split('-')
        return f'{p[2]}/{p[1]}/{p[0]}'
    return value or ''

# ── Blueprints ────────────────────────────────────────────────────────────────
app.register_blueprint(auth_bp)
app.register_blueprint(pessoas_bp)
app.register_blueprint(empresas_bp)
app.register_blueprint(contratos_bp)
app.register_blueprint(anexos_bp)

# Garante que as tabelas existem ao iniciar (tanto gunicorn quanto python app.py)
with app.app_context():
    init_db()

# ── Rotas simples ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return redirect(url_for('anexos.home'))

@app.route('/manual')
@login_required
def manual():
    return render_template('manual.html')

# ── Health check (Railway e monitoramento) ───────────────────────────────────
@app.route('/health')
def health():
    from flask import jsonify
    return jsonify({'status': 'ok', 'version': '0.4.3'}), 200


# ── Proteção global: todas as rotas exigem login ──────────────────────────────
@app.before_request
def require_login():
    # Rotas que não precisam de login
    public = {'auth.login', 'auth.logout', 'static', 'health'}
    if request.endpoint in public:
        return
    if not session.get('logged_in'):
        return redirect(url_for('auth.login', next=request.path))

# ── Modo local: Flask em thread + janela tkinter ──────────────────────────────
def run_flask():
    host = '0.0.0.0' if USE_POSTGRES else '127.0.0.1'
    app.run(debug=False, host=host, port=5000, use_reloader=False, threaded=True)


def abrir_janela_controle():
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title('Gerador de Anexos')
    root.geometry('320x200')
    root.resizable(False, False)
    root.configure(bg='#f0f2f5')

    def ao_fechar():
        if messagebox.askokcancel('Encerrar', 'Deseja encerrar o Gerador de Anexos?'):
            root.destroy()
            os._exit(0)

    root.protocol('WM_DELETE_WINDOW', ao_fechar)

    tk.Label(root, text='Gerador de Anexos',
             font=('Segoe UI', 13, 'bold'),
             bg='#f0f2f5', fg='#003087').pack(pady=(24, 4))
    tk.Label(root, text='Rodando em http://localhost:5000',
             font=('Segoe UI', 9), bg='#f0f2f5', fg='#555').pack()
    tk.Button(root, text='Abrir no navegador',
              font=('Segoe UI', 10), bg='#003087', fg='white', relief='flat',
              padx=12, pady=6, cursor='hand2',
              command=lambda: webbrowser.open('http://localhost:5000')).pack(pady=(16, 6))
    tk.Button(root, text='Encerrar sistema',
              font=('Segoe UI', 10), bg='#c00', fg='white', relief='flat',
              padx=12, pady=6, cursor='hand2', command=ao_fechar).pack()
    root.mainloop()


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support()
    init_db()

    if USE_POSTGRES:
        print('Modo servidor (PostgreSQL). Acesse http://0.0.0.0:5000')
        app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False, threaded=True)
    else:
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        threading.Timer(1.5, lambda: webbrowser.open('http://localhost:5000')).start()
        abrir_janela_controle()
