import decimal as _decimal

# Formato de data padrão brasileiro
DATE_FMT = '%d/%m/%Y'


def valor_por_extenso(valor: float) -> str:
    """
    Converte valor numérico para extenso em português brasileiro.

    Usa ``decimal.Decimal`` internamente para garantir que o número
    escrito por extenso seja sempre idêntico ao valor exibido em
    R$ XX.XXX,XX — sem divergência causada por imprecisão de float.

    Exemplos::

        valor_por_extenso(1500.00)  → 'R$ 1.500,00 (um mil e quinhentos reais)'
        valor_por_extenso(10.50)    → 'R$ 10,50 (dez reais e cinquenta centavos)'
        valor_por_extenso(0.01)     → 'R$ 0,01 (um centavo)'
    """
    if valor < 0:
        return 'menos ' + valor_por_extenso(-valor)

    # Converte para Decimal com 2 casas para eliminar imprecisão de float.
    # str(round(valor, 2)) evita que Decimal receba a representação binária
    # completa do float (ex: 900851.8599999998...).
    d = _decimal.Decimal(str(round(valor, 2)))

    # Extrai reais e centavos sem risco de arredondamento incorreto
    centavos = int(d * 100) % 100
    reais    = int(d)

    # ── Funções auxiliares de conversão ──────────────────────────────────────

    def unidade(n):
        u = [
            '', 'um', 'dois', 'três', 'quatro', 'cinco', 'seis', 'sete',
            'oito', 'nove', 'dez', 'onze', 'doze', 'treze', 'quatorze',
            'quinze', 'dezesseis', 'dezessete', 'dezoito', 'dezenove',
        ]
        return u[n] if n < 20 else ''

    def dezena(n):
        d2 = [
            '', '', 'vinte', 'trinta', 'quarenta', 'cinquenta',
            'sessenta', 'setenta', 'oitenta', 'noventa',
        ]
        if n < 20:
            return unidade(n)
        resto = n % 10
        return d2[n // 10] + (' e ' + unidade(resto) if resto else '')

    def centena(n):
        if n == 100:
            return 'cem'
        c = [
            '', 'cento', 'duzentos', 'trezentos', 'quatrocentos', 'quinhentos',
            'seiscentos', 'setecentos', 'oitocentos', 'novecentos',
        ]
        resto = n % 100
        return c[n // 100] + (' e ' + dezena(resto) if resto else '')

    def grupo(n):
        if n == 0:    return ''
        if n < 100:   return dezena(n)
        if n < 1000:  return centena(n)
        return ''

    def numero_extenso(n):
        if n == 0:
            return 'zero'
        bilhoes  = n // 1_000_000_000
        milhoes  = (n % 1_000_000_000) // 1_000_000
        milhares = (n % 1_000_000) // 1_000
        resto    = n % 1_000
        partes = []
        if bilhoes:  partes.append(grupo(bilhoes)  + (' bilhão'  if bilhoes  == 1 else ' bilhões'))
        if milhoes:  partes.append(grupo(milhoes)  + (' milhão'  if milhoes  == 1 else ' milhões'))
        if milhares: partes.append(grupo(milhares) + ' mil')
        if resto:    partes.append(grupo(resto))
        resultado = ''
        for i, p in enumerate(partes):
            if i == 0:
                resultado = p
            elif i == len(partes) - 1:
                resultado += ' e ' + p
            else:
                resultado += ', ' + p
        return resultado

    def fmt_brl(v):
        """Formata no padrão BR (1.500,00) independente do locale do sistema."""
        s = f'{v:,.2f}'                                        # en_US: 1,500.00
        s = s.replace(',', 'X').replace('.', ',').replace('X', '.')  # → 1.500,00
        return f'R$ {s}'

    # ── Monta o resultado ─────────────────────────────────────────────────────

    reais_ext   = numero_extenso(reais)
    reais_label = 'real' if reais == 1 else 'reais'

    if centavos == 0:
        return f'{fmt_brl(valor)} ({reais_ext} {reais_label})'

    centavos_ext   = numero_extenso(centavos)
    centavos_label = 'centavo' if centavos == 1 else 'centavos'

    if reais == 0:
        return f'{fmt_brl(valor)} ({centavos_ext} {centavos_label})'

    return (
        f'{fmt_brl(valor)} '
        f'({reais_ext} {reais_label} e {centavos_ext} {centavos_label})'
    )


MESES = {
    1: 'Janeiro',  2: 'Fevereiro', 3: 'Março',    4: 'Abril',
    5: 'Maio',     6: 'Junho',     7: 'Julho',     8: 'Agosto',
    9: 'Setembro', 10: 'Outubro',  11: 'Novembro', 12: 'Dezembro',
}


def mes_nome(mes: int) -> str:
    return MESES.get(mes, '')


def formatar_cnpj(cnpj: str) -> str:
    cnpj = ''.join(filter(str.isdigit, cnpj or ''))
    if len(cnpj) == 14:
        return f'{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}'
    return cnpj


def validar_cnpj(cnpj: str) -> bool:
    """Valida CNPJ com verificação dos dígitos verificadores (algoritmo da Receita Federal)."""
    cnpj = ''.join(filter(str.isdigit, cnpj or ''))
    if len(cnpj) != 14:
        return False
    if cnpj == cnpj[0] * 14:
        return False

    def calc_digito(cnpj, pesos):
        soma  = sum(int(cnpj[i]) * pesos[i] for i in range(len(pesos)))
        resto = soma % 11
        return 0 if resto < 2 else 11 - resto

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = calc_digito(cnpj, pesos1)
    d2 = calc_digito(cnpj, pesos2)
    return int(cnpj[12]) == d1 and int(cnpj[13]) == d2
