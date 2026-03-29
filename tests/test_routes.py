"""
Testes de integração para as rotas Flask.

Usa o test client do Flask com banco SQLite em memória.
Cada teste começa com banco limpo.
"""
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_app_with_temp_db():
    """Cria instância do app com banco temporário isolado."""
    import database
    import app as app_module

    tf = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tf.close()
    temp_db = tf.name

    database.get_db_path = lambda: temp_db
    database.USE_POSTGRES = False

    flask_app = app_module.app
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key'

    with flask_app.app_context():
        database.init_db()

    return flask_app, temp_db


def _login(client):
    """Faz login no cliente de teste."""
    return client.post('/login', data={
        'usuario': 'admin',
        'senha': 'Pacu88123',
        'next': '/',
    }, follow_redirects=True)


class TestHealth:
    """Testa o endpoint de health check."""

    def test_health_retorna_200(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                resp = client.get('/health')
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert data['status'] == 'ok'
        finally:
            os.unlink(temp_db)

    def test_health_sem_autenticacao(self):
        """Health check deve funcionar sem login."""
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                resp = client.get('/health')
                assert resp.status_code == 200
        finally:
            os.unlink(temp_db)


class TestAuth:
    """Testa login e logout."""

    def test_login_pagina_get(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                resp = client.get('/login')
                assert resp.status_code == 200
        finally:
            os.unlink(temp_db)

    def test_login_credenciais_invalidas(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                resp = client.post('/login', data={
                    'usuario': 'admin',
                    'senha': 'senha_errada',
                    'next': '/',
                })
                assert resp.status_code == 200
                assert 'incorretos' in resp.data.decode('utf-8')
        finally:
            os.unlink(temp_db)

    def test_rota_protegida_sem_login(self):
        """Rota protegida deve redirecionar para login."""
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                resp = client.get('/pessoas')
                assert resp.status_code == 302
                assert '/login' in resp.headers['Location']
        finally:
            os.unlink(temp_db)

    def test_logout(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.get('/logout', follow_redirects=False)
                assert resp.status_code == 302
        finally:
            os.unlink(temp_db)


class TestPessoas:
    """Testa CRUD de pessoas."""

    def _setup(self):
        flask_app, temp_db = _make_app_with_temp_db()
        client = flask_app.test_client()
        client.__enter__()
        _login(client)
        return flask_app, client, temp_db

    def test_listar_vazio(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.get('/api/pessoas')
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert isinstance(data, list)
        finally:
            os.unlink(temp_db)

    def test_criar_pessoa(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.post('/api/pessoas',
                    data=json.dumps({'nome': 'Pedro Silva', 'matricula': '12345'}),
                    content_type='application/json')
                assert resp.status_code == 201
                data = json.loads(resp.data)
                assert data['nome'] == 'Pedro Silva'
                assert data['matricula'] == '12345'
        finally:
            os.unlink(temp_db)

    def test_criar_pessoa_campos_obrigatorios(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.post('/api/pessoas',
                    data=json.dumps({'nome': 'Sem matricula'}),
                    content_type='application/json')
                assert resp.status_code == 400
                data = json.loads(resp.data)
                assert 'error' in data
        finally:
            os.unlink(temp_db)

    def test_criar_e_listar(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                client.post('/api/pessoas',
                    data=json.dumps({'nome': 'Ana Costa', 'matricula': '99999'}),
                    content_type='application/json')
                resp = client.get('/api/pessoas')
                pessoas = json.loads(resp.data)
                nomes = [p['nome'] for p in pessoas]
                assert 'Ana Costa' in nomes
        finally:
            os.unlink(temp_db)

    def test_criar_matricula_duplicada(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                payload = json.dumps({'nome': 'João', 'matricula': '11111'})
                client.post('/api/pessoas', data=payload,
                            content_type='application/json')
                resp = client.post('/api/pessoas', data=payload,
                                   content_type='application/json')
                assert resp.status_code == 400

        finally:
            os.unlink(temp_db)

    def test_atualizar_pessoa(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                # Cria
                resp = client.post('/api/pessoas',
                    data=json.dumps({'nome': 'Maria', 'matricula': '55555'}),
                    content_type='application/json')
                pid = json.loads(resp.data)['id']
                # Atualiza
                resp = client.put(f'/api/pessoas/{pid}',
                    data=json.dumps({'nome': 'Maria Silva', 'matricula': '55555'}),
                    content_type='application/json')
                assert resp.status_code == 200
                # Verifica
                lista = json.loads(client.get('/api/pessoas').data)
                nomes = [p['nome'] for p in lista]
                assert 'Maria Silva' in nomes
        finally:
            os.unlink(temp_db)

    def test_deletar_pessoa(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.post('/api/pessoas',
                    data=json.dumps({'nome': 'Deletável', 'matricula': '77777'}),
                    content_type='application/json')
                pid = json.loads(resp.data)['id']
                resp = client.delete(f'/api/pessoas/{pid}')
                assert resp.status_code == 200
                lista = json.loads(client.get('/api/pessoas').data)
                assert all(p['id'] != pid for p in lista)
        finally:
            os.unlink(temp_db)

    def test_busca_por_nome(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                client.post('/api/pessoas',
                    data=json.dumps({'nome': 'Carlos Souza', 'matricula': '33333'}),
                    content_type='application/json')
                resp = client.get('/api/pessoas?q=carlos')
                data = json.loads(resp.data)
                assert any('Carlos' in p['nome'] for p in data)


        finally:
            os.unlink(temp_db)


class TestEmpresas:
    """Testa CRUD de empresas com validação de CNPJ."""

    # CNPJ válido para testes
    CNPJ_VALIDO = '33.000.167/0001-01'
    CNPJ_INVALIDO = '12.345.678/0001-99'

    def test_criar_empresa_cnpj_valido(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.post('/api/empresas',
                    data=json.dumps({
                        'razao_social': 'Empresa Teste Ltda',
                        'cnpj': self.CNPJ_VALIDO,
                    }),
                    content_type='application/json')
                assert resp.status_code == 201
                data = json.loads(resp.data)
                assert data['razao_social'] == 'Empresa Teste Ltda'
        finally:
            os.unlink(temp_db)

    def test_criar_empresa_cnpj_invalido(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.post('/api/empresas',
                    data=json.dumps({
                        'razao_social': 'Empresa Inválida',
                        'cnpj': self.CNPJ_INVALIDO,
                    }),
                    content_type='application/json')
                assert resp.status_code == 400
                data = json.loads(resp.data)
                assert 'CNPJ' in data['error']
        finally:
            os.unlink(temp_db)

    def test_validar_cnpj_endpoint(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.post('/api/cnpj/validar',
                    data=json.dumps({'cnpj': self.CNPJ_VALIDO}),
                    content_type='application/json')
                assert json.loads(resp.data)['valido'] is True

                resp = client.post('/api/cnpj/validar',
                    data=json.dumps({'cnpj': self.CNPJ_INVALIDO}),
                    content_type='application/json')
                assert json.loads(resp.data)['valido'] is False
        finally:
            os.unlink(temp_db)

    def test_campos_obrigatorios(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.post('/api/empresas',
                    data=json.dumps({'razao_social': 'Só o nome'}),
                    content_type='application/json')
                assert resp.status_code == 400
        finally:
            os.unlink(temp_db)


class TestContratos:
    """Testa criação e validação de contratos."""

    CNPJ = '33.000.167/0001-01'

    def _criar_pre_requisitos(self, client):
        """Cria empresa e 4 pessoas necessárias para um contrato."""
        emp = json.loads(client.post('/api/empresas',
            data=json.dumps({'razao_social': 'Fornecedor Ltda', 'cnpj': self.CNPJ}),
            content_type='application/json').data)

        pessoas = []
        for i, nome in enumerate(['Gestor T', 'Gestor S', 'Fiscal T', 'Fiscal S']):
            p = json.loads(client.post('/api/pessoas',
                data=json.dumps({'nome': nome, 'matricula': f'1000{i}'}),
                content_type='application/json').data)
            pessoas.append(p['id'])

        return emp['id'], pessoas

    def _payload_contrato(self, empresa_id, pessoas):
        return {
            'numero': '001/2025',
            'empresa_id': empresa_id,
            'vigencia_inicio': '2025-01-01',
            'vigencia_fim': '2025-12-31',
            'objeto': 'Prestação de serviços de TI',
            'processo': 'PROC-001',
            'gestor_titular_id': pessoas[0],
            'gestor_suplente_id': pessoas[1],
            'fiscal_titular_id': pessoas[2],
            'fiscal_suplente_id': pessoas[3],
            'empenhos': [
                {'numero': '1001/2025', 'valor_total': 100000.0}
            ],
        }

    def test_criar_contrato(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                emp_id, pessoas = self._criar_pre_requisitos(client)
                payload = self._payload_contrato(emp_id, pessoas)
                resp = client.post('/api/contratos',
                    data=json.dumps(payload),
                    content_type='application/json')
                assert resp.status_code == 201
                data = json.loads(resp.data)
                assert data['numero'] == '001/2025'
                assert len(data['empenhos']) == 1
        finally:
            os.unlink(temp_db)

    def test_roles_duplicados_rejeitados(self):
        """Mesma pessoa em dois papéis deve ser rejeitada."""
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                emp_id, pessoas = self._criar_pre_requisitos(client)
                payload = self._payload_contrato(emp_id, pessoas)
                # Coloca a mesma pessoa como gestor titular e suplente
                payload['gestor_suplente_id'] = payload['gestor_titular_id']
                resp = client.post('/api/contratos',
                    data=json.dumps(payload),
                    content_type='application/json')
                assert resp.status_code == 400
                data = json.loads(resp.data)
                assert 'papel' in data['error'].lower() or 'pap' in data['error'].lower()
        finally:
            os.unlink(temp_db)

    def test_listar_contratos(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                emp_id, pessoas = self._criar_pre_requisitos(client)
                client.post('/api/contratos',
                    data=json.dumps(self._payload_contrato(emp_id, pessoas)),
                    content_type='application/json')
                resp = client.get('/api/contratos')
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert len(data) >= 1
        finally:
            os.unlink(temp_db)

    def test_campos_obrigatorios(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.post('/api/contratos',
                    data=json.dumps({'numero': 'SEM_EMPRESA'}),
                    content_type='application/json')
                assert resp.status_code == 400
        finally:
            os.unlink(temp_db)


class TestAnexosSaldoValidation:
    """Testa validações de saldo nos endpoints de NF."""

    CNPJ = '22.840.676/0001-26'

    def _criar_contrato_completo(self, client):
        """Cria contrato com empenho de R$ 10.000."""
        emp = json.loads(client.post('/api/empresas',
            data=json.dumps({'razao_social': 'Target Ltda', 'cnpj': self.CNPJ}),
            content_type='application/json').data)

        pessoas_ids = []
        for i, nome in enumerate(['GT', 'GS', 'FT', 'FS']):
            p = json.loads(client.post('/api/pessoas',
                data=json.dumps({'nome': nome, 'matricula': f'2000{i}'}),
                content_type='application/json').data)
            pessoas_ids.append(p['id'])

        contrato = json.loads(client.post('/api/contratos',
            data=json.dumps({
                'numero': '002/2025',
                'empresa_id': emp['id'],
                'vigencia_inicio': '2025-01-01',
                'vigencia_fim': '2025-12-31',
                'objeto': 'Serviços gerais',
                'gestor_titular_id': pessoas_ids[0],
                'gestor_suplente_id': pessoas_ids[1],
                'fiscal_titular_id': pessoas_ids[2],
                'fiscal_suplente_id': pessoas_ids[3],
                'empenhos': [{'numero': '2001/2025', 'valor_total': 10000.0}],
            }),
            content_type='application/json').data)

        return contrato, pessoas_ids

    def test_validar_saldo_suficiente(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                contrato, pessoas = self._criar_contrato_completo(client)
                emp_id = contrato['empenhos'][0]['id']

                resp = client.post('/api/nf/validar-saldo',
                    data=json.dumps({
                        'empenhos_usados': [{'empenho_id': emp_id, 'valor_usado': 5000.0}]
                    }),
                    content_type='application/json')
                data = json.loads(resp.data)
                assert data['ok'] is True
                assert data['erros'] == []
        finally:
            os.unlink(temp_db)

    def test_validar_saldo_insuficiente(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                contrato, pessoas = self._criar_contrato_completo(client)
                emp_id = contrato['empenhos'][0]['id']

                resp = client.post('/api/nf/validar-saldo',
                    data=json.dumps({
                        'empenhos_usados': [{'empenho_id': emp_id, 'valor_usado': 99999.0}]
                    }),
                    content_type='application/json')
                data = json.loads(resp.data)
                assert data['ok'] is False
                assert len(data['erros']) > 0
        finally:
            os.unlink(temp_db)

    def test_dashboard_retorna_200(self):
        flask_app, temp_db = _make_app_with_temp_db()
        try:
            with flask_app.test_client() as client:
                _login(client)
                resp = client.get('/api/dashboard')
                assert resp.status_code == 200
                data = json.loads(resp.data)
                assert 'contratos' in data
                assert 'empenhos' in data
                assert 'alertas' in data
        finally:
            os.unlink(temp_db)
