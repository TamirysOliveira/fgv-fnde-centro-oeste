"""
Configurações da raspagem de preços e fretes.

Regras vigentes (revisadas pela chefia em 09/10/2026):
    * Somente GO (CEP 74933-130). DF não é mais pesquisado.
    * 5 preços com frete por insumo.
    * O frete para GO precisa estar visível no print. Frete grátis ->
      "VALOR FRETE" vazio e observação em "OBS FRETE".
    * Site sem calculadora de CEP: só vale se a própria página do produto
      (a do print) mostrar frete grátis sem condição, ex.: "FRETE GRÁTIS
      PARA TODO BRASIL". Aviso com condição ("acima de R$ X") não vale.
    * Login/cadastro (preço, frete ou carrinho que só aparecem logado): a
      linha vai para a coluna P ("Link aproveitável"), com o motivo em
      OBS FRETE, e o próximo fornecedor é tentado. Outros fretes que não
      podem ser calculados descartam o fornecedor.
    * Preço = o preço visível na página (sem cupom, PIX ou outros descontos).
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

from fgv_precos.config import DIR_FNDE_CO, DIR_SAIDA_FORNECEDORES, NOME_ARQUIVO_POR_GRUPO

CEPS: dict[str, str] = {"GO": "74933130"}
PRECOS_POR_UF: int = 5

DIR_ENTREGA = DIR_FNDE_CO / "Entrega"
DIR_PRINTS = DIR_ENTREGA / "prints"
ARQ_MODELO_SAIDA = DIR_FNDE_CO / "FNDE_output.csv"
ARQ_INSUMOS = DIR_FNDE_CO / "Pesquisa_SEAD_GO_Limpeza_Predial.csv"
DIR_PLANILHAS_FORNECEDORES = DIR_SAIDA_FORNECEDORES
ARQUIVO_FORNECEDORES_POR_GRUPO = NOME_ARQUIVO_POR_GRUPO

# Nome da pasta de prints por grupo ("/" não é permitido em pastas no Windows).
PASTA_PRINT_POR_GRUPO: dict[str, str] = {
    g: n.removeprefix("FNDE_").removesuffix(".xlsx") for g, n in NOME_ARQUIVO_POR_GRUPO.items()
}

# Navegador
VIEWPORT = {"width": 1366, "height": 900}
TIMEOUT_NAVEGACAO_MS = 45_000
ESPERA_FRETE_MS = 8_000          # tempo máximo esperando o resultado do frete
MAX_RESULTADOS_BUSCA = 12        # quantos resultados da busca avaliar por site
PAUSA_ENTRE_ACOES_MS = 800       # gentileza com os servidores

# Codificação/separador do modelo FNDE_output.csv (Excel em português).
CODIFICACAO_SAIDA = "cp1252"
SEPARADOR_SAIDA = ";"
