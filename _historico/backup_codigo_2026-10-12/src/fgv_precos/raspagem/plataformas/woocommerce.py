"""
Plataforma WooCommerce (ex.: Casa da Limpeza).

No WooCommerce a calculadora de frete costuma existir só no carrinho (sem
login). Fluxo: esvazia o carrinho -> adiciona o produto -> abre o carrinho ->
"Calcular frete" -> CEP/UF -> lê as opções. O print é do carrinho, que mostra
nome do produto, preço e frete juntos.
"""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

from playwright.sync_api import Error as PlaywrightError

from fgv_precos.raspagem.config_raspagem import ESPERA_FRETE_MS
from fgv_precos.raspagem.modelos import Candidato, Frete
from fgv_precos.raspagem.plataformas.base import LojaBase

log = logging.getLogger(__name__)


class WooCommerce(LojaBase):
    plataforma = "WooCommerce"

    def __init__(self, page, fornecedor) -> None:
        super().__init__(page, fornecedor)
        self._url_produto_atual = ""

    def url_busca(self, termo: str) -> str:
        return f"{self.base}/?s={quote_plus(termo)}&post_type=product"

    def extrair_resultados(self) -> list[Candidato]:
        # Quando há um único resultado, o WooCommerce abre direto o produto.
        if self.page.locator("body.single-product").count():
            nome = self.page.locator("h1").first.inner_text().strip()
            return [Candidato(nome=nome, url=self.page.url)]
        itens = self.page.eval_on_selector_all(
            "li.product, div.product",
            """els => els.map(e => {
                const a = e.querySelector('a.woocommerce-LoopProduct-link, a[href*="/produto/"], a[href*="/product/"]');
                const t = e.querySelector('.woocommerce-loop-product__title, h2, h3');
                return a && t ? {n: t.innerText.trim(), u: a.href} : null;
            }).filter(Boolean)""")
        return [Candidato(nome=i["n"], url=i["u"]) for i in itens]

    def ler_produto(self, url: str):
        produto = super().ler_produto(url)
        self._url_produto_atual = url
        return produto

    # ------------------------------------------------------------ carrinho
    def _url_carrinho(self) -> str:
        try:
            return self.page.evaluate(
                "() => (window.wc_add_to_cart_params && wc_add_to_cart_params.cart_url) || ''"
            ) or f"{self.base}/carrinho/"
        except PlaywrightError:
            return f"{self.base}/carrinho/"

    def _esvaziar_carrinho(self, url_carrinho: str) -> None:
        if not self._ir(url_carrinho):
            return
        for _ in range(10):
            remover = self.page.locator("a.remove, .product-remove a")
            if not remover.count():
                break
            try:
                remover.first.click(timeout=3_000)
                self.page.wait_for_timeout(2_000)
            except PlaywrightError:
                break

    def calcular_frete(self, cep: str, uf: str) -> Frete:
        url_carrinho = self._url_carrinho()
        try:
            self._esvaziar_carrinho(url_carrinho)
            if not self._ir(self._url_produto_atual):
                return Frete(ok=False, motivo="não reabriu o produto")
            botao = self.page.locator(".single_add_to_cart_button, button[name='add-to-cart']")
            if not botao.count():
                return Frete(ok=False, motivo="botão de comprar não encontrado")
            botao.first.click(timeout=5_000)
            self.page.wait_for_timeout(2_500)
            if not self._ir(url_carrinho):
                return Frete(ok=False, motivo="carrinho não abriu")
            abrir = self.page.locator(".shipping-calculator-button")
            if abrir.count() and abrir.first.is_visible():
                abrir.first.click()
                self.page.wait_for_timeout(800)
            campo = self.page.locator("#calc_shipping_postcode")
            if not campo.count():
                return Frete(ok=False, motivo="carrinho sem calculadora de frete")
            pais = self.page.locator("#calc_shipping_country")
            if pais.count():
                try:
                    pais.select_option("BR")
                except PlaywrightError:
                    pass
            estado = self.page.locator("#calc_shipping_state")
            if estado.count():
                try:
                    estado.select_option(uf)
                except PlaywrightError:
                    pass
            campo.fill(cep)
            self.page.locator("button[name='calc_shipping']").first.click()
            self.page.wait_for_timeout(ESPERA_FRETE_MS // 2)
            area = self.page.locator(".woocommerce-shipping-totals, #shipping_method, .cart_totals")
            texto = area.first.inner_text() if area.count() else ""
            frete = self.interpretar_frete(texto)
            if not frete.ok and "nenhum" in texto.lower():
                frete.motivo = "loja não entrega neste CEP"
            return frete
        except PlaywrightError as exc:
            return Frete(ok=False, motivo=f"erro no carrinho: {exc}")
