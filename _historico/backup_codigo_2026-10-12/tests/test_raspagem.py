"""Testes das regras da raspagem que não dependem de internet."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fgv_precos.raspagem.descricao import interpretar, pontuar  # noqa: E402
from fgv_precos.raspagem.modelos import valor_br_para_float  # noqa: E402
from fgv_precos.raspagem.plataformas.base import LojaBase  # noqa: E402


def test_leitura_descricao():
    i = interpretar("1056", "LIMPEZA PREDIAL", "BALDE PLÁSTICO – 5 L - COM ALÇA.")
    assert i.nomes_busca == ["Balde Plástico"]
    assert (5.0, "l") in i.medidas_obrigatorias
    i = interpretar("1104", "EPI / UNIFORME", "CAMISETA/CAMISA DE UNIFORME - MALHA FRIA")
    assert i.nomes_busca[:2] == ["Camiseta De Uniforme", "Camisa De Uniforme"]
    i = interpretar("1012", "X", "DESODORIZADOR SANITÁRIO/PEDRA SANITÁRIA - COM REDE")
    assert i.nomes_busca[:2] == ["Desodorizador Sanitário", "Pedra Sanitária"]


def test_aderencia():
    i = interpretar("1000", "X", "ÁGUA SANITÁRIA - HIPOCLORITO; USO", "GALÃO 5 L")
    assert pontuar(i, "Água Sanitária Mahju 5L") > 0
    assert pontuar(i, "Água Sanitária 5 Litros Suprema") > 0
    assert pontuar(i, "Água Sanitária Gota Limpa 1L") == 0      # medida errada
    assert pontuar(i, "Alvejante 5L") == 0                       # outro produto
    i = interpretar("1082", "X", "ASPIRADOR DE PÓ – MÍNIMO 1.600 W - USO")
    assert pontuar(i, "Aspirador de Pó 1800W") > 0
    assert pontuar(i, "Aspirador de Pó 1200W") == 0


def test_frete():
    f = LojaBase.interpretar_frete("R$ 45,04 10 dias úteis Jadlog\nR$ 56,33 6 dias úteis PAC")
    assert f.ok and f.valor == 45.04 and not f.gratis
    f = LojaBase.interpretar_frete("Frete grátis acima de R$ 300,00\nSEDEX R$ 30,00 3 dias")
    assert f.valor == 30.0
    assert LojaBase.interpretar_frete("Entrega Grátis 7 dias úteis").gratis
    assert not LojaBase.interpretar_frete("Retirar na loja Grátis").ok
    assert valor_br_para_float("R$ 1.234,56") == 1234.56


def test_motivos_sem_preco():
    from fgv_precos.raspagem.plataformas.base import (
        RE_ESGOTADO,
        RE_PRECO_LOGIN,
        RE_SOB_CONSULTA,
    )
    assert RE_PRECO_LOGIN.search("Faça login para ver o preço")
    assert RE_PRECO_LOGIN.search("Preços exclusivos para clientes cadastrados")
    assert not RE_PRECO_LOGIN.search("Entrar | Minha conta")
    assert RE_SOB_CONSULTA.search("Preço sob consulta")
    assert RE_SOB_CONSULTA.search("Solicite um orçamento")
    assert RE_ESGOTADO.search("Produto esgotado")
    assert not RE_ESGOTADO.search("Frete indisponível para este CEP")


def test_frete_em_varias_linhas_e_ponto_decimal():
    antes = "Água Sanitária 5L - Qboa\nR$ 25,90\nCalcule o frete\nCalcular"
    depois = antes + "\nR$ 59,10\n7 dias úteis\nCorreios PAC\n* Este prazo de entrega..."
    f = LojaBase.interpretar_frete(depois, antes)
    assert f.ok and f.valor == 59.10                     # não pega o preço do produto
    f = LojaBase.interpretar_frete("Econômico: R$ 35.43 - 8 dias úteis")
    assert f.ok and f.valor == 35.43
    f = LojaBase.interpretar_frete("Não existem fretes disponíveis para o CEP informado")
    assert not f.ok and "não entrega" in f.motivo


def test_busca_e_aderencia_posicional():
    i = interpretar("1056", "X", "BALDE PLÁSTICO – 5 L - COM ALÇA.")
    assert i.termos_de_busca == ["Balde Plástico", "Balde"]
    assert pontuar(i, "Balde Plástico 5L com Alça") > 0
    assert pontuar(i, "Conjunto Mop Rotatório (Balde 5L C/Cesto)") == 0


def test_nome_do_card():
    from fgv_precos.raspagem.plataformas.base import melhor_linha
    assert melhor_linha(" (56)\nÁgua Sanitária 5L Suprema\nR$ 11,90\nAdicionar ao carrinho") \
        == "Água Sanitária 5L Suprema"


def test_unidade_lts_e_regras_de_09_10():
    """'5Lts' é 5 litros; aviso de login para ver preço; modal de frete da Cobra."""
    from fgv_precos.raspagem.plataformas.base import RE_FRETE_LOGIN, RE_PRECO_LOGIN
    i = interpretar("1056", "X", "BALDE PLÁSTICO – 5 L - COM ALÇA.")
    assert pontuar(i, "Balde Plástico 5Lts com Alça") > 0
    assert pontuar(i, "Balde Retrátil Perfect Pro 5L 1UN") > 0
    assert RE_PRECO_LOGIN.search("É necessário fazer login para que você possa ver os preços")
    assert RE_FRETE_LOGIN.search("Faça login para calcular o frete")
    f = LojaBase.interpretar_frete(
        "FORMA DE ENVIO\n\t\nVALOR\n\t\nPRAZO\n\nExpresso\tR$ 51,20\tem até 11 dias úteis\n"
        "PAC - Econômico\tR$ 54,29\tem até 13 dias úteis")
    assert f.ok and f.valor == 51.20


def test_busca_descoberta_com_campos_ocultos():
    """Formulário Tray com campo oculto 'loja' (erro do urlencode no log de 09/10)."""
    info = {"acao": "https://www.lojas360.com.br/loja/busca.php", "campo": "palavra_busca",
            "extras": [["loja", "123"], ["acao", "busca"]]}   # formato devolvido pelo JavaScript
    assert LojaBase.modelo_de_busca(info) == (
        "https://www.lojas360.com.br/loja/busca.php?loja=123&acao=busca&palavra_busca={termo}")
