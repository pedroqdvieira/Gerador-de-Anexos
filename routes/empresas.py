from flask import Blueprint, request, jsonify, render_template
from database import get_db
from utils import validar_cnpj

empresas_bp = Blueprint('empresas', __name__)

@empresas_bp.route('/empresas')
def listar():
    db       = get_db()
    empresas = db.execute('SELECT * FROM empresas ORDER BY razao_social').fetchall()
    db.close()
    return render_template('empresas.html', empresas=[dict(e) for e in empresas])

@empresas_bp.route('/api/empresas', methods=['GET'])
def api_listar():
    db    = get_db()
    busca = request.args.get('q', '').strip()
    if busca:
        like = f'%{busca}%'
        rows = db.execute(
            'SELECT * FROM empresas WHERE razao_social LIKE ? OR cnpj LIKE ? ORDER BY razao_social',
            (like, like)).fetchall()
    else:
        rows = db.execute('SELECT * FROM empresas ORDER BY razao_social').fetchall()
    db.close()
    return jsonify([dict(e) for e in rows])

@empresas_bp.route('/api/empresas', methods=['POST'])
def criar():
    data = request.json
    if not data.get('razao_social') or not data.get('cnpj'):
        return jsonify({'error': 'Razão Social e CNPJ são obrigatórios'}), 400
    if not validar_cnpj(data['cnpj']):
        return jsonify({'error': 'CNPJ inválido. Verifique os dígitos informados.'}), 400
    db = get_db()
    try:
        db.execute('''INSERT INTO empresas
            (razao_social, cnpj, endereco, banco, agencia, conta_bancaria, tipo_operacao)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (data['razao_social'].strip(), data['cnpj'].strip(),
             data.get('endereco', ''), data.get('banco', ''),
             data.get('agencia', ''), data.get('conta_bancaria', ''),
             data.get('tipo_operacao', '')))
        db.commit()
        empresa = db.execute('SELECT * FROM empresas WHERE cnpj=?',
                             (data['cnpj'].strip(),)).fetchone()
        db.close()
        return jsonify(dict(empresa)), 201
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

@empresas_bp.route('/api/empresas/<int:eid>', methods=['PUT'])
def atualizar(eid):
    data = request.json
    if not validar_cnpj(data.get('cnpj', '')):
        return jsonify({'error': 'CNPJ inválido. Verifique os dígitos informados.'}), 400
    db = get_db()
    try:
        db.execute('''UPDATE empresas SET razao_social=?, cnpj=?, endereco=?,
            banco=?, agencia=?, conta_bancaria=?, tipo_operacao=? WHERE id=?''',
            (data['razao_social'].strip(), data['cnpj'].strip(),
             data.get('endereco', ''), data.get('banco', ''),
             data.get('agencia', ''), data.get('conta_bancaria', ''),
             data.get('tipo_operacao', ''), eid))
        db.commit()
        db.close()
        return jsonify({'ok': True})
    except Exception as e:
        db.close()
        return jsonify({'error': str(e)}), 400

@empresas_bp.route('/api/empresas/<int:eid>', methods=['DELETE'])
def deletar(eid):
    db = get_db()
    db.execute('DELETE FROM empresas WHERE id=?', (eid,))
    db.commit()
    db.close()
    return jsonify({'ok': True})

@empresas_bp.route('/api/cnpj/validar', methods=['POST'])
def validar():
    cnpj = request.json.get('cnpj', '')
    return jsonify({'valido': validar_cnpj(cnpj)})