"""
Registro da pesquisa manual de fornecedores (out/2026), Centro-Oeste.

Gera ``data/curated/fornecedores_centro_oeste.csv`` com os fornecedores
conferidos um a um: site visitado, preço visível conferido e CNPJ/CNAE
consultado em base pública da Receita (fonte registrada na coluna "Fonte").
Mantido como script, e não só como CSV, para que cada entrada fique
versionada e auditável no Git.

Nada aqui é estimado: campo não encontrado na fonte fica vazio ("").
"""

from __future__ import annotations

import csv

from fgv_precos.config import ARQ_FORNECEDORES_CURADOS, COLUNAS_SAIDA

LH, LP, EPI = "LIMPEZA E HIGIENE", "LIMPEZA PREDIAL", "EPI / UNIFORME"
ECONODATA = "https://www.econodata.com.br/consulta-empresa/{}"
CNPJWS = "https://publica.cnpj.ws/cnpj/{}"
OBS_FORA = ("Fornecedor fora de GO/DF: completa as cestas de GO e DF porque a meta "
            "de 5 fornecedores com preço visível não foi atingida localmente.")

# ---------------------------------------------------------------------------
# Empresas (dados comuns a todos os grupos em que aparecem)
# ---------------------------------------------------------------------------
EMPRESAS: dict[str, dict[str, str]] = {
    "casa_limpeza": {
        "Estado": "GO", "Cidade": "Goiânia", "Nome da Empresa": "CASA DA LIMPEZA LTDA",
        "CNPJ": "07.964.337/0001-68", "CNAE atacadista": "4649-4/08 (secundário)",
        "Site Oficial": "https://casadalimpeza.net", "Telefone": "(62) 3942-2020",
        "E-mail Comercial": "",
        "Endereço": "Av. T-63, nº 2761, Qd. 358, Lt. 3/4, Jardim América, Goiânia - GO, 74250-325",
        "Fonte": "https://casadalimpeza.net/loja/ | " + CNPJWS.format("07964337000168"),
        "Atende UF": "GO",
    },
    "stars": {
        "Estado": "MT", "Cidade": "Várzea Grande",
        "Nome da Empresa": "J. F. DE MEDEIROS LTDA (Stars Produtos de Limpeza)",
        "CNPJ": "58.509.800/0001-12",
        "CNAE atacadista": "4649-4/09 (principal); 4649-4/08 (secundário)",
        "Site Oficial": "https://www.starsprodutosdelimpeza.com.br",
        "Telefone": "(65) 3364-1038", "E-mail Comercial": "",
        "Endereço": "Av. Gonçalo Botelho de Campos, 2844, Cristo Rei, Várzea Grande - MT, 78118-071",
        "Fonte": "https://www.starsprodutosdelimpeza.com.br | " + ECONODATA.format("58509800000112"),
        "Atende UF": "GO/DF",
    },
    "braslimpo": {
        "Estado": "SP", "Cidade": "Guarulhos", "Nome da Empresa": "BRASLIMPO COMERCIAL LTDA",
        "CNPJ": "65.833.410/0001-69",
        "CNAE atacadista": "4693-1/00 (principal); 4649-4/08, 4686-9/02 e outros (secundários)",
        "Site Oficial": "https://www.lojabraslimpo.com.br", "Telefone": "(11) 2081-8000",
        "E-mail Comercial": "sacecommerce@braslimpo.com.br",
        "Endereço": "Av. Lauro de Gusmão Silveira, 158, Jardim São Geraldo, Guarulhos - SP, 07140-010",
        "Fonte": "https://www.lojabraslimpo.com.br | " + CNPJWS.format("65833410000169"),
        "Atende UF": "GO/DF",
    },
    "supriflex": {
        "Estado": "RS", "Cidade": "Porto Alegre",
        "Nome da Empresa": "SUPRIFLEX SUPRIMENTOS ONLINE LTDA", "CNPJ": "46.412.993/0001-00",
        "CNAE atacadista": "4642-7/02 e 4649-4/08 (secundários)",
        "Site Oficial": "https://www.supriflex.com.br", "Telefone": "(51) 3779-4304",
        "E-mail Comercial": "supriflex@supriflex.com.br",
        "Endereço": "Rua Enes Bandeira, 45, Cristo Redentor, Porto Alegre - RS, 91040-330",
        "Fonte": "https://www.supriflex.com.br | " + CNPJWS.format("46412993000100"),
        "Atende UF": "GO/DF",
    },
    "edona": {
        "Estado": "SP", "Cidade": "São Paulo",
        "Nome da Empresa": "E.DONA COMERCIO ELETRONICO DE PRODUTOS DESCARTAVEIS",
        "CNPJ": "47.498.059/0001-15",
        "CNAE atacadista": "4646-0/02, 4647-8/01, 4641-9/02 e outros (secundários)",
        "Site Oficial": "https://edona.com.br", "Telefone": "(11) 2723-4550",
        "E-mail Comercial": "",
        "Endereço": "Rua Professor Hasegawa, 250, Galpão 01, Sala 01, São Paulo - SP, 08260-090",
        "Fonte": "https://edona.com.br | " + ECONODATA.format("47498059000115"),
        "Atende UF": "GO/DF",
    },
    "km": {
        "Estado": "PR", "Cidade": "Curitiba",
        "Nome da Empresa": "K.M COMERCIO DE EMBALAGENS E PRODUTOS DE LIMPEZA LTDA (Casa do Saco de Lixo)",
        "CNPJ": "02.236.630/0001-95",
        "CNAE atacadista": "4649-4/08, 4686-9/02, 4646-0/02 e outros (secundários)",
        "Site Oficial": "https://loja.casadosacodelixo.com.br", "Telefone": "(41) 3044-3939",
        "E-mail Comercial": "vendas@casadosacodelixo.com.br",
        "Endereço": "Rua Tenente Francisco Ferreira de Souza, 1052, Hauer, Curitiba - PR, 81630-010",
        "Fonte": "https://loja.casadosacodelixo.com.br | " + ECONODATA.format("02236630000195"),
        "Atende UF": "GO/DF",
    },
    "anhanguera": {
        "Estado": "SP", "Cidade": "Campinas",
        "Nome da Empresa": "ANHANGUERA COMERCIO DE FERRAMENTAS LTDA", "CNPJ": "00.565.813/0001-29",
        "CNAE atacadista": "4672-9/00 (principal)",
        "Site Oficial": "https://www.anhangueraferramentas.com.br", "Telefone": "(19) 3116-4000",
        "E-mail Comercial": "vendas@anhangueraferramentas.com.br",
        "Endereço": "Rua Ronald Cladstone Negri, 375, Campinas - SP, 13069-472",
        "Fonte": "https://www.anhangueraferramentas.com.br | " + ECONODATA.format("00565813000129"),
        "Atende UF": "GO/DF",
    },
    "mundo_azul": {
        "Estado": "PR", "Cidade": "Curitiba",
        "Nome da Empresa": "MUNDO AZUL COMERCIO E SERVICOS LTDA", "CNPJ": "15.536.864/0001-08",
        "CNAE atacadista": "4663-0/00 (principal)",
        "Site Oficial": "https://lojamundoazul.com.br", "Telefone": "(41) 3151-0055",
        "E-mail Comercial": "",
        "Endereço": "Rua das Carmelitas, 3033, Boqueirão, Curitiba - PR, 81650-060",
        "Fonte": "https://lojamundoazul.com.br | " + ECONODATA.format("15536864000108"),
        "Atende UF": "GO/DF",
    },
    "bhz": {
        "Estado": "MG", "Cidade": "Belo Horizonte",
        "Nome da Empresa": "BHZ EPI DISTRIBUIDORA LTDA", "CNPJ": "31.893.116/0001-20",
        "CNAE atacadista": "4642-7/02 (principal); 4643-5/01, 4672-9/00 e outros (secundários)",
        "Site Oficial": "https://www.loja.bhzepi.com.br", "Telefone": "(31) 2522-2378",
        "E-mail Comercial": "vendedor.ecommerce@bhzepi.com.br",
        "Endereço": "Rua Messias Coutinho, 93, Céu Azul, Belo Horizonte - MG, 31580-400",
        "Fonte": "https://www.loja.bhzepi.com.br | " + CNPJWS.format("31893116000120"),
        "Atende UF": "GO/DF",
    },
    "lojas360": {
        "Estado": "SP", "Cidade": "Limeira",
        "Nome da Empresa": "LOJAS 360 INDUSTRIA, COMERCIO, IMPORTACAO, EXPORTACAO LTDA",
        "CNPJ": "27.061.442/0002-85",
        "CNAE atacadista": "4642-7/02, 4643-5/01, 4672-9/00 e outros (secundários)",
        "Site Oficial": "https://www.lojas360.com.br", "Telefone": "(19) 99913-4899",
        "E-mail Comercial": "contato@epi360.com.br",
        "Endereço": "Rua Paschoal Pinto Ferraz, 335, Jardim Senador Vergueiro, Limeira - SP, 13482-379",
        "Fonte": "https://www.lojas360.com.br | " + ECONODATA.format("27061442000285"),
        "Atende UF": "GO/DF",
    },
    "seguranca_total": {
        "Estado": "SP", "Cidade": "Mogi Guaçu",
        "Nome da Empresa": "SEGURANCA TOTAL EPIS LTDA", "CNPJ": "39.268.527/0001-37",
        "CNAE atacadista": "4642-7/02, 4649-4/99, 4669-9/99 e outros (secundários)",
        "Site Oficial": "https://www.segurancatotal.com.br", "Telefone": "(19) 99844-4508",
        "E-mail Comercial": "atendimento@segurancatotal.com.br",
        "Endereço": "Rua Tomé de Souza, 115, Vila Paraíso, Mogi Guaçu - SP, 13843-006",
        "Fonte": "https://www.segurancatotal.com.br | " + ECONODATA.format("39268527000137"),
        "Atende UF": "GO/DF",
    },
    "singular": {
        "Estado": "SP", "Cidade": "Atibaia",
        "Nome da Empresa": "SINGULAR COMERCIO DE EQUIPAMENTOS DE PROTECAO INDIVIDUAL LTDA (Loja do EPI)",
        "CNPJ": "20.838.307/0001-73", "CNAE atacadista": "4642-7/02 (principal)",
        "Site Oficial": "https://www.lojadoepi.com.br", "Telefone": "(11) 4413-0092",
        "E-mail Comercial": "atendimento@lojadoepi.com.br",
        "Endereço": "Av. Dom Pedro II, 637, Atibaia - SP, 12950-090",
        "Fonte": "https://www.lojadoepi.com.br | " + ECONODATA.format("20838307000173"),
        "Atende UF": "GO/DF",
    },
}

