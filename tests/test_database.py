"""
Testes para database.py — DBConn, PGRow, context manager.
Usa SQLite em memória para não precisar de banco externo.
"""
import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPGRow:
    """Testa o wrapper PGRow que permite acesso por nome e por índice."""

    def _make_row(self, data: dict):
        from database import PGRow
        return PGRow(data)

    def test_acesso_por_nome(self):
        row = self._make_row({'nome': 'Pedro', 'matricula': '123'})
        assert row['nome'] == 'Pedro'

    def test_acesso_por_indice(self):
        row = self._make_row({'nome': 'Pedro', 'matricula': '123'})
        assert row[0] == 'Pedro'
        assert row[1] == '123'

    def test_get_por_nome(self):
        row = self._make_row({'id': 42})
        assert row.get('id') == 42
        assert row.get('nao_existe', 'default') == 'default'

    def test_indice_fora_de_range(self):
        from database import PGRow
        row = PGRow({'a': 1})
        try:
            _ = row[99]
            assert False, "Deveria ter lançado KeyError"
        except KeyError:
            pass  # comportamento esperado

    def test_keys(self):
        row = self._make_row({'x': 1, 'y': 2})
        assert set(row.keys()) == {'x', 'y'}

    def test_dict_conversion(self):
        row = self._make_row({'id': 1, 'nome': 'Teste'})
        d = dict(row)
        assert d == {'id': 1, 'nome': 'Teste'}


class TestDBConnContextManager:
    """Testa que DBConn funciona como context manager."""

    def _get_sqlite_conn(self):
        """Cria uma DBConn SQLite em memória para testes."""
        from database import DBConn
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        return DBConn(conn, is_postgres=False)

    def test_context_manager_fecha_conexao(self):
        """O __exit__ deve chamar close() automaticamente."""
        from database import DBConn
        fechou = []
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        db = DBConn(conn, is_postgres=False)

        # Sobrescreve close para detectar chamada
        original_close = db.close
        def mock_close():
            fechou.append(True)
            original_close()
        db.close = mock_close

        with db:
            db.execute('SELECT 1')

        assert fechou, "close() não foi chamado ao sair do with"

    def test_context_manager_nao_suprime_excecao(self):
        """Exceções dentro do with devem propagar normalmente."""
        db = self._get_sqlite_conn()
        try:
            with db:
                raise ValueError("Erro de teste")
            assert False, "Exceção deveria ter propagado"
        except ValueError as e:
            assert str(e) == "Erro de teste"

    def test_execute_retorna_resultado(self):
        db = self._get_sqlite_conn()
        with db:
            db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, nome TEXT)')
            db.execute("INSERT INTO t (nome) VALUES (?)", ('Teste',))
            db.commit()
            row = db.execute('SELECT * FROM t WHERE id=1').fetchone()
        assert row is not None

    def test_commit_e_rollback(self):
        """Testa que commit salva e rollback desfaz."""
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        from database import DBConn
        db = DBConn(conn, is_postgres=False)

        db.execute('CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)')
        db.commit()

        db.execute("INSERT INTO t (val) VALUES (?)", ('pendente',))
        db.rollback()

        rows = db.execute('SELECT * FROM t').fetchall()
        db.close()
        assert len(rows) == 0, "Rollback não funcionou"


class TestInitDB:
    """Testa que init_db cria as tabelas corretamente."""

    def test_init_db_cria_tabelas(self):
        """init_db deve criar todas as 8 tabelas esperadas."""
        import database
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_db = f.name

        original_fn = database.get_db_path
        original_use = database.USE_POSTGRES
        database.get_db_path = lambda: temp_db
        database.USE_POSTGRES = False

        try:
            database.init_db()
            # Verifica tabelas criadas
            conn = sqlite3.connect(temp_db)
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tabelas = {row[0] for row in cursor.fetchall()}
            conn.close()
        finally:
            database.get_db_path = original_fn
            database.USE_POSTGRES = original_use
            os.unlink(temp_db)

        esperadas = {
            'pessoas', 'empresas', 'contratos', 'prorrogacoes',
            'empenhos', 'notas_fiscais', 'nf_empenhos', 'historico_alteracoes',
        }
        assert esperadas.issubset(tabelas), f"Tabelas faltando: {esperadas - tabelas}"

    def test_init_db_idempotente(self):
        """init_db chamada duas vezes não deve falhar."""
        import database
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_db = f.name

        original_fn = database.get_db_path
        original_use = database.USE_POSTGRES
        database.get_db_path = lambda: temp_db
        database.USE_POSTGRES = False

        try:
            database.init_db()
            database.init_db()  # Segunda chamada não deve lançar exceção
        finally:
            database.get_db_path = original_fn
            database.USE_POSTGRES = original_use
            os.unlink(temp_db)
