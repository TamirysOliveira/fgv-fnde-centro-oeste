"""
Plataforma WooCommerce (ex.: Casa da Limpeza).

No WooCommerce a calculadora de frete costuma existir só no carrinho (sem
login). Fluxo: carrinho novo (limpa os cookies) -> adiciona o produto -> abre
o carrinho -> confere que só há este produto -> "Calcular frete" -> CEP/UF ->
lê as opções. O print é do carrinho, que mostra nome do produto, preço e
frete juntos.

Por que conferir o carrinho: na coleta de 10/10/2026 o carrinho da Casa da
Limpeza não foi esvaziado entre os insumos; com 8 produtos (R$ 1.136,80) a
loja liberou o "frete grátis acima de R$ 300" e itens de R$ 5,90 saíram com
frete grátis.
"""

from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

from playwright.sync_api import Error as PlaywrightError

from fgv_precos.precos import valor_br_para_float
from fgv_precos.raspagem.config_raspagem import ESPERA_FRETE_MS
from fgv_precos.raspagem.modelos import Candidato, Frete, Produto
from fgv_precos.raspagem.plataformas.base import LojaBase

log = logging.getLogger(__name__)

_ITENS_CARRINHO = "tr.cart_item, .woocommerce-cart-form__cart-item, .wc-block-cart-items__row"
_SUBTOTAL_CARRINHO = ".cart-subtotal .amount, .wc-block-components-totals-item__value"
_RE_LINHA_TOTAL = re.compile(r"^\s*(sub)?total\b", re.I)


def conferir_carrinho(n_itens: int, subtotal: float | None, preco: float | None) -> str:
    """'' se o carrinho tem só o produto da coleta; senão, o motivo do problema."""
    if n_itens != 1:
        return f"carrinho com {n_itens} itens (esperado 1)"
    if subtotal is not None and preco is not None and abs(subtotal - preco) > 0.01:
        return f"subtotal do carrinho (R$ {subtotal:.2f}) diferente do preço (R$ {preco:.2f})"
    return ""


class WooCommerce(LojaBase):
    plataforma = "WooCommerce"

    def __init__(self, page, fornecedor) -> None:
        super().__init__(page, fornecedor)
        self._produto_atual: Produto | None = None

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

    def ler_produto(self, url: str) -> Produto | None:
        produto = super().ler_produto(url)
        self._produto_atual = produto
        return produto

    # ------------------------------------------------------------ carrinho
    def _url_carrinho(self) -> str:
        try:
            return self.page.evaluate(
                "() => (window.wc_add_to_cart_params && wc_add_to_cart_params.cart_url) || ''"
            ) or f"{self.base}/carrinho/"
        except PlaywrightError:
            return f"{self.base}/carrinho/"

    def _problema_no_carrinho(self) -> str:
        subtotal_loc = self.page.locator(_SUBTOTAL_CARRINHO)
        subtotal = (valor_br_para_float(subtotal_loc.first.inner_text())
                    if subtotal_loc.count() else None)
        preco = self._produto_atual.preco_final if self._produto_atual else None
        return conferir_carrinho(self.page.locator(_ITENS_CARRINHO).count(), subtotal, preco)

    def _texto_do_frete(self) -> str:
        area = self.page.locator(".woocommerce-shipping-totals, #shipping_method")
        if area.count():
            return area.first.inner_text()
        # Tema sem a linha de frete separada: usa o quadro de totais, sem as
        # linhas de subtotal/total (que não são frete).
        totais = self.page.locator(".cart_totals")
        texto = totais.first.inner_text() if totais.count() else ""
        return "\n".join(v for v in texto.splitlines() if not _RE_LINHA_TOTAL.search(v))

    def calcular_frete(self, cep: str, uf: str) -> Frete:
        if self._produto_atual is None:
            return Frete(ok=False, motivo="produto não foi lido antes do frete")
        try:
            # Carrinho novo: o WooCommerce guarda o carrinho num cookie de sessão.
            self.page.context.clear_cookies()
            if not self.abrir(self._produto_atual.url):
                return Frete(ok=False, motivo="não reabriu o produto")
            url_carrinho = self._url_carrinho()
            botao = self.page.locator(".single_add_to_cart_button, button[name='add-to-cart']")
            if not botao.count():
                return Frete(ok=False, motivo="botão de comprar não encontrado")
            botao.first.click(timeout=5_000)
            self.page.wait_for_timeout(2_500)
            if not self.abrir(url_carrinho):
                return Frete(ok=False, motivo="carrinho não abriu")
            problema = self._problema_no_carrinho()
            if problema:
                log.warning("[%s] %s; frete não usado.", self.fornecedor.nome, problema)
                return Frete(ok=False, motivo=problema)

            abrir_calculadora = self.page.locator(".shipping-calculator-button")
            if abrir_calculadora.count() and abrir_calculadora.first.is_visible():
                abrir_calculadora.first.click()
                self.page.wait_for_timeout(800)
            campo = self.page.locator("#calc_shipping_postcode")
            if not campo.count():
                return Frete(ok=False, motivo="carrinho sem calculadora de frete")
            for seletor, valor in (("#calc_shipping_country", "BR"), ("#calc_shipping_state", uf)):
                caixa = self.page.locator(seletor)
                if caixa.count():
                    try:
                        caixa.select_option(valor)
                    except PlaywrightError:
                        log.debug("[%s] Não selecionou %s=%s", self.fornecedor.nome, seletor, valor)
            problema = self.preencher_cep(campo.first, cep)
            if problema:
                return Frete(ok=False, motivo=problema)
            self.page.locator("button[name='calc_shipping']").first.click()
            self.page.wait_for_timeout(ESPERA_FRETE_MS // 2)
            texto = self._texto_do_frete()
            frete = self.interpretar_frete(texto)
            if not frete.ok and "nenhum" in texto.lower():
                frete.motivo = "loja não entrega neste CEP"
            return frete
        except PlaywrightError as exc:
            return Frete(ok=False, motivo=f"erro no carrinho: {exc}")
