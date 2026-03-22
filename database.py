"""
database.py — Camada de acesso ao banco de dados.

Suporta dois modos:
  - SQLite (local): usado quando DATABASE_URL não está definida
  - PostgreSQL (Railway): usado quando DATABASE_URL está definida

A classe DBConn abstrai as diferenças entre os dois bancos,
permitindo que o restante do código use a mesma API em ambos os casos.
"""
import os
import sys
from datetime import date


# ── Detecta qual banco usar ───────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Railway retorna URLs no formato postgres://, mas psycopg2 exige postgresql://
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

USE_POSTGRES = bool(DATABASE_URL)


# ── Localização do SQLite (apenas quando rodando localmente) ─────────────────
def get_db_path():
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(os.path.dirname(sys.executable), 'semed.db')
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'semed.db')


# ── Wrapper de cursor que imita sqlite3.Row ──────────────────────────────────
class PGRow(dict):
    """Permite acesso por nome (row['campo']), índice (row[0]) e atributo (row.campo)."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Guarda lista de valores para acesso por índice numérico
        self._values_list = list(dict(*args, **kwargs).values()) if args or kwargs else []

    def __getitem__(self, key):
        if isinstance(key, int):
            try:
                return self._values_list[key]
            except IndexError:
                raise KeyError(key)
        return super().__getitem__(key)

    def get(self, key, default=None):
        if isinstance(key, int):
            try:
                return self._values_list[key]
            except IndexError:
                return default
        return super().get(key, default)

    def keys(self):
        return super().keys()


class PGCursor:
    """
    Cursor PostgreSQL que imita a API do sqlite3:
    - execute() retorna self (para encadear .fetchone(), etc.)
    - fetchone() / fetchall() retornam PGRow (dict-like)
    - lastrowid disponível após INSERT
    """
    def __init__(self, cursor):
        self._cur = cursor
        self.lastrowid = None

    def execute(self, sql, params=None):
        # Converte placeholders ? (SQLite) para %s (PostgreSQL)
        pg_sql = sql.replace('?', '%s')
        # AUTOINCREMENT não existe no PostgreSQL; é ignorado no CREATE TABLE
        pg_sql = pg_sql.replace('AUTOINCREMENT', '')
        # PRAGMA não existe no PostgreSQL; ignora silenciosamente
        if pg_sql.strip().upper().startswith('PRAGMA'):
            return self
        # Para INSERT no PostgreSQL, adiciona RETURNING id para capturar o ID gerado
        stripped = pg_sql.strip().upper()
        if stripped.startswith('INSERT') and 'RETURNING' not in stripped:
            pg_sql = pg_sql.rstrip().rstrip(';') + ' RETURNING id'
            self._cur.execute(pg_sql, params or ())
            row = self._cur.fetchone()
            self.lastrowid = row[0] if row else None
        else:
            self._cur.execute(pg_sql, params or ())
            self.lastrowid = None
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        desc = self._cur.description
        if not desc:
            # Sem descrição (ex: após INSERT com RETURNING já consumido)
            return None
        cols = [d[0] for d in desc]
        return PGRow(zip(cols, row))

    def fetchall(self):
        rows = self._cur.fetchall()
        if not rows:
            return []
        cols = [d[0] for d in self._cur.description]
        return [PGRow(zip(cols, row)) for row in rows]


# ── Wrapper de conexão que unifica SQLite e PostgreSQL ───────────────────────
class DBConn:
    """
    Conexão unificada. Expõe:
      - execute(sql, params) → cursor compatível
      - commit()
      - close()
      - cursor()  (para init_db que usa c = conn.cursor())
    """
    def __init__(self, conn, is_postgres=False):
        self._conn = conn
        self._is_postgres = is_postgres
        self._pg_cur = conn.cursor() if is_postgres else None

    def execute(self, sql, params=None):
        if self._is_postgres:
            cur = PGCursor(self._conn.cursor())
            return cur.execute(sql, params)
        else:
            # SQLite: retorna o cursor nativo (já tem .lastrowid e .fetchone/.fetchall)
            return self._conn.execute(sql, params or ())

    def cursor(self):
        """Retorna um cursor compatível (usado em init_db)."""
        if self._is_postgres:
            return PGCursor(self._conn.cursor())
        else:
            class SQLiteCursorWrapper:
                def __init__(self, conn):
                    self._conn = conn
                    self.lastrowid = None
                def execute(self, sql, params=None):
                    cur = self._conn.execute(sql, params or ())
                    self.lastrowid = cur.lastrowid
                    return self
                def fetchone(self):
                    return self._conn.execute('SELECT 1').fetchone()
            return SQLiteCursorWrapper(self._conn)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


# ── Fábrica de conexões ───────────────────────────────────────────────────────
def get_db():
    if USE_POSTGRES:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        return DBConn(conn, is_postgres=True)
    else:
        import sqlite3
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return DBConn(conn, is_postgres=False)


# ── Criação das tabelas ───────────────────────────────────────────────────────
def init_db():
    conn = get_db()

    # No PostgreSQL, SERIAL equivale ao INTEGER PRIMARY KEY AUTOINCREMENT do SQLite
    # Mas como o wrapper remove AUTOINCREMENT, precisamos de CREATE TABLE IF NOT EXISTS
    # com SERIAL para Postgres e INTEGER PRIMARY KEY AUTOINCREMENT para SQLite.
    # Solução: usamos templates separados apenas para a parte de tipo de ID.
    if USE_POSTGRES:
        pk = 'SERIAL PRIMARY KEY'
        fk_pragma = ''
    else:
        pk = 'INTEGER PRIMARY KEY AUTOINCREMENT'
        fk_pragma = ''  # PRAGMA é executado no get_db() para SQLite

    tables = [
        f'''CREATE TABLE IF NOT EXISTS pessoas (
            id {pk},
            nome TEXT NOT NULL,
            matricula TEXT NOT NULL UNIQUE
        )''',
        f'''CREATE TABLE IF NOT EXISTS empresas (
            id {pk},
            razao_social TEXT NOT NULL,
            cnpj TEXT NOT NULL UNIQUE,
            endereco TEXT,
            banco TEXT,
            agencia TEXT,
            conta_bancaria TEXT,
            tipo_operacao TEXT
        )''',
        f'''CREATE TABLE IF NOT EXISTS contratos (
            id {pk},
            numero TEXT NOT NULL UNIQUE,
            empresa_id INTEGER NOT NULL,
            vigencia_inicio TEXT NOT NULL,
            vigencia_fim TEXT NOT NULL,
            objeto TEXT NOT NULL,
            processo TEXT,
            preposto TEXT,
            gestor_titular_id INTEGER NOT NULL,
            gestor_suplente_id INTEGER NOT NULL,
            fiscal_titular_id INTEGER NOT NULL,
            fiscal_suplente_id INTEGER NOT NULL
        )''',
        f'''CREATE TABLE IF NOT EXISTS prorrogacoes (
            id {pk},
            contrato_id INTEGER NOT NULL,
            vigencia_anterior TEXT NOT NULL,
            vigencia_nova TEXT NOT NULL,
            motivo TEXT,
            data_registro TEXT NOT NULL
        )''',
        f'''CREATE TABLE IF NOT EXISTS empenhos (
            id {pk},
            contrato_id INTEGER NOT NULL,
            numero TEXT NOT NULL,
            valor_total REAL NOT NULL,
            saldo_atual REAL NOT NULL,
            fonte_recurso TEXT,
            codigo_aplicacao TEXT,
            banco TEXT,
            agencia TEXT,
            conta_bancaria TEXT,
            tipo_operacao TEXT
        )''',
        f'''CREATE TABLE IF NOT EXISTS notas_fiscais (
            id {pk},
            contrato_id INTEGER NOT NULL,
            numero_nf TEXT NOT NULL,
            valor_nf REAL NOT NULL,
            mes_referencia INTEGER NOT NULL,
            ano_referencia INTEGER NOT NULL,
            periodo_inicio TEXT NOT NULL,
            periodo_fim TEXT NOT NULL,
            numero_medicao TEXT NOT NULL,
            gestor_id INTEGER NOT NULL,
            fiscal_id INTEGER NOT NULL,
            meio_recebimento TEXT NOT NULL,
            data_verificacao_certidoes TEXT,
            houve_ocorrencias INTEGER NOT NULL DEFAULT 0,
            ocorrencia_execucao TEXT,
            ocorrencia_providencias TEXT,
            ocorrencia_resultados TEXT,
            checklist_json TEXT,
            cancelada INTEGER NOT NULL DEFAULT 0,
            data_geracao TEXT
        )''',
        f'''CREATE TABLE IF NOT EXISTS nf_empenhos (
            id {pk},
            nota_fiscal_id INTEGER NOT NULL,
            empenho_id INTEGER NOT NULL,
            valor_usado REAL NOT NULL,
            saldo_anterior REAL NOT NULL
        )''',
        f'''CREATE TABLE IF NOT EXISTS historico_alteracoes (
            id {pk},
            tabela TEXT NOT NULL,
            registro_id INTEGER NOT NULL,
            campo TEXT NOT NULL,
            valor_anterior TEXT,
            valor_novo TEXT,
            data_alteracao TEXT NOT NULL
        )''',
    ]

    for sql in tables:
        conn.execute(sql)
    conn.commit()
    conn.close()


# ── Log de auditoria ─────────────────────────────────────────────────────────
def registrar_alteracao(db, tabela, registro_id, campo, valor_anterior, valor_novo):
    if str(valor_anterior or '') != str(valor_novo or ''):
        db.execute(
            '''INSERT INTO historico_alteracoes
               (tabela, registro_id, campo, valor_anterior, valor_novo, data_alteracao)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (tabela, registro_id, campo,
             str(valor_anterior) if valor_anterior is not None else '',
             str(valor_novo)     if valor_novo     is not None else '',
             date.today().strftime('%d/%m/%Y'))
        )


if __name__ == '__main__':
    init_db()
    modo = 'PostgreSQL' if USE_POSTGRES else f'SQLite em {get_db_path()}'
    print(f'Banco inicializado: {modo}')
