from flask import Blueprint, request, jsonify, render_template
from database import get_db

pessoas_bp = Blueprint('pessoas', __name__)


@pessoas_bp.route('/pessoas')
def listar():
    with get_db() as db:
        pessoas = db.execute('SELECT * FROM pessoas ORDER BY nome').fetchall()
    return render_template('pessoas.html', pessoas=[dict(p) for p in pessoas])


@pessoas_bp.route('/api/pessoas', methods=['GET'])
def api_listar():
    busca = request.args.get('q', '').strip()
    with get_db() as db:
        if busca:
            like = f'%{busca}%'
            rows = db.execute(
                'SELECT * FROM pessoas WHERE nome LIKE ? OR matricula LIKE ? ORDER BY nome',
                (like, like),
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM pessoas ORDER BY nome').fetchall()
    return jsonify([dict(p) for p in rows])


@pessoas_bp.route('/api/pessoas', methods=['POST'])
def criar():
    data = request.json
    if not data.get('nome') or not data.get('matricula'):
        return jsonify({'error': 'Nome e matrícula são obrigatórios'}), 400
    db = get_db()
    try:
        db.execute(
            'INSERT INTO pessoas (nome, matricula) VALUES (?, ?)',
            (data['nome'].strip(), data['matricula'].strip()),
        )
        db.commit()
        pessoa = db.execute(
            'SELECT * FROM pessoas WHERE matricula = ?',
            (data['matricula'].strip(),),
        ).fetchone()
        db.close()
        return jsonify(dict(pessoa)), 201
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': 'Erro ao salvar pessoa'}), 400


@pessoas_bp.route('/api/pessoas/<int:pid>', methods=['PUT'])
def atualizar(pid):
    data = request.json
    db = get_db()
    try:
        db.execute(
            'UPDATE pessoas SET nome=?, matricula=? WHERE id=?',
            (data['nome'].strip(), data['matricula'].strip(), pid),
        )
        db.commit()
        db.close()
        return jsonify({'ok': True})
    except Exception as e:
        db.rollback()
        db.close()
        return jsonify({'error': 'Erro ao atualizar pessoa'}), 400


@pessoas_bp.route('/api/pessoas/<int:pid>', methods=['DELETE'])
def deletar(pid):
    with get_db() as db:
        db.execute('DELETE FROM pessoas WHERE id=?', (pid,))
        db.commit()
    return jsonify({'ok': True})
