"""Testes das regras da raspagem que não dependem de internet."""


from fgv_precos.precos import valor_br_para_float
from fgv_precos.raspagem.descricao import interpretar, pontuar
from fgv_precos.raspagem.plataformas.base import LojaBase


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


def test_palavra_principal_primeiro_e_prefixos_recusados():
    """Regra de 12/10/2026: a palavra principal abre o nome; kit, tecido etc. são recusados."""
    meia = interpretar("1106", "X", "MEIA - ALGODÃO/POLIAMIDA/ELASTANO; COR PRETA OU AZUL.")
    assert pontuar(meia, "Tecido Meia Malha Pa Azul Claro 1m") == 0
    assert pontuar(meia, "Óculos Meia Clear Antirrisco Incolor") == 0
    luva = interpretar("1109", "X", "LUVA DE PVC - CANO MÉDIO OU LONGO; PARA LIMPEZA.")
    assert pontuar(luva, "Kit 10 Luva Pvc Forrado Cano Longo") == 0
    assert pontuar(luva, "Luva de PVC Sem Forro Palma Áspera 70cm") > 0
    vassoura = interpretar("1099", "X", "VASSOURA DE CERDAS NATURAIS/PALHA - ÁREAS EXTERNAS.")
    assert pontuar(vassoura, "Organizador de Vassouras Para 11 Cabos") == 0
    # A palavra proibida é aceita quando a descrição do insumo a usa.
    refil = interpretar("1004", "X", "ÁLCOOL ETÍLICO 70% EM GEL – REFIL - REFIL PARA DISPENSADOR")
    assert pontuar(refil, "Álcool em Gel Edumax 70% Antisséptico para Mãos Refil 800ml") > 0
    capa = interpretar("1117", "X", "CAPA DE CHUVA - PVC IMPERMEÁVEL, COM CAPUZ")
    assert pontuar(capa, "CAPA P/ CHUVA PVC MORCEGO C/CAPUZ") > 0


def test_produto_recusado_na_revisao_nao_volta(tmp_path):
    """Revisão de 12/10/2026: um link recusado para o insumo não é escolhido de novo."""
    from fgv_precos.raspagem.coletor import Coletor, ler_produtos_recusados, normalizar_url
    from fgv_precos.raspagem.modelos import Candidato, Fornecedor, Produto

    assert normalizar_url("https://www.loja.com.br/luva-pvc/?PID=1") == "loja.com.br/luva-pvc"
    arquivo = tmp_path / "produtos_recusados.csv"
    arquivo.write_text("ID FGV;Fornecedor;Produto;Link;Motivo\n"
                       "1110;Loja;Luva de PVC forrada;https://loja.com.br/luva-pvc;PVC, não látex\n",
                       encoding="utf-8-sig")
    assert ler_produtos_recusados(arquivo) == {"1110": {"loja.com.br/luva-pvc"}}
    assert ler_produtos_recusados(tmp_path / "nao_existe.csv") == {}

    class LojaFalsa:
        fornecedor = Fornecedor(nome="Loja", cnpj="", site="https://loja.com.br")

        def buscar(self, _termo):
            return [Candidato("Luva de PVC forrada", "https://loja.com.br/luva-pvc"),
                    Candidato("Luva de Látex Forrada Amarela", "https://loja.com.br/luva-latex")]

        def ler_produto(self, url):
            return Produto(nome="Luva de Látex Forrada Amarela", url=url, preco_final=5.0)

    coletor = Coletor()
    coletor.recusados = ler_produtos_recusados(arquivo)
    insumo = interpretar("1110", "X", "LUVA DE LÁTEX FORRADA - CANO CURTO; TAMANHOS VARIADOS.")
    escolhido = coletor._escolher_produto(LojaFalsa(), insumo)
    assert escolhido.url == "https://loja.com.br/luva-latex"


