"""
Testes unitários para utils.py

Execute com:
    python -m pytest tests/ -v
    python -m pytest tests/test_utils.py -v --tb=short
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import valor_por_extenso, validar_cnpj, formatar_cnpj, mes_nome, DATE_FMT


class TestValorPorExtenso:
    def test_zero(self):
        assert 'zero' in valor_por_extenso(0.0).lower()

    def test_um_real(self):
        assert 'um real' in valor_por_extenso(1.0).lower()

    def test_dois_reais(self):
        assert 'dois reais' in valor_por_extenso(2.0).lower()

    def test_cem_reais(self):
        assert 'cem reais' in valor_por_extenso(100.0).lower()

    def test_mil(self):
        assert 'mil' in valor_por_extenso(1000.0).lower()

    def test_vinte_e_cinco_mil(self):
        r = valor_por_extenso(25000.0).lower()
        assert 'vinte' in r and 'cinco' in r and 'mil' in r

    def test_com_centavos(self):
        r = valor_por_extenso(10.50).lower()
        assert 'dez reais' in r and 'cinquenta centavos' in r

    def test_um_centavo(self):
        assert 'um centavo' in valor_por_extenso(0.01).lower()

    def test_negativo(self):
        assert 'menos' in valor_por_extenso(-10.0).lower()

    def test_inclui_valor_r(self):
        r = valor_por_extenso(1500.0)
        assert 'R$' in r and '1.500,00' in r

    def test_novecentos_noventa_e_nove(self):
        r = valor_por_extenso(999.0).lower()
        assert 'novecentos' in r and 'noventa' in r and 'nove' in r


class TestValidarCNPJ:
    VALIDOS = [
        '11.222.333/0001-81',
        '22.840.676/0001-26',
        '33.000.167/0001-01',
    ]
    INVALIDOS = [
        '11.222.333/0001-82',
        '00000000000000',
        '11111111111111',
        '123', '', None,
        '12.345.678/0001-90',
    ]

    def test_cnpjs_validos(self):
        for cnpj in self.VALIDOS:
            assert validar_cnpj(cnpj), f"Deveria ser válido: {cnpj}"

    def test_cnpjs_invalidos(self):
        for cnpj in self.INVALIDOS:
            assert not validar_cnpj(cnpj), f"Deveria ser inválido: {cnpj}"

    def test_todos_iguais_invalidos(self):
        for d in '0123456789':
            assert not validar_cnpj(d * 14)

    def test_aceita_formatado_e_sem(self):
        assert validar_cnpj('33000167000101')
        assert validar_cnpj('33.000.167/0001-01')


class TestFormatarCNPJ:
    def test_formata(self):
        assert formatar_cnpj('33000167000101') == '33.000.167/0001-01'

    def test_ja_formatado(self):
        assert formatar_cnpj('33.000.167/0001-01') == '33.000.167/0001-01'

    def test_curto_retorna_original(self):
        assert formatar_cnpj('123') == '123'

    def test_none(self):
        assert formatar_cnpj(None) == ''


class TestMesNome:
    def test_janeiro(self):
        assert mes_nome(1) == 'Janeiro'

    def test_dezembro(self):
        assert mes_nome(12) == 'Dezembro'

    def test_invalido(self):
        assert mes_nome(0) == ''
        assert mes_nome(13) == ''

    def test_todos(self):
        nomes = ['Janeiro','Fevereiro','Março','Abril','Maio','Junho',
                 'Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
        for i, n in enumerate(nomes, 1):
            assert mes_nome(i) == n


class TestDateFmt:
    def test_formato_br(self):
        from datetime import date
        assert date(2025, 4, 30).strftime(DATE_FMT) == '30/04/2025'

    def test_constante(self):
        assert DATE_FMT == '%d/%m/%Y'