# (grupo, chave da empresa, link do catálogo, observação específica)
VALIDOS: list[tuple[str, str, str, str]] = [
    # LIMPEZA E HIGIENE
    (LH, "casa_limpeza", "https://casadalimpeza.net/loja/",
     "Químicos, descartáveis e papéis com preço no site (ex.: Alvejante Deoline 1 L R$ 18,90 em out/2026). "
     "E-mail comercial não publicado no site."),
    (LH, "stars", "https://www.starsprodutosdelimpeza.com.br",
     "Centro-Oeste. Ex.: Água Sanitária 1 L R$ 3,50 em out/2026. " + OBS_FORA),
    (LH, "braslimpo", "https://www.lojabraslimpo.com.br/limpeza-profissional/produtos-de-limpeza-profissional",
     OBS_FORA),
    (LH, "supriflex", "https://www.supriflex.com.br/87847362534",
     "Ex.: Desinfetante Marqui 5 L R$ 14,38 em out/2026. " + OBS_FORA),
    (LH, "edona", "https://edona.com.br",
     "Ex.: Papel Toalha Interfolha Toppel R$ 8,70 em out/2026. " + OBS_FORA),
    (LH, "km", "https://loja.casadosacodelixo.com.br/produtos-de-limpeza",
     "Razão social no rodapé do site difere da Receita (vale a da Receita). " + OBS_FORA),
    # LIMPEZA PREDIAL
    (LP, "casa_limpeza", "https://casadalimpeza.net/loja/",
     "Carrinhos, mops, rodos, vassouras, lixeiras, dispensers e escadas (ex.: Carro Funcional América "
     "R$ 1.165,00 em out/2026). Baldes, aspiradores e enceradeiras não apareceram na listagem."),
    (LP, "stars", "https://www.starsprodutosdelimpeza.com.br",
     "Centro-Oeste. Baldes, mops, vassouras, rodos, máquinas de piso e placas de sinalização. " + OBS_FORA),
    (LP, "supriflex",
     "https://www.supriflex.com.br/balde-com-espremedor-2-aguas-20-litros-amarelo-superpro-bettanin-ref-sp90105",
     "Baldes, carro funcional, vassouras, rodos, pás, lixeiras e dispensadores. " + OBS_FORA),
    (LP, "braslimpo", "https://www.lojabraslimpo.com.br",
     "Baldes e dispensers (ex.: Balde 5 L Kunber R$ 63,29 em out/2026). " + OBS_FORA),
    (LP, "anhanguera", "https://www.anhangueraferramentas.com.br/fabricante/karcher",
     "Aspiradores e lavadoras Kärcher (ex.: Aspirador NT 3000 R$ 717,08 em out/2026). " + OBS_FORA),
    (LP, "mundo_azul", "https://lojamundoazul.com.br/karcher-goiania/",
     "Lavadoras de alta pressão Kärcher (ex.: K2 R$ 499,99 em out/2026). E-mail oculto no site. " + OBS_FORA),
    # EPI / UNIFORME
    (EPI, "casa_limpeza", "https://casadalimpeza.net/loja/",
     "Somente calçados e luvas (ex.: Bota Branca Cano Curto R$ 51,90 em out/2026). Não vende uniformes."),
    (EPI, "bhz", "https://www.loja.bhzepi.com.br",
     "Botas, luvas, óculos, uniformes. " + OBS_FORA),
    (EPI, "lojas360", "https://www.lojas360.com.br",
     "Luvas, calçados, óculos, proteção auditiva, sinalização. " + OBS_FORA),
    (EPI, "seguranca_total", "https://www.segurancatotal.com.br/produto/"
     "kit-epi-completo-protecao-trabalho-servicos-gerais-botina-oculos-protetor-luva.html",
     "Pede identificação só para fechar pedido; preço visível sem login. " + OBS_FORA),
    (EPI, "singular", "https://www.lojadoepi.com.br",
     "Bota PVC, luvas, óculos, protetor auricular, avental, uniformes. " + OBS_FORA),
    (EPI, "supriflex", "https://www.supriflex.com.br/luva-latex-multiuso-flex-vabene-amarela-p",
     "Luvas e EPIs; botas não confirmadas no site. " + OBS_FORA),
]

