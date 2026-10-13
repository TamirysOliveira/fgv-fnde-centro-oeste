"""Testes das regras puras (sem rede). Rodar com: python -m pytest"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fgv_precos.fornecedores import receita_dump  # noqa: E402
from fgv_precos.fornecedores.cnae import (  # noqa: E402
    cnaes_atacadistas,
    eh_cnae_atacadista,
    formatar_cnae,
    formatar_cnpj,
    validar_cnpj,
)
from fgv_precos.fornecedores.site_checker import (  # noqa: E402
    eh_marketplace,
    site_a_partir_do_email,
)


def test_cnae_divisao_46():
    assert eh_cnae_atacadista("4649408")
    assert eh_cnae_atacadista("46.42-7-02")
    assert not eh_cnae_atacadista("4789005")   # varejo
    assert not eh_cnae_atacadista("")


def test_cnae_principal_ou_secundario():
    assert cnaes_atacadistas("4789005", ["4649408", "4744001"]) == ["4649-4/08 (secundário)"]
    assert cnaes_atacadistas("4642702", []) == ["4642-7/02 (principal)"]
    assert cnaes_atacadistas("4789005", ["4744001"]) == []


def test_formatacao():
    assert formatar_cnae("4649408") == "4649-4/08"
    assert formatar_cnpj("07964337000168") == "07.964.337/0001-68"


def test_validar_cnpj():
    assert validar_cnpj("07.964.337/0001-68")
    assert not validar_cnpj("07.964.337/0001-69")
    assert not validar_cnpj("11111111111111")


def test_marketplace_e_email():
    assert eh_marketplace("https://produto.mercadolivre.com.br/x")
    assert eh_marketplace("www.amazon.com.br")
    assert not eh_marketplace("https://casadalimpeza.net")
    assert site_a_partir_do_email("vendas@empresa.com.br") == "https://empresa.com.br"
    assert site_a_partir_do_email("fulano@gmail.com") is None


def test_mascara_cnae_dump():
    principal = pd.Series(["4789005", "4642702", "4744001"])
    secundaria = pd.Series(["4649408,4744001", "", "4744099"])
    assert receita_dump._tem_cnae_atacadista(principal, secundaria).tolist() == [True, True, False]
