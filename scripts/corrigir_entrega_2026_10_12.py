"""
Correção da entrega de 10/10/2026 (FNDE/Centro Oeste/Entrega) SEM coletar de novo.

Os problemas foram encontrados na revisão de 12/10/2026, conferindo a planilha
contra os 437 prints (leitura de texto dos prints + conferência visual):

    corrigir          (rodar uma vez)
      1. Copia as planilhas e resumos para _historico/entrega_backup_2026-10-12/.
      2. Nomes com código HTML ("Prote&#231;&#227;o") -> texto normal.
      3. OBS FRETE sem os botões da página ("Lista de Desejos", "Compartilhar"...)
         e sem a linha de retirada na loja.
      4. Singular 1104, 1111 e 1118: a retirada na loja (R$ 0,00) tinha sido
         gravada como frete; o frete PAC certo foi lido no próprio print.
      5. Frete que o print não comprova para o CEP 74933-130 -> coluna P
         (link para coleta manual; não conta entre os 5 preços):
           - Casa da Limpeza, itens abaixo de R$ 300: o carrinho tinha 8
             produtos e o "frete grátis acima de R$ 300" valeu pelo total;
           - Singular 1105, 1108, 1109, 1110, 1112 e 1115: o campo de CEP
             ficou 49331-307 (Sergipe);
           - HP Máquinas: o print mostra o campo de CEP vazio, sem frete.
      6. Maroma: a página diz "Não foram encontradas formas de envio para o
         CEP informado" (não entrega em GO); o "frete" era o preço de um produto
         relacionado. Pela regra, o fornecedor é descartado: as linhas saem.
      7. Prints das linhas que deixaram de ter preço vão para
         _historico/prints_removidos/<Grupo>/ (nada é apagado) e os demais são
         renumerados na ordem da planilha (<ID>_GO_1, _2...).
      8. resumo_coleta.csv recalculado.
      9. Gera _historico/revisao_aderencia_2026-10-12.xlsx: as linhas cujo produto
         não passa na regra de aderência de 12/10 (exceto o Balde Retrátil
         5 L do Gimba, mantido por decisão da equipe), para revisão humana.

    aplicar-revisao   (depois de preencher a coluna "Manter? (S/N)")
      Tira da entrega as linhas marcadas com N (prints para _historico).

    aplicar-regra
      Tira da entrega todas as linhas cujo produto não passa na regra de
      aderência (descricao.pontuar, regra de 12/10/2026: a palavra principal
      do insumo abre o nome do produto; kit, tecido, suporte, refil,
      organizador, jogo de, capa para e peça são recusados). Exceção: o Balde
      Retrátil 5 L do Gimba (1056), mantido por decisão da equipe. Os prints
      das linhas retiradas vão para _historico/prints_removidos/<Grupo>/.

    incorporar --ids ... --fornecedor ...
      Leva para a planilha do grupo o resultado de uma coleta feita só com um
      fornecedor (raspar_precos_centro_oeste.py --ids ... --fornecedor ...),
      gravado em _historico/coleta_bruta. Para cada insumo com resultado
      novo, as linhas antigas desse fornecedor saem (prints para _historico)
      e as novas entram, com o print renomeado para o próximo número livre
      (os prints dos outros fornecedores não mudam de nome). Insumo sem
      resultado novo fica como está. A coluna D (UF) das linhas novas é
      conferida com a planilha de fornecedores (ver corrigir-uf).

    corrigir-uf       (regra de 13/10/2026)
      A coluna D (UF) passa a ser a UF de onde a mercadoria sai: a UF do
      estabelecimento do fornecedor (CNPJ da coluna G), lida na coluna
      "Estado" das planilhas Fornecedores/FNDE_<Grupo>.xlsx. Antes ela trazia
      GO, que é só o destino do frete. Só a coluna D muda; linhas, prints e
      resumos ficam como estão. Cópia das planilhas em
      _historico/entrega_backup_2026-10-13_uf/. Fornecedor não encontrado:
      a UF fica vazia e o log avisa (CONFERIR).

Exemplos (na raiz do repositório):
    python scripts/corrigir_entrega_2026_10_12.py corrigir
    python scripts/corrigir_entrega_2026_10_12.py aplicar-revisao
    python scripts/corrigir_entrega_2026_10_12.py aplicar-regra
    python scripts/corrigir_entrega_2026_10_12.py incorporar --ids 1105 1108 --fornecedor singular
    python scripts/corrigir_entrega_2026_10_12.py corrigir-uf
"""

