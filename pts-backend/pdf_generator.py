"""
Geração do PDF da PTS (Permissão de Trabalho Seguro).

Usa a biblioteca reportlab para desenhar o documento diretamente em memória
(sem salvar arquivo temporário em disco), retornando os bytes prontos do PDF.
"""
import base64
import io
from datetime import datetime
from textwrap import wrap

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

CATS = {
    "altura": {"label": "Trabalho em Altura"},
    "confinado": {"label": "Espaço Confinado"},
    "eletricidade": {"label": "Eletricidade"},
    "quente": {"label": "Trabalho a Quente"},
}

CHECKLISTS = {
    "altura": [
        "Pontos de ancoragem inspecionados e aprovados",
        "Cinto de segurança tipo paraquedista em bom estado",
        "Talabarte duplo com absorvedor de energia",
        "Trava-quedas ou linha de vida instalado",
        "Área abaixo isolada e sinalizada",
        "Condições climáticas favoráveis (sem vento forte ou chuva)",
        "Capacete com jugular utilizado",
        "Análise de Risco (APR) revisada com a equipe",
    ],
    "confinado": [
        "Teste atmosférico realizado (O2, LEL, gases tóxicos)",
        "Ventilação forçada instalada e testada",
        "Vigia de entrada posicionado e treinado",
        "Plano de resgate definido e equipamento disponível",
        "Iluminação adequada (antichama, se necessário)",
        "Entrada isolada e sinalizada",
        "Comunicação estabelecida entre vigia e executante",
    ],
    "eletricidade": [
        "Desenergização confirmada",
        "Bloqueio e etiquetagem (LOTO) aplicados",
        "Teste de ausência de tensão realizado",
        "Aterramento temporário instalado, se aplicável",
        "EPIs dielétricos verificados (luvas, calçado)",
        "Ferramentas isoladas em bom estado",
        "Zona de risco isolada e sinalizada",
    ],
    "quente": [
        "Área isolada e sinalizada",
        "Materiais inflamáveis removidos ou protegidos (raio mín. 10m)",
        "Extintor de incêndio disponível no local",
        "Vigia contra incêndio designado",
        "Verificação pós-trabalho por 30 min após conclusão",
        "Ventilação adequada para fumos e gases",
    ],
}

EPI_COMUM = [
    "Capacete de segurança",
    "Óculos de proteção",
    "Luvas apropriadas ao risco",
    "Calçado de segurança",
    "Protetor auricular (quando aplicável)",
    "Uniforme / vestimenta adequada",
]


def _decode_image(data_url):
    """Converte uma dataURL (ex: 'data:image/png;base64,....') em um ImageReader do reportlab."""
    if not data_url:
        return None
    try:
        _, b64data = data_url.split(",", 1)
        raw = base64.b64decode(b64data)
        return ImageReader(io.BytesIO(raw))
    except Exception:
        return None


def _fmt_datetime(ts_ms):
    if not ts_ms:
        return "—"
    dt = datetime.fromtimestamp(ts_ms / 1000)
    return dt.strftime("%d/%m/%Y às %H:%M")


