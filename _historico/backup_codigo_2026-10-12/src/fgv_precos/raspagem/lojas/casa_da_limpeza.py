"""
Raspagem: Casa da Limpeza Ltda - CNPJ 07.964.337/0001-68

WooCommerce; frete só no carrinho. Observação do site: entrega em Goiânia e região.
"""

from fgv_precos.raspagem.plataformas.woocommerce import WooCommerce

CNPJ = "07964337000168"


class CasaDaLimpeza(WooCommerce):
    """Usa o comportamento padrão da plataforma WooCommerce."""