from __future__ import annotations

import argparse
import csv
import html
import logging
import re
import shutil
import sys
from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

from fgv_precos.config import (
    ARQ_INSUMOS_PADRAO,
    DIR_HISTORICO,
    DIR_SAIDA_FORNECEDORES,
    NOME_ARQUIVO_POR_GRUPO,
)
from fgv_precos.fornecedores.insumos import ler_insumos
from fgv_precos.logging_config import configurar_logging
from fgv_precos.precos import float_para_br, todos_valores
from fgv_precos.raspagem import saida
from fgv_precos.raspagem.config_raspagem import (
    ARQ_SAIDA,
    DIR_ENTREGA,
    DIR_PRINTS,
    PASTA_PRINT_POR_GRUPO,
    PRECOS_POR_UF,
)
from fgv_precos.raspagem.descricao import Insumo, interpretar, palavras_faltantes, pontuar
from fgv_precos.raspagem.uf_origem import MapaUF, ler_mapa_uf

log = logging.getLogger("corrigir_entrega")

# Pasta do grupo em Entrega -> nome da pasta de prints dentro dela.
GRUPOS = {"EPI UNIFORME": "EPI_UNIFORME", "LIMPEZA E HIGIENE": "LIMPEZA E HIGIENE",
          "LIMPEZA PREDIAL": "LIMPEZA PREDIAL"}
# Nada disso fica na Entrega: cópias, lista de revisão e prints retirados vão para _historico.
DIR_BACKUP = DIR_HISTORICO / "entrega_backup_2026-10-12"
ARQ_REVISAO = DIR_HISTORICO / "revisao_aderencia_2026-10-12.xlsx"
DIR_PRINTS_REMOVIDOS = DIR_HISTORICO / "prints_removidos"
DIR_BACKUP_UF = DIR_HISTORICO / "entrega_backup_2026-10-13_uf"

# Colunas (0 = A) do FNDE_output.
UF, CNPJ = 3, 6
CODIGO, EMPRESA, FONTE, PRODUTO, PRECO, FINAL = 1, 5, 7, 8, 9, 12
VALOR_FRETE, OBS_FRETE, LINK_P = 13, 14, 15
CEP = "74933-130"

# Lido nos prints (Loja do EPI / Singular, campo de CEP com 74933-130).
FRETE_LIDO_NO_PRINT = {
    "1104": (21.39, "Pac R$ 21,39 7 dia(s) útil(eis)"),
    "1111": (23.77, "Pac R$ 23,77 7 dia(s) útil(eis)"),
    "1118": (21.39, "Pac R$ 21,39 7 dia(s) útil(eis)"),
}
SINGULAR_CEP_ERRADO = {"1105", "1108", "1109", "1110", "1112", "1115"}
LIMITE_FRETE_GRATIS_CASA_DA_LIMPEZA = 300.0

_RE_LIXO = re.compile(r"\b(lista de desejos|adicionar aos desejos|compartilhar|compartilhe)\b\s*",
                      re.I)
_RE_RETIRADAS = (
    re.compile(r"Retirada em loja\s*R\$\s*0,00\s*\d+\s*dia\(s\)\s*útil\(eis\)\s*", re.I),
    re.compile(r"R\$\s*0,00\s*\d+\s*dias?\s*(?:útil|úteis)\s*Retirar pessoalmente\s*", re.I),
    re.compile(r"Retirar na loja\s*A RETIRAR\s*O pedido ficará disponível.*?pagamento\.\s*",
               re.I | re.S),
)


@dataclass
class Linha:
    valores: list
    grupo: str
    print_original: int | None = None      # nº do print antes da correção (só linhas com preço)
    print_externo: Path | None = None      # print de uma coleta nova, fora da pasta do grupo
    removida: bool = False
    notas: list[str] = field(default_factory=list)

    @property
    def codigo(self) -> str:
        return str(self.valores[CODIGO])

    @property
    def empresa(self) -> str:
        return str(self.valores[EMPRESA] or "")

    @property
    def na_coluna_p(self) -> bool:
        return bool(self.valores[LINK_P])

    @property
    def chave(self) -> tuple[str, str, str]:
        return self.codigo, self.empresa, str(self.valores[PRODUTO] or "")


