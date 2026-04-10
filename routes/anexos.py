import json
import zipfile
import io
import csv
from datetime import date, datetime
from flask import Blueprint, request, jsonify, render_template, send_file, abort
from database import get_db
from routes.contratos import get_contrato_full
from utils import DATE_FMT, formatar_valor_br, to_decimal
from pdf_generator import gerar_anexo_iii, gerar_anexo_vi, gerar_anexo_ix, gerar_ateste
from pypdf import PdfWriter, PdfReader

anexos_bp = Blueprint('anexos', __name__)

MESES = {1:'Janeiro',2:'Fevereiro',3:'Março',4:'Abril',5:'Maio',6:'Junho',
         7:'Julho',8:'Agosto',9:'Setembro',10:'Outubro',11:'Novembro',12:'Dezembro'}


def _safe_int(value, default=None):
    """Converte valor para int com segurança; retorna default se inválido."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def get_dados_for_pdf(db, nf_id):
    nf = db.execute('SELECT * FROM notas_fiscais WHERE id=?', (nf_id,)).fetchone()
    if not nf:
        return None
    nf = dict(nf)
    contrato = db.execute('''SELECT c.*, e.razao_social as empresa_nome, e.cnpj, e.endereco,
        e.banco as emp_banco, e.agencia as emp_agencia, e.conta_bancaria as emp_conta,
        e.tipo_operacao as emp_tipo_op
        FROM contratos c JOIN empresas e ON c.empresa_id = e.id WHERE c.id=?''',
        (nf['contrato_id'],)).fetchone()
    contrato = dict(contrato)
    gestor = dict(db.execute('SELECT * FROM pessoas WHERE id=?', (nf['gestor_id'],)).fetchone())
    fiscal = dict(db.execute('SELECT * FROM pessoas WHERE id=?', (nf['fiscal_id'],)).fetchone())
    gestor['suplente'] = (gestor['id'] == contrato['gestor_suplente_id'])
    fiscal['suplente'] = (fiscal['id'] == contrato['fiscal_suplente_id'])
    fiscal['titulo'] = 'Fiscal Suplente do Contrato' if fiscal['suplente'] else 'Fiscal do Contrato'
    nf_empenhos = db.execute(
        'SELECT ne.*, e.* FROM nf_empenhos ne JOIN empenhos e ON ne.empenho_id = e.id WHERE ne.nota_fiscal_id=?',
        (nf_id,)).fetchall()
    empenhos_usados = [{'id': dict(e)['empenho_id'], 'numero': dict(e)['numero'], 'valor_total': dict(e)['valor_total'],
        'saldo_anterior': dict(e)['saldo_anterior'], 'valor_usado': dict(e)['valor_usado'],
        'fonte_recurso': dict(e).get('fonte_recurso',''), 'codigo_aplicacao': dict(e).get('codigo_aplicacao',''),
        'banco': dict(e).get('banco',''), 'agencia': dict(e).get('agencia',''),
        'conta_bancaria': dict(e).get('conta_bancaria',''), 'tipo_operacao': dict(e).get('tipo_operacao','')}
        for e in nf_empenhos]
    empresa = {'banco': contrato['emp_banco'], 'agencia': contrato['emp_agencia'],
        'conta_bancaria': contrato['emp_conta'], 'tipo_operacao': contrato['emp_tipo_op']}
    contrato_info = {'numero': contrato['numero'], 'empresa': contrato['empresa_nome'],
        'cnpj': contrato['cnpj'], 'objeto': contrato['objeto'],
        'processo': contrato.get('processo',''), 'preposto': contrato.get('preposto',''),
        'vigencia_inicio': contrato['vigencia_inicio'], 'vigencia_fim': contrato['vigencia_fim'],
        'gestor_titular_id': contrato['gestor_titular_id'],
        'fiscal_titular_id': contrato['fiscal_titular_id'],
        'gestor_suplente_id': contrato['gestor_suplente_id']}
    checklist = {}
    if nf.get('checklist_json'):
        try:
            checklist = json.loads(nf['checklist_json'])
        except Exception:
            checklist = {}
    return {'nf': nf, 'contrato': contrato_info, 'gestor': gestor, 'fiscal': fiscal,
            'empenhos_usados': empenhos_usados, 'empresa': empresa, 'checklist': checklist}

@anexos_bp.route('/')
def home():
    return render_template('home.html')

@anexos_bp.route('/api/dashboard')
def api_dashboard():
    db = get_db()
    hoje = date.today()

    # ── Contratos por status ──────────────────────────────────────────────
    contratos = db.execute('''SELECT c.numero, c.vigencia_fim, e.razao_social as empresa
        FROM contratos c JOIN empresas e ON c.empresa_id=e.id''').fetchall()
    vigente = vencendo = vencido = 0
    alertas = []
    for c in contratos:
        try:
            fim = datetime.strptime(c['vigencia_fim'], '%Y-%m-%d').date()
            dias = (fim - hoje).days
            if dias < 0:
                vencido += 1
            elif dias <= 30:
                vencendo += 1
                alertas.append({'numero': c['numero'], 'empresa': c['empresa'],
                                'dias': dias, 'vigencia_fim': c['vigencia_fim']})
            else:
                vigente += 1
        except Exception:
            pass
    alertas.sort(key=lambda x: x['dias'])

    # ── Empenhos ─────────────────────────────────────────────────────────
    emp = db.execute('''SELECT
        SUM(saldo_atual) as saldo_total,
        SUM(valor_total) as valor_total,
        COUNT(*) as qtd
        FROM empenhos''').fetchone()
    saldo_total  = emp['saldo_total']  or 0
    valor_total  = emp['valor_total']  or 0
    qtd_empenhos = emp['qtd'] or 0
    utilizado    = valor_total - saldo_total

    # ── Totais gerais ─────────────────────────────────────────────────────
    total_contratos = len(contratos)
    r_emp = db.execute('SELECT COUNT(*) AS total FROM empresas').fetchone()
    r_pes = db.execute('SELECT COUNT(*) AS total FROM pessoas').fetchone()
    total_empresas  = r_emp['total'] if r_emp else 0
    total_pessoas   = r_pes['total'] if r_pes else 0

    # ── NFs recentes ──────────────────────────────────────────────────────
    nfs = db.execute('''SELECT nf.id, nf.numero_nf, nf.valor_nf,
        nf.mes_referencia, nf.ano_referencia, nf.data_geracao,
        nf.cancelada, nf.data_geracao,
        c.numero as contrato_numero, e.razao_social as empresa
        FROM notas_fiscais nf
        JOIN contratos c ON nf.contrato_id=c.id
        JOIN empresas e ON c.empresa_id=e.id
        ORDER BY nf.id DESC LIMIT 6''').fetchall()

    db.close()
    return jsonify({
        'contratos': {'vigente': vigente, 'vencendo': vencendo,
                      'vencido': vencido, 'total': total_contratos},
        'empenhos': {'saldo': saldo_total, 'total': valor_total,
                     'utilizado': utilizado, 'qtd': qtd_empenhos},
        'totais': {'empresas': total_empresas, 'pessoas': total_pessoas},
        'alertas': alertas[:5],
        'nfs_recentes': [dict(n) for n in nfs],
    })

@anexos_bp.route('/gerar-anexos')
def gerar_form():
    db = get_db()
    contratos = db.execute('''SELECT c.id, c.numero, e.razao_social as empresa_nome
        FROM contratos c JOIN empresas e ON c.empresa_id = e.id ORDER BY c.numero''').fetchall()
    db.close()
    rascunho_id = request.args.get('rascunho', '')
    return render_template('gerar_anexos.html',
                           contratos=[dict(c) for c in contratos],
                           rascunho_id=rascunho_id)

@anexos_bp.route('/api/contrato/<int:cid>/dados-formulario')
def dados_formulario(cid):
    db = get_db()
    cd = get_contrato_full(db, cid)
    db.close()
    if not cd:
        return jsonify({'error': 'Contrato não encontrado'}), 404
    return jsonify(cd)

@anexos_bp.route('/api/nf/validar-saldo', methods=['POST'])
def validar_saldo():
    """Valida se os empenhos têm saldo suficiente e verifica alertas."""
    data = request.json
    db = get_db()
    alertas = []
    erros = []
    for emp_uso in data.get('empenhos_usados', []):
        emp = db.execute('SELECT * FROM empenhos WHERE id=?', (emp_uso['empenho_id'],)).fetchone()
        if not emp:
            continue
        valor_uso = float(emp_uso['valor_usado'])
        saldo = emp['saldo_atual']
        if valor_uso > saldo:
            erros.append(f'Empenho {emp["numero"]}: saldo insuficiente. '
                         f'Disponível: R$ {formatar_valor_br(saldo)} | Solicitado: R$ {formatar_valor_br(valor_uso)}')
        # Alerta: saldo após pagamento menor que o valor deste pagamento
        # Usar to_decimal para operações aritméticas evita erros de ponto flutuante
        saldo_apos = float(to_decimal(saldo) - to_decimal(valor_uso))
        if saldo_apos < valor_uso and saldo_apos > 0:
            alertas.append(f'Empenho {emp["numero"]}: após este pagamento o saldo restante '
                           f'(R$ {formatar_valor_br(saldo_apos)}) será menor que o valor pago '
                           f'(R$ {formatar_valor_br(valor_uso)}).')
        elif saldo_apos <= 0 and saldo_apos == 0:
            alertas.append(f'Empenho {emp["numero"]}: este pagamento zerará o saldo do empenho.')
    db.close()
    return jsonify({'erros': erros, 'alertas': alertas, 'ok': len(erros) == 0})

@anexos_bp.route('/api/rascunhos')
def api_rascunhos():
    """Lista NFs em rascunho (sem data_geracao e nao canceladas) com dados completos."""
    db = get_db()
    rascunhos = db.execute('''
        SELECT nf.id, nf.contrato_id, nf.numero_nf, nf.valor_nf,
               nf.mes_referencia, nf.ano_referencia, nf.periodo_inicio, nf.periodo_fim,
               nf.numero_medicao, nf.gestor_id, nf.fiscal_id, nf.meio_recebimento,
               nf.data_verificacao_certidoes, nf.houve_ocorrencias,
               nf.ocorrencia_execucao, nf.ocorrencia_providencias, nf.ocorrencia_resultados,
               nf.checklist_json,
               c.numero as contrato_numero, e.razao_social as empresa_nome
        FROM notas_fiscais nf
        JOIN contratos c ON nf.contrato_id = c.id
        JOIN empresas e ON c.empresa_id = e.id
        WHERE nf.data_geracao IS NULL AND nf.cancelada = 0
        ORDER BY nf.id DESC
    ''').fetchall()
    result = []
    for r in rascunhos:
        d = dict(r)
        # Inclui empenhos usados
        emps = db.execute(
            'SELECT empenho_id, valor_usado FROM nf_empenhos WHERE nota_fiscal_id=?',
            (r['id'],)).fetchall()
        d['empenhos_usados'] = [dict(e) for e in emps]
        result.append(d)
    db.close()
    return jsonify(result)

@anexos_bp.route('/api/nf/salvar-rascunho', methods=['POST'])
def salvar_rascunho():
    data = request.json

    # Valida campos obrigatórios antes de abrir o banco
    gestor_id = data.get('gestor_id')
    fiscal_id = data.get('fiscal_id')
    if not gestor_id or not fiscal_id:
        return jsonify({
            'error': 'Selecione o gestor e o fiscal do contrato antes de salvar.'
        }), 400
    if not data.get('contrato_id'):
        return jsonify({'error': 'Selecione um contrato.'}), 400

    db = get_db()
    # Validar saldo antes de salvar
    for emp_uso in data.get('empenhos_usados', []):
        emp = db.execute('SELECT * FROM empenhos WHERE id=?', (emp_uso['empenho_id'],)).fetchone()
        if not emp:
            db.close()
            return jsonify({'error': f'Empenho não encontrado'}), 400
        if float(emp_uso['valor_usado']) > emp['saldo_atual']:
            db.close()
            return jsonify({'error': f'Saldo insuficiente no empenho {emp["numero"]}. '
                           f'Disponível: R$ {formatar_valor_br(emp["saldo_atual"])}'}), 400
    try:
        checklist_json = json.dumps(data.get('checklist', {}))
        nf_id_existente = data.get('nf_id')  # Se presente, atualiza rascunho existente

        if nf_id_existente:
            # Atualiza rascunho existente
            db.execute('''UPDATE notas_fiscais SET
                contrato_id=?, numero_nf=?, valor_nf=?, mes_referencia=?, ano_referencia=?,
                periodo_inicio=?, periodo_fim=?, numero_medicao=?, gestor_id=?, fiscal_id=?,
                meio_recebimento=?, data_verificacao_certidoes=?,
                houve_ocorrencias=?, ocorrencia_execucao=?, ocorrencia_providencias=?,
                ocorrencia_resultados=?, checklist_json=?
                WHERE id=? AND data_geracao IS NULL AND cancelada=0''',
                (data['contrato_id'], data['numero_nf'], float(data['valor_nf']),
                 _safe_int(data.get('mes_referencia')),
                 _safe_int(data.get('ano_referencia')),
                 data['periodo_inicio'], data['periodo_fim'], data['numero_medicao'],
                 data['gestor_id'], data['fiscal_id'], data['meio_recebimento'],
                 data.get('data_verificacao_certidoes', ''),
                 1 if data.get('houve_ocorrencias') else 0,
                 data.get('ocorrencia_execucao', ''), data.get('ocorrencia_providencias', ''),
                 data.get('ocorrencia_resultados', ''), checklist_json, nf_id_existente))
            # Recria empenhos
            db.execute('DELETE FROM nf_empenhos WHERE nota_fiscal_id=?', (nf_id_existente,))
            for emp_uso in data.get('empenhos_usados', []):
                emp = db.execute('SELECT * FROM empenhos WHERE id=?', (emp_uso['empenho_id'],)).fetchone()
                db.execute('''INSERT INTO nf_empenhos (nota_fiscal_id, empenho_id, valor_usado, saldo_anterior)
                    VALUES (?, ?, ?, ?)''',
                    (nf_id_existente, emp_uso['empenho_id'], float(emp_uso['valor_usado']), emp['saldo_atual']))
            db.commit()
            db.close()
            return jsonify({'nf_id': nf_id_existente})
        else:
            # Novo rascunho
            cur = db.execute('''INSERT INTO notas_fiscais
                (contrato_id, numero_nf, valor_nf, mes_referencia, ano_referencia,
                 periodo_inicio, periodo_fim, numero_medicao, gestor_id, fiscal_id,
                 meio_recebimento, data_verificacao_certidoes,
                 houve_ocorrencias, ocorrencia_execucao, ocorrencia_providencias, ocorrencia_resultados,
                 checklist_json, cancelada, data_geracao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)''',
                (data['contrato_id'], data['numero_nf'], float(data['valor_nf']),
                 _safe_int(data.get('mes_referencia')),
                 _safe_int(data.get('ano_referencia')),
                 data['periodo_inicio'], data['periodo_fim'], data['numero_medicao'],
                 data['gestor_id'], data['fiscal_id'], data['meio_recebimento'],
                 data.get('data_verificacao_certidoes', ''),
                 1 if data.get('houve_ocorrencias') else 0,
                 data.get('ocorrencia_execucao', ''), data.get('ocorrencia_providencias', ''),
                 data.get('ocorrencia_resultados', ''), checklist_json))
            nf_id = cur.lastrowid
            for emp_uso in data.get('empenhos_usados', []):
                emp = db.execute('SELECT * FROM empenhos WHERE id=?', (emp_uso['empenho_id'],)).fetchone()
                db.execute('''INSERT INTO nf_empenhos (nota_fiscal_id, empenho_id, valor_usado, saldo_anterior)
                    VALUES (?, ?, ?, ?)''',
                    (nf_id, emp_uso['empenho_id'], float(emp_uso['valor_usado']), emp['saldo_atual']))
            db.commit()
            db.close()
            return jsonify({'nf_id': nf_id})
    except Exception as e:
        import logging
        logging.getLogger(__name__).error('Erro em salvar_rascunho: %s', e, exc_info=True)
        db.rollback()
        db.close()
        return jsonify({'error': f'Erro ao salvar rascunho: {e}'}), 400

@anexos_bp.route('/api/nf/<int:nf_id>/confirmar', methods=['POST'])
def confirmar_nf(nf_id):
    db = get_db()
    nf = db.execute('SELECT * FROM notas_fiscais WHERE id=?', (nf_id,)).fetchone()
    if not nf:
        db.close()
        return jsonify({'error': 'NF não encontrada'}), 404
    if nf['data_geracao']:
        db.close()
        return jsonify({'error': 'NF já foi confirmada'}), 400
    nf_empenhos = db.execute('SELECT * FROM nf_empenhos WHERE nota_fiscal_id=?', (nf_id,)).fetchall()
    try:
        for ne in nf_empenhos:
            db.execute('UPDATE empenhos SET saldo_atual = saldo_atual - ? WHERE id=?',
                       (ne['valor_usado'], ne['empenho_id']))
        db.execute('UPDATE notas_fiscais SET data_geracao=? WHERE id=?',
                   (date.today().strftime(DATE_FMT), nf_id))
        db.commit()
        db.close()
        return jsonify({'ok': True})
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': 'Erro ao confirmar NF'}), 400

@anexos_bp.route('/api/nf/<int:nf_id>/cancelar', methods=['POST'])
def cancelar_nf(nf_id):
    db = get_db()
    nf = db.execute('SELECT * FROM notas_fiscais WHERE id=?', (nf_id,)).fetchone()
    if not nf:
        db.close()
        return jsonify({'error': 'NF não encontrada'}), 404
    if nf['cancelada']:
        db.close()
        return jsonify({'error': 'NF já está cancelada'}), 400
    nf_empenhos = db.execute('SELECT * FROM nf_empenhos WHERE nota_fiscal_id=?', (nf_id,)).fetchall()
    try:
        if nf['data_geracao']:
            for ne in nf_empenhos:
                db.execute('UPDATE empenhos SET saldo_atual = saldo_atual + ? WHERE id=?',
                           (ne['valor_usado'], ne['empenho_id']))
        db.execute('UPDATE notas_fiscais SET cancelada=1 WHERE id=?', (nf_id,))
        db.commit()
        db.close()
        return jsonify({'ok': True})
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': 'Erro ao cancelar NF'}), 400

@anexos_bp.route('/api/nf/<int:nf_id>/pdf/<tipo>')
def download_pdf(nf_id, tipo):
    db = get_db()
    dados = get_dados_for_pdf(db, nf_id)
    db.close()
    if not dados:
        abort(404)
    nf_num = dados["nf"]["numero_nf"]
    if tipo == 'anexo_iii':
        pdf_bytes = gerar_anexo_iii(dados)
        filename = f'Anexo_III_NF_{nf_num}.pdf'
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    elif tipo == 'anexo_vi':
        pdf_bytes = gerar_anexo_vi(dados)
        filename = f'Anexo_VI_NF_{nf_num}.pdf'
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    elif tipo == 'anexo_ix':
        pdf_bytes = gerar_anexo_ix(dados)
        filename = f'Anexo_IX_NF_{nf_num}.pdf'
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    elif tipo == 'ateste':
        pdf_bytes = gerar_ateste(dados)
        filename = f'Ateste_NF_{nf_num}.pdf'
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                         as_attachment=True, download_name=filename)
    elif tipo == 'zip':
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f'Anexo_III_NF_{nf_num}.pdf', gerar_anexo_iii(dados))
            zf.writestr(f'Anexo_VI_NF_{nf_num}.pdf',  gerar_anexo_vi(dados))
            zf.writestr(f'Anexo_IX_NF_{nf_num}.pdf',  gerar_anexo_ix(dados))
            zf.writestr(f'Ateste_NF_{nf_num}.pdf',    gerar_ateste(dados))
        buf.seek(0)
        return send_file(buf, mimetype='application/zip',
                         as_attachment=True, download_name=f'Anexos_NF_{nf_num}.zip')
    else:
        abort(404)

@anexos_bp.route('/historico')
def historico():
    db = get_db()
    contratos = db.execute('''SELECT c.id, c.numero, e.razao_social as empresa_nome
        FROM contratos c JOIN empresas e ON c.empresa_id=e.id ORDER BY c.numero''').fetchall()
    db.close()
    return render_template('historico.html', contratos=[dict(c) for c in contratos])

@anexos_bp.route('/api/historico')
def api_historico():
    db = get_db()
    filtro = request.args.get('q', '').strip().lower()
    contrato_id = request.args.get('contrato_id', '').strip()
    query = '''SELECT nf.*, c.numero as contrato_numero, e.razao_social as empresa_nome
        FROM notas_fiscais nf
        JOIN contratos c ON nf.contrato_id = c.id
        JOIN empresas e ON c.empresa_id = e.id'''
    params = []
    conditions = []
    if contrato_id:
        conditions.append('nf.contrato_id = ?')
        params.append(contrato_id)
    if filtro:
        conditions.append('''(LOWER(c.numero) LIKE ? OR LOWER(e.razao_social) LIKE ?
            OR LOWER(nf.numero_nf) LIKE ? OR LOWER(nf.numero_medicao) LIKE ?
            OR LOWER(nf.data_geracao) LIKE ?)''')
        params.extend([f'%{filtro}%'] * 5)
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' ORDER BY nf.id DESC'
    nfs = db.execute(query, params).fetchall()
    db.close()
    return jsonify([dict(n) for n in nfs])

@anexos_bp.route('/api/nf/<int:nf_id>')
def api_get_nf(nf_id):
    db = get_db()
    dados = get_dados_for_pdf(db, nf_id)
    db.close()
    if not dados:
        return jsonify({'error': 'NF não encontrada'}), 404
    return jsonify(dados)

@anexos_bp.route('/api/nf/<int:nf_id>/deletar', methods=['DELETE'])
def deletar_nf(nf_id):
    db = get_db()
    nf = db.execute('SELECT * FROM notas_fiscais WHERE id=?', (nf_id,)).fetchone()
    if not nf:
        db.close()
        return jsonify({'error': 'NF não encontrada'}), 404
    if nf['data_geracao'] and not nf['cancelada']:
        db.close()
        return jsonify({'error': 'Confirme o cancelamento antes de deletar'}), 400
    db.execute('DELETE FROM nf_empenhos WHERE nota_fiscal_id=?', (nf_id,))
    db.execute('DELETE FROM notas_fiscais WHERE id=?', (nf_id,))
    db.commit()
    db.close()
    return jsonify({'ok': True})

@anexos_bp.route('/api/historico/exportar-xlsx')
def exportar_xlsx():
    """Exporta histórico de pagamentos como CSV (sem dependência de openpyxl)."""
    db = get_db()
    contrato_id = request.args.get('contrato_id', '').strip()
    query = '''SELECT nf.id, c.numero as contrato, e.razao_social as empresa,
        nf.numero_nf, nf.valor_nf, nf.numero_medicao,
        nf.mes_referencia, nf.ano_referencia,
        nf.periodo_inicio, nf.periodo_fim,
        nf.data_geracao, nf.cancelada
        FROM notas_fiscais nf
        JOIN contratos c ON nf.contrato_id = c.id
        JOIN empresas e ON c.empresa_id = e.id'''
    params = []
    if contrato_id:
        query += ' WHERE nf.contrato_id = ?'
        params.append(contrato_id)
    query += ' ORDER BY nf.id'
    nfs = db.execute(query, params).fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(['ID', 'Contrato', 'Empresa', 'Nota Fiscal', 'Valor (R$)',
                     'Medição', 'Mês Ref.', 'Ano Ref.', 'Período Início',
                     'Período Fim', 'Data Geração', 'Status',
                     'Empenhos Usados', 'Valores por Empenho'])
    for nf in nfs:
        emps = db.execute('''SELECT e.numero, ne.valor_usado FROM nf_empenhos ne
            JOIN empenhos e ON ne.empenho_id=e.id WHERE ne.nota_fiscal_id=?''',
            (nf['id'],)).fetchall()
        emp_nums = ' | '.join(e['numero'] for e in emps)
        emp_vals = ' | '.join(f'R$ {formatar_valor_br(e["valor_usado"])}' for e in emps)
        mes = MESES.get(nf['mes_referencia'], str(nf['mes_referencia']))
        status = 'Cancelada' if nf['cancelada'] else ('Confirmada' if nf['data_geracao'] else 'Rascunho')
        writer.writerow([
            nf['id'], nf['contrato'], nf['empresa'],
            nf['numero_nf'], f"R$ {formatar_valor_br(nf['valor_nf'])}",
            nf['numero_medicao'], mes, nf['ano_referencia'],
            nf['periodo_inicio'], nf['periodo_fim'],
            nf['data_geracao'] or '', status, emp_nums, emp_vals
        ])
    db.close()
    output.seek(0)
    # Add BOM for Excel UTF-8 compatibility
    bom = '\ufeff'
    content = bom + output.getvalue()
    buf = io.BytesIO(content.encode('utf-8'))
    filename = f'historico_pagamentos{"_contrato_" + contrato_id if contrato_id else ""}.csv'
    return send_file(buf, mimetype='text/csv; charset=utf-8',
                     as_attachment=True, download_name=filename)