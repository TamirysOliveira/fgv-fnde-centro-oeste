"""
Demais plataformas: VTEX, Shopify, Tray e Nuvemshop.

Só mudam a URL de busca e a forma de listar resultados; preço (JSON-LD) e
frete (calculadora da página do produto) usam o comportamento genérico.
"""

from __future__ import annotations

from urllib.parse import quote, quote_plus

from fgv_precos.raspagem.modelos import Candidato
from fgv_precos.raspagem.plataformas.base import LojaBase, melhor_linha


def _links(page, seletor: str, filtro_href: str) -> list[Candidato]:
    itens = page.eval_on_selector_all(
        seletor,
        """(els, f) => els.filter(a => a.href && a.href.includes(f))
               .map(a => ({n: (a.innerText || a.title || a.getAttribute('aria-label') || '').trim(),
                           u: a.href.split('?')[0]}))""",
        filtro_href)
    vistos, saida = set(), []
    for it in itens:
        nome = melhor_linha(it["n"])
        if it["u"] in vistos or len(nome) < 4:
            continue
        vistos.add(it["u"])
        saida.append(Candidato(nome=nome, url=it["u"]))
    return saida


class Vtex(LojaBase):
    """VTEX IO (ex.: Braslimpo). Busca por texto livre: /<termo>?_q=<termo>&map=ft."""
    plataforma = "VTEX"

    def url_busca(self, termo: str) -> str:
        return f"{self.base}/{quote(termo)}?_q={quote(termo)}&map=ft"

    def extrair_resultados(self) -> list[Candidato]:
        self.page.wait_for_timeout(2_000)       # vitrine VTEX é montada por JavaScript
        return _links(self.page, "a[class*='product-summary'], section a[href$='/p']", "/p")


class Shopify(LojaBase):
    """Shopify (ex.: e.dona). Busca: /search?q=<termo>&type=product."""
    plataforma = "Shopify"

    def url_busca(self, termo: str) -> str:
        return f"{self.base}/search?q={quote_plus(termo)}&type=product"

    def extrair_resultados(self) -> list[Candidato]:
        self.page.wait_for_timeout(2_000)
        return _links(self.page, "a[href*='/products/']", "/products/")


class Tray(LojaBase):
    """Tray. A busca exige o número da loja (``/loja/busca.php?loja=<n>&palavra_busca=``),
    que é lido do formulário de busca do próprio site (ver ``LojaBase._descobrir_busca``).
    Conferido em lojas360.com.br em 09/10/2026."""
    plataforma = "Tray"


class Nuvemshop(LojaBase):
    """Nuvemshop. Busca descoberta no formulário do site; produtos em /produtos/."""
    plataforma = "Nuvemshop"

    def extrair_resultados(self) -> list[Candidato]:
        return _links(self.page, "a[href*='/produtos/']", "/produtos/")