# ---------------------------------------------------------------- leitura
def ler_grupo(grupo: str) -> list[Linha]:
    wb = load_workbook(DIR_ENTREGA / grupo / "FNDE_output.xlsx", read_only=True)
    try:
        brutas = [list(r[:16]) for r in wb.active.iter_rows(min_row=2, values_only=True)
                  if any(v not in (None, "") for v in r)]
    finally:
        wb.close()
    linhas, pos = [], Counter()
    for valores in brutas:
        linha = Linha(valores, grupo)
        if not linha.na_coluna_p:
            pos[linha.codigo] += 1
            linha.print_original = pos[linha.codigo]
        linhas.append(linha)
    return linhas


def ler_insumos_interpretados() -> dict[str, Insumo]:
    df = ler_insumos(ARQ_INSUMOS_PADRAO)
    return {str(r["ID FGV"]): interpretar(r["ID FGV"], r["Grupo de Insumo"], r["Descrição"],
                                          r.get("Embalagem", "")) for _, r in df.iterrows()}


# ------------------------------------------------------------- correções
def limpar_obs(obs: str, valor: float | None) -> str:
    """Tira botões da página e a linha de retirada do texto da OBS FRETE."""
    prefixo, _, modalidade = obs.partition(": ")
    if not prefixo.startswith("Opção mais barata"):
        return obs
    for regex in _RE_RETIRADAS:
        modalidade = regex.sub(" ", modalidade)
    modalidade = _RE_LIXO.sub(" ", modalidade).split(" * Este prazo")[0]
    modalidade = " ".join(modalidade.split()).strip(" -.")
    if valor is not None:
        valor_br = f"R$ {float_para_br(valor)}"
        if valor not in todos_valores(modalidade):
            modalidade = f"{valor_br} ({modalidade})" if modalidade else valor_br
    return f"{prefixo}: {modalidade}"


def mover_para_coluna_p(linha: Linha, motivo: str) -> None:
    v = linha.valores
    preco = v[PRECO]
    link = v[FONTE]
    v[FONTE] = ""
    v[PRECO:VALOR_FRETE + 1] = [None] * (VALOR_FRETE + 1 - PRECO)
    v[OBS_FRETE] = (f"Frete a coletar manualmente: {motivo} "
                    f"(preço na página: R$ {float_para_br(preco)})")
    v[LINK_P] = link
    linha.notas.append("coluna P: " + motivo)


def corrigir_linha(linha: Linha) -> None:
    v = linha.valores
    nome = html.unescape(str(v[PRODUTO] or ""))
    if nome != v[PRODUTO]:
        v[PRODUTO] = nome
        linha.notas.append("nome sem código HTML")
    if linha.na_coluna_p:
        return

    empresa, codigo = linha.empresa.upper(), linha.codigo
    if empresa.startswith("MAROMA") and "Ver mais" in str(v[OBS_FRETE] or ""):
        linha.removida = True
        linha.notas.append("removida: Maroma não entrega no CEP (frete era preço de outro produto)")
        return
    if empresa.startswith("SINGULAR") and codigo in FRETE_LIDO_NO_PRINT:
        valor, texto = FRETE_LIDO_NO_PRINT[codigo]
        v[VALOR_FRETE], v[OBS_FRETE] = valor, f"Opção mais barata para o CEP {CEP}: {texto}"
        linha.notas.append("frete lido no print (era a retirada R$ 0,00)")
        return
    if empresa.startswith("SINGULAR") and codigo in SINGULAR_CEP_ERRADO:
        mover_para_coluna_p(linha, "o frete do print foi calculado para o CEP 49331-307 (errado)")
        return
    if empresa.startswith("HP M"):
        mover_para_coluna_p(linha, f"o print não mostra o frete para o CEP {CEP}")
        return
    if (empresa.startswith("CASA DA LIMPEZA") and v[VALOR_FRETE] is None
            and (v[PRECO] or 0) < LIMITE_FRETE_GRATIS_CASA_DA_LIMPEZA):
        mover_para_coluna_p(linha, "o carrinho tinha outros produtos e o frete grátis "
                                   "veio do valor total acima de R$ 300")
        return
    obs = str(v[OBS_FRETE] or "")
    limpa = limpar_obs(obs, v[VALOR_FRETE])
    if limpa != obs:
        v[OBS_FRETE] = limpa
        linha.notas.append("OBS FRETE limpa")


