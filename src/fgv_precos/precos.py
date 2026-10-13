"""
Leitura de valores em reais ("R$ 1.234,56") a partir de texto.

Fica num módulo próprio porque é usada nas duas etapas do projeto: na
verificação dos sites de fornecedores (há preço visível?) e na raspagem de
preços e fretes.
"""

from __future__ import annotations

import re

# Aceita "R$ 1.234,56", "R$ 39,90" e também "R$39.90" (alguns sites usam ponto).
_RE_VALOR = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2}|\d+\.\d{2})(?![\d,])")

# Trechos que NÃO são o preço visível do produto (regra da coleta: sem
# parcelamento nem desconto por forma de pagamento, como PIX ou boleto).
_RE_PARCELA = re.compile(r"\d+\s*x\s*(?:de\s*)?R\$\s*[\d.,]+(?:\s*sem\s+juros)?", re.IGNORECASE)
_RE_DESCONTO_PAGAMENTO = re.compile(
    r"R\$\s*[\d.,]+\s*(?:no|via|com|pelo|pagando\s+(?:no|com))?\s*(?:pix|boleto|dep[óo]sito)",
    re.IGNORECASE,
)


def _para_float(bruto: str) -> float:
    if "," in bruto:                       # padrão brasileiro
        return float(bruto.replace(".", "").replace(",", "."))
    return float(bruto)                    # "39.90"


def valor_br_para_float(texto: str) -> float | None:
    """'R$ 1.234,56' -> 1234.56; 'R$39.90' -> 39.9. None se não houver valor."""
    m = _RE_VALOR.search(texto or "")
    return _para_float(m.group(1)) if m else None


def todos_valores(texto: str) -> list[float]:
    """Todos os valores em reais do texto, na ordem em que aparecem."""
    return [_para_float(v) for v in _RE_VALOR.findall(texto or "")]


def valores_de_preco(texto: str) -> list[float]:
    """Como ``todos_valores``, mas ignora parcelas ("10x de R$ 4,99") e preços
    condicionados à forma de pagamento ("R$ 47,40 no PIX")."""
    limpo = _RE_PARCELA.sub(" ", texto or "")
    limpo = _RE_DESCONTO_PAGAMENTO.sub(" ", limpo)
    return todos_valores(limpo)


def float_para_br(valor: float | None) -> str:
    """1234.5 -> '1234,50' (formato do Excel em português). None -> ''."""
    return "" if valor is None else f"{valor:.2f}".replace(".", ",")
