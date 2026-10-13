"""
Configurações centrais do projeto de pesquisa de fornecedores / preços (FGV IBRE).

Tudo o que é "regra de negócio" fica aqui, em um só lugar, para que as
regras combinadas com a equipe sejam fáceis de auditar e de alterar sem
mexer na lógica dos módulos.

Regras de negócio vigentes (confirmadas com a responsável pela coleta):

1. CNAE atacadista = qualquer subclasse da Divisão 46 da CNAE 2.0/IBGE
   (Comércio por atacado, exceto veículos automotores e motocicletas),
   seja como atividade PRINCIPAL ou SECUNDÁRIA do CNPJ.
2. Marketplaces de terceiros (Mercado Livre, Amazon, Shopee etc.) nunca
   contam como fonte. Vale apenas o domínio próprio do fornecedor.
3. O fornecedor precisa ter site próprio com catálogo E preço visível
   (sem login, sem "sob consulta"), porque a etapa seguinte é tirar
   prints dos preços. Quem só tem catálogo "sob consulta" vai para uma
   aba de referência, nunca para a lista principal.
4. Região prioritária: Goiás (GO) e Distrito Federal (DF). Meta mínima de
   5 fornecedores válidos por UF em cada Grupo de Insumo. Se a UF não
   atingir a meta, é permitido completar com outros Estados, marcando a
   origem na coluna "Observações".
5. PASSAGEM e SAÚDE OCUPACIONAL são serviços (sem CNAE atacadista que os
   cubra): as planilhas desses grupos são geradas vazias, com observação.
6. Nenhum dado é inventado. Campo não encontrado fica vazio.
"""

from __future__ import annotations

from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------
# Raiz do repositório = três níveis acima deste arquivo (src/fgv_precos/config.py)
RAIZ_PROJETO: Path = Path(__file__).resolve().parents[2]

DIR_DADOS: Path = RAIZ_PROJETO / "data"
DIR_DADOS_BRUTOS: Path = DIR_DADOS / "raw"          # dumps da Receita (não versionados)
DIR_DADOS_INTERMEDIARIOS: Path = DIR_DADOS / "interim"  # candidatos filtrados
DIR_DADOS_CURADOS: Path = DIR_DADOS / "curated"     # pesquisa verificada manualmente
DIR_LOGS: Path = RAIZ_PROJETO / "logs"
# Cópias e arquivos de trabalho (backups, listas de revisão, prints retirados).
# Fica fora de FNDE/Centro Oeste/Entrega, para a Entrega ter só o que é entregue.
DIR_HISTORICO: Path = RAIZ_PROJETO / "_historico"

# Entradas e saídas do projeto FNDE - Centro-Oeste
DIR_FNDE_CO: Path = RAIZ_PROJETO / "FNDE" / "Centro Oeste"
ARQ_INSUMOS_PADRAO: Path = DIR_FNDE_CO / "Pesquisa_SEAD_GO_Limpeza_Predial.csv"
DIR_SAIDA_FORNECEDORES: Path = DIR_FNDE_CO / "Fornecedores"
ARQ_FORNECEDORES_CURADOS: Path = DIR_DADOS_CURADOS / "fornecedores_centro_oeste.csv"

# ---------------------------------------------------------------------------
# Regras de enquadramento
# ---------------------------------------------------------------------------
UFS_PRIORITARIAS: tuple[str, ...] = ("GO", "DF")
META_POR_UF: int = 5

# Divisão 46 da CNAE 2.0. Os códigos chegam como "4649408" (Receita) ou
# "46.49-4-08" (APIs); a comparação é feita só com dígitos.
PREFIXO_CNAE_ATACADISTA: str = "46"

# Situação cadastral "02" = ATIVA no layout de dados abertos da Receita.
SITUACAO_ATIVA_RECEITA: str = "02"

# Grupos de insumo, exatamente como aparecem na coluna "Grupo de Insumo".
GRUPOS_PRODUTO: tuple[str, ...] = ("LIMPEZA E HIGIENE", "LIMPEZA PREDIAL", "EPI / UNIFORME")
GRUPOS_SERVICO: tuple[str, ...] = ("PASSAGEM", "SAÚDE OCUPACIONAL")

# Nome do arquivo de saída por grupo. O Windows não aceita "/" em nomes de
# arquivo; por decisão da equipe, "EPI / UNIFORME" vira "EPI_UNIFORME".
NOME_ARQUIVO_POR_GRUPO: dict[str, str] = {
    "LIMPEZA E HIGIENE": "FNDE_LIMPEZA E HIGIENE.xlsx",
    "LIMPEZA PREDIAL": "FNDE_LIMPEZA PREDIAL.xlsx",
    "EPI / UNIFORME": "FNDE_EPI_UNIFORME.xlsx",
    "PASSAGEM": "FNDE_PASSAGEM.xlsx",
    "SAÚDE OCUPACIONAL": "FNDE_SAÚDE OCUPACIONAL.xlsx",
}