# ------------------------------------------------------------ gravação
def gravar_grupo(grupo: str, linhas: list[Linha], cab: list[str]) -> None:
    """Grava a planilha e o resumo e reorganiza os prints do grupo."""
    pasta_prints = DIR_ENTREGA / grupo / "prints" / GRUPOS[grupo]
    removidos = DIR_PRINTS_REMOVIDOS / grupo
    removidos.mkdir(parents=True, exist_ok=True)

    finais = [ln for ln in linhas if not ln.removida]
    ordenadas = saida.ordenar_linhas([ln.valores for ln in finais])
    # Prints: as linhas que continuam com preço recebem 1, 2, 3... na ordem da planilha.
    por_valores = {id(ln.valores): ln for ln in finais}
    destino: dict[Path, Path] = {}
    novo_n = Counter()
    for valores in ordenadas:
        ln = por_valores[id(valores)]
        if ln.print_externo is not None:
            origem = ln.print_externo
        elif ln.print_original is not None:
            origem = pasta_prints / f"{ln.codigo}_GO_{ln.print_original}.png"
        else:
            continue
        if ln.na_coluna_p:
            destino[origem] = removidos / origem.name
        else:
            novo_n[ln.codigo] += 1
            destino[origem] = pasta_prints / f"{ln.codigo}_GO_{novo_n[ln.codigo]}.png"
    for ln in linhas:
        if ln.removida and ln.print_original is not None:
            origem = pasta_prints / f"{ln.codigo}_GO_{ln.print_original}.png"
            destino[origem] = removidos / origem.name
    _mover_prints(destino, pasta_prints)

    saida.escrever_planilha(ordenadas, cab, DIR_ENTREGA / grupo / "FNDE_output.xlsx")
    _gravar_resumo(grupo, ordenadas)


def _mover_prints(destino: dict[Path, Path], pasta: Path) -> None:
    """Renomeia em duas etapas (nome temporário -> final) para não sobrescrever nada."""
    temporarios = {}
    for origem, final in destino.items():
        if origem == final:
            continue
        if not origem.exists():
            log.warning("Print não encontrado: %s", origem.name)
            continue
        if final.parent != pasta and final.exists():
            final = final.with_name(f"{final.stem}_2{final.suffix}")
        temp = origem.with_name(f"_tmp_{origem.name}")
        origem.rename(temp)
        temporarios[temp] = final
    for temp, final in temporarios.items():
        if final.exists():
            raise FileExistsError(f"Não sobrescrevo {final}; confira a pasta de prints.")
        temp.rename(final)
    log.info("%s: %d prints renomeados/movidos.", pasta.name, len(temporarios))


# Mesmas colunas de coletor.COLUNAS_RESUMO (o script não importa o coletor, que exige o Playwright).
COLUNAS_RESUMO = ["ID FGV", "Grupo", "UF", "Preços coletados", "Faltam",
                  "Sem preço visível (coluna P)"]


def _gravar_resumo(grupo: str, linhas: list[list]) -> None:
    """Recalcula o resumo do grupo a partir da planilha.

    Sempre grava as colunas padrão (o cabeçalho antigo, com "Link aproveitável",
    fazia esta função falhar) e só os insumos do próprio grupo. A coluna "UF"
    do resumo é a UF da cesta (destino do frete, GO), não a do fornecedor.
    """
    arquivo = DIR_ENTREGA / grupo / "resumo_coleta.csv"
    categoria = next(c for c, pasta in PASTA_POR_CATEGORIA.items() if pasta == grupo)
    with open(arquivo, encoding="utf-8-sig", newline="") as fh:
        antigo = list(csv.DictReader(fh, delimiter=";"))
    fora = [r["ID FGV"] for r in antigo if r.get("Grupo") != categoria]
    if fora:
        log.info("%s: o resumo tinha insumos de outro grupo (%s); eles saem do resumo.",
                 grupo, ", ".join(fora))
    precos = Counter(str(v[CODIGO]) for v in linhas if not v[LINK_P])
    manuais = Counter(str(v[CODIGO]) for v in linhas if v[LINK_P])
    novo = []
    for r in antigo:
        if r.get("Grupo") != categoria:
            continue
        n = precos[r["ID FGV"]]
        novo.append({"ID FGV": r["ID FGV"], "Grupo": categoria, "UF": r.get("UF") or "GO",
                     "Preços coletados": str(n), "Faltam": str(max(PRECOS_POR_UF - n, 0)),
                     "Sem preço visível (coluna P)": str(manuais[r["ID FGV"]])})
    with open(arquivo, "w", encoding="utf-8-sig", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=COLUNAS_RESUMO, delimiter=";")
        escritor.writeheader()
        escritor.writerows(novo)