# Atacadistas/distribuidores de GO e DF com catálogo, mas SEM preço visível
# (regra 3). Ficam só como referência. (grupo, UF, cidade, nome, cnpj, cnae,
# site, telefone, email, endereço, observação)
REFERENCIA: list[tuple[str, ...]] = [
    (EPI, "DF", "Brasília", "W2 COMERCIAL LTDA (Vulcão da Borracha)", "03.809.833/0001-96",
     "4642-7/02, 4661-3/00, 4665-6/00 (secundários)", "https://www.vulcaodaborracha.com.br",
     "(61) 3012-8750", "pedidos@vulcaodaborracha.com.br",
     "SIA Q 5 C Loja 1, Guará, Brasília - DF, 71200-055",
     "Catálogo com 188 EPIs, todos 'Sob consulta'. CNAE conferido em monitorcnpj.com.br.",
     "https://www.vulcaodaborracha.com.br/epis-brasilia-df | https://monitorcnpj.com.br/cnpj/03809833000196/"),
    (EPI, "GO", "Goiânia", "Rede EPI", "", "", "https://redeepi.com.br", "(62) 3924-0700", "", "",
     "Atende Goiânia e Brasília (WhatsApp DF (61) 98325-1791). Catálogo sem preço (orçamento). "
     "CNPJ não publicado no site; CNAE não verificado.", "https://redeepi.com.br"),
    (EPI, "GO", "Goiânia", "Mega EPI", "18.302.957/0001-58", "", "https://megaepi.com.br",
     "(62) 3275-9122", "vendas1@megaepi.com.br", "",
     "Catálogo sem preço. CNAE não verificado.", "https://megaepi.com.br"),
    (EPI, "GO", "Goiânia", "Mais Segurança", "43.903.641/0001-69", "",
     "https://lp.maisseguranca.online", "(62) 98147-7897", "contato@maissegurancaepi.online",
     "Rua JG05, 147, Qd. 5, Lt. 24, Jardim Gramado, Goiânia - GO, 74583-705",
     "Compra só via WhatsApp, sem preço no site. CNAE não verificado.",
     "https://lp.maisseguranca.online"),
    (LH, "GO", "Aparecida de Goiânia", "Super Pack", "24.982.773/0001-89", "",
     "https://superpackdistribuidora.com.br", "(62) 3622-8636", "", "",
     "Preços só após contato. Filiais em Goiânia. CNAE não verificado.",
     "https://superpackdistribuidora.com.br"),
    (LH, "GO", "Goiânia", "Neoclean", "", "", "https://neoclean.com.br", "(62) 3932-0202",
     "contato@neoclean.com.br",
     "Rua FP 30, nº 50, Qd. 33, Lts. 13/15, Recreio do Funcionário Público, Goiânia - GO, 74393-280",
     "Químicos e equipamentos sem preço no site. CNPJ não publicado; CNAE não verificado.",
     "https://neoclean.com.br"),
    (LP, "GO", "Goiânia", "Neoclean", "", "", "https://neoclean.com.br", "(62) 3932-0202",
     "contato@neoclean.com.br",
     "Rua FP 30, nº 50, Qd. 33, Lts. 13/15, Recreio do Funcionário Público, Goiânia - GO, 74393-280",
     "86 equipamentos no catálogo, sem preço. CNPJ não publicado; CNAE não verificado.",
     "https://neoclean.com.br"),
    (LH, "GO", "Goiânia", "Clean Paper Produtos e Equipamentos de Limpeza Ltda", "", "",
     "https://cleanpaper.com.br", "(62) 3999-4872", "faleconosco@cleanpaper.com.br",
     "Rua 07, Qd. 22, Lt. 01, Sala 01, Jardim Santo Antônio, Goiânia - GO, 74853-200",
     "Só orçamento. CNPJ não publicado; CNAE não verificado.", "https://cleanpaper.com.br"),
    (LH, "GO", "Aparecida de Goiânia", "Nacional Suprimentos", "", "",
     "https://www.nacionalsuprimentos.com.br", "(62) 3277-4522", "",
     "Av. Chevalier Nami Jafet, Qd. 36, Lt. 03, Vila Mariana, Aparecida de Goiânia - GO",
     "Só orçamento. CNPJ não publicado; CNAE não verificado.",
     "https://www.nacionalsuprimentos.com.br"),
    (LH, "GO", "Goiânia", "Goiás Atacado Distribuidor", "", "", "https://www.goiasatacado.com.br",
     "", "", "", "Loja com cadastro/login; preço não aparece sem entrar. CNAE não verificado.",
     "https://www.goiasatacado.com.br/limpeza"),
    (LH, "DF", "Brasília", "Rei da Limpeza DF", "", "", "https://www.reidalimpezadf.com.br",
     "(61) 3532-6346", "vendas@reidalimpezadf.com.br",
     "QNH 09, Lote 01, Loja 03, Taguatinga Norte, Brasília - DF, 72130-590",
     "Sem preço no site. CNPJ não publicado; CNAE não verificado.",
     "https://www.reidalimpezadf.com.br"),
    (LH, "DF", "Brasília", "Lumiar Distribuidora", "", "", "https://www.distribuidoralumiar.com.br",
     "(61) 98184-8048", "vendas@distribuidoralumiar.com.br",
     "QR 508, Conjunto 02, Casa 25, Samambaia Sul, Brasília - DF, 72312-302",
     "Pedidos por WhatsApp, sem preço. CNPJ não publicado; CNAE não verificado.",
     "https://www.distribuidoralumiar.com.br"),
]