def test_teor_faixa_e_atributo_texto():
    """Regras de 13/10/2026: teor, faixa só nas pontas e atributo de texto obrigatório."""
    i = interpretar("1001", "X", "ÁLCOOL ETÍLICO 46,2° LÍQUIDO - USO GERAL.", "GALÃO 5 L")
    assert pontuar(i, "Álcool Líquido Audax 46° Facilita 5L 1 UN") > 0      # 46° vale (decisão)
    assert pontuar(i, "Álcool Etílico Hidratado 46,2 INPM 5 Litros") > 0
    assert pontuar(i, "Álcool líquido 70º - Tupi - 5 Litros") == 0          # outro teor
    assert pontuar(i, "Álcool Líquido Coperalcool 5L") > 0                  # sem teor: conferência
    i = interpretar("1000", "X", "ÁGUA SANITÁRIA - HIPOCLORITO DE SÓDIO, TEOR DE CLORO ATIVO "
                    "ENTRE 2% E 2,5%; USO GERAL.", "GALÃO 5 L")
    assert i.teores == {2.0, 2.5}
    assert pontuar(i, "Água Sanitária 2,5% 5L") > 0
    assert pontuar(i, "Água sanitária 1% 5L") == 0
    i = interpretar("1055", "X", "SODA CÁUSTICA - EM ESCAMAS, CONCENTRAÇÃO MÍNIMA DE 96%; EMBALAGEM.")
    assert pontuar(i, "Soda Cáustica Escamas 99% 1kg") > 0
    assert pontuar(i, "Soda Cáustica 50% 1kg") == 0
    i = interpretar("1032", "X", "PANO DE CHÃO ALVEJADO - 100% ALGODÃO; APROXIMADAMENTE 60 X 80 CM.")
    assert not i.teores                                                     # 100% algodão não é teor
    i = interpretar("1005", "X", "AROMATIZADOR/DESODORIZADOR DE AMBIENTES – AEROSSOL - COM FRAGRÂNCIA.",
                    "FRASCO 300–400 ML")
    assert pontuar(i, "Aromatizador de Ambientes Aerossol 300 ml") > 0     # ponta da faixa
    assert pontuar(i, "Desodorizador de Ambientes Spray 400ml") > 0
    assert pontuar(i, "Desodorizador de Ambientes Aerossol 360ml") == 0    # meio da faixa
    assert pontuar(i, "Aromatizador de Ambientes Difusor Varetas 400ml") == 0  # não é aerossol
    i = interpretar("1066", "X", "LIXEIRA PLÁSTICA – 6 A 8 L - COM TAMPA E PEDAL.")
    assert pontuar(i, "Lixeira Plástica com Pedal 6 Litros") > 0
    assert pontuar(i, "Lixeira Plástica com Pedal 7L") == 0
    i = interpretar("1089", "X", "PÁ COLETORA DE LIXO – CABO LONGO - COM TAMPA.")
    assert pontuar(i, "Pá Coletora de Lixo Cabo Longo") > 0
    assert pontuar(i, "Pá Coletora de Lixo Plástica") > 0                  # 1089: confere no print
    i = interpretar("1005", "X", "AROMATIZADOR DE AMBIENTES – AEROSSOL - COM FRAGRÂNCIA.",
                    "FRASCO 300–400 ML")
    assert pontuar(i, "Aromatizador de Ambientes Gel 400ml") == 0          # demais: obrigatório
    i = interpretar("1091", "X", "PLACA SINALIZADORA – BANHEIRO INTERDITADO - DOBRÁVEL/PORTÁTIL.")
    assert pontuar(i, "Placa Sinalizadora Banheiro Fora de Uso") > 0


def test_1114_respirador_pff2_aceito_como_mascara_descartavel():
    """Decisão de 16/10/2026: respirador/máscara PFF2 descartável vale para o 1114."""
    i = interpretar("1114", "EPI / UNIFORME",
                    "MÁSCARA DE PROTEÇÃO DESCARTÁVEL - USO CONFORME RISCO/ATIVIDADE.")
    assert pontuar(i, "RESPIRADOR PFF2 AZ S/VALV PRO SAFETY - DELTA PLUS CA.38504") > 0
    assert pontuar(i, "Mascara Pff2 sem Válvula Tnt Azul – Deltaplus") > 0
    # os nomes já aceitos continuam valendo
    assert pontuar(i, "MASCARA DESCARTAVEL PFF2 COM VALVULA") > 0
    assert pontuar(i, "Máscara de Proteção PFF1 - Sem Válvula - CA 45020") > 0
    # respirador reutilizável (sem PFF2) continua fora
    assert pontuar(i, "Respirador Semi Facial 6200 3M") == 0
    # a alternativa vale só para o 1114
    outro = interpretar("1113", "EPI / UNIFORME", "ÓCULOS DE PROTEÇÃO - INCOLOR.")
    assert pontuar(outro, "RESPIRADOR PFF2 AZ S/VALV") == 0


def test_1001_aceita_46_2_46_e_54():
    """15/10/2026 (William): para o 1001 valem 46,2°, 46° e 54%; 70° continua fora."""
    i = interpretar("1001", "LIMPEZA E HIGIENE", "ÁLCOOL ETÍLICO 46,2° LÍQUIDO - USO GERAL.")
    assert pontuar(i, "Álcool Etílico 46,2° Líquido 5L") > 0
    assert pontuar(i, "Álcool Líquido 46° 1L") > 0
    assert pontuar(i, "Álcool Etílico 54% Líquido 1L") > 0
    assert pontuar(i, "Álcool Líquido 70° 5L") == 0


def test_1107_sapato_tenis_bota_botina():
    """16/10/2026: sapato = calçado; tênis, bota e botina de segurança valem para o 1107."""
    i = interpretar("1107", "EPI / UNIFORME", "CALÇADO DE SEGURANÇA ANTIDERRAPANTE - PROTEÇÃO "
                    "CONTRA AGENTES MECÂNICOS; IMPERMEÁVEL QUANDO APLICÁVEL.")
    assert pontuar(i, "SAPATO IMPERMEAVEL ANTIDERRAPANTE PRETO MAN 41 - STICKY SHOES CA.39674") > 0
    assert pontuar(i, "Tênis de Segurança Sticky Shoe Copa Branco Ca 44589 Antiderrapante") > 0
    assert pontuar(i, "Bota EVA BB87 Cano Longo Preta CA 42632 - Soft Works | Antiderrapante e Segurança") > 0
    assert pontuar(i, "Botina de Segurança Elástica Preta 70B19-E-BP - Marluvas") > 0
    # bota de PVC comum (sem "segurança"/"antiderrapante") fica para o 1108
    assert pontuar(i, "Bota PVC 82BPC600 Cano Curto Preta - Bracol") == 0
    # "Sapato Flex Clean" não traz nem "antiderrapante" nem "segurança"
    assert pontuar(i, "Sapato Flex Clean 101 – Preto – Marluvas") == 0