# ------------------------------------------------------- lista de revisão
COLUNAS_REVISAO = ["Manter? (S/N)", "Grupo", "Código FGV", "Descrição do insumo", "Fornecedor",
                   "Produto encontrado", "Preço", "Situação na entrega",
                   "Palavras do insumo que faltam no produto", "Print", "Link"]


def mantida_por_decisao(ln: Linha) -> bool:
    """Exceção decidida pela equipe em 12/10/2026: o Balde Retrátil 5 L do Gimba (1056) fica."""
    return ln.codigo == "1056" and "Retrátil" in str(ln.valores[PRODUTO])


def passa_na_regra(ln: Linha, insumo: Insumo) -> bool:
    """A linha atende à regra de aderência (``descricao.pontuar``) ou é exceção decidida."""
    return mantida_por_decisao(ln) or pontuar(insumo, str(ln.valores[PRODUTO])) > 0


def gerar_revisao(todas: list[Linha], insumos: dict[str, Insumo]) -> int:
    linhas = []
    for ln in todas:
        v, insumo = ln.valores, insumos.get(ln.codigo)
        if ln.removida or insumo is None or not v[PRODUTO]:
            continue
        if passa_na_regra(ln, insumo):
            continue
        faltam = palavras_faltantes(insumo, str(v[PRODUTO]))
        linhas.append(["", ln.grupo, ln.codigo, v[2], ln.empresa, v[PRODUTO], v[PRECO],
                       "coluna P (sem preço/frete)" if ln.na_coluna_p else "com preço",
                       ", ".join(faltam) or "(palavra principal fora do início do nome)",
                       "", v[LINK_P] or v[FONTE]])
    linhas.sort(key=lambda r: (r[2], r[4]))

    wb = Workbook()
    ws = wb.active
    ws.title = "Revisão"
    ws.append(COLUNAS_REVISAO)
    for linha in linhas:
        ws.append(linha)
    for cel in ws[1]:
        cel.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cel.fill = PatternFill("solid", start_color="1F4E78")
        cel.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in ws.iter_rows(min_row=2):
        for cel in row:
            cel.font = Font(name="Arial", size=10)
            cel.alignment = Alignment(vertical="top", wrap_text=True)
        if str(row[-1].value or "").startswith("http"):
            row[-1].hyperlink = row[-1].value
            row[-1].font = Font(name="Arial", size=10, color="0563C1", underline="single")
        row[6].number_format = "#,##0.00"
    for letra, largura in zip("ABCDEFGHIJK", (10, 16, 9, 40, 28, 40, 10, 16, 26, 16, 40), strict=True):
        ws.column_dimensions[letra].width = largura
    validacao = DataValidation(type="list", formula1='"S,N"', allow_blank=True)
    ws.add_data_validation(validacao)
    validacao.add(f"A2:A{max(ws.max_row, 2)}")
    ws.freeze_panes = "B2"
    ws.auto_filter.ref = ws.dimensions
    ARQ_REVISAO.parent.mkdir(parents=True, exist_ok=True)
    wb.save(ARQ_REVISAO)
    return len(linhas)


def _preencher_prints_na_revisao() -> None:
    """Depois da renumeração, anota o nome do print atual de cada linha com preço."""
    wb = load_workbook(ARQ_REVISAO)
    ws = wb.active
    atuais = {}
    for grupo in GRUPOS:
        for ln in ler_grupo(grupo):
            if ln.print_original is not None:
                atuais[ln.chave] = f"{ln.codigo}_GO_{ln.print_original}.png"
    for row in ws.iter_rows(min_row=2):
        chave = (str(row[2].value), str(row[4].value), str(row[5].value))
        row[9].value = atuais.get(chave, "")
    wb.save(ARQ_REVISAO)


