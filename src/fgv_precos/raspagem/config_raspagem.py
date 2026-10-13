"""
Configurações da raspagem de preços e fretes.

Regras vigentes (revisadas pela chefia em 09/10/2026):
    * Somente GO (CEP 74933-130). DF não é mais pesquisado.
    * 5 preços com frete por insumo.
    * O frete para GO precisa estar visível no print. Frete grátis ->
      "VALOR FRETE" vazio e observação em "OBS FRETE".
    * Retirada na loja não é frete de entrega e nunca é usada.
    * Site sem calculadora de CEP: só vale se a própria página do produto
      (a do print) mostrar frete grátis sem condição, ex.: "FRETE GRÁTIS
      PARA TODO BRASIL". Aviso com condição ("acima de R$ X") não vale.
    * Login/cadastro (preço, frete ou carrinho que só aparecem logado): a
      linha vai para a coluna P ("Link aproveitável"), com o motivo em
      OBS FRETE, e o próximo fornecedor é tentado. Outros fretes que não
      podem ser calculados descartam o fornecedor.
    * Preço = o preço visível na página (sem cupom, PIX, boleto ou parcelas).
    * Produto correspondente sem preço visível: a linha vai para a planilha
      com o link na coluna P ("Link aproveitável"), para coleta manual, e o
      motivo em OBS FRETE ("Preço só com login", "Preço sob consulta/orçamento"
      ou "Preço não exibido (motivo não identificado)"). NÃO conta entre os 5
      preços. Só o produto claramente esgotado é ignorado.
    * Prints em Entrega/prints/<Grupo>/<ID FGV>_GO_<n>.png, com nome do
      produto, preço e frete.
    * Saída .xlsx com as colunas de FNDE/Centro Oeste/FNDE_output.csv;
      "FONTE" = link (clicável) da página do produto de onde o print saiu.
"""

from __future__ import annotations

from fgv_precos.config import DIR_FNDE_CO, DIR_HISTORICO, NOME_ARQUIVO_POR_GRUPO

CEPS: dict[str, str] = {"GO": "74933130"}
PRECOS_POR_UF: int = 5

# Entrega: só as pastas de grupo (FNDE_output.xlsx, resumo_coleta.csv, prints).
DIR_ENTREGA = DIR_FNDE_CO / "Entrega"
ARQ_MODELO_SAIDA = DIR_FNDE_CO / "FNDE_output.csv"
# Resultado bruto da coleta (raspar_precos_centro_oeste.py). Fica fora da Entrega e
# só chega a ela pelo comando "incorporar" do script de correção.
DIR_COLETA = DIR_HISTORICO / "coleta_bruta"
DIR_PRINTS = DIR_COLETA / "prints"
ARQ_SAIDA = DIR_COLETA / "FNDE_output.xlsx"
ARQ_RESUMO = DIR_COLETA / "resumo_coleta.csv"
# Produtos que a revisão humana recusou para um insumo (ID FGV;Fornecedor;Produto;
# Link;Motivo). A coleta nunca escolhe de novo um link desta lista para aquele insumo.
ARQ_PRODUTOS_RECUSADOS = DIR_FNDE_CO / "produtos_recusados.csv"

# Nome da pasta de prints por grupo ("/" não é permitido em pastas no Windows).
PASTA_PRINT_POR_GRUPO: dict[str, str] = {
    g: n.removeprefix("FNDE_").removesuffix(".xlsx") for g, n in NOME_ARQUIVO_POR_GRUPO.items()
}

# Aderência do produto ao insumo (ver ``descricao.pontuar``). Além da palavra
# principal, quantas outras palavras do nome do insumo precisam aparecer no
# nome do produto. 1 evita "Carro Guia Maçarico" para "Carro Funcional";
# 0 volta ao comportamento anterior (só a palavra principal).
PALAVRAS_EXTRAS_MINIMAS: int = 1

# Frete maior que este múltiplo do preço gera um aviso no log, para conferência.
FRETE_ALERTA_MULTIPLO: float = 3.0

# Navegador. Alguns sites recusam o Chromium "de teste" do Playwright (erro
# "conexão interrompida" no log de 09/10/2026), por isso o padrão é usar o
# Edge ou o Chrome instalados; o Chromium do Playwright (None) é o último recurso.
CANAIS_NAVEGADOR: tuple[str | None, ...] = ("msedge", "chrome", None)
ARGS_NAVEGADOR: list[str] = ["--disable-blink-features=AutomationControlled"]
USER_AGENT_NAVEGADOR: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0"
)
VIEWPORT = {"width": 1366, "height": 900}
TIMEOUT_NAVEGACAO_MS = 45_000
ESPERA_FRETE_MS = 8_000          # tempo máximo esperando o resultado do frete
MAX_RESULTADOS_BUSCA = 12        # quantos resultados da busca avaliar por site
PAUSA_ENTRE_ACOES_MS = 800       # gentileza com os servidores

# Codificação/separador do modelo FNDE_output.csv (Excel em português).
CODIFICACAO_SAIDA = "cp1252"
SEPARADOR_SAIDA = ";"
