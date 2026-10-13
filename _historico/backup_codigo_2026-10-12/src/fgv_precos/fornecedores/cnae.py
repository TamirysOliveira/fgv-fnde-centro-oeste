"""
Regras de CNAE e CNPJ (funções puras, sem rede — fáceis de testar).
"""

from __future__ import annotations

import re
from typing import Iterable

from fgv_precos.config import PREFIXO_CNAE_ATACADISTA

_SO_DIGITOS = re.compile(r"\D")


def somente_digitos(valor: str | int | None) -> str:
    """Remove tudo que não for dígito. ``None`` vira string vazia."""
    if valor is None:
        return ""
    return _SO_DIGITOS.sub("", str(valor))


def formatar_cnae(codigo: str | int) -> str:
    """Formata um código de subclasse CNAE no padrão IBGE: ``4649-4/08``."""
    d = somente_digitos(codigo).zfill(7)
    return f"{d[:4]}-{d[4]}/{d[5:7]}"


def eh_cnae_atacadista(codigo: str | int | None) -> bool:
    """True se o código pertence à Divisão 46 (comércio atacadista)."""
    d = somente_digitos(codigo)
    return len(d) >= 2 and d.startswith(PREFIXO_CNAE_ATACADISTA)


def cnaes_atacadistas(principal: str | int | None,
                      secundarios: Iterable[str | int] | None) -> list[str]:
    """Devolve os CNAEs atacadistas do CNPJ, já formatados, principal primeiro.

    Regra: o CNAE da Divisão 46 vale tanto como principal quanto secundário.
    """
    encontrados: list[str] = []
    if eh_cnae_atacadista(principal):
        encontrados.append(formatar_cnae(principal) + " (principal)")
    for cod in secundarios or []:
        if eh_cnae_atacadista(cod):
            encontrados.append(formatar_cnae(cod) + " (secundário)")
    return encontrados


def validar_cnpj(cnpj: str | int | None) -> bool:
    """Valida os dígitos verificadores de um CNPJ (14 dígitos)."""
    d = somente_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False

    def _dv(base: str, pesos: list[int]) -> str:
        soma = sum(int(n) * p for n, p in zip(base, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    dv1 = _dv(d[:12], pesos1)
    dv2 = _dv(d[:12] + dv1, pesos2)
    return d[12:] == dv1 + dv2


def formatar_cnpj(cnpj: str | int) -> str:
    """Formata 14 dígitos como ``00.000.000/0000-00``."""
    d = somente_digitos(cnpj).zfill(14)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
