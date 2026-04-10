import os
import io
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, Image, PageBreak, HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas as canvas_module

from utils import valor_por_extenso, mes_nome, formatar_cnpj, formatar_valor_br, to_decimal

def fmt_data(valor):
    """Converte yyyy-mm-dd para dd/mm/yyyy. Retorna o valor original se já estiver no formato correto."""
    if valor and len(valor) == 10 and valor[4] == '-':
        try:
            partes = valor.split('-')
            return f'{partes[2]}/{partes[1]}/{partes[0]}'
        except Exception:
            pass
    return valor or ''

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMBRADO_PATH = os.path.join(BASE_DIR, 'static', 'img', 'papelTimbrado.png')

PAGE_W, PAGE_H = A4
MARGIN_LEFT = 2.5 * cm
MARGIN_RIGHT = 2.0 * cm
MARGIN_TOP = 5.5 * cm   # space for timbrado header
MARGIN_BOTTOM = 2.0 * cm
CONTENT_W = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT

# Colors
BLUE = colors.HexColor('#003087')
RED = colors.HexColor('#C8102E')
DARK_GRAY = colors.HexColor('#333333')
LIGHT_GRAY = colors.HexColor('#F5F5F5')
TABLE_HEADER_BG = colors.HexColor('#1F3864')
BLACK = colors.black
WHITE = colors.white

