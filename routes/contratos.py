from flask import Blueprint, request, jsonify, render_template
from database import get_db, registrar_alteracao
from utils import DATE_FMT
from datetime import date, datetime

contratos_bp = Blueprint('contratos', __name__)

FIELD_LABELS = {
    'numero': 'Número', 'empresa_id': 'Empresa', 'vigencia_inicio': 'Vigência Início',
    'vigencia_fim': 'Vigência Fim', 'objeto': 'Objeto', 'processo': 'Processo',
    'preposto': 'Preposto', 'gestor_titular_id': 'Gestor Titular',
    'gestor_suplente_id': 'Gestor Suplente', 'fiscal_titular_id': 'Fiscal Titular',
    'fiscal_suplente_id': 'Fiscal Suplente',
    'numero_emp': 'Número do Empenho', 'valor_total': 'Valor Total',
    'fonte_recurso': 'Fonte de Recurso', 'codigo_aplicacao': 'Código de Aplicação',
    'banco': 'Banco', 'agencia': 'Agência', 'conta_bancaria': 'Conta Bancária',
    'tipo_operacao': 'Tipo de Operação',
}

def dias_para_vencer(vigencia_fim):
    try:
        fim = datetime.strptime(vigencia_fim, '%Y-%m-%d').date()
        return (fim - date.today()).days
    except Exception:
        return None

def get_contrato_full(db, cid):
    c = db.execute('''SELECT c.*, e.razao_social as empresa_nome, e.cnpj, e.endereco,
        e.banco as emp_banco, e.agencia as emp_agencia, e.conta_bancaria as emp_conta,
        e.tipo_operacao as emp_tipo_op
        FROM contratos c JOIN empresas e ON c.empresa_id = e.id
        WHERE c.id=?''', (cid,)).fetchone()
    if not c:
        return None
    cd = dict(c)
    cd['dias_para_vencer'] = dias_para_vencer(cd.get('vigencia_fim', ''))
    for role in ['gestor_titular', 'gestor_suplente', 'fiscal_titular', 'fiscal_suplente']:
        pid = cd.get(f'{role}_id')
        if pid:
            p = db.execute('SELECT * FROM pessoas WHERE id=?', (pid,)).fetchone()
            cd[f'{role}_info'] = dict(p) if p else None
    emps = db.execute('SELECT * FROM empenhos WHERE contrato_id=? ORDER BY numero', (cid,)).fetchall()
    cd['empenhos'] = [dict(e) for e in emps]
    prorr = db.execute('SELECT * FROM prorrogacoes WHERE contrato_id=? ORDER BY id DESC', (cid,)).fetchall()
    cd['prorrogacoes'] = [dict(p) for p in prorr]
    return cd

@contratos_bp.route('/contratos')
def listar():
    db = get_db()
    contratos = db.execute('''SELECT c.*, e.razao_social as empresa_nome
        FROM contratos c JOIN empresas e ON c.empresa_id = e.id
        ORDER BY c.numero''').fetchall()
    empresas = db.execute('SELECT * FROM empresas ORDER BY razao_social').fetchall()
    pessoas = db.execute('SELECT * FROM pessoas ORDER BY nome').fetchall()
    result = []
    for c in contratos:
        cd = dict(c)
        cd['dias_para_vencer'] = dias_para_vencer(cd.get('vigencia_fim', ''))
        emps = db.execute('SELECT * FROM empenhos WHERE contrato_id=?', (cd['id'],)).fetchall()
        cd['empenhos'] = [dict(e) for e in emps]
        result.append(cd)
    db.close()
    return render_template('contratos.html', contratos=result,
                           empresas=[dict(e) for e in empresas],
                           pessoas=[dict(p) for p in pessoas])

@contratos_bp.route('/api/contratos', methods=['GET'])
def api_listar():
    db = get_db()
    contratos = db.execute('''SELECT c.*, e.razao_social as empresa_nome
        FROM contratos c JOIN empresas e ON c.empresa_id = e.id
        ORDER BY c.numero''').fetchall()
    result = []
    for c in contratos:
        cd = dict(c)
        cd['dias_para_vencer'] = dias_para_vencer(cd.get('vigencia_fim', ''))
        emps = db.execute('SELECT * FROM empenhos WHERE contrato_id=?', (cd['id'],)).fetchall()
        cd['empenhos'] = [dict(e) for e in emps]
        result.append(cd)
    db.close()
    return jsonify(result)

@contratos_bp.route('/api/contratos/<int:cid>', methods=['GET'])
def api_get(cid):
    db = get_db()
    cd = get_contrato_full(db, cid)
    db.close()
    if not cd:
        return jsonify({'error': 'Contrato não encontrado'}), 404
    return jsonify(cd)