# Têm preço visível, mas o CNPJ não foi localizado: NÃO usar até validar.
PENDENTES: list[tuple[str, ...]] = [
    (LH, "SP", "Santo André", "Nova Limp Comércio de Embalagens e Descartáveis", "", "",
     "https://www.novalimp.com.br", "(11) 2139-7300", "comercial@novalimp.com.br",
     "Rua Xingu, 1210, Santo André - SP",
     "Preço visível (ex.: Rodo 40 cm R$ 4,37). CNPJ não publicado no site: CNAE não verificado.",
     "https://www.novalimp.com.br"),
    (EPI, "SP", "Embu das Artes", "Renascer EPI", "", "", "https://www.renascerepi.com.br",
     "(11) 4244-1211", "contato@renascerepi.com.br", "Rua Coxim, 185, Embu das Artes - SP",
     "Preço visível (ex.: Luva Nitril Volk R$ 8,32). CNPJ não publicado no site: CNAE não verificado.",
     "https://www.renascerepi.com.br"),
]

# ---------------------------------------------------------------------------
# Empresas incluídas em 09/10/2026. CNPJ, CNAE, endereço e telefone conferidos
# na base pública da Receita (publica.cnpj.ws) em 09/10/2026.
#   * As 15 primeiras vieram da lista_sites.xlsx da equipe (guias EPI e
#     UNIFORME) e já estavam na FNDE_EPI_UNIFORME.xlsx, mas não neste
#     registro (um 'exportar' as apagaria). Todas têm CNAE da Divisão 46.
#   * Gimba, NC Bella e Cobra: pesquisa de 09/10/2026 (site, preço, produto e
#     frete para o CEP 74933-130 conferidos no navegador).
# E-mail só quando é do domínio da empresa e não é de contabilidade/fiscal.
# ---------------------------------------------------------------------------
EMPRESAS.update({
    "zen": {
        "Estado": "PR", "Cidade": "Curitiba",
        "Nome da Empresa": "ZEN UNIFORMES LTDA (Zengo Uniformes)",
        "CNPJ": "22.692.670/0001-59", "CNAE atacadista": "4642-7/02 (secundário)",
        "Site Oficial": "https://zengouniformes.com.br", "Telefone": "(41) 3117-4992",
        "E-mail Comercial": "",
        "Endereço": "Rua Hélio Dirceu Woitikiw, 121, Pinheirinho, Curitiba - PR, 81870-350",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("22692670000159"),
        "Atende UF": "GO/DF",
    },
    "zeus": {
        "Estado": "SC", "Cidade": "Blumenau",
        "Nome da Empresa": "ZEUS DO BRASIL LTDA (loja EPI Zeus)",
        "CNPJ": "82.699.588/0001-88", "CNAE atacadista": "4642-7/02 (principal); 4649-4/01, 4649-4/02, 4649-4/06, 4652-4/00 e outros (secundários)",
        "Site Oficial": "zeusdobrasil.com.br / epizeus.com.br", "Telefone": "(47) 3231-1111",
        "E-mail Comercial": "contato@zeusdobrasil.com.br",
        "Endereço": "Rodovia BR 470, 8484, Km 63, Sala 02, Badenfurt, Blumenau - SC, 89070-200",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("82699588000188"),
        "Atende UF": "GO/DF",
    },
    "agil": {
        "Estado": "PR", "Cidade": "Curitiba",
        "Nome da Empresa": "AGIL DISTRIBUIDORA DE GAS E CONFECCOES LTDA (Agil Uniformes)",
        "CNPJ": "62.783.106/0001-66", "CNAE atacadista": "4642-7/02, 4649-4/02 (secundários)",
        "Site Oficial": "https://agiluniformes.com.br", "Telefone": "(41) 3030-2332",
        "E-mail Comercial": "",
        "Endereço": "Av. Manoel Ribas, 7600, Butiatuvinha, Curitiba - PR, 82320-750",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("62783106000166"),
        "Atende UF": "GO/DF",
    },
    "superpro": {
        "Estado": "SC", "Cidade": "Garuva",
        "Nome da Empresa": "SUPER-PRO COMERCIO DE EQUIPAMENTOS E FERRAMENTAS LTDA (Super Pro Atacado / Ferramentas Kennedy)",
        "CNPJ": "08.858.579/0015-35", "CNAE atacadista": "4672-9/00 (principal); 4642-7/02, 4647-8/01, 4649-4/02, 4661-3/00 e outros (secundários)",
        "Site Oficial": "https://superproatacado.com.br", "Telefone": "(41) 2109-8000",
        "E-mail Comercial": "",
        "Endereço": "Rodovia Contorno Sul de Garuva Sidney Pensky, 8661, Setor 13, Palmital, Garuva - SC, 89248-000",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("08858579001535"),
        "Atende UF": "GO/DF",
    },
    "multiseg": {
        "Estado": "SC", "Cidade": "Joinville",
        "Nome da Empresa": "MULTISEG COMERCIO DE EQUIPAMENTOS DE SEGURANCA LTDA",
        "CNPJ": "10.498.304/0001-84", "CNAE atacadista": "4642-7/02 (principal); 4669-9/99, 4679-6/04, 4679-6/99, 4689-3/99 (secundários)",
        "Site Oficial": "https://multiseg.com.br", "Telefone": "(47) 3426-1212",
        "E-mail Comercial": "multiseg@multisegonline.com.br",
        "Endereço": "Rua São Paulo, 3393, Itaum, Joinville - SC, 89210-001",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("10498304000184"),
        "Atende UF": "GO/DF",
    },
    "astro": {
        "Estado": "SC", "Cidade": "Criciúma",
        "Nome da Empresa": "ASTRO DISTRIBUIDORA LTDA",
        "CNPJ": "18.597.685/0001-60", "CNAE atacadista": "4642-7/02 (principal); 4673-7/00, 4679-6/99 (secundários)",
        "Site Oficial": "https://astrodistribuidora.com", "Telefone": "(48) 3045-7562",
        "E-mail Comercial": "vendas@astrodistribuidora.com",
        "Endereço": "Rodovia Otávio Dassoler, 3790, Pavilhão 01, Lotes 06 e 07, Linha Batista, Criciúma - SC, 88812-850",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("18597685000160"),
        "Atende UF": "GO/DF",
    },
    "artlimp": {
        "Estado": "SP", "Cidade": "Mogi Guaçu",
        "Nome da Empresa": "ART LIMP BRASIL -DISTRIBUICAO - GESTAO E LOGISTICA LTDA (Art Limp Brasil - Distribuicao - Gestao e Logistica Ltda)",
        "CNPJ": "13.186.075/0001-50", "CNAE atacadista": "4637-1/01, 4637-1/02, 4637-1/99, 4641-9/03 e outros (secundários)",
        "Site Oficial": "https://artlimpbrasil.com.br", "Telefone": "(19) 3851-4000",
        "E-mail Comercial": "contato@artlimpbrasil.com.br",
        "Endereço": "Rua Manoel Mendes, 407, Vila Pinheiro, Mogi Guaçu - SP, 13845-284",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("13186075000150"),
        "Atende UF": "GO/DF",
    },
    "livpro": {
        "Estado": "SP", "Cidade": "Mogi das Cruzes",
        "Nome da Empresa": "LIVPRO LTDA",
        "CNPJ": "60.147.971/0001-90", "CNAE atacadista": "4642-7/01, 4642-7/02, 4643-5/01, 4646-0/01 e outros (secundários)",
        "Site Oficial": "https://livpro.com.br", "Telefone": "(11) 4799-0399",
        "E-mail Comercial": "",
        "Endereço": "Av. Valentina Mello Freire Borenstein, 450, Letra A, Vila São Francisco, Mogi das Cruzes - SP, 08735-270",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("60147971000190"),
        "Atende UF": "GO/DF",
    },
    "acb": {
        "Estado": "SP", "Cidade": "São Paulo",
        "Nome da Empresa": "ACB CONFECCOES DE UNIFORMES LTDA",
        "CNPJ": "08.305.131/0001-99", "CNAE atacadista": "4642-7/02 (secundário)",
        "Site Oficial": "https://brasbord.com", "Telefone": "(11) 2081-0960",
        "E-mail Comercial": "",
        "Endereço": "Rua Bresser, 163, Brás, São Paulo - SP, 03017-000",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("08305131000199"),
        "Atende UF": "GO/DF",
    },
    "dimensional": {
        "Estado": "SP", "Cidade": "Limeira",
        "Nome da Empresa": "DIMENSIONAL BRASIL SOLUCOES LTDA",
        "CNPJ": "06.913.480/0001-68", "CNAE atacadista": "4673-7/00 (principal); 4642-7/02, 4649-4/08, 4651-6/01, 4651-6/02 e outros (secundários)",
        "Site Oficial": "https://dimensional.com.br", "Telefone": "(19) 3446-7548",
        "E-mail Comercial": "",
        "Endereço": "Av. Armando Ragonha, 190, Village Limeira, Limeira - SP, 13481-316",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("06913480000168"),
        "Atende UF": "GO/DF",
    },
    "prosul": {
        "Estado": "SC", "Cidade": "Joinville",
        "Nome da Empresa": "PROSUL EQUIPAMENTOS LTDA (Prosul Distribuidora / Prosul Epis & Ferramentas)",
        "CNPJ": "48.815.919/0001-60", "CNAE atacadista": "4642-7/02 (principal)",
        "Site Oficial": "https://prosuldistribuidora.com.br", "Telefone": "(47) 3034-6803",
        "E-mail Comercial": "",
        "Endereço": "Rua Ottokar Doerffel, 1112, Galpão K 01 A, Atiradores, Joinville - SC, 89203-210",
        "Fonte": "lista_sites.xlsx (guia UNIFORME)" + " | " + CNPJWS.format("48815919000160"),
        "Atende UF": "GO/DF",
    },
    "dms": {
        "Estado": "SC", "Cidade": "São José",
        "Nome da Empresa": "DMS Confecção e Comércio de Equipamentos de Proteção Individual LTDA",
        "CNPJ": "13.786.240/0001-05", "CNAE atacadista": "4642-7/02 (principal); 4616-8/00, 4643-5/01 (secundários)",
        "Site Oficial": "https://www.dmsepi.com/", "Telefone": "(48) 3205-9371",
        "E-mail Comercial": "",
        "Endereço": "Rua Domingos Jalmeno Costa, 152, Bloco B, Galpão 10, Fazenda Santo Antônio, São José - SC, 88104-600",
        "Fonte": "lista_sites.xlsx (guia EPI)" + " | " + CNPJWS.format("13786240000105"),
        "Atende UF": "GO/DF",
    },
    "tr": {
        "Estado": "PR", "Cidade": "Londrina",
        "Nome da Empresa": "TR Distribuidora de Equipamentos de Segurança LTDA",
        "CNPJ": "14.213.841/0001-91", "CNAE atacadista": "4642-7/02 (principal); 4643-5/01, 4663-0/00 (secundários)",
        "Site Oficial": "https://www.trepis.com.br/", "Telefone": "(43) 3374-3374",
        "E-mail Comercial": "",
        "Endereço": "Rua São Salvador, 1350, Vila Ziober, Londrina - PR, 86026-480",
        "Fonte": "lista_sites.xlsx (guia EPI)" + " | " + CNPJWS.format("14213841000191"),
        "Atende UF": "GO/DF",
    },
    "amaster": {
        "Estado": "PR", "Cidade": "Curitiba",
        "Nome da Empresa": "A MASTER ARTIGOS PARA PROTECAO INDIVIDUAL E INDUSTRIAL LTDA (A Master EPI)",
        "CNPJ": "16.603.654/0001-40", "CNAE atacadista": "4642-7/02 (principal); 4643-5/01, 4646-0/02, 4649-4/01, 4649-4/08 e outros (secundários)",
        "Site Oficial": "https://www.amasterepi.com.br/", "Telefone": "(41) 3272-0257",
        "E-mail Comercial": "amaster@amasterepi.com.br",
        "Endereço": "Rua Marcos Mocellin, 458, Santa Felicidade, Curitiba - PR, 82020-510",
        "Fonte": "lista_sites.xlsx (guia EPI)" + " | " + CNPJWS.format("16603654000140"),
        "Atende UF": "GO/DF",
    },
    "pisebem": {
        "Estado": "PR", "Cidade": "Curitiba",
        "Nome da Empresa": "PISEBEM COMERCIO DE EQUIPAMENTOS DE PROTECAO INDIVIDUAL LTDA",
        "CNPJ": "11.156.413/0001-86", "CNAE atacadista": "4642-7/02 (principal); 4645-1/01 (secundário)",
        "Site Oficial": "https://www.pisebem.com.br/", "Telefone": "(41) 3045-3031",
        "E-mail Comercial": "",
        "Endereço": "Rua José Hauer, 1071, Boqueirão, Curitiba - PR, 81730-400",
        "Fonte": "lista_sites.xlsx (guia EPI)" + " | " + CNPJWS.format("11156413000186"),
        "Atende UF": "GO/DF",
    },
    "gimba": {
        "Estado": "SP", "Cidade": "Barueri",
        "Nome da Empresa": "SUPRICORP SUPRIMENTOS LTDA (Gimba)",
        "CNPJ": "54.651.716/0011-50", "CNAE atacadista": "4647-8/01 (principal); 4637-1/99, 4639-7/01, 4645-1/01, 4646-0/01 e outros (secundários)",
        "Site Oficial": "https://www.gimba.com.br", "Telefone": "(11) 2109-7000",
        "E-mail Comercial": "",
        "Endereço": "Av. Prefeito João Vilallobo Quero, 1160, Jardim Belval, Barueri - SP, 06422-122",
        "Fonte": "https://www.gimba.com.br" + " | " + CNPJWS.format("54651716001150"),
        "Atende UF": "GO/DF",
    },
    "ncbella": {
        "Estado": "SP", "Cidade": "São Paulo",
        "Nome da Empresa": "NC BELLA COMERCIO E DISTRIBUICAO DE EQUIPAMENTOS E MATERIAIS DE LIMPEZA LTDA (NC Bella Distribuidora)",
        "CNPJ": "57.935.095/0001-52", "CNAE atacadista": "4693-1/00 (principal); 4619-2/00, 4646-0/01, 4646-0/02, 4649-4/01 e outros (secundários)",
        "Site Oficial": "https://www.ncbelladistribuidora.com.br", "Telefone": "",
        "E-mail Comercial": "contato@ncbella.com.br",
        "Endereço": "Praça Dona Mariquinha Sciascia, 84, Box 7, Vila Albertina, São Paulo - SP, 02372-050",
        "Fonte": "https://www.ncbelladistribuidora.com.br" + " | " + CNPJWS.format("57935095000152"),
        "Atende UF": "GO/DF",
    },
    "cobra": {
        "Estado": "RS", "Cidade": "Carlos Barbosa",
        "Nome da Empresa": "COBRA INDUSTRIA E COMERCIO DE EMBALAGENS LTDA. (Cobra Embalagens)",
        "CNPJ": "02.949.470/0001-21", "CNAE atacadista": "4686-9/02 (principal)",
        "Site Oficial": "https://loja.cobraembalagens.com.br", "Telefone": "(54) 3461-4177",
        "E-mail Comercial": "",
        "Endereço": "Rua Uruguai, 226, Nossa Senhora de Fátima, Carlos Barbosa - RS, 95185-000",
        "Fonte": "https://loja.cobraembalagens.com.br" + " | " + CNPJWS.format("02949470000121"),
        "Atende UF": "GO/DF",
    },
})

