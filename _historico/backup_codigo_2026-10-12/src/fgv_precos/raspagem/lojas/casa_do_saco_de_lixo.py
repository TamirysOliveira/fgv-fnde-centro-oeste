"""
Raspagem: K.M Comércio de Embalagens e Produtos de Limpeza Ltda (Casa do Saco de Lixo) - CNPJ 02.236.630/0001-95

Loja Integrada (plataforma conferida em 09/10/2026).
"""

from fgv_precos.raspagem.plataformas.loja_integrada import LojaIntegrada

CNPJ = "02236630000195"


class CasaDoSacoDeLixo(LojaIntegrada):
    """Usa o comportamento padrão da plataforma LojaIntegrada."""
