import os
from functools import wraps
from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint('auth', __name__)

# ── Credenciais ────────────────────────────────────────────────────────────────
# Hash da senha gerado com werkzeug.security.generate_password_hash
# Para alterar a senha, gere um novo hash com:
#   python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('NOVA_SENHA'))"
# e defina a variável de ambiente ADMIN_PASSWORD_HASH no Railway.
DEFAULT_HASH = (
    'scrypt:32768:8:1$LmWgYkLX0BJbBam9$e19ec950bebd64c1efe2a8aa97d6c170ea9f1af396d5'
    '7be412a47a8504c5bfd3dcb14d8481280c401244179f17e7775098e951794cec77b55fc0fa0c674b2e4a'
)
ADMIN_USER = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_HASH = os.environ.get('ADMIN_PASSWORD_HASH', DEFAULT_HASH)


def login_required(f):
    """Decorator que bloqueia rotas para usuários não autenticados."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('anexos.home'))

    error = None
    if request.method == 'POST':
        usuario  = request.form.get('usuario', '').strip()
        senha    = request.form.get('senha', '')
        next_url = request.form.get('next', '/')

        if usuario == ADMIN_USER and check_password_hash(ADMIN_HASH, senha):
            session.permanent = True
            session['logged_in'] = True
            session['usuario'] = usuario
            # Valida next_url para evitar Open Redirect para domínios externos
            if not next_url or not next_url.startswith('/'):
                next_url = url_for('anexos.home')
            return redirect(next_url)
        else:
            error = 'Usuário ou senha incorretos.'

    next_url = request.args.get('next', '/')
    return render_template('login.html', error=error, next=next_url)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