OBS_LISTA = "Da lista_sites.xlsx da equipe; CNAE conferido em 09/10/2026. "

VALIDOS += [
    # EPI / UNIFORME - lista_sites.xlsx (já estavam na planilha; agora registrados aqui)
    (EPI, "zen", "https://zengouniformes.com.br",
     OBS_LISTA + "O site não abriu na coleta de 09/10/2026 (conexão interrompida). " + OBS_FORA),
    (EPI, "zeus", "https://epizeus.com.br",
     OBS_LISTA + "A loja de EPI é a epizeus.com.br. " + OBS_FORA),
    (EPI, "agil", "https://agiluniformes.com.br", OBS_LISTA + OBS_FORA),
    (EPI, "superpro", "https://superproatacado.com.br", OBS_LISTA + OBS_FORA),
    (EPI, "multiseg", "https://multiseg.com.br", OBS_LISTA + OBS_FORA),
    (EPI, "astro", "https://astrodistribuidora.com", OBS_LISTA + OBS_FORA),
    (EPI, "artlimp", "https://artlimpbrasil.com.br", OBS_LISTA + OBS_FORA),
    (EPI, "livpro", "https://livpro.com.br", OBS_LISTA + OBS_FORA),
    (EPI, "acb", "https://brasbord.com", OBS_LISTA + OBS_FORA),
    (EPI, "dimensional", "https://dimensional.com.br", OBS_LISTA + OBS_FORA),
    (EPI, "prosul", "https://prosuldistribuidora.com.br", OBS_LISTA + OBS_FORA),
    (EPI, "dms", "https://www.dmsepi.com/", OBS_LISTA + OBS_FORA),
    (EPI, "tr", "https://www.trepis.com.br/", OBS_LISTA + OBS_FORA),
    (EPI, "amaster", "https://www.amasterepi.com.br/", OBS_LISTA + OBS_FORA),
    (EPI, "pisebem", "https://www.pisebem.com.br/", OBS_LISTA + OBS_FORA),
    # LIMPEZA E HIGIENE - pesquisa de 09/10/2026 (água sanitária 5 L com frete para GO)
    (LH, "gimba", "https://www.gimba.com.br/?txt-busca=agua+sanitaria+5&btn-buscar=Buscar",
     "Atacadista de suprimentos para empresas. Ex.: Água Sanitária Suprema 5L R$ 15,49 em out/2026; "
     "frete para 74933-130 calculado na página do produto. " + OBS_FORA),
    (LH, "ncbella", "https://www.ncbelladistribuidora.com.br/agua-sanitaria-5-litros-valencia",
     "Ex.: Água Sanitária 5 Litros Valência R$ 20,00 em out/2026; frete para 74933-130 a partir de "
     "R$ 35,75 (Jadlog). Telefone da Receita é genérico, por isso ficou em branco. " + OBS_FORA),
    (LH, "cobra", "https://loja.cobraembalagens.com.br/agua-sanitaria-c-2-l",
     "Ex.: Água Sanitária 5 L R$ 21,72 em out/2026 (item 'sob encomenda'); frete para 74933-130 a "
     "partir de R$ 51,20 (Expresso), exibido numa janela após calcular. " + OBS_FORA),
    # LIMPEZA PREDIAL - pesquisa de 09/10/2026
    (LP, "gimba", "https://www.gimba.com.br/baldes-e-bacias/balde-retratil-perfect-pro-5l-1un/?PID=203677",
     "Único balde de 5 L encontrado com frete para GO: Balde Retrátil Perfect Pro 5L R$ 38,99 em "
     "out/2026; frete para 74933-130 a partir de R$ 32,87 (Correios PAC). " + OBS_FORA),
    (LP, "ncbella", "https://www.ncbelladistribuidora.com.br",
     "Baldes (4 L, 12 L, 16 L), mops, enceradeiras e carros funcionais. Sem balde de 5 L em out/2026. "
     + OBS_FORA),
    (LP, "artlimp", "https://www.artlimpbrasil.com.br/balde-plastico-com-tampa-5-litros.html",
     OBS_LISTA + "Baldes e utensílios de limpeza. O Balde Plástico com Tampa 5 Litros (R$ 18,99) "
     "estava fora de estoque em 09/10/2026. " + OBS_FORA),
]

