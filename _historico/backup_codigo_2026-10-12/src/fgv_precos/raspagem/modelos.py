"""Estruturas de dados da raspagem."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Aceita "R$ 1.234,56", "R$ 39,90" e também "R$39.90" (alguns sites usam ponto).
_RE_VALOR = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2}|\d+\.\d{2})(?![\d,])")


def _para_float(bruto: str) -> float:
    if "," in bruto:                       # padrão brasileiro
        return float(bruto.replace(".", "").replace(",", "."))
    return float(bruto)                    # "39.90"


def valor_br_para_float(texto: str) -> float | None:
    """'R$ 1.234,56' -> 1234.56; 'R$39.90' -> 39.9. None se não houver valor."""
    m = _RE_VALOR.search(texto or "")
    return _para_float(m.group(1)) if m else None


def todos_valores(texto: str) -> list[float]:
    return [_para_float(v) for v in _RE_VALOR.findall(texto or "")]


def float_para_br(valor: float | None) -> str:
    """1234.5 -> '1234,50' (formato do Excel em português). None -> ''."""
    return "" if valor is None else f"{valor:.2f}".replace(".", ",")


@dataclass
class Fornecedor:
    nome: str
    cnpj: str
    site: str
    estado: str = ""


@dataclass
class Candidato:
    """Produto listado na busca do site."""
    nome: str
    url: str
    pontuacao: float = 0.0


@dataclass
class Produto:
    """Dados lidos na página do produto."""
    nome: str
    url: str
    preco_final: float | None
    preco_de: float | None = None      # preço "de" (riscado); só informativo
    disponivel: bool = True
    # Preenchido quando a página não mostra preço (e o produto não está
    # esgotado): "Preço só com login", "Preço sob consulta/orçamento" ou
    # "Preço não exibido (motivo não identificado)".
    motivo_sem_preco: str = ""


@dataclass
class Frete:
    ok: bool                            # False = não foi possível calcular
    valor: float | None = None          # None quando grátis ou quando falhou
    gratis: bool = False
    modalidade: str = ""
    motivo: str = ""                    # por que falhou (vai para o log)
    opcoes: list[str] = field(default_factory=list)


@dataclass
class Coleta:
    """Uma linha da planilha de saída.

    ``link_aproveitavel`` preenchido = produto correspondente sem preço visível:
    a linha serve para coleta manual (coluna P), traz o motivo em OBS FRETE e
    não conta entre os 5 preços.
    """
    insumo_id: str
    grupo: str
    descricao: str
    uf: str
    data: str
    fornecedor: Fornecedor
    produto: Produto
    frete: Frete | None
    caminho_print: str = ""
    link_aproveitavel: str = ""