def gerar_pdf(record: dict) -> bytes:
    """Recebe o dicionário da PTS (mesmo formato salvo no banco) e devolve os bytes do PDF."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    _, altura_pagina = A4

    def y_to_pt(y_mm):
        # reportlab mede a posição vertical de baixo para cima; nosso "y" é medido
        # de cima para baixo (mais parecido com CSS/HTML) — esta função faz a conversão
        return altura_pagina - y_mm * mm

    y = 18
    cat = CATS[record["categoria"]]

    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(A4[0] / 2, y_to_pt(y), "PERMISSÃO DE TRABALHO SEGURO")
    y += 6
    c.setFont("Helvetica", 10)
    c.drawCentredString(A4[0] / 2, y_to_pt(y), f'{record["numero"]}  ·  {cat["label"]}')
    y += 10
    c.setStrokeColorRGB(0.82, 0.82, 0.82)
    c.line(15 * mm, y_to_pt(y), 195 * mm, y_to_pt(y))
    y += 8

    def campo(label, valor):
        nonlocal y
        c.setFont("Helvetica-Bold", 9)
        c.drawString(15 * mm, y_to_pt(y), f"{label}:")
        c.setFont("Helvetica", 9)
        c.drawString(55 * mm, y_to_pt(y), str(valor or "—"))
        y += 6

    def _fmt_data_hora_local(valor):
        # recebe algo como "2026-08-29T08:00" (formato do <input type=datetime-local>)
        if not valor:
            return "—"
        try:
            dt = datetime.strptime(valor, "%Y-%m-%dT%H:%M")
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return valor

    campo("Local / Setor", record.get("local"))
    campo("Empresa executante", record.get("empresa"))
    try:
        data_fmt = datetime.strptime(record.get("dataEmissao", ""), "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        data_fmt = record.get("dataEmissao") or "—"
    campo("Data de emissão", data_fmt)
    campo("Validade", f'{_fmt_data_hora_local(record.get("validadeInicio"))} até '
                       f'{_fmt_data_hora_local(record.get("validadeFim"))}')
    campo("Status", "Ativa" if record.get("status") == "aberta" else "Encerrada")
    y += 2

    c.setFont("Helvetica-Bold", 9)
    c.drawString(15 * mm, y_to_pt(y), "Descrição do trabalho:")
    y += 5
    c.setFont("Helvetica", 9)
    for linha in wrap(record.get("descricao") or "—", 95) or ["—"]:
        c.drawString(15 * mm, y_to_pt(y), linha)
        y += 4.5
    y += 4

    if y > 260:
        c.showPage()
        y = 18

    c.setFont("Helvetica-Bold", 9)
    c.drawString(15 * mm, y_to_pt(y), "Checklist de segurança (itens confirmados)")
    y += 6
    c.setFont("Helvetica", 9)

    checklist_epi = record.get("checklistEpi") or {}
    checklist_risco = record.get("checklistRisco") or {}

    for i, item in enumerate(EPI_COMUM):
        if checklist_epi.get(str(i)) or checklist_epi.get(i):
            if y > 275:
                c.showPage()
                y = 18
            c.drawString(17 * mm, y_to_pt(y), f"\u2713 {item}")
            y += 5
    for i, item in enumerate(CHECKLISTS[record["categoria"]]):
        if checklist_risco.get(str(i)) or checklist_risco.get(i):
            if y > 275:
                c.showPage()
                y = 18
            c.drawString(17 * mm, y_to_pt(y), f"\u2713 {item}")
            y += 5
    y += 4

    if y > 230:
        c.showPage()
        y = 18
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, y_to_pt(y), "Assinaturas e validação facial")
    y += 7

    papeis = [
        ("emitente", "Emitente / Técnico de Segurança"),
        ("executante", "Executante Responsável"),
        ("supervisor", "Responsável pela Área"),
    ]
    assinaturas = record.get("assinaturas") or {}
    for role, label in papeis:
        sig = assinaturas.get(role)
        if not sig:
            continue
        if y > 235:
            c.showPage()
            y = 18
        c.setFont("Helvetica-Bold", 9)
        c.drawString(15 * mm, y_to_pt(y), label)
        y += 4
        c.setFont("Helvetica", 9)
        c.drawString(15 * mm, y_to_pt(y), f'{sig.get("nome")}  \u2014  {_fmt_datetime(sig.get("dataHora"))}')
        y += 3
        foto_img = _decode_image(sig.get("foto"))
        if foto_img:
            c.drawImage(foto_img, 15 * mm, y_to_pt(y + 20), width=20 * mm, height=20 * mm,
                        preserveAspectRatio=True, mask="auto")
        assin_img = _decode_image(sig.get("imagem"))
        if assin_img:
            c.drawImage(assin_img, 40 * mm, y_to_pt(y + 18), width=45 * mm, height=15 * mm,
                        preserveAspectRatio=True, mask="auto")
        y += 25

    encerramento = record.get("encerramento")
    if record.get("status") == "encerrada" and encerramento:
        if y > 230:
            c.showPage()
            y = 18
        c.setFont("Helvetica-Bold", 10)
        c.drawString(15 * mm, y_to_pt(y), "Encerramento")
        y += 5
        c.setFont("Helvetica", 9)
        c.drawString(15 * mm, y_to_pt(y),
                     f'{encerramento.get("nome")}  \u2014  {_fmt_datetime(encerramento.get("dataHora"))}')
        y += 3
        foto_img = _decode_image(encerramento.get("foto"))
        if foto_img:
            c.drawImage(foto_img, 15 * mm, y_to_pt(y + 20), width=20 * mm, height=20 * mm,
                        preserveAspectRatio=True, mask="auto")
        assin_img = _decode_image(encerramento.get("imagem"))
        if assin_img:
            c.drawImage(assin_img, 40 * mm, y_to_pt(y + 18), width=45 * mm, height=15 * mm,
                        preserveAspectRatio=True, mask="auto")
        y += 25
        obs = encerramento.get("observacoes")
        if obs:
            for linha in wrap(f"Observações: {obs}", 95):
                c.drawString(15 * mm, y_to_pt(y), linha)
                y += 4.5

    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.6, 0.6, 0.6)
    rodape = (
        "Documento gerado digitalmente pelo aplicativo de PTS em "
        f"{_fmt_datetime(int(datetime.now().timestamp() * 1000))}. "
        "Assinaturas capturadas em tela, com validação facial associada, sem certificação ICP-Brasil."
    )
    c.drawString(15 * mm, y_to_pt(290), rodape)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
