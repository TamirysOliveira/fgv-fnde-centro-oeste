"""Estruturas de dados da raspagem."""

from __future__ import annotations

import html
from dataclasses import dataclass, field


def limpar_nome(texto: str | None) -> str:
    """Decodifica entidades HTML ("Prote&#231;&#227;o" -> "Proteção") e
    normaliza os espaços. Alguns sites gravam o nome assim no JSON-LD."""
    return " ".join(html.unescape(texto or "").split())


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
