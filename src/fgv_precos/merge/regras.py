"""Regras do merge (sem dependência de navegador ou de Excel, para poder testar).

Regras combinadas com a Aline em 13/10/2026:
    * As linhas da base ficam (exceto as retiradas por correção); os candidatos só
      completam as vagas até 5 preços por insumo.
    * Ordem de prioridade dos candidatos: fornecedor de GO primeiro; depois o menor
      preço + frete.
    * Duplicado = mesmo CNPJ no mesmo insumo. Um mesmo produto (link) não entra em
      dois insumos.
    * Frete de GO para GO não é calculado: VALOR FRETE vazio e OBS FRETE
      "Frete não calculado (GO para GO)", acrescido de " | frete real: R$ X" quando
      o valor real é conhecido.
    * Preço = preço cheio, sem desconto por forma de pagamento.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

PRECOS_POR_INSUMO = 5
UF_DESTINO = "GO"
OBS_GO = "Frete não calculado (GO para GO)"


def somente_digitos(texto: object) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def normalizar_url(url: object) -> str:
    """Endereço sem esquema, "www.", parâmetros e barra final (para comparar links).

    O "#..." é descartado, exceto quando é a rota de um site feito em JavaScript
    ("#/produto-detalhes/..."): nesse caso é ele que identifica o produto (Mais
    Segurança, 16/10/2026: os links do 1107 e do 1114 só diferem depois do "#").
    """
    partes = urlparse(str(url or "").strip())
    base = f"{partes.netloc.lower().removeprefix('www.')}{partes.path.rstrip('/')}"
    rota = partes.fragment
    if rota.startswith(("/", "!/")):
        return f"{base}#{rota.rstrip('/')}"
    return base


def reais(valor: float) -> str:
    """12345.6 -> 'R$ 12.345,60'."""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def obs_frete_go(frete_real: float | None = None) -> str:
    """OBS FRETE das linhas de fornecedor de GO (frete não calculado)."""
    if frete_real:
        return f"{OBS_GO} | frete real: {reais(frete_real)}"
    return OBS_GO


@dataclass
class Candidato:
    """Linha que pode preencher uma vaga (já aprovada na revisão)."""
    id_fgv: str
    cnpj: str
    uf: str
    link: str
    preco: float
    frete: float | None
    chave: str = ""                 # identifica a linha na planilha de candidatos
    dados: dict = field(default_factory=dict)

    @property
    def eh_go(self) -> bool:
        return self.uf == UF_DESTINO

    @property
    def custo(self) -> float:
        """Preço + frete (o frete de GO para GO não é calculado e não entra)."""
        return self.preco + (0.0 if self.eh_go else (self.frete or 0.0))


def selecionar(vagas: dict[str, int], candidatos: list[Candidato],
               cnpjs_ocupados: dict[str, set[str]], links_ocupados: set[str]) -> list[Candidato]:
    """Escolhe, por insumo, os candidatos que preenchem as vagas.

    ``cnpjs_ocupados[id]``: CNPJs (só dígitos) que já têm linha no insumo.
    ``links_ocupados``: links (normalizados) já usados em qualquer insumo.
    Um candidato é ignorado se o CNPJ já está no insumo ou se o link já foi usado.
    """
    escolhidos: list[Candidato] = []
    usados = set(links_ocupados)
    ordem = sorted(candidatos, key=lambda c: (not c.eh_go, c.custo, c.chave))
    ocupados = {i: set(v) for i, v in cnpjs_ocupados.items()}
    restantes = dict(vagas)
    for c in ordem:
        if restantes.get(c.id_fgv, 0) <= 0:
            continue
        cnpj, link = somente_digitos(c.cnpj), normalizar_url(c.link)
        if cnpj in ocupados.setdefault(c.id_fgv, set()) or link in usados:
            continue
        escolhidos.append(c)
        ocupados[c.id_fgv].add(cnpj)
        usados.add(link)
        restantes[c.id_fgv] -= 1
    return escolhidos