@contratos_bp.route('/api/contratos', methods=['POST'])
def criar():
    data = request.json
    required = ['numero', 'empresa_id', 'vigencia_inicio', 'vigencia_fim',
                'objeto', 'gestor_titular_id', 'gestor_suplente_id',
                'fiscal_titular_id', 'fiscal_suplente_id']
    for f in required:
        if not data.get(f):
            return jsonify({'error': f'Campo obrigatório: {f}'}), 400
    roles_ids = [
        data.get('gestor_titular_id'), data.get('gestor_suplente_id'),
        data.get('fiscal_titular_id'), data.get('fiscal_suplente_id'),
    ]
    roles_validos = [r for r in roles_ids if r]
    if len(roles_validos) != 4 or len(set(roles_validos)) != 4:
        return jsonify({
            'error': 'Uma pessoa não pode desempenhar dois papéis no mesmo contrato'
        }), 400
    db = get_db()
    try:
        cur = db.execute('''INSERT INTO contratos
            (numero, empresa_id, vigencia_inicio, vigencia_fim, objeto, processo, preposto,
             gestor_titular_id, gestor_suplente_id, fiscal_titular_id, fiscal_suplente_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (data['numero'].strip(), data['empresa_id'],
             data['vigencia_inicio'], data['vigencia_fim'],
             data['objeto'].strip(), data.get('processo', ''), data.get('preposto', ''),
             data['gestor_titular_id'], data['gestor_suplente_id'],
             data['fiscal_titular_id'], data['fiscal_suplente_id']))
        cid = cur.lastrowid
        for emp in data.get('empenhos', []):
            if emp.get('numero') and emp.get('valor_total'):
                db.execute('''INSERT INTO empenhos
                    (contrato_id, numero, valor_total, saldo_atual, fonte_recurso,
                     codigo_aplicacao, banco, agencia, conta_bancaria, tipo_operacao)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (cid, emp['numero'].strip(), float(emp['valor_total']),
                     float(emp['valor_total']),
                     emp.get('fonte_recurso', ''), emp.get('codigo_aplicacao', ''),
                     emp.get('banco', ''), emp.get('agencia', ''),
                     emp.get('conta_bancaria', ''), emp.get('tipo_operacao', '')))
        db.commit()
        result = get_contrato_full(db, cid)
        db.close()
        return jsonify(result), 201
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': 'Erro ao salvar contrato'}), 400

