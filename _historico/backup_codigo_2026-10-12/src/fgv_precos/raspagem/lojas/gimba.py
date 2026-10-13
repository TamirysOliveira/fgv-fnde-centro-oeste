"""
Raspagem: SupriCorp Suprimentos Ltda (Gimba) - CNPJ 54.651.716/0011-50

Loja própria (ASP.NET). Conferido no navegador em 09/10/2026:
    * a busca não usa formulário GET; a URL é ``/?txt-busca=<termo>&btn-buscar=Buscar``
      (``/busca?q=`` devolve erro 404);
    * a página do produto tem JSON-LD (nome e preço) e a calculadora de frete
      ("Digite seu CEP" + "Calcular"). Ex.: Balde Retrátil Perfect Pro 5L,
      R$ 38,99, frete para 74933-130 a partir de R$ 32,87 (Correios PAC).
"""

from urllib.parse import quote_plus

from fgv_precos.raspagem.plataformas.base import LojaBase

CNPJ = "54651716001150"


class Gimba(LojaBase):
    plataforma = "Gimba (própria)"

    def url_busca(self, termo: str) -> str:
        return f"{self.base}/?txt-busca={quote_plus(termo)}&btn-buscar=Buscar"
