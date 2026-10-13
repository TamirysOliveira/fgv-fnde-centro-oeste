"""
Raspagem: Cobra Indústria e Comércio de Embalagens Ltda - CNPJ 02.949.470/0001-21

Plataforma Dooca. Conferido no navegador em 09/10/2026:
    * busca pelo formulário do site (``/produtos?q=<termo>``), descoberta
      automaticamente;
    * o resultado do frete NÃO aparece ao lado do campo de CEP: abre uma janela
      (modal ``.product-shipping-modal``) com a tabela "FORMA DE ENVIO / VALOR /
      PRAZO". Ex.: Água Sanitária 5 L, R$ 21,72, frete para 74933-130 a partir
      de R$ 51,20 (Expresso).
O print é tirado com a janela do frete aberta.
"""

from playwright.sync_api import Error as PlaywrightError

from fgv_precos.raspagem.config_raspagem import ESPERA_FRETE_MS
from fgv_precos.raspagem.modelos import Frete
from fgv_precos.raspagem.plataformas.base import LojaBase

CNPJ = "02949470000121"


class CobraEmbalagens(LojaBase):
    plataforma = "Dooca"

    def calcular_frete(self, cep: str, uf: str) -> Frete:
        form = self.page.locator("form.product-shipping-form")
        if not form.count():
            return super().calcular_frete(cep, uf)
        try:
            campo = form.first.locator("input[name=zipcode]")
            campo.fill("")
            campo.type(cep, delay=60)
            form.first.locator("button").first.click(timeout=3_000)
            modal = self.page.locator(".product-shipping-modal")
            modal.first.wait_for(state="visible", timeout=ESPERA_FRETE_MS)
            self.page.wait_for_timeout(1_000)
            return self.interpretar_frete(modal.first.inner_text())
        except PlaywrightError as exc:
            return Frete(ok=False, motivo=f"erro ao calcular frete: {exc}")