@contratos_bp.route('/api/contratos/<int:cid>', methods=['PUT'])
def atualizar(cid):
    data = request.json
    roles_ids = [
        data.get('gestor_titular_id'), data.get('gestor_suplente_id'),
        data.get('fiscal_titular_id'), data.get('fiscal_suplente_id'),
    ]
    roles_validos = [r for r in roles_ids if r]
    if len(roles_validos) != 4 or len(set(roles_validos)) != 4:
        return jsonify({
            'error': 'Uma pessoa não pode desempenhar dois papéis no mesmo contrato'
        }), 400
    db = get_db()
    try:
        # Busca valores anteriores para log
        anterior = db.execute('SELECT * FROM contratos WHERE id=?', (cid,)).fetchone()
        if anterior:
            campos = ['numero', 'empresa_id', 'vigencia_inicio', 'vigencia_fim', 'objeto',
                      'processo', 'preposto', 'gestor_titular_id', 'gestor_suplente_id',
                      'fiscal_titular_id', 'fiscal_suplente_id']
            novos = {'numero': data['numero'].strip(), 'empresa_id': data['empresa_id'],
                     'vigencia_inicio': data['vigencia_inicio'], 'vigencia_fim': data['vigencia_fim'],
                     'objeto': data['objeto'].strip(), 'processo': data.get('processo', ''),
                     'preposto': data.get('preposto', ''), 'gestor_titular_id': data['gestor_titular_id'],
                     'gestor_suplente_id': data['gestor_suplente_id'],
                     'fiscal_titular_id': data['fiscal_titular_id'],
                     'fiscal_suplente_id': data['fiscal_suplente_id']}
            for campo in campos:
                registrar_alteracao(db, 'contratos', cid,
                    FIELD_LABELS.get(campo, campo),
                    anterior[campo], novos[campo])

        db.execute('''UPDATE contratos SET numero=?, empresa_id=?, vigencia_inicio=?,
            vigencia_fim=?, objeto=?, processo=?, preposto=?,
            gestor_titular_id=?, gestor_suplente_id=?,
            fiscal_titular_id=?, fiscal_suplente_id=? WHERE id=?''',
            (data['numero'].strip(), data['empresa_id'],
             data['vigencia_inicio'], data['vigencia_fim'],
             data['objeto'].strip(), data.get('processo', ''), data.get('preposto', ''),
             data['gestor_titular_id'], data['gestor_suplente_id'],
             data['fiscal_titular_id'], data['fiscal_suplente_id'], cid))

        used_emp_ids = {r['empenho_id'] for r in db.execute(
            '''SELECT DISTINCT empenho_id FROM nf_empenhos ne
               JOIN empenhos e ON ne.empenho_id = e.id WHERE e.contrato_id=?''', (cid,)).fetchall()}
        existing_ids = {r['id'] for r in db.execute(
            'SELECT id FROM empenhos WHERE contrato_id=?', (cid,)).fetchall()}

        # IDs enviados pelo frontend (empenhos que devem ser mantidos)
        ids_no_payload = {
            int(e['id']) for e in data.get('empenhos', [])
            if e.get('id') and str(e['id']).strip()
        }

        # Só deleta empenhos que:
        # 1. Existem no banco
        # 2. NÃO vieram no payload (usuário removeu explicitamente)
        # 3. NÃO têm NF vinculada (protegidos)
        deletable = existing_ids - ids_no_payload - used_emp_ids
        if deletable:
            db.execute(
                f'DELETE FROM empenhos WHERE id IN ({",".join("?" * len(deletable))})',
                list(deletable),
            )

        for emp in data.get('empenhos', []):
            if not emp.get('numero') or not emp.get('valor_total'):
                continue
            eid = emp.get('id')
            if eid and int(eid) in used_emp_ids:
                # Log empenho changes (non-financial fields only)
                ant_emp = db.execute('SELECT * FROM empenhos WHERE id=?', (int(eid),)).fetchone()
                if ant_emp:
                    for campo in ['fonte_recurso', 'codigo_aplicacao', 'banco', 'agencia', 'conta_bancaria', 'tipo_operacao']:
                        registrar_alteracao(db, 'empenhos', int(eid),
                            FIELD_LABELS.get(campo, campo),
                            ant_emp[campo], emp.get(campo, ''))
                db.execute('''UPDATE empenhos SET fonte_recurso=?, codigo_aplicacao=?,
                    banco=?, agencia=?, conta_bancaria=?, tipo_operacao=? WHERE id=?''',
                    (emp.get('fonte_recurso', ''), emp.get('codigo_aplicacao', ''),
                     emp.get('banco', ''), emp.get('agencia', ''),
                     emp.get('conta_bancaria', ''), emp.get('tipo_operacao', ''), int(eid)))
            elif eid and int(eid) in existing_ids:
                ant_emp = db.execute('SELECT * FROM empenhos WHERE id=?', (int(eid),)).fetchone()
                if ant_emp:
                    for campo in ['numero', 'valor_total', 'fonte_recurso', 'codigo_aplicacao',
                                  'banco', 'agencia', 'conta_bancaria', 'tipo_operacao']:
                        registrar_alteracao(db, 'empenhos', int(eid),
                            FIELD_LABELS.get(campo, campo),
                            ant_emp[campo], emp.get(campo if campo != 'numero' else 'numero', ''))
                db.execute('''UPDATE empenhos SET numero=?, valor_total=?, saldo_atual=?,
                    fonte_recurso=?, codigo_aplicacao=?, banco=?, agencia=?,
                    conta_bancaria=?, tipo_operacao=? WHERE id=?''',
                    (emp['numero'].strip(), float(emp['valor_total']),
                     float(emp.get('saldo_atual', emp['valor_total'])),
                     emp.get('fonte_recurso', ''), emp.get('codigo_aplicacao', ''),
                     emp.get('banco', ''), emp.get('agencia', ''),
                     emp.get('conta_bancaria', ''), emp.get('tipo_operacao', ''), int(eid)))
            else:
                db.execute('''INSERT INTO empenhos
                    (contrato_id, numero, valor_total, saldo_atual, fonte_recurso,
                     codigo_aplicacao, banco, agencia, conta_bancaria, tipo_operacao)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (cid, emp['numero'].strip(), float(emp['valor_total']),
                     float(emp['valor_total']),
                     emp.get('fonte_recurso', ''), emp.get('codigo_aplicacao', ''),
                     emp.get('banco', ''), emp.get('agencia', ''),
                     emp.get('conta_bancaria', ''), emp.get('tipo_operacao', '')))
        db.commit()
        result = get_contrato_full(db, cid)
        db.close()
        return jsonify(result)
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': 'Erro ao atualizar contrato'}), 400

@contratos_bp.route('/api/contratos/<int:cid>/prorrogar', methods=['POST'])
def prorrogar(cid):
    data = request.json
    db = get_db()
    try:
        contrato = db.execute('SELECT * FROM contratos WHERE id=?', (cid,)).fetchone()
        if not contrato:
            db.close()
            return jsonify({'error': 'Contrato não encontrado'}), 404
        vigencia_anterior = contrato['vigencia_fim']
        vigencia_nova = data.get('vigencia_nova')
        motivo = data.get('motivo', '')
        if not vigencia_nova:
            db.close()
            return jsonify({'error': 'Nova data de vigência é obrigatória'}), 400
        db.execute('''INSERT INTO prorrogacoes
            (contrato_id, vigencia_anterior, vigencia_nova, motivo, data_registro)
            VALUES (?, ?, ?, ?, ?)''',
            (cid, vigencia_anterior, vigencia_nova, motivo, date.today().strftime(DATE_FMT)))
        db.execute('UPDATE contratos SET vigencia_fim=? WHERE id=?', (vigencia_nova, cid))
        registrar_alteracao(db, 'contratos', cid, 'Vigência Fim', vigencia_anterior, vigencia_nova)
        db.commit()
        db.close()
        return jsonify({'ok': True})
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': 'Erro ao prorrogar contrato'}), 400

@contratos_bp.route('/api/contratos/<int:cid>/historico-alteracoes')
def historico_alteracoes(cid):
    db = get_db()
    # Alterações do contrato
    alt_contrato = db.execute('''SELECT * FROM historico_alteracoes
        WHERE tabela='contratos' AND registro_id=? ORDER BY id DESC''', (cid,)).fetchall()
    # Alterações dos empenhos do contrato
    emps = db.execute('SELECT id, numero FROM empenhos WHERE contrato_id=?', (cid,)).fetchall()
    alt_empenhos = []
    for emp in emps:
        rows = db.execute('''SELECT ha.*, ? as empenho_numero FROM historico_alteracoes ha
            WHERE tabela='empenhos' AND registro_id=? ORDER BY id DESC''',
            (emp['numero'], emp['id'])).fetchall()
        alt_empenhos.extend([dict(r) for r in rows])
    db.close()
    return jsonify({
        'contrato': [dict(r) for r in alt_contrato],
        'empenhos': sorted(alt_empenhos, key=lambda x: x['id'], reverse=True),
    })

@contratos_bp.route('/api/contratos/<int:cid>/relatorio-empenhos')
def relatorio_empenhos(cid):
    db = get_db()
    contrato = db.execute('''SELECT c.*, e.razao_social as empresa_nome
        FROM contratos c JOIN empresas e ON c.empresa_id=e.id WHERE c.id=?''', (cid,)).fetchone()
    if not contrato:
        db.close()
        return jsonify({'error': 'Contrato não encontrado'}), 404
    emps = db.execute('SELECT * FROM empenhos WHERE contrato_id=? ORDER BY numero', (cid,)).fetchall()
    result = []
    for emp in emps:
        usos = db.execute('''SELECT ne.*, nf.numero_nf, nf.mes_referencia, nf.ano_referencia,
            nf.numero_medicao, nf.data_geracao, nf.cancelada
            FROM nf_empenhos ne JOIN notas_fiscais nf ON ne.nota_fiscal_id=nf.id
            WHERE ne.empenho_id=? ORDER BY nf.id''', (emp['id'],)).fetchall()
        result.append({**dict(emp), 'usos': [dict(u) for u in usos]})
    db.close()
    return jsonify({'contrato': dict(contrato), 'empenhos': result})

@contratos_bp.route('/api/contratos/<int:cid>', methods=['DELETE'])
def deletar(cid):
    db = get_db()
    nfs = db.execute('SELECT id FROM notas_fiscais WHERE contrato_id=?', (cid,)).fetchall()
    if nfs:
        db.close()
        return jsonify({'error': 'Contrato possui notas fiscais registradas e não pode ser excluído'}), 400
    db.execute('DELETE FROM prorrogacoes WHERE contrato_id=?', (cid,))
    db.execute('DELETE FROM empenhos WHERE contrato_id=?', (cid,))
    db.execute('DELETE FROM historico_alteracoes WHERE tabela=\'contratos\' AND registro_id=?', (cid,))
    db.execute('DELETE FROM contratos WHERE id=?', (cid,))
    db.commit()
    db.close()
    return jsonify({'ok': True})

@contratos_bp.route('/api/empenhos/<int:eid>', methods=['GET'])
def get_empenho(eid):
    db = get_db()
    emp = db.execute('SELECT * FROM empenhos WHERE id=?', (eid,)).fetchone()
    db.close()
    if not emp:
        return jsonify({'error': 'Empenho não encontrado'}), 404
    return jsonify(dict(emp))