# -------------------------------------------------------------- comandos
def cmd_corrigir(_args) -> int:
    if DIR_BACKUP.exists():
        log.error("%s já existe: a correção já foi aplicada. Nada foi alterado.", DIR_BACKUP)
        return 1
    for grupo in GRUPOS:
        (DIR_BACKUP / grupo).mkdir(parents=True)
        for nome in ("FNDE_output.xlsx", "resumo_coleta.csv"):
            shutil.copy2(DIR_ENTREGA / grupo / nome, DIR_BACKUP / grupo / nome)
    log.info("Cópia de segurança em %s", DIR_BACKUP)

    cab = saida.colunas_modelo()
    insumos = ler_insumos_interpretados()
    todas: list[Linha] = []
    for grupo in GRUPOS:
        linhas = ler_grupo(grupo)
        for ln in linhas:
            corrigir_linha(ln)
            for nota in ln.notas:
                log.info("[%s] %s | %s | %s", ln.codigo, ln.empresa[:30],
                         str(ln.valores[PRODUTO])[:40], nota)
        gravar_grupo(grupo, linhas, cab)
        todas.extend(linhas)

    contagem = Counter(n.split(":")[0] if n.startswith(("coluna P", "removida")) else n
                       for ln in todas for n in ln.notas)
    log.info("Correções: %s", dict(contagem))
    n_revisao = gerar_revisao(todas, insumos)
    _preencher_prints_na_revisao()
    log.info("Lista de revisão: %s (%d linhas)", ARQ_REVISAO.name, n_revisao)
    return 0


def cmd_aplicar_revisao(_args) -> int:
    if not ARQ_REVISAO.exists():
        log.error("Lista de revisão não encontrada: %s", ARQ_REVISAO)
        return 1
    wb = load_workbook(ARQ_REVISAO, read_only=True)
    try:
        respostas = {(str(r[2]), str(r[4]), str(r[5])): str(r[0] or "").strip().upper()
                     for r in wb.active.iter_rows(min_row=2, values_only=True) if r[2]}
    finally:
        wb.close()
    sem_resposta = [k for k, v in respostas.items() if v not in ("S", "N")]
    if sem_resposta:
        log.error("%d linhas sem S/N na coluna 'Manter?' (ex.: %s). Nada foi alterado.",
                  len(sem_resposta), sem_resposta[:3])
        return 1
    remover = {k for k, v in respostas.items() if v == "N"}
    cab = saida.colunas_modelo()
    removidas = 0
    for grupo in GRUPOS:
        linhas = ler_grupo(grupo)
        for ln in linhas:
            if ln.chave in remover:
                ln.removida = True
                removidas += 1
                log.info("[%s] removida na revisão: %s | %s", ln.codigo, ln.empresa[:30],
                         ln.valores[PRODUTO])
        gravar_grupo(grupo, linhas, cab)
    log.info("Revisão aplicada: %d linhas removidas, %d mantidas.", removidas,
             len(respostas) - removidas)
    return 0


def cmd_aplicar_regra(_args) -> int:
    """Tira da entrega as linhas que não passam na regra de aderência (ver docstring)."""
    insumos = ler_insumos_interpretados()
    cab = saida.colunas_modelo()
    total = Counter()
    for grupo in GRUPOS:
        linhas = ler_grupo(grupo)
        for ln in linhas:
            insumo = insumos.get(ln.codigo)
            if insumo is None or not ln.valores[PRODUTO] or passa_na_regra(ln, insumo):
                continue
            ln.removida = True
            total["coluna P" if ln.na_coluna_p else "com preço"] += 1
            log.info("[%s] sai pela regra: %s | %s", ln.codigo, ln.empresa[:30],
                     ln.valores[PRODUTO])
        gravar_grupo(grupo, linhas, cab)
    _atualizar_revisao()
    log.info("Regra aplicada: %d linhas retiradas (%d com preço, %d da coluna P).",
             sum(total.values()), total["com preço"], total["coluna P"])
    return 0


# Coluna A (Categoria) -> pasta do grupo em Entrega.
PASTA_POR_CATEGORIA = {"EPI / UNIFORME": "EPI UNIFORME", "LIMPEZA E HIGIENE": "LIMPEZA E HIGIENE",
                       "LIMPEZA PREDIAL": "LIMPEZA PREDIAL"}


