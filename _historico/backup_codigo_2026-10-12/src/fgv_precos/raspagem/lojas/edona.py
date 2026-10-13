"""
Raspagem: E.dona Comércio Eletrônico de Produtos Descartáveis - CNPJ 47.498.059/0001-15

Shopify. Conferido no navegador em 09/10/2026:
    * a calculadora de frete da página do produto (``.product-shipping``,
      campo ``#billing_cep``) existe no código, mas o próprio site a deixa
      oculta (``display: none``). O frete não aparece para o visitante,
      então não pode sair no print -> fornecedor descartado pela regra.
    * o campo ``#cepInput`` é de um modal de endereço geral, não do frete.
Se o site voltar a exibir a calculadora, basta apagar ``calcular_frete`` abaixo.
"""

from fgv_precos.raspagem.modelos import Frete
from fgv_precos.raspagem.plataformas.outras import Shopify

CNPJ = "47498059000115"


class Edona(Shopify):

    def calcular_frete(self, cep: str, uf: str) -> Frete:
        calculadora = self.page.locator(".product-shipping")
        if calculadora.count() and calculadora.first.is_visible():
            return super().calcular_frete(cep, uf)
        return Frete(ok=False, motivo="calculadora de frete oculta pelo próprio site")
