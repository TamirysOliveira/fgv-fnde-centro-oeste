"""UF de onde a mercadoria sai (coluna D "UF" do FNDE_output).

Regra combinada com a equipe em 13/10/2026: a coluna D traz a UF de onde a
mercadoria sai, isto é, a UF do estabelecimento do fornecedor cujo CNPJ está
na coluna G (quem fatura e despacha). Ela vem da coluna "Estado" das planilhas
``Fornecedores/FNDE_<Grupo>.xlsx``. GO é só o destino do frete (CEP 74933-130)
e não vai para a coluna D.

Os 19 fornecedores da entrega de 13/10/2026 tiveram a UF conferida na Receita
(cnpja.com / cnpj-api.com): todas iguais à coluna "Estado".

Se o fornecedor não for encontrado (nem pelo CNPJ nem pelo site), ou se o mesmo
CNPJ aparecer com UFs diferentes, a UF fica vazia para conferência: nunca se
inventa uma UF.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import openpyxl

from fgv_precos.fornecedores.cnae import somente_digitos

log = logging.getLogger(__name__)

UFS_BR = frozenset({
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
})
# Abas das planilhas de fornecedores que trazem empresas (a aba "Resumo" não).
_ABAS_IGNORADAS = {"Resumo"}


def dominio(url: str | None) -> str:
    """'https://www.loja.com.br/x' -> 'loja.com.br' (vazio se não for link)."""
    texto = str(url or "").strip()
    if not texto:
        return ""
    if "://" not in texto:
        texto = "https://" + texto
    host = urlparse(texto).netloc.lower().split(":")[0]
    return host.removeprefix("www.")


def normalizar_uf(valor: str | None) -> str:
    """Sigla da UF em maiúsculas, ou vazio se não for uma UF válida."""
    uf = str(valor or "").strip().upper()
    return uf if uf in UFS_BR else ""


@dataclass
class MapaUF:
    """UF do fornecedor por CNPJ (só dígitos) e por domínio do site."""
    por_cnpj: dict[str, str] = field(default_factory=dict)
    por_dominio: dict[str, str] = field(default_factory=dict)
    conflitos: set[str] = field(default_factory=set)

    def _guardar(self, tabela: dict[str, str], chave: str, uf: str) -> None:
        if not chave or not uf:
            return
        anterior = tabela.get(chave)
        if anterior and anterior != uf:
            self.conflitos.add(chave)
            log.warning("CONFERIR: '%s' aparece com UF %s e %s nas planilhas de fornecedores.",
                        chave, anterior, uf)
        tabela.setdefault(chave, uf)

    def adicionar(self, uf: str | None, cnpj: str | None = "", *sites: str | None) -> None:
        uf = normalizar_uf(uf)
        self._guardar(self.por_cnpj, somente_digitos(str(cnpj or "")), uf)
        for site in sites:
            self._guardar(self.por_dominio, dominio(site), uf)

    def uf(self, cnpj: str | None, *links: str | None) -> str:
        """UF do fornecedor: primeiro pelo CNPJ, depois pelo domínio do link."""
        digitos = somente_digitos(str(cnpj or ""))
        if digitos and digitos in self.por_cnpj:
            return "" if digitos in self.conflitos else self.por_cnpj[digitos]
        for link in links:
            host = dominio(link)
            if not host:
                continue
            for chave, uf in self.por_dominio.items():
                if host == chave or host.endswith("." + chave) or chave.endswith("." + host):
                    return "" if chave in self.conflitos else uf
        return ""


def ler_mapa_uf(arquivos: list[Path]) -> MapaUF:
    """Monta o mapa a partir das planilhas ``Fornecedores/FNDE_<Grupo>.xlsx``."""
    mapa = MapaUF()
    for arquivo in arquivos:
        if not arquivo.exists():
            log.warning("Planilha de fornecedores não encontrada: %s", arquivo)
            continue
        wb = openpyxl.load_workbook(arquivo, read_only=True, data_only=True)
        try:
            for ws in wb.worksheets:
                if ws.title in _ABAS_IGNORADAS:
                    continue
                linhas = list(ws.iter_rows(values_only=True))
                if not linhas:
                    continue
                cab = [str(c or "").strip() for c in linhas[0]]
                if "Estado" not in cab:
                    continue
                idx = {nome: cab.index(nome) for nome in
                       ("Estado", "CNPJ", "Site Oficial", "Link (clicável)") if nome in cab}

                def campo(linha: tuple, nome: str, idx=idx) -> str:
                    i = idx.get(nome)
                    return str(linha[i] or "").strip() if i is not None and i < len(linha) else ""

                for linha in linhas[1:]:
                    mapa.adicionar(campo(linha, "Estado"), campo(linha, "CNPJ"),
                                   campo(linha, "Site Oficial"), campo(linha, "Link (clicável)"))
        finally:
            wb.close()
    return mapa