def get_styles():
    styles = getSampleStyleSheet()
    base = dict(fontName='Helvetica', fontSize=9, textColor=DARK_GRAY, leading=12)
    styles.add(ParagraphStyle('AnexoTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=11, alignment=TA_CENTER, spaceAfter=4, textColor=BLACK))
    styles.add(ParagraphStyle('AnexoSubTitle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=10, alignment=TA_CENTER, spaceAfter=6, textColor=BLACK))
    styles.add(ParagraphStyle('Normal9', parent=styles['Normal'], **base))
    styles.add(ParagraphStyle('Normal9J', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, textColor=DARK_GRAY, leading=13, alignment=TA_JUSTIFY))
    styles.add(ParagraphStyle('Normal9C', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, textColor=DARK_GRAY, leading=12, alignment=TA_CENTER))
    styles.add(ParagraphStyle('Bold9', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9, textColor=DARK_GRAY, leading=12))
    styles.add(ParagraphStyle('Bold9C', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9, textColor=DARK_GRAY, leading=12, alignment=TA_CENTER))
    styles.add(ParagraphStyle('Small8', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, textColor=DARK_GRAY, leading=10))
    styles.add(ParagraphStyle('Small8C', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8, textColor=DARK_GRAY, leading=10, alignment=TA_CENTER))
    styles.add(ParagraphStyle('FootnoteStyle', parent=styles['Normal'],
        fontName='Helvetica', fontSize=7, textColor=DARK_GRAY, leading=9))
    styles.add(ParagraphStyle('SignatureStyle', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9, alignment=TA_CENTER, leading=12))
    styles.add(ParagraphStyle('SignatureSubStyle', parent=styles['Normal'],
        fontName='Helvetica', fontSize=9, alignment=TA_CENTER, leading=12))
    return styles


class TimbradoBackground(Flowable):
    """Draws timbrado background on each page."""
    def __init__(self, path):
        Flowable.__init__(self)
        self.path = path

    def draw(self):
        pass  # handled in onPage


def timbrado_canvas(canvas, doc):
    """Called for each page to draw the timbrado background."""
    canvas.saveState()
    if os.path.exists(TIMBRADO_PATH):
        canvas.drawImage(TIMBRADO_PATH, 0, 0, width=PAGE_W, height=PAGE_H,
                         preserveAspectRatio=False, mask='auto')
    canvas.restoreState()


def build_doc(story, buffer, on_page=None):
    """Build PDF document with timbrado."""
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN_LEFT,
        rightMargin=MARGIN_RIGHT,
        topMargin=MARGIN_TOP,
        bottomMargin=MARGIN_BOTTOM,
    )

    def on_page_wrapper(canvas, doc):
        timbrado_canvas(canvas, doc)
        if on_page:
            on_page(canvas, doc)

    doc.build(story, onFirstPage=on_page_wrapper, onLaterPages=on_page_wrapper)


# ─── PORTARIA BOX (top right corner) ────────────────────────────────────────
def portaria_box_table(data):
    """Small box top-right with portaria info."""
    styles = get_styles()
    text = 'Portaria publicada no\nDiário Oficial do Município\n– DIO/VV.'
    cell = Paragraph(text, styles['Small8'])
    t = Table([[cell]], colWidths=[5.5 * cm])
    t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def portaria_row(extra_text=''):
    """Returns a table row that positions portaria box to the right."""
    styles = get_styles()
    txt = 'Portaria publicada no\nDiário Oficial do Município\n– DIO/VV.'
    if extra_text:
        txt += f'\n{extra_text}'
    cell = Paragraph(txt, styles['Small8'])
    box = Table([[cell]], colWidths=[5.0 * cm])
    box.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    spacer_col = CONTENT_W - 5.0 * cm
    t = Table([[Paragraph('', styles['Normal9']), box]],
              colWidths=[spacer_col, 5.0 * cm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


# ─── ANEXO III ───────────────────────────────────────────────────────────────
def gerar_anexo_iii(dados: dict) -> bytes:
    styles = get_styles()
    buffer = io.BytesIO()
    story = []

    story.append(portaria_row())
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph('ANEXO III', styles['AnexoTitle']))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph('ACOMPANHAMENTO DA EXECUÇÃO DOS SERVIÇOS – FISCAL DO CONTRATO',
                            styles['AnexoSubTitle']))
    story.append(Spacer(1, 0.3 * cm))

    contrato = dados['contrato']
    nf = dados['nf']
    fiscal = dados['fiscal']

    vigencia = f"{fmt_data(contrato['vigencia_inicio'])} a {fmt_data(contrato['vigencia_fim'])}"
    periodo = f"{fmt_data(nf['periodo_inicio'])} a {fmt_data(nf['periodo_fim'])}"

    def lbl(text):
        return Paragraph(f'<b>{text}</b>', styles['Normal9'])

    def val(text):
        return Paragraph(text or '', styles['Normal9'])

    # Header table
    header_data = [
        [lbl('Contrato nº:'), val(contrato['numero']),
         lbl('Vigência do contrato:'), val(vigencia)],
        [lbl('Contratado:'), val(contrato['empresa']),
         lbl('Local de execução dos serviços:'), val('Secretaria Municipal de\nEducação - SEMED')],
        [lbl('Objeto do contrato:'), val(contrato['objeto']), '', ''],
        [lbl('Preposto da empresa contratada:'), val(contrato.get('preposto', '')), '', ''],
        [lbl('Período do Acompanhamento:'), val(periodo), '', ''],
    ]

    col_w = [3.5 * cm, CONTENT_W/2 - 3.5*cm, 3.5*cm, CONTENT_W/2 - 3.5*cm]

    ht = Table(header_data, colWidths=col_w)
    ht.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('SPAN', (1, 2), (3, 2)),
        ('SPAN', (1, 3), (3, 3)),
        ('SPAN', (1, 4), (3, 4)),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(ht)
    story.append(Spacer(1, 0.1 * cm))

    # Ocorrências section
    houve = nf.get('houve_ocorrencias', False)

    # Title row
    occ_title = Table([[Paragraph('<b>OCORRÊNCIAS</b>', styles['Bold9C'])]],
                       colWidths=[CONTENT_W])
    occ_title.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(occ_title)

    def occ_row(header_center, date_val, content_val):
        header_p = Paragraph(header_center, styles['Normal9C'])
        date_p = Paragraph(date_val or '-', styles['Normal9C'])
        content_p = Paragraph(content_val or '', styles['Normal9'])
        inner = Table([[date_p, content_p]],
                       colWidths=[2.0 * cm, CONTENT_W - 2.0 * cm])
        inner.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 30),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        header_row = Table([[header_p]], colWidths=[CONTENT_W])
        header_row.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        return [header_row, inner]

    if not houve:
        sem_occ_text = ('Execução Contratual\n'
            '(Deverá ser relatada a forma que vem sendo prestado o serviço, conforme pactuado no\n'
            'Contrato, e cada problema detectado)')
        rows = occ_row(sem_occ_text, None, 'Não houve ocorrências no período.')
        for r in rows:
            story.append(r)
        rows2 = occ_row(
            'Providências / Documentos Expedidos\n'
            '(Deverão ser relatadas as providências adotadas para solução de cada problema detectado\n'
            'na execução, bem como os documentos expedidos à empresa contratada e anexadas cópias)',
            None, '')
        for r in rows2:
            story.append(r)
        rows3 = occ_row(
            'Resultados\n'
            '(Informar se os problemas foram sanados ou não e quais as consequências e encaminhamentos)',
            None, '')
        for r in rows3:
            story.append(r)
    else:
        rows = occ_row(
            'Execução Contratual\n'
            '(Deverá ser relatada a forma que vem sendo prestado o serviço, conforme pactuado no\n'
            'Contrato, e cada problema detectado)',
            None, nf.get('ocorrencia_execucao', ''))
        for r in rows:
            story.append(r)
        rows2 = occ_row(
            'Providências / Documentos Expedidos\n'
            '(Deverão ser relatadas as providências adotadas para solução de cada problema detectado\n'
            'na execução, bem como os documentos expedidos à empresa contratada e anexadas cópias)',
            None, nf.get('ocorrencia_providencias', ''))
        for r in rows2:
            story.append(r)
        rows3 = occ_row(
            'Resultados\n'
            '(Informar se os problemas foram sanados ou não e quais as consequências e encaminhamentos)',
            None, nf.get('ocorrencia_resultados', ''))
        for r in rows3:
            story.append(r)

    story.append(Spacer(1, 0.4 * cm))

    # Signature block
    hoje = date.today().strftime('%d/%m/%Y')
    sig_data = [
        [Paragraph(f'Nome e Cargo do Fiscal do Contrato: <b>{fiscal["nome"]}</b>', styles['Normal9']),
         Paragraph(f'Matrícula: <b>{fiscal["matricula"]}</b>', styles['Normal9'])],
        [Paragraph('Assinatura do Fiscal do Contrato:', styles['Normal9']),
         Paragraph(f'Data:\nVila Velha - ES, {hoje}', styles['Normal9'])],
    ]
    sig_t = Table(sig_data, colWidths=[CONTENT_W * 0.65, CONTENT_W * 0.35])
    sig_t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(sig_t)

    build_doc(story, buffer)
    return buffer.getvalue()


# ─── ANEXO VI ────────────────────────────────────────────────────────────────
CHECKLIST_ITEMS = [
    ('1. MEDIÇÃO', None),
    ('1.1', 'Medição dos serviços prestados?'),
    ('1.2', 'Avaliação do Fiscal sobre os serviços prestados?'),
    ('2. NOTA FISCAL', None),
    ('2.1', 'Solicitação de pagamento da empresa?'),
    ('2.2', 'Nota Fiscal correspondente ao mês de medição?'),
    ('2.3', 'A Nota Fiscal é um documento válido?'),
    ('2.4', 'Constam retenções contratuais na Nota Fiscal?'),
    ('2.5', 'Consta retenção de INSS na Nota Fiscal?'),
    ('2.6', 'A Razão Social, Endereço e o CNPJ da Unidade Gestora estão corretos?'),
    ('2.7', 'A Razão Social, o Endereço e o CNPJ da empresa contratada estão corretos?'),
    ('2.8', 'Possui o ateste do Fiscal do Contrato no documento fiscal?'),
    ('3. SALÁRIO/VALE TRANSPORTE/ALIMENTAÇÃO/FÉRIAS', None),
    ('3.1', 'Consta Folha de Pagamento da empresa em dia com o mês de referência da documentação?'),
    ('3.2', 'Consta de 13º Salário, quando devido?'),
    ('3.3', 'Contracheques e Comprovantes de depósito bancário do mês de referência?'),
    ('3.4', 'Consta documento com a relação de funcionários?'),
    ('3.5', 'Folha de Ponto?'),
    ('3.6', 'Seguro de vida obrigatório?'),
    ('3.7', 'Relatório de Movimentação Funcional dos Empregados Vinculados ao Contrato?'),
    ('3.8', 'Comprovante de pagamento de Vale Transporte com relação de funcionários e renúncia de vale-transporte?'),
    ('3.9', 'Comprovante de pagamento de Vale Refeição e relação de funcionários?'),
    ('3.10', 'Avisos e recibos de pagamento de férias?'),
    ('3.11', 'Aviso prévio ou pedido de demissão dos empregados da empresa contratada vinculados ao contrato?'),
    ('3.12', 'Documento com as eventuais rescisões ocorridas?'),
    ('3.13', 'Guia de recolhimento dos Rescisórios do FGTS – GRRF, dos empregados da empresa contratada, vinculados ao contrato, com a autenticação mecânica ou acompanhada do comprovante de recolhimento bancário ou o comprovante emitido quando efetivado pela Internet?'),
    ('3.14', 'Reembolso de Termo de Rescisão de Contrato de Trabalho – TRCT?'),
    ('4. RECOLHIMENTOS', None),
    ('4.1', 'Comprovante de declaração à previdência?'),
    ('4.2', 'Apresenta guia (GPS) e comprovante de pagamento de INSS do mês de referência da documentação – Recolhimento Empresa?'),
    ('4.3', 'Apresenta guia (GRF) e comprovante de pagamento de FGTS do mês de referência da documentação?'),
    ('4.4', 'Apresenta o relatório GFIP/SEFIP?'),
    ('4.5', 'O valor constante na GFIP/SEFIP coincide com as guias de pagamento? Se não, justificar.'),
    ('4.6', 'Relação dos trabalhadores constantes no arquivo SEFIP – RE?'),
    ('4.7', 'Relação Tomadores/Obras – RET?'),
    ('4.8', 'Apresenta Protocolo Conectividade Social do mês de referência da documentação?'),
    ('4.9', 'Recolhimento do ISS?'),
    ('5. CERTIDÕES NEGATIVAS', None),
    ('5.1', 'Apresenta Certidão Negativa da União?'),
    ('5.2', 'Apresenta Certidão Negativa da Fazenda Pública Estadual da sede da empresa?'),
    ('5.3', 'Apresenta Certidão Negativa da Fazenda Pública Municipal da sede da empresa?'),
    ('5.4', 'Apresenta Certidão Negativa da Fazenda Pública Municipal do Município de Vila Velha?'),
    ('5.5', 'Apresenta Certidão de Regularidade de FGTS (Matriz e Filial)?'),
    ('5.6', 'Apresenta Certidão Negativa de Débitos Trabalhistas (CNDT)?'),
    ('6. OUTROS DOCUMENTOS', None),
    ('6.1', 'Consta a Declaração de Contabilidade Regular?'),
    ('6.2', 'Consta o Relatório de Comprovação de Adimplência de Encargos (RECAE)?'),
    ('6.3', 'Consta do Processo de Pagamento cópia do Contrato?'),
    ('6.4', 'Consta do Processo de Pagamento cópia do Aditivo contratual vigente?'),
    ('6.5', 'Consta do Processo de Pagamento cópia da publicação da Portaria de nomeação do Gestor e Fiscal e seus suplentes do Contrato?'),
    ('6.6', 'Consta do Processo de Pagamento cópia da Nota de Empenho?'),
    ('6.7', 'Saldo de Empenho?'),
    ('6.8', 'Garantia contratual vigente?'),
    ('6.9', 'Empresa optante pelo SIMPLES (Consulta Optantes – Simples Nacional)?'),
]

def _check_mark(value):
    """Returns X or empty based on value."""
    return 'X' if value else ''


def gerar_anexo_vi(dados: dict) -> bytes:
    styles = get_styles()
    buffer = io.BytesIO()
    story = []

    story.append(portaria_row('Em 02/09/2022.'))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph('ANEXO VI', styles['AnexoTitle']))
    story.append(Paragraph(
        'CHECKLIST DAS OBRIGAÇÕES TRABALHISTAS E CONTRATUAIS QUE DEVEM SER\nVERIFICADAS PELO GESTOR DO CONTRATO',
        styles['AnexoSubTitle']))
    story.append(Spacer(1, 0.2 * cm))

    contrato = dados['contrato']
    nf = dados['nf']
    checklist = dados.get('checklist', {})
    gestor = dados['gestor']

    # Header info table
    header_data = [
        [Paragraph(f'<b>Contrato nº:</b> {contrato["numero"]}', styles['Normal9']),
         Paragraph('<b>Unidade:</b>\nSEMED', styles['Normal9'])],
        [Paragraph(f'<b>Empresa Contratada:</b> {contrato["empresa"]}', styles['Normal9']), ''],
        [Paragraph(f'<b>Serviços:</b> {contrato["objeto"]}', styles['Normal9']), ''],
        [Paragraph(f'<b>Nº de Funcionários:</b> {nf.get("num_funcionarios", "N/A")}', styles['Normal9']),
         Paragraph(f'<b>Valor Bruto Devido:</b> R$ {formatar_valor_br(nf["valor_nf"])}', styles['Normal9'])],
        [Paragraph(f'<b>Nota Fiscal nº:</b> {nf["numero_nf"]}', styles['Normal9']),
         Paragraph(f'<b>Valor Bruto Faturado:</b> R$ {formatar_valor_br(nf["valor_nf"])}', styles['Normal9'])],
    ]
    hcols = [CONTENT_W * 0.65, CONTENT_W * 0.35]
    ht = Table(header_data, colWidths=hcols)
    ht.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
        ('SPAN', (0, 1), (1, 1)),
        ('SPAN', (0, 2), (1, 2)),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(ht)
    story.append(Spacer(1, 0.2 * cm))

    # Checklist table
    col_n = 1.2 * cm
    col_item = CONTENT_W - col_n - 1.8 * cm - 1.8 * cm - 1.8 * cm
    col_sim = 1.8 * cm
    col_nao = 1.8 * cm
    col_na = 1.8 * cm
    col_widths = [col_n, col_item, col_sim, col_nao, col_na]

    table_data = [
        [Paragraph('<b>Nº</b>', styles['Bold9C']),
         Paragraph('<b>Itens</b>', styles['Bold9C']),
         Paragraph('<b>Sim</b>', styles['Bold9C']),
         Paragraph('<b>Não</b>', styles['Bold9C']),
         Paragraph('<b>N/A</b>', styles['Bold9C'])],
    ]
    span_commands = []
    row_idx = 1

    for (num, desc) in CHECKLIST_ITEMS:
        if desc is None:
            # Section header
            table_data.append([
                Paragraph(f'<b>{num}</b>', styles['Bold9']),
                '', '', '', ''
            ])
            span_commands.append(('SPAN', (0, row_idx), (4, row_idx)))
            span_commands.append(('BACKGROUND', (0, row_idx), (4, row_idx), LIGHT_GRAY))
        else:
            key = num
            sim = _check_mark(checklist.get(key) == 'sim')
            nao = _check_mark(checklist.get(key) == 'nao')
            na = _check_mark(checklist.get(key) == 'na')
            table_data.append([
                Paragraph(num, styles['Normal9C']),
                Paragraph(desc, styles['Normal9']),
                Paragraph(sim, styles['Bold9C']),
                Paragraph(nao, styles['Bold9C']),
                Paragraph(na, styles['Bold9C']),
            ])
        row_idx += 1

    ct = Table(table_data, colWidths=col_widths)
    ts = [
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, BLACK),
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_GRAY),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (2, 0), (4, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ] + span_commands
    ct.setStyle(TableStyle(ts))
    story.append(ct)

    story.append(Spacer(1, 0.3 * cm))
    obs = Paragraph(
        '<i>*OBS.: Entende-se por "mês de referência" o mês anterior à medição atual.</i>',
        styles['Small8'])
    story.append(obs)
    story.append(Spacer(1, 0.3 * cm))

    # Declaration
    decl_text = (
        '<b>Declaração:</b><br/>'
        'Declaro, para os devidos fins, que as informações constantes neste check-list foram '
        'confrontadas entre si, tais como: relação de empregados constantes na declaração '
        'enviada à Previdência Social, folha de pagamento, recolhimento dos encargos '
        'trabalhistas, benefícios computados por meio do contrato.'
    )
    story.append(Paragraph(decl_text, styles['Normal9J']))
    story.append(Spacer(1, 0.4 * cm))

    hoje = date.today().strftime('%d/%m/%Y')
    sig_data = [
        [Paragraph(f'Nome e Cargo do Gestor do Contrato: <b>{gestor["nome"]}</b>', styles['Normal9']),
         Paragraph(f'Matrícula: <b>{gestor["matricula"]}</b>', styles['Normal9'])],
        [Paragraph('Assinatura do Gestor do Contrato', styles['Normal9']),
         Paragraph(f'Vila Velha - ES, {hoje}', styles['Normal9'])],
    ]
    sig_t = Table(sig_data, colWidths=[CONTENT_W * 0.65, CONTENT_W * 0.35])
    sig_t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(sig_t)

    build_doc(story, buffer)
    return buffer.getvalue()