def cmd_incorporar(args) -> int:
    arquivo = ARQ_SAIDA          # resultado bruto da coleta, em _historico/coleta_bruta
    if not arquivo.exists():
        log.error("Resultado da coleta não encontrado: %s", arquivo)
        return 1
    ids, filtro = {str(i) for i in args.ids}, args.fornecedor.casefold()
    wb = load_workbook(arquivo, read_only=True)
    try:
        brutas = [list(r[:16]) for r in wb.active.iter_rows(min_row=2, values_only=True)
                  if r and r[CODIGO] is not None]
    finally:
        wb.close()

    novas_por_grupo: dict[str, list[Linha]] = {}
    pos = Counter()
    for valores in brutas:
        codigo, categoria = str(valores[CODIGO]), valores[0]
        if not valores[LINK_P]:
            pos[codigo] += 1          # numeração dos prints da coleta nova
        if codigo not in ids or filtro not in str(valores[EMPRESA] or "").casefold():
            continue
        grupo = PASTA_POR_CATEGORIA[categoria]
        uf = mapa_uf().uf(valores[CNPJ], valores[FONTE], valores[LINK_P])
        if uf != valores[UF]:
            log.info("[%s] UF %s -> %s (%s)", codigo, valores[UF], uf or "(vazia: CONFERIR)",
                     str(valores[EMPRESA])[:30])
            valores[UF] = uf
        ln = Linha(valores, grupo)
        if not valores[LINK_P]:
            pasta_nova = DIR_PRINTS / PASTA_PRINT_POR_GRUPO[categoria]
            ln.print_externo = pasta_nova / f"{codigo}_GO_{pos[codigo]}.png"
            if not ln.print_externo.exists():
                log.error("Print da coleta nova não encontrado: %s", ln.print_externo)
                return 1
        novas_por_grupo.setdefault(grupo, []).append(ln)

    com_resultado = {ln.codigo for novas in novas_por_grupo.values() for ln in novas}
    for codigo in sorted(ids - com_resultado):
        log.warning("Insumo %s: a coleta nova não trouxe nada de '%s'; linhas atuais mantidas.",
                    codigo, args.fornecedor)
    cab = saida.colunas_modelo()
    for grupo, novas in novas_por_grupo.items():
        linhas = ler_grupo(grupo)
        for ln in linhas:
            if ln.codigo in com_resultado and filtro in ln.empresa.casefold():
                ln.removida = True
                log.info("[%s] sai: %s | %s", ln.codigo, ln.empresa[:30], ln.valores[PRODUTO])
        for ln in novas:
            log.info("[%s] entra: %s | %s | preço %s | frete %s", ln.codigo, ln.empresa[:30],
                     ln.valores[PRODUTO], ln.valores[PRECO], ln.valores[VALOR_FRETE])
        gravar_grupo(grupo, linhas + novas, cab)
    _atualizar_revisao()
    log.info("Incorporado: %d linhas novas em %s.", sum(map(len, novas_por_grupo.values())),
             sorted(novas_por_grupo))
    return 0


# ------------------------------------------------------------ UF (13/10)
@cache
def mapa_uf() -> MapaUF:
    """UF de cada fornecedor (planilhas Fornecedores/FNDE_<Grupo>.xlsx), lida uma vez."""
    return ler_mapa_uf([DIR_SAIDA_FORNECEDORES / nome for nome in NOME_ARQUIVO_POR_GRUPO.values()])


