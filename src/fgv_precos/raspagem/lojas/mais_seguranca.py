"""
Raspagem: Mais Segurança EPI (Goiânia/GO) - CNPJ 43.903.641/0001-69

Loja NPC Store (maisseguranca.online), toda em JavaScript (Vue). Conferido no
navegador em 15-16/10/2026:
    * o link do produto é ``/#/produto-detalhes/<id empresa>/<id produto>``; ao trocar
      só o "#..." a página não recarrega o produto, por isso ``ler_produto`` recarrega;
    * não há JSON-LD nem botão "adicionar ao carrinho" (o botão é só "adicionar"),
      então a regra genérica dizia "não é página de produto";
    * nome em ``span.titulo`` (seguido de " Ref: ..."), preço em ``span.titulo-valor``
      ("V: R$ 1,00") e estoque por tamanho em ``.adicionar-carrinho-tamanho`` ("UN (13)");
    * produto sem preço de varejo aparece como "V: R$ 0,00" (com estoque 0 ou negativo):
      tratado como esgotado/sem preço, nunca como preço zero;
    * fornecedor de GO: o frete não é calculado (regra de 13/10/2026).
"""

from __future__ import annotations

import logging
import re

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from fgv_precos.precos import valores_de_preco
from fgv_precos.raspagem.config_raspagem import TIMEOUT_NAVEGACAO_MS
from fgv_precos.raspagem.modelos import Produto, limpar_nome
from fgv_precos.raspagem.plataformas.base import MOTIVO_DESCONHECIDO, LojaBase

log = logging.getLogger(__name__)

CNPJ = "43903641000169"
ESPERA_PRODUTO_MS = 15_000


def interpretar_pagina(titulo: str, texto_preco: str, estoques: list[str]) -> tuple[str, float | None, bool]:
    """(nome, preço, disponível) a partir dos textos da página do produto."""
    nome = limpar_nome(re.split(r"\s+Ref:", titulo or "", maxsplit=1)[0])
    valores = valores_de_preco(texto_preco or "")
    preco = min(valores) if valores else None
    if preco is not None and preco <= 0:
        preco = None
    numeros = [int(n) for e in estoques for n in re.findall(r"\((-?\d+)\)", e or "")]
    disponivel = any(n > 0 for n in numeros) if numeros else True
    return nome, preco, disponivel


class MaisSeguranca(LojaBase):
    plataforma = "Mais Segurança (NPC Store)"

    def ler_produto(self, url: str) -> Produto | None:
        if not self.abrir(url):
            return None
        try:
            self.page.reload(timeout=TIMEOUT_NAVEGACAO_MS, wait_until="domcontentloaded")
            self.page.locator("span.titulo").first.wait_for(timeout=ESPERA_PRODUTO_MS)
            self.page.locator("span.titulo-valor").first.wait_for(timeout=ESPERA_PRODUTO_MS)
            titulo = self.page.locator("span.titulo").first.inner_text()
            texto_preco = self.page.locator("span.titulo-valor").first.inner_text()
            estoques = self.page.locator(".adicionar-carrinho-tamanho").all_inner_texts()
        except (PlaywrightTimeout, PlaywrightError) as exc:
            log.info("[%s] %s: página do produto não carregou (%s).", self.fornecedor.nome, url, exc)
            return None
        nome, preco, disponivel = interpretar_pagina(titulo, texto_preco, estoques)
        if not nome:
            return None
        # Sem estoque em nenhum tamanho = esgotado (descartado). Com estoque e sem preço
        # (R$ 0,00) = coluna P, pela regra de 09/10/2026.
        motivo = MOTIVO_DESCONHECIDO if preco is None and disponivel else ""
        return Produto(nome=nome, url=self.page.url, preco_final=preco,
                       disponivel=disponivel, motivo_sem_preco=motivo)