# ─── ANEXO IX ────────────────────────────────────────────────────────────────
def gerar_anexo_ix(dados: dict) -> bytes:
    styles = get_styles()
    buffer = io.BytesIO()
    story = []

    story.append(portaria_row())
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph('ANEXO IX', styles['AnexoTitle']))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph('FORMULÁRIO DE CONTROLE DE SALDO DE EMPENHO', styles['AnexoSubTitle']))
    story.append(Spacer(1, 0.3 * cm))

    contrato = dados['contrato']
    nf = dados['nf']
    gestor = dados['gestor']
    empenhos_usados = dados['empenhos_usados']  # list of dicts
    hoje = date.today().strftime('%d/%m/%Y')

    mes_ref = f'{mes_nome(nf["mes_referencia"])}/{nf["ano_referencia"]}'

    # Top info table
    top_data = [
        [Paragraph('CONTROLE DE SALDO DE EMPENHO', styles['Bold9C']),
         '', ''],
        [Paragraph('Secretaria Municipal de Educação - SEMED', styles['Normal9']),
         Paragraph(f'MEDIÇÃO Nº {nf["numero_medicao"]}', styles['Normal9']),
         Paragraph(f'PERÍODO DA MEDIÇÃO\n{fmt_data(nf["periodo_inicio"])} a {fmt_data(nf["periodo_fim"])}', styles['Normal9'])],
    ]
    top_t = Table(top_data, colWidths=[CONTENT_W * 0.45, CONTENT_W * 0.25, CONTENT_W * 0.30])
    top_t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
        ('SPAN', (0, 0), (2, 0)),
        ('BACKGROUND', (0, 0), (2, 0), LIGHT_GRAY),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (0, 0), (2, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(top_t)

    # Process / Contract info
    info_data = [
        [Paragraph(f'<b>Processo:</b> {contrato.get("processo", "")}', styles['Normal9'])],
        [Paragraph(f'<b>Contrato:</b> {contrato["numero"]}', styles['Normal9'])],
        [Paragraph(f'<b>Empresa:</b> {contrato["empresa"]}', styles['Normal9'])],
        [Paragraph(f'<b>Posição da data:</b> {hoje}', styles['Normal9'])],
    ]
    info_t = Table(info_data, colWidths=[CONTENT_W])
    info_t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_t)

    # Main empenho table - one block per empenho
    c1 = 2.8 * cm  # Empenho Nº
    c2 = 2.5 * cm  # Valor Empenho
    c3 = 2.0 * cm  # Medição nº
    c4 = 2.8 * cm  # Pagamento Competência
    c5 = 2.5 * cm  # Nota Fiscal Nº
    c6 = 2.5 * cm  # Valor NF
    c7 = 2.4 * cm  # Saldo Empenho
    total_c = c1 + c2 + c3 + c4 + c5 + c6 + c7

    # Header row
    main_header = [
        [Paragraph('<b>Empenho Nº:</b>', styles['Small8C']),
         Paragraph('<b>Valor do\nEmpenho</b>', styles['Small8C']),
         Paragraph('<b>Medição nº</b>', styles['Small8C']),
         Paragraph('<b>Pagamento\nCompetência:\nMês / Ano</b>', styles['Small8C']),
         Paragraph('<b>Nota Fiscal Nº</b>', styles['Small8C']),
         Paragraph('<b>Valor da Nota\nFiscal R$</b>', styles['Small8C']),
         Paragraph('<b>Saldo do\nEmpenho</b>', styles['Small8C'])],
    ]

    table_rows = list(main_header)
    span_cmds = []
    row_i = 1

    # Linha "Saldo inicial" — única, antes de todos os empenhos
    table_rows.append([
        Paragraph('', styles['Small8C']),
        Paragraph('', styles['Small8C']),
        Paragraph('', styles['Small8C']),
        Paragraph('Saldo inicial', styles['Small8C']),
        Paragraph('', styles['Small8C']),
        Paragraph('', styles['Small8C']),
        Paragraph('', styles['Small8C']),
    ])
    span_cmds.append(('SPAN', (3, row_i), (5, row_i)))
    row_i += 1

    # Uma linha por empenho, todos compartilhando medição/mês/NF/valor NF
    # Apenas o primeiro empenho repete medição, mês/ano, NF e valor — os demais ficam em branco
    # pois as células são mescladas verticalmente no original
    num_empenhos = len(empenhos_usados)
    for idx, emp in enumerate(empenhos_usados):
        saldo_antes = emp['saldo_anterior']  # Saldo disponível no momento da medição
        valor_usado = emp['valor_usado']  # Valor usado neste pagamento
        # Usar Decimal para operações aritméticas evita erros de ponto flutuante
        saldo_depois = float(to_decimal(saldo_antes) - to_decimal(valor_usado))

        # Medição, mês/ano, NF e valor da NF só aparecem na primeira linha do grupo
        if idx == 0:
            col_medicao = Paragraph(nf['numero_medicao'], styles['Small8C'])
            col_mes = Paragraph(mes_ref, styles['Small8C'])
            col_nf = Paragraph(nf['numero_nf'], styles['Small8C'])
            col_val_nf = Paragraph(f'R$ {formatar_valor_br(nf["valor_nf"])}', styles['Small8C'])
        else:
            col_medicao = Paragraph('', styles['Small8C'])
            col_mes = Paragraph('', styles['Small8C'])
            col_nf = Paragraph('', styles['Small8C'])
            col_val_nf = Paragraph('', styles['Small8C'])

        table_rows.append([
            Paragraph(emp['numero'], styles['Small8C']),
            Paragraph(f'R$ {formatar_valor_br(saldo_antes)}', styles['Small8C']),
            col_medicao,
            col_mes,
            col_nf,
            col_val_nf,
            Paragraph(f'R$ {formatar_valor_br(saldo_depois)}', styles['Small8C']),
        ])

        # Mescla verticalmente medição/mês/NF/valorNF se múltiplos empenhos
        if idx == 0 and num_empenhos > 1:
            span_cmds.append(('SPAN', (2, row_i), (2, row_i + num_empenhos - 1)))
            span_cmds.append(('SPAN', (3, row_i), (3, row_i + num_empenhos - 1)))
            span_cmds.append(('SPAN', (4, row_i), (4, row_i + num_empenhos - 1)))
            span_cmds.append(('SPAN', (5, row_i), (5, row_i + num_empenhos - 1)))

        row_i += 1

    # Linhas vazias para espaçamento visual
    for _ in range(10):
        table_rows.append(['', '', '', '', '', '', ''])
        row_i += 1

    # Totalização — uma linha por empenho
    tot_start = row_i
    for idx, emp in enumerate(empenhos_usados):
        # Usar Decimal para operações aritméticas evita erros de ponto flutuante
        saldo_depois = float(to_decimal(emp['saldo_anterior']) - to_decimal(emp['valor_usado']))
        if idx == 0:
            col_tot_label = Paragraph('<b>Totalização e\nSaldo atual</b>', styles['Small8C'])
        else:
            col_tot_label = Paragraph('', styles['Small8C'])

        table_rows.append([
            Paragraph('', styles['Small8C']),
            Paragraph('', styles['Small8C']),
            Paragraph('', styles['Small8C']),
            col_tot_label,
            Paragraph('', styles['Small8C']),
            Paragraph(f'<b>{emp["numero"]}</b>', styles['Small8C']),
            Paragraph(f'<b>R$ {formatar_valor_br(saldo_depois)}</b>', styles['Small8C']),
        ])

        # Mescla coluna "Totalização" verticalmente se múltiplos empenhos
        if idx == 0 and num_empenhos > 1:
            span_cmds.append(('SPAN', (3, row_i), (3, row_i + num_empenhos - 1)))
            span_cmds.append(('SPAN', (4, row_i), (4, row_i + num_empenhos - 1)))

        row_i += 1

    main_t = Table(table_rows, colWidths=[c1, c2, c3, c4, c5, c6, c7])
    ts = [
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, BLACK),
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_GRAY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        # Fundo amarelo nas linhas de totalização
        ('BACKGROUND', (3, tot_start), (6, row_i - 1), colors.HexColor('#FFE699')),
    ] + span_cmds

    main_t.setStyle(TableStyle(ts))
    story.append(main_t)

    story.append(Spacer(1, 0.5 * cm))

    # Location and date
    loc_data = [
        [Paragraph(f'Local: Vila Velha - ES', styles['Normal9']),
         Paragraph(f'Data: {hoje}', styles['Normal9'])],
    ]
    loc_t = Table(loc_data, colWidths=[CONTENT_W * 0.5, CONTENT_W * 0.5])
    loc_t.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(loc_t)
    story.append(Spacer(1, 1.0 * cm))

    # Signature
    story.append(Paragraph(f'<b>{gestor["nome"]} – {gestor["matricula"]}</b>',
                            styles['SignatureStyle']))
    story.append(Paragraph(gestor.get('titulo', 'Gestor do Contrato'),
                            styles['SignatureSubStyle']))

    build_doc(story, buffer)
    return buffer.getvalue()


