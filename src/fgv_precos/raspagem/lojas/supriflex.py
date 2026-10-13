"""
Raspagem: Supriflex Suprimentos Online Ltda - CNPJ 46.412.993/0001-00

Loja Integrada; busca, preço e frete conferidos no navegador em 09/10/2026.
"""

from fgv_precos.raspagem.plataformas.loja_integrada import LojaIntegrada

CNPJ = "46412993000100"


class Supriflex(LojaIntegrada):
    """Usa o comportamento padrão da plataforma LojaIntegrada."""