PENDENTES += [
    (LP, "RS", "Santa Maria", "Sislimpa (Sistemas de Limpeza)", "", "",
     "https://loja.sislimpa.com.br", "(55) 3212-7700", "sislimpa@sislimpa.com.br",
     "Rod. RST 287, 6000, Camobi, Santa Maria - RS",
     "Vende o Balde 5 Litros Kunber com alça, mas o preço só aparece com login (seria 'Link "
     "aproveitável'). CNPJ não publicado no site: CNAE não verificado.",
     "https://loja.sislimpa.com.br/produto/83640/BALDE5LITROSCINZACOMALAAZULKUNBER"),
    (LH, "SP", "São Paulo", "General Clean", "", "", "https://www.generalclean.com.br",
     "(11) 93323-3682", "contato@generalclean.com.br", "",
     "Água Sanitária 5 Litros R$ 17,24 e frete para GO (PAC R$ 38,09) em 09/10/2026. CNPJ não "
     "publicado no site: CNAE não verificado.",
     "https://www.generalclean.com.br/agua-sanitaria-5-litros"),
]


CAMPOS_SIMPLES = ("Estado", "Cidade", "Nome da Empresa", "CNPJ", "CNAE atacadista",
                  "Site Oficial", "Telefone", "E-mail Comercial", "Endereço")


