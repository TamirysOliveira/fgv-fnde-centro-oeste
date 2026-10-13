"""
Registro das lojas: um arquivo por fornecedor com particularidades.

``loja_para(page, fornecedor)`` devolve a classe certa:
    1. se existe um módulo com o CNPJ do fornecedor, usa a classe dele;
    2. senão, abre a página inicial e detecta a plataforma (Loja Integrada,
       VTEX, Shopify, WooCommerce, Tray, Nuvemshop) ou usa a genérica.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil

from fgv_precos.fornecedores.cnae import somente_digitos
from fgv_precos.raspagem.plataformas.base import LojaBase, detectar_plataforma
from fgv_precos.raspagem.plataformas.loja_integrada import LojaIntegrada
from fgv_precos.raspagem.plataformas.outras import Nuvemshop, Shopify, Tray, Vtex
from fgv_precos.raspagem.plataformas.woocommerce import WooCommerce

log = logging.getLogger(__name__)

POR_PLATAFORMA = {
    "loja_integrada": LojaIntegrada, "vtex": Vtex, "shopify": Shopify,
    "woocommerce": WooCommerce, "tray": Tray, "nuvemshop": Nuvemshop, "generica": LojaBase,
}


def _modulos_por_cnpj() -> dict[str, type[LojaBase]]:
    registro: dict[str, type[LojaBase]] = {}
    for info in pkgutil.iter_modules(__path__):
        modulo = importlib.import_module(f"{__name__}.{info.name}")
        cnpj = getattr(modulo, "CNPJ", "")
        classes = [v for v in vars(modulo).values()
                   if isinstance(v, type) and issubclass(v, LojaBase) and v.__module__ == modulo.__name__]
        if cnpj and classes:
            registro[cnpj] = classes[0]
    return registro


REGISTRO = _modulos_por_cnpj()


def loja_para(page, fornecedor) -> LojaBase:
    classe = REGISTRO.get(somente_digitos(fornecedor.cnpj))
    if classe is None:
        provisoria = LojaBase(page, fornecedor)
        if provisoria._ir(provisoria.base):
            classe = POR_PLATAFORMA[detectar_plataforma(page)]
        else:
            classe = LojaBase
        log.info("[%s] Sem módulo próprio; plataforma detectada: %s",
                 fornecedor.nome, classe.plataforma)
    return classe(page, fornecedor)
