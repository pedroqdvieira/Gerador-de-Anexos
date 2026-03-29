import os
import time
from functools import wraps
from flask import (
    Blueprint, request, session, redirect, url_for, render_template
)
from werkzeug.security import check_password_hash

auth_bp = Blueprint('auth', __name__)

# ── Credenciais ───────────────────────────────────────────────────────────────
# Em produção, defina ADMIN_USERNAME e ADMIN_PASSWORD_HASH como variáveis
# de ambiente no Railway. O DEFAULT_HASH abaixo é usado APENAS em
# desenvolvimento local; em produção ele é ignorado se ADMIN_PASSWORD_HASH
# estiver definida.
#
# Para gerar um novo hash:
#   python3 -c "from werkzeug.security import generate_password_hash; \
#               print(generate_password_hash('NOVA_SENHA'))"
_DEFAULT_HASH = (
    'scrypt:32768:8:1$LmWgYkLX0BJbBam9$e19ec950bebd64c1efe2a8aa97d6c170ea9f1af396d5'
    '7be412a47a8504c5bfd3dcb14d8481280c401244179f17e7775098e951794cec77b55fc0fa0c674b2e4a'
)
ADMIN_USER = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_HASH = os.environ.get('ADMIN_PASSWORD_HASH', _DEFAULT_HASH)

# ── Proteção contra brute force ───────────────────────────────────────────────
_MAX_FALHAS = 10            # máximo de tentativas antes de bloquear
_DELAY_FALHA = 0.5          # segundos de delay após cada falha
_BLOQUEIO_SEGUNDOS = 300    # 5 minutos de bloqueio após _MAX_FALHAS tentativas


def _chave_ip():
    return request.remote_addr or 'unknown'


def _verificar_bloqueio():
    """Retorna True se o IP atual está bloqueado."""
    chave = f'login_falhas_{_chave_ip()}'
    dados = session.get(chave, {'falhas': 0, 'bloqueado_ate': 0})
    if dados['bloqueado_ate'] > time.time():
        return True
    return False


def _registrar_falha():
    """Incrementa contador de falhas; bloqueia se atingir o limite."""
    chave = f'login_falhas_{_chave_ip()}'
    dados = session.get(chave, {'falhas': 0, 'bloqueado_ate': 0})
    dados['falhas'] = dados.get('falhas', 0) + 1
    if dados['falhas'] >= _MAX_FALHAS:
        dados['bloqueado_ate'] = time.time() + _BLOQUEIO_SEGUNDOS
        dados['falhas'] = 0
    session[chave] = dados
    time.sleep(_DELAY_FALHA)


def _limpar_falhas():
    """Remove contador de falhas após login bem-sucedido."""
    chave = f'login_falhas_{_chave_ip()}'
    session.pop(chave, None)


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
        if _verificar_bloqueio():
            error = 'Muitas tentativas. Aguarde alguns minutos.'
            return render_template('login.html', error=error,
                                   next=request.form.get('next', '/'))

        usuario  = request.form.get('usuario', '').strip()
        senha    = request.form.get('senha', '')
        next_url = request.form.get('next', '/')

        if usuario == ADMIN_USER and check_password_hash(ADMIN_HASH, senha):
            _limpar_falhas()
            session.permanent = True
            session['logged_in'] = True
            session['usuario'] = usuario
            # Valida next_url para evitar Open Redirect para domínios externos
            if not next_url or not next_url.startswith('/'):
                next_url = url_for('anexos.home')
            return redirect(next_url)

        _registrar_falha()
        error = 'Usuário ou senha incorretos.'

    next_url = request.args.get('next', '/')
    return render_template('login.html', error=error, next=next_url)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))
