"""
Plataforma Loja Integrada (ex.: Supriflex, Stars, Casa do Saco de Lixo).

Conferido no navegador em 09/10/2026 (supriflex.com.br):
    * busca: /buscar?q=<termo>; itens em ``.listagem-item``, nome em ``a.nome-produto``
    * página do produto: preço em ``.acoes-produto .preco-promocional`` /
      ``.preco-venda`` (preenchido por JavaScript após o carregamento)
    * frete: campo ``input.input-cep`` + botão "OK"; as opções aparecem logo
      abaixo, numa linha ("R$ 45,04 10 dias úteis Jadlog") ou em várias
      ("R$ 59,10" / "7 dias úteis" / "Correios PAC" - stars, 09/10/2026).
    * produtos com variação (tamanho, cor...): o frete só é calculado depois de
      escolher a opção ("Antes de calcular o frete é necessário escolher as
      opções do produto" - bhzepi, 09/10/2026). Opções em ``.atributos a.atributo-item``.
"""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from playwright.sync_api import Error as PlaywrightError

from fgv_precos.raspagem.descricao import medidas
from fgv_precos.raspagem.modelos import Candidato, Produto, todos_valores
from fgv_precos.raspagem.plataformas.base import LojaBase, melhor_linha

log = logging.getLogger(__name__)


class LojaIntegrada(LojaBase):
    plataforma = "Loja Integrada"

    def url_busca(self, termo: str) -> str:
        return f"{self.base}/buscar?q={quote_plus(termo)}"

    def extrair_resultados(self) -> list[Candidato]:
        itens = self.page.eval_on_selector_all(
            ".listagem-item",
            """els => els.map(e => {
                const a = e.querySelector('a.nome-produto');
                return a ? {n: a.innerText.trim(), u: a.href} : null;
            }).filter(Boolean)""")
        return [Candidato(nome=melhor_linha(i["n"]), url=i["u"]) for i in itens]

    def _escolher_variacoes(self) -> list[str]:
        """Escolhe uma opção em cada grade (tamanho, cor...).

        Preferência: a opção cuja medida bate com a do insumo (ex.: "5L");
        senão, a primeira opção disponível. Devolve as escolhas feitas.
        """
        escolhas = []
        grades = self.page.locator(".atributos .atributo-comum")
        exigidas = self.insumo.medidas_obrigatorias if self.insumo else set()
        for g in range(grades.count()):
            opcoes = grades.nth(g).locator("a.atributo-item:not(.indisponivel)")
            if not opcoes.count():
                continue
            alvo = opcoes.first
            for i in range(opcoes.count()):
                nome = opcoes.nth(i).get_attribute("data-variacao-nome") or ""
                if exigidas and exigidas & medidas(nome):
                    alvo = opcoes.nth(i)
                    break
            try:
                alvo.click(timeout=3_000)
                self.page.wait_for_timeout(1_200)
                grade = alvo.get_attribute("data-grade-nome") or "Opção"
                escolhas.append(f"{grade}: {alvo.get_attribute('data-variacao-nome') or ''}".strip())
            except PlaywrightError as exc:
                log.info("[%s] Não consegui escolher a variação: %s", self.fornecedor.nome, exc)
        return escolhas

    def ler_produto(self, url: str) -> Produto | None:
        produto = super().ler_produto(url)
        if produto is None:
            return None
        escolhas = self._escolher_variacoes()
        if escolhas:
            final, de = self.ler_preco_pagina()
            if final is not None:
                produto.preco_final, produto.preco_de = final, de
                produto.motivo_sem_preco = ""
            produto.nome = f"{produto.nome} ({'; '.join(escolhas)})"
            log.info("[%s] Variação escolhida: %s", self.fornecedor.nome, "; ".join(escolhas))
        return produto

    def ler_preco_pagina(self):
        # Espera o JavaScript trocar o modelo "--PRODUTO_PRECO_POR--" pelo valor.
        try:
            self.page.wait_for_function(
                "() => /R\\$\\s*\\d/.test((document.querySelector('.acoes-produto') || document.body).innerText)",
                timeout=8_000)
        except PlaywrightError:
            pass
        for sel_final in (".acoes-produto .preco-promocional", ".acoes-produto .preco-venda",
                          ".principal .preco-promocional", ".principal .preco-venda"):
            loc = self.page.locator(sel_final)
            for i in range(loc.count()):
                try:
                    if loc.nth(i).is_visible():
                        valores = todos_valores(loc.nth(i).inner_text())
                        if valores:
                            de_loc = self.page.locator(".acoes-produto .preco-venda.titulo, "
                                                       ".acoes-produto s, .acoes-produto del")
                            de = todos_valores(de_loc.first.inner_text()) if de_loc.count() else []
                            final = min(valores)
                            return final, (max(de) if de and max(de) > final else None)
                except PlaywrightError:
                    continue
        return super().ler_preco_pagina()

    def _campo_cep(self):
        campos = self.page.locator("input.input-cep")
        for i in range(campos.count()):
            if campos.nth(i).is_visible():
                return campos.nth(i)
        return super()._campo_cep()