def _linha_de_tupla(t: tuple[str, ...], situacao: str) -> dict[str, str]:
    grupo, uf, cidade, nome, cnpj, cnae, site, tel, email, end, obs, fonte = t
    return {"Grupo de Insumo": grupo, "Situação": situacao, "Atende UF": uf,
            "Estado": uf, "Cidade": cidade, "Nome da Empresa": nome, "CNPJ": cnpj,
            "CNAE atacadista": cnae, "Site Oficial": site, "Link (clicável)": site,
            "Telefone": tel, "E-mail Comercial": email, "Endereço": end,
            "Observações": obs, "Fonte": fonte}


def montar_linhas() -> list[dict[str, str]]:
    linhas = []
    for grupo, chave, link, obs in VALIDOS:
        emp = EMPRESAS[chave]
        linha = {"Grupo de Insumo": grupo, "Situação": "VALIDO", "Atende UF": emp["Atende UF"]}
        linha.update({c: emp[c] for c in CAMPOS_SIMPLES})
        linha.update({"Link (clicável)": link, "Observações": obs, "Fonte": emp["Fonte"]})
        linhas.append(linha)
    linhas += [_linha_de_tupla(t, "REFERENCIA_SEM_PRECO") for t in REFERENCIA]
    linhas += [_linha_de_tupla(t, "PENDENTE_VALIDACAO") for t in PENDENTES]
    return linhas


def main() -> None:
    colunas = ["Grupo de Insumo", "Situação", "Atende UF", *COLUNAS_SAIDA]
    ARQ_FORNECEDORES_CURADOS.parent.mkdir(parents=True, exist_ok=True)
    with open(ARQ_FORNECEDORES_CURADOS, "w", newline="", encoding="utf-8-sig") as fh:
        escritor = csv.DictWriter(fh, fieldnames=colunas, delimiter=";")
        escritor.writeheader()
        escritor.writerows(montar_linhas())
    print(f"Gravado: {ARQ_FORNECEDORES_CURADOS}")


if __name__ == "__main__":
    main()