OBSERVACAO_GRUPO_SERVICO: dict[str, str] = {
    "PASSAGEM": (
        "Grupo de serviço (tarifa de transporte coletivo municipal de Goiânia). "
        "Não existe CNAE de comércio atacadista (Divisão 46) que cubra este "
        "insumo, portanto a regra de fornecedor atacadista não se aplica. "
        "Planilha gerada vazia por decisão da equipe; tratamento a definir."
    ),
    "SAÚDE OCUPACIONAL": (
        "Grupo de serviço (exames ASO admissional, demissional e periódico). "
        "Não existe CNAE de comércio atacadista (Divisão 46) que cubra este "
        "insumo, portanto a regra de fornecedor atacadista não se aplica. "
        "Planilha gerada vazia por decisão da equipe; tratamento a definir."
    ),
}

# Colunas da planilha final (ordem pedida pela equipe + CNPJ e CNAE).
COLUNAS_SAIDA: tuple[str, ...] = (
    "Estado",
    "Cidade",
    "Nome da Empresa",
    "CNPJ",
    "CNAE atacadista",
    "Site Oficial",
    "Link (clicável)",
    "Telefone",
    "E-mail Comercial",
    "Endereço",
    "Observações",
    "Fonte",
)

# ---------------------------------------------------------------------------
# Marketplaces proibidos (regra 2). Comparação por "termina com" no domínio.
# ---------------------------------------------------------------------------
DOMINIOS_MARKETPLACE: tuple[str, ...] = (
    "mercadolivre.com.br", "mercadolibre.com", "amazon.com.br", "amazon.com",
    "shopee.com.br", "americanas.com.br", "magazineluiza.com.br", "magalu.com",
    "aliexpress.com", "olx.com.br", "submarino.com.br", "shoptime.com.br",
    "casasbahia.com.br", "extra.com.br", "carrefour.com.br", "netshoes.com.br",
    "kabum.com.br", "shein.com", "temu.com", "elo7.com.br", "enjoei.com.br",
)

# Provedores de e-mail gratuitos: o domínio do e-mail NÃO indica site próprio.
DOMINIOS_EMAIL_GRATUITO: tuple[str, ...] = (
    "gmail.com", "hotmail.com", "outlook.com", "live.com", "yahoo.com",
    "yahoo.com.br", "bol.com.br", "uol.com.br", "terra.com.br", "ig.com.br",
    "icloud.com", "msn.com", "globo.com", "globomail.com", "zipmail.com.br",
)

# ---------------------------------------------------------------------------
# Palavras-chave por grupo (usadas para checar se o site vende itens do grupo).
# Derivadas das descrições da planilha de insumos.
# ---------------------------------------------------------------------------
PALAVRAS_CHAVE_GRUPO: dict[str, tuple[str, ...]] = {
    "LIMPEZA E HIGIENE": (
        "água sanitária", "agua sanitaria", "álcool", "alcool", "desinfetante",
        "detergente", "papel higiênico", "papel higienico", "papel toalha",
        "saco de lixo", "saco para lixo", "sabonete", "limpa vidro", "multiuso",
        "esponja", "flanela", "cera", "removedor", "sapólio", "sapolio",
    ),
    "LIMPEZA PREDIAL": (
        "balde", "rodo", "vassoura", "mop", "carro funcional", "lixeira",
        "contentor", "dispenser", "dispensador", "pá coletora", "pa coletora",
        "enceradeira", "lavadora", "aspirador", "escada", "mangueira",
        "placa sinalizadora", "desentupidor", "espanador",
    ),
    "EPI / UNIFORME": (
        "luva", "bota", "botina", "calçado de segurança", "calcado de seguranca",
        "óculos de proteção", "oculos de protecao", "protetor auricular",
        "avental", "capa de chuva", "uniforme", "camiseta", "calça", "calca",
        "máscara", "mascara", "protetor solar",
    ),
}

# Frases que indicam preço oculto (regra 3 -> vai para aba de referência).
FRASES_PRECO_OCULTO: tuple[str, ...] = (
    "sob consulta", "solicite um orçamento", "solicite orçamento",
    "solicite seu orçamento", "faça login para ver", "entre para ver o preço",
    "consulte o preço", "preço sob consulta",
)

# ---------------------------------------------------------------------------
# Rede
# ---------------------------------------------------------------------------
HTTP_TIMEOUT_S: int = 20
HTTP_USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 FGV-IBRE-pesquisa"
)
# APIs públicas de CNPJ têm limite (~3 req/min). Intervalo mínimo entre chamadas:
CNPJ_API_INTERVALO_S: float = 21.0
CNPJ_API_MAX_TENTATIVAS: int = 3

# Dados abertos do CNPJ (Receita Federal). A Receita muda o endereço de tempos
# em tempos; se o download falhar, baixe os .zip manualmente e use --dump-dir.
URL_BASE_DADOS_ABERTOS_CNPJ: str = (
    "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/"
)
