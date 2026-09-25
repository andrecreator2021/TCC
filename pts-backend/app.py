"""
Backend do App de PTS — Flask + SQLite.

Endpoints:
  GET    /api/pts                 lista todas as PTS
  POST   /api/pts                 cria uma nova PTS
  GET    /api/pts/<id>            busca uma PTS específica
  PUT    /api/pts/<id>/encerrar   encerra uma PTS (assinatura de encerramento)
  DELETE /api/pts/<id>            exclui uma PTS
  GET    /api/pts/<id>/pdf        gera e baixa o PDF da PTS
  POST   /api/pts/<id>/enviar     envia o PDF por e-mail ou WhatsApp a um contato cadastrado
"""
import json
import os
import sqlite3
import time
import uuid
from io import BytesIO

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, request, send_file, send_from_directory

from pdf_generator import gerar_pdf
from sender import enviar_email, enviar_whatsapp

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "pts.db")

app = Flask(__name__, static_folder="static", static_url_path="")

CATS_CODE = {"altura": "ALT", "confinado": "CONF", "eletricidade": "ELE", "quente": "QNT"}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pts (
            id TEXT PRIMARY KEY,
            numero TEXT,
            categoria TEXT,
            data_emissao TEXT,
            local TEXT,
            empresa TEXT,
            descricao TEXT,
            validade_inicio TEXT,
            validade_fim TEXT,
            equipe TEXT,
            checklist_risco TEXT,
            checklist_epi TEXT,
            assinaturas TEXT,
            contatos_envio TEXT,
            status TEXT,
            encerramento TEXT,
            created_at INTEGER,
            updated_at INTEGER
        )
    """)
    conn.commit()
    conn.close()


def row_to_record(row):
    return {
        "id": row["id"],
        "numero": row["numero"],
        "categoria": row["categoria"],
        "dataEmissao": row["data_emissao"],
        "local": row["local"],
        "empresa": row["empresa"],
        "descricao": row["descricao"],
        "validadeInicio": row["validade_inicio"],
        "validadeFim": row["validade_fim"],
        "equipe": row["equipe"],
        "checklistRisco": json.loads(row["checklist_risco"] or "{}"),
        "checklistEpi": json.loads(row["checklist_epi"] or "{}"),
        "assinaturas": json.loads(row["assinaturas"] or "{}"),
        "contatosEnvio": json.loads(row["contatos_envio"] or "[]"),
        "status": row["status"],
        "encerramento": json.loads(row["encerramento"]) if row["encerramento"] else None,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


@app.route("/api/pts", methods=["GET"])
def listar_pts():
    conn = get_db()
    rows = conn.execute("SELECT * FROM pts ORDER BY created_at DESC").fetchall()
    conn.close()
    return jsonify([row_to_record(r) for r in rows])


@app.route("/api/pts", methods=["POST"])
def criar_pts():
    data = request.get_json(force=True)
    if not data.get("categoria") or data["categoria"] not in CATS_CODE:
        return jsonify({"erro": "categoria inválida"}), 400

    conn = get_db()
    ano = time.strftime("%Y")
    total = conn.execute(
        "SELECT COUNT(*) FROM pts WHERE categoria=?", (data["categoria"],)
    ).fetchone()[0] + 1
    numero = f'PTS-{CATS_CODE[data["categoria"]]}-{ano}-{total:03d}'
    novo_id = uuid.uuid4().hex[:12]
    agora = int(time.time() * 1000)

    conn.execute(
        """INSERT INTO pts (id, numero, categoria, data_emissao, local, empresa, descricao,
           validade_inicio, validade_fim, equipe, checklist_risco, checklist_epi, assinaturas,
           contatos_envio, status, encerramento, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            novo_id, numero, data["categoria"], data.get("dataEmissao"), data.get("local"),
            data.get("empresa"), data.get("descricao"), data.get("validadeInicio"),
            data.get("validadeFim"), data.get("equipe"),
            json.dumps(data.get("checklistRisco", {})), json.dumps(data.get("checklistEpi", {})),
            json.dumps(data.get("assinaturas", {})), json.dumps(data.get("contatosEnvio", [])),
            "aberta", None, agora, agora,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM pts WHERE id=?", (novo_id,)).fetchone()
    conn.close()
    return jsonify(row_to_record(row)), 201


@app.route("/api/pts/<id>", methods=["GET"])
def obter_pts(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM pts WHERE id=?", (id,)).fetchone()
    conn.close()
    if not row:
        abort(404)
    return jsonify(row_to_record(row))


@app.route("/api/pts/<id>", methods=["DELETE"])
def excluir_pts(id):
    conn = get_db()
    conn.execute("DELETE FROM pts WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return "", 204


@app.route("/api/pts/<id>/encerrar", methods=["PUT"])
def encerrar_pts(id):
    data = request.get_json(force=True)
    conn = get_db()
    row = conn.execute("SELECT * FROM pts WHERE id=?", (id,)).fetchone()
    if not row:
        conn.close()
        abort(404)

    encerramento = {
        "nome": data.get("nome"),
        "dataHora": int(time.time() * 1000),
        "imagem": data.get("imagem"),
        "foto": data.get("foto"),
        "observacoes": data.get("observacoes", ""),
    }
    conn.execute(
        "UPDATE pts SET status='encerrada', encerramento=?, updated_at=? WHERE id=?",
        (json.dumps(encerramento), int(time.time() * 1000), id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM pts WHERE id=?", (id,)).fetchone()
    conn.close()
    return jsonify(row_to_record(row))


@app.route("/api/pts/<id>/pdf", methods=["GET"])
def baixar_pdf(id):
    conn = get_db()
    row = conn.execute("SELECT * FROM pts WHERE id=?", (id,)).fetchone()
    conn.close()
    if not row:
        abort(404)
    record = row_to_record(row)
    pdf_bytes = gerar_pdf(record)
    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f'{record["numero"]}.pdf',
    )


@app.route("/api/pts/<id>/enviar", methods=["POST"])
def enviar_pts(id):
    data = request.get_json(force=True)
    idx = data.get("contato_index")

    conn = get_db()
    row = conn.execute("SELECT * FROM pts WHERE id=?", (id,)).fetchone()
    conn.close()
    if not row:
        abort(404)

    record = row_to_record(row)
    contatos = record["contatosEnvio"]
    if idx is None or idx >= len(contatos) or not contatos[idx].get("valor"):
        return jsonify({"ok": False, "erro": "Contato inválido"}), 400

    contato = contatos[idx]
    pdf_bytes = gerar_pdf(record)

    assunto = f'PTS {record["numero"]} — {record["categoria"]}'
    corpo = (
        f'Segue a Permissão de Trabalho Seguro {record["numero"]} ({record["local"]}), '
        f'emitida em {record["dataEmissao"]}. Documento gerado automaticamente pelo sistema.'
    )

    try:
        if contato["tipo"] == "email":
            enviar_email(contato["valor"], assunto, corpo, pdf_bytes, f'{record["numero"]}.pdf')
        else:
            base_url = os.environ.get("PUBLIC_BASE_URL", request.url_root.rstrip("/"))
            media_url = f'{base_url}/api/pts/{id}/pdf'
            enviar_whatsapp(contato["valor"], corpo, media_url=media_url)
        return jsonify({"ok": True})
    except KeyError as e:
        # variável de ambiente obrigatória não configurada (.env incompleto)
        return jsonify({"ok": False, "erro": f"Configuração ausente: {e}"}), 500
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