# ─── ATESTE ──────────────────────────────────────────────────────────────────
def gerar_ateste(dados: dict) -> bytes:
    styles = get_styles()
    buffer = io.BytesIO()
    story = []

    contrato = dados['contrato']
    nf = dados['nf']
    fiscal = dados['fiscal']
    gestor = dados['gestor']
    empenhos_usados = dados['empenhos_usados']
    empresa = dados['empresa']

    hoje = date.today().strftime('%d/%m/%Y')
    mes_ref = f'{mes_nome(nf["mes_referencia"])}/{nf["ano_referencia"]}'
    meio = nf.get('meio_recebimento', 'e-mail')
    periodo = f'{fmt_data(nf["periodo_inicio"])} a {fmt_data(nf["periodo_fim"])}'

    story.append(portaria_row())
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph('ANEXO I', styles['AnexoTitle']))
    story.append(Spacer(1, 0.1 * cm))
    story.append(Paragraph('(a que se refere o art. 7º do Decreto nº 157/2025)', styles['Normal9C']))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph('MODELO PADRÃO DE ATESTE – SERVIÇOS DE QUALQUER NATUREZA',
                            styles['AnexoSubTitle']))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph('Ao Gestor do Contrato,', styles['Normal9']))
    story.append(Spacer(1, 0.4 * cm))

    intro = (
        f'Na condição de Fiscal do Contrato abaixo discriminado, declaro o recebimento da '
        f'documentação enviada pela empresa contratada, através de {meio}, referente ao '
        f'faturamento relacionado aos serviços prestados no mês de {mes_ref}, abaixo relacionada:'
    )
    story.append(Paragraph(intro, styles['Normal9J']))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph('- Dados da Medição e do Credor', styles['Normal9']))
    story.append(Spacer(1, 0.2 * cm))

    val_extenso = valor_por_extenso(nf['valor_nf'])

    # DADOS DA MEDIÇÃO
    med_header = [[Paragraph('<b>DADOS DA MEDIÇÃO E DO CREDOR</b>', styles['Bold9C'])]]
    med_ht = Table(med_header, colWidths=[CONTENT_W])
    med_ht.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(med_ht)

    col2 = CONTENT_W / 2
    med_data = [
        [Paragraph(f'<b>Credor:</b> {contrato["empresa"]}', styles['Normal9']),
         Paragraph(f'<b>Nota fiscal nº:</b> {nf["numero_nf"]}', styles['Normal9'])],
        [Paragraph(f'<b>Valor (em R$ e por extenso):</b> {val_extenso}', styles['Normal9']),
         Paragraph(f'<b>Número e Período da medição:</b> {nf["numero_medicao"]} - {periodo}', styles['Normal9'])],
        [Paragraph(f'<b>Contrato:</b> {contrato["numero"]}', styles['Normal9']),
         Paragraph(f'<b>Objeto:</b> {contrato["objeto"]}', styles['Normal9'])],
        [Paragraph(f'<b>Banco:</b> {empresa.get("banco", "")}', styles['Normal9']),
         Paragraph(f'<b>Agência:</b> {empresa.get("agencia", "")}', styles['Normal9'])],
        [Paragraph(f'<b>Conta bancária nº:</b> {empresa.get("conta_bancaria", "")}', styles['Normal9']),
         Paragraph(f'<b>Tipo de operação bancária:</b> {empresa.get("tipo_operacao", "")}', styles['Normal9'])],
    ]
    med_t = Table(med_data, colWidths=[col2, col2])
    med_t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(med_t)
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph('- Dados para liquidação e pagamento – fonte do recurso¹', styles['Normal9']))
    story.append(Spacer(1, 0.2 * cm))

    # One table per empenho
    for emp in empenhos_usados:
        liq_header = [[Paragraph(
            '<b>DADOS PARA LIQUIDAÇÃO E PAGAMENTO – FONTE DO RECURSO²</b>',
            styles['Bold9C'])]]
        liq_ht = Table(liq_header, colWidths=[CONTENT_W])
        liq_ht.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
            ('BACKGROUND', (0, 0), (-1, -1), LIGHT_GRAY),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(liq_ht)

        liq_data = [
            [Paragraph(f'<b>Empenho n°:</b> {emp["numero"]}', styles['Normal9']), ''],
            [Paragraph(f'<b>Fonte/Destinação de Recurso:</b> {emp.get("fonte_recurso", "")}', styles['Normal9']),
             Paragraph(f'<b>Código de Aplicação:</b> {emp.get("codigo_aplicacao", "")}', styles['Normal9'])],
            [Paragraph(f'<b>Banco:</b> {emp.get("banco", "")}', styles['Normal9']),
             Paragraph(f'<b>Agência:</b> {emp.get("agencia", "")}', styles['Normal9'])],
            [Paragraph(f'<b>Conta bancária nº:</b> {emp.get("conta_bancaria", "")}', styles['Normal9']),
             Paragraph(f'<b>Tipo de operação bancária:</b> {emp.get("tipo_operacao", "")}', styles['Normal9'])],
        ]
        liq_t = Table(liq_data, colWidths=[col2, col2])
        liq_t.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, BLACK),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BLACK),
            ('SPAN', (0, 0), (1, 0)),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        story.append(liq_t)
        story.append(Spacer(1, 0.15 * cm))
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(
        '¹ Obrigatório para cada código de fonte/destinação de recurso a que a despesa estiver vinculada.',
        styles['FootnoteStyle']))
        story.append(HRFlowable(width=CONTENT_W * 0.4, thickness=0.5, color=BLACK))
        story.append(Spacer(1, 0.5 * cm))

    # Document list
    docs = [
        '- Relatório de Comprovação de Adimplência de Encargos – RECAE;',
        '- Declaração de Contabilidade Regular;',
        '- CND Federal;',
        '- CND Estadual;',
        '- CND Municipal (Sede da empresa);',
        '- CND Municipal Vila Velha;',
        '- Certificado de Regularidade do FGTS;',
        '- CND Trabalhista;',
    ]
    for d in docs:
        story.append(Paragraph(d, styles['Normal9']))

    story.append(Spacer(1, 0.4 * cm))

    data_verif = nf.get('data_verificacao_certidoes') or hoje
    decl1 = (
        f'Declaro ainda, a autenticidade das Certidões bem como das NFS-e {nf["numero_nf"]}, '
        f'acima mencionadas, verificada em {data_verif}.'
    )
    story.append(Paragraph(decl1, styles['Normal9J']))
    story.append(Spacer(1, 0.4 * cm))

    atesto = (
        f'<b>ATESTO</b> que os serviços relativos à NFS-e nº {nf["numero_nf"]}, foram '
        f'devidamente prestados, conforme disposto no contrato, no período de '
        f'{fmt_data(nf["periodo_inicio"])} até {fmt_data(nf["periodo_fim"])}.'
    )
    story.append(Paragraph(atesto, styles['Normal9J']))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph(f'<b>DATA DO ATESTE: {hoje}</b>', styles['SignatureStyle']))
    story.append(Spacer(1, 0.8 * cm))

    fiscal_titulo = 'Fiscal Suplente do Contrato' if fiscal.get('suplente') else 'Fiscal do Contrato'
    gestor_titulo = 'Gestor Suplente do Contrato' if gestor.get('suplente') else 'Gestor do Contrato'

    story.append(Paragraph(f'<b>{fiscal["nome"]} – {fiscal["matricula"]}</b>',
                            styles['SignatureStyle']))
    story.append(Paragraph(f'{fiscal_titulo}', styles['SignatureSubStyle']))
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(f'<b>{gestor["nome"]} – {gestor["matricula"]}</b>',
                            styles['SignatureStyle']))
    story.append(Paragraph(f'{gestor_titulo}', styles['SignatureSubStyle']))

    build_doc(story, buffer)
    return buffer.getvalue()