def cmd_corrigir_uf(_args) -> int:
    """Coluna D = UF de onde a mercadoria sai (ver docstring). Só a coluna D muda."""
    mapa = mapa_uf()
    if not mapa.por_cnpj:
        log.error("Nenhum fornecedor lido em %s; nada foi alterado.", DIR_SAIDA_FORNECEDORES)
        return 1
    # Nada muda se alguma planilha estiver aberta no Excel (as três mudam juntas).
    abertas = []
    for grupo in GRUPOS:
        arquivo = DIR_ENTREGA / grupo / "FNDE_output.xlsx"
        try:
            with open(arquivo, "r+b"):
                pass
        except PermissionError:
            abertas.append(str(arquivo))
    if abertas:
        log.error("Feche no Excel e rode de novo (nada foi alterado): %s", "; ".join(abertas))
        return 1
    # Cópia antes de mexer (não sobrescreve uma cópia anterior).
    for grupo in GRUPOS:
        origem = DIR_ENTREGA / grupo / "FNDE_output.xlsx"
        destino = DIR_BACKUP_UF / grupo / origem.name
        if destino.exists():
            log.info("Cópia já existe, mantida: %s", destino)
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
    log.info("Cópia das planilhas em %s", DIR_BACKUP_UF)

    sem_uf: list[str] = []
    for grupo in GRUPOS:
        arquivo = DIR_ENTREGA / grupo / "FNDE_output.xlsx"
        wb = load_workbook(arquivo)
        ws = wb.active
        if str(ws.cell(1, UF + 1).value).strip() != "UF":
            log.error("%s: a coluna D não é 'UF' (%r); nada foi alterado.", arquivo,
                      ws.cell(1, UF + 1).value)
            return 1
        mudou, por_uf = 0, Counter()
        for (cel_uf,) in ws.iter_rows(min_row=2, min_col=UF + 1, max_col=UF + 1):
            r = cel_uf.row
            if ws.cell(r, CODIGO + 1).value in (None, ""):
                continue
            cnpj = ws.cell(r, CNPJ + 1).value
            fonte, link_p = ws.cell(r, FONTE + 1).value, ws.cell(r, LINK_P + 1).value
            uf = mapa.uf(cnpj, fonte, link_p)
            if not uf:
                sem_uf.append(f"{grupo} linha {r}: {ws.cell(r, EMPRESA + 1).value} ({cnpj})")
            if uf != cel_uf.value:
                cel_uf.value = uf or None
                mudou += 1
            por_uf[uf or "(vazia)"] += 1
        try:
            wb.save(arquivo)
        except PermissionError:
            log.error("Feche o arquivo no Excel e rode de novo: %s", arquivo)
            return 1
        log.info("%s: %d linhas com a UF alterada. Por UF: %s", grupo, mudou,
                 ", ".join(f"{u} {n}" for u, n in sorted(por_uf.items())))
    for item in sem_uf:
        log.warning("CONFERIR: fornecedor sem UF na planilha de fornecedores: %s", item)
    log.info("UF corrigida. %d linhas ficaram sem UF.", len(sem_uf))
    return 0


def _atualizar_revisao() -> None:
    """Tira da lista de revisão as linhas que não existem mais na entrega (mantém as respostas)."""
    if not ARQ_REVISAO.exists():
        return
    atuais = {ln.chave for grupo in GRUPOS for ln in ler_grupo(grupo)}
    wb = load_workbook(ARQ_REVISAO)
    ws = wb.active
    sairam = [row[0].row for row in ws.iter_rows(min_row=2)
              if (str(row[2].value), str(row[4].value), str(row[5].value)) not in atuais]
    for indice in reversed(sairam):
        ws.delete_rows(indice)
    wb.save(ARQ_REVISAO)
    if sairam:
        log.info("Lista de revisão: %d linhas saíram (não estão mais na entrega).", len(sairam))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("corrigir", help="aplica as correções e gera a lista de revisão").set_defaults(
        func=cmd_corrigir)
    sub.add_parser("aplicar-revisao", help="remove as linhas marcadas com N").set_defaults(
        func=cmd_aplicar_revisao)
    sub.add_parser("aplicar-regra", help="remove as linhas que não passam na regra de aderência"
                   ).set_defaults(func=cmd_aplicar_regra)
    p = sub.add_parser("incorporar", help="leva uma coleta de um só fornecedor para a entrega")
    p.add_argument("--ids", nargs="+", required=True)
    p.add_argument("--fornecedor", required=True)
    p.set_defaults(func=cmd_incorporar)
    sub.add_parser("corrigir-uf", help="coluna D = UF de onde a mercadoria sai (fornecedor)"
                   ).set_defaults(func=cmd_corrigir_uf)
    args = parser.parse_args(argv)
    configurar_logging(f"corrigir_entrega_{args.comando}")
    if not any((DIR_ENTREGA / g / "FNDE_output.xlsx").exists() for g in PASTA_POR_CATEGORIA.values()):
        # Desde 13/10/2026 a Entrega é montada por scripts/montar_merge.py; a antiga
        # FNDE_output.xlsx está em _historico/merge/base_entrega_2026-10-13/.
        log.error("A Entrega agora é montada por scripts/montar_merge.py. Para levar uma coleta "
                  "do robô à revisão, use: python scripts/montar_merge.py importar-robo")
        return 1
    try:
        return args.func(args)
    except Exception:  # noqa: BLE001 - registra qualquer erro no log antes de sair
        log.exception("Falha ao corrigir a entrega")
        return 1


if __name__ == "__main__":
    sys.exit(main())
