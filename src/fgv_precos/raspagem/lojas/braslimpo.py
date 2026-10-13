"""
Raspagem: Braslimpo Comercial Ltda - CNPJ 65.833.410/0001-69

VTEX IO (plataforma conferida em 09/10/2026).
"""

from fgv_precos.raspagem.plataformas.outras import Vtex

CNPJ = "65833410000169"


class Braslimpo(Vtex):
    """Usa o comportamento padrão da plataforma Vtex."""
