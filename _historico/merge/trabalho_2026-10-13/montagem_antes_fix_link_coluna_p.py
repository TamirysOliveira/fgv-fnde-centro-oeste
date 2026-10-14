"""Montagem da Entrega a partir da base, das correções e dos candidatos aprovados.

Arquivos (todos em _historico/merge, menos a Entrega):
    base_entrega_2026-10-13/<Pasta>/FNDE_output.xlsx   base (nunca alterada)
    base_entrega_2026-10-13/<Pasta>/prints/<Sub>/      prints da base (<ID>_GO_<n>.png)
    correcoes_entrega.csv                               linhas da base a retirar
    candidatos.xlsx                                     linhas de outras fontes + revisão
    prints_candidatos/                                  prints dos candidatos
    montagens/<data_hora>/relatorio.csv                 o que entrou em cada montagem
Saída (FNDE/Centro Oeste/Entrega/<Pasta>/): fnde_resultado_merge.xlsx, resumo_coleta.csv
e prints/<Sub>/<ID>_GO_<n>.png (numerados na ordem da planilha). Os prints que estavam
na Entrega vão para _historico/merge/prints_substituidos/<data_hora>/ (nada é apagado).
"""

from __future__ import annotations

import csv
import filecmp
import logging
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import openpyxl
import pandas as pd

from fgv_precos.config import ARQ_INSUMOS_PADRAO, DIR_FNDE_CO, DIR_HISTORICO
from fgv_precos.merge.observacoes import observacoes
from fgv_precos.merge.regras import (
    PRECOS_POR_INSUMO,
    UF_DESTINO,
    Candidato,
    normalizar_url,
    obs_frete_go,
    selecionar,
    somente_digitos,
)
from fgv_precos.raspagem import saida

log = logging.getLogger(__name__)

DIR_MERGE = DIR_HISTORICO / "merge"
DIR_BASE = DIR_MERGE / "base_entrega_2026-10-13"
ARQ_CORRECOES = DIR_MERGE / "correcoes_entrega.csv"
ARQ_CANDIDATOS = DIR_MERGE / "candidatos.xlsx"
DIR_PRINTS_CANDIDATOS = DIR_MERGE / "prints_candidatos"
DIR_MONTAGENS = DIR_MERGE / "montagens"
DIR_PRINTS_SUBSTITUIDOS = DIR_MERGE / "prints_substituidos"
DIR_ENTREGA = DIR_FNDE_CO / "Entrega"
ARQ_DASHBOARD = DIR_ENTREGA / "dashboard_resumo_coleta.xlsx"
NOME_SAIDA = "fnde_resultado_merge.xlsx"

# Pasta na Entrega e subpasta de prints, por grupo (Categoria da planilha).
GRUPOS = {
    "EPI / UNIFORME": ("EPI UNIFORME", "EPI_UNIFORME"),
    "LIMPEZA E HIGIENE": ("LIMPEZA E HIGIENE", "LIMPEZA E HIGIENE"),
    "LIMPEZA PREDIAL": ("LIMPEZA PREDIAL", "LIMPEZA PREDIAL"),
}
COLUNAS_RESUMO = ["ID FGV", "Grupo", "UF", "Preços coletados", "Faltam",
                  "Sem preço visível (coluna P)"]
# Colunas da planilha de candidatos (arquivo de trabalho, não é entregue).
COLUNAS_CANDIDATOS = [
    "Chave", "Origem", "Grupo", "ID FGV", "Nome Empresa", "CNPJ", "UF", "Data coleta",
    "FONTE", "PRODUTO PESQUISADO", "Preço lido", "Preço pela regra", "VALOR FRETE",
    "OBS FRETE (origem)", "Print", "Situação", "Motivo", "Sugestão",
]
APROVADO = "APROVADO"
# Coluna L: era "OBS Desconto" no modelo; desde 13/10/2026 é "OBS", com as observações
# pertinentes da linha (equivalência, medida aceita pela tolerância...; ver merge/observacoes.py).
COLUNA_OBS = "OBS"
# Índices (0 = coluna A) das 16 colunas da saída.
C_CAT, C_ID, C_ITEM, C_UF, C_DATA, C_EMP, C_CNPJ, C_FONTE, C_PROD = range(9)
C_PRECO, C_DESC, C_OBSD, C_FINAL, C_FRETE, C_OBSF, C_P = range(9, 16)


def ler_insumos() -> pd.DataFrame:
    df = pd.read_csv(ARQ_INSUMOS_PADRAO, sep=";", dtype=str, encoding="cp1252").fillna("")
    return df.set_index("ID FGV")


def ler_correcoes(arquivo: Path = ARQ_CORRECOES) -> set[tuple[str, str]]:
    """{(ID FGV, CNPJ só dígitos)} das linhas da base que saem do merge."""
    if not arquivo.exists():
        return set()
    with open(arquivo, encoding="utf-8-sig", newline="") as fh:
        return {(r["ID FGV"].strip(), somente_digitos(r["CNPJ"]))
                for r in csv.DictReader(fh, delimiter=";") if r.get("Ação", "").strip() == "retirar"}


def ler_candidatos(arquivo: Path = ARQ_CANDIDATOS) -> pd.DataFrame:
    if not arquivo.exists():
        return pd.DataFrame(columns=COLUNAS_CANDIDATOS)
    df = pd.read_excel(arquivo, sheet_name="Candidatos", dtype=str).fillna("")
    faltam = [c for c in COLUNAS_CANDIDATOS if c not in df.columns]
    if faltam:
        raise ValueError(f"{arquivo.name}: colunas ausentes {faltam}")
    return df


def _num(texto: str) -> float | None:
    texto = str(texto or "").strip()
    if not texto:
        return None
    return float(texto.replace(",", ".")) if re.fullmatch(r"-?\d+([.,]\d+)?", texto) else None


def _ler_base(pasta: str) -> list[list]:
    wb = openpyxl.load_workbook(DIR_BASE / pasta / "FNDE_output.xlsx")
    try:
        return [[c.value for c in r][:16] for r in wb.active.iter_rows(min_row=2)
                if any(c.value not in (None, "") for c in r)]
    finally:
        wb.close()


def _print_base(pasta: str, sub: str, id_fgv: str, n: int) -> Path:
    return DIR_BASE / pasta / "prints" / sub / f"{id_fgv}_GO_{n}.png"


def _linha_candidato(c: Candidato, cat: str, item: str) -> list:
    d = c.dados
    data = d.get("Data coleta", "")
    try:
        data = datetime.strptime(data[:10], "%Y-%m-%d")
    except ValueError:
        pass
    if c.eh_go:
        frete, obs = None, obs_frete_go(None)
    else:
        frete = c.frete
        origem = d.get("OBS FRETE (origem)", "").strip()
        obs = origem if origem.startswith("Opção mais barata") else \
            f"Opção mais barata para o CEP 74933-130: {origem}"
    return [cat, c.id_fgv, item, c.uf, data, d["Nome Empresa"], d["CNPJ"], c.link,
            d["PRODUTO PESQUISADO"], c.preco, None, None, c.preco, frete, obs, None]


def _com_obs(linha: list) -> list:
    """Preenche a coluna L ("OBS") com as observações pertinentes da linha."""
    obs = observacoes(str(linha[C_ID]), str(linha[C_PROD] or ""), str(linha[C_FONTE] or ""))
    if not obs:
        return linha
    linha = list(linha)
    atual = str(linha[C_OBSD] or "").strip()
    linha[C_OBSD] = " ".join([atual, *obs] if atual else obs)
    return linha


def _ajustar_go_base(linha: list) -> list:
    """Linha da base de fornecedor de GO com frete pago: o frete não é calculado (13/10/2026)."""
    if linha[C_UF] == UF_DESTINO and not linha[C_P] and linha[C_FRETE]:
        linha = list(linha)
        linha[C_OBSF] = obs_frete_go(float(linha[C_FRETE]))
        linha[C_FRETE] = None
    return linha


def montar(simular: bool = False) -> Path:
    """Monta a Entrega. Com ``simular=True`` só grava o relatório (não mexe na Entrega)."""
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    pasta_montagem = DIR_MONTAGENS / (carimbo + ("_simulacao" if simular else ""))
    pasta_montagem.mkdir(parents=True, exist_ok=True)
    insumos = ler_insumos()
    correcoes = ler_correcoes()
    cand_df = ler_candidatos()
    cab = saida.colunas_modelo()
    cab[C_OBSD] = COLUNA_OBS    # decisão de 13/10/2026: "OBS Desconto" vira "OBS"
    relatorio: list[dict] = []
    resumo_geral: dict[str, dict] = {}

    # Links de toda a base mantida, para um mesmo produto não entrar em dois insumos.
    bases = {cat: _ler_base(pasta) for cat, (pasta, _) in GRUPOS.items()}
    links_base = {normalizar_url(r[C_FONTE] or r[C_P]) for linhas in bases.values()
                  for r in linhas if (str(r[C_ID]), somente_digitos(r[C_CNPJ])) not in correcoes}

    for cat, (pasta, sub) in GRUPOS.items():
        ids = [i for i in insumos.index if insumos.loc[i, "Grupo de Insumo"] == cat]
        mantidas, contagem, cnpjs = [], {i: 0 for i in ids}, {i: set() for i in ids}
        ordem_base: dict[str, int] = {}
        for r in bases[cat]:
            i = str(r[C_ID])
            if not r[C_P]:
                ordem_base[i] = ordem_base.get(i, 0) + 1
            chave = (i, somente_digitos(r[C_CNPJ]))
            n_print = None if r[C_P] else ordem_base[i]
            if chave in correcoes:
                relatorio.append({"Grupo": cat, "ID FGV": i, "Origem": "base", "Empresa": r[C_EMP],
                                  "Situação": "retirada (correção)", "Preço": r[C_PRECO]})
                continue
            mantidas.append((_ajustar_go_base(r), "base", n_print))
            if not r[C_P]:
                cnpjs.setdefault(i, set()).add(chave[1])
                contagem[i] = contagem.get(i, 0) + 1

        vagas = {i: max(PRECOS_POR_INSUMO - contagem.get(i, 0), 0) for i in ids}
        aprovados = []
        for _, c in cand_df[(cand_df["Situação"] == APROVADO) & (cand_df["Grupo"] == cat)].iterrows():
            preco = _num(c["Preço pela regra"]) or _num(c["Preço lido"])
            if preco is None:
                log.warning("CONFERIR: candidato %s aprovado sem preço; ignorado.", c["Chave"])
                continue
            aprovados.append(Candidato(id_fgv=c["ID FGV"], cnpj=c["CNPJ"], uf=c["UF"],
                                       link=c["FONTE"], preco=preco, frete=_num(c["VALOR FRETE"]),
                                       chave=c["Chave"], dados=c.to_dict()))
        escolhidos = selecionar(vagas, aprovados, cnpjs, links_base)
        links_base |= {normalizar_url(c.link) for c in escolhidos}
        # Linha da coluna P da base trocada por um candidato com preço do mesmo fornecedor.
        trocadas = {(c.id_fgv, somente_digitos(c.cnpj)) for c in escolhidos}
        mantidas = [t for t in mantidas if not (t[0][C_P] and (str(t[0][C_ID]),
                    somente_digitos(t[0][C_CNPJ])) in trocadas)]
        for c in escolhidos:
            item = insumos.loc[c.id_fgv, "Descrição"]
            mantidas.append((_linha_candidato(c, cat, item), c, None))
            contagem[c.id_fgv] += 1
        nao_usados = [c for c in aprovados if c not in escolhidos]
        for c in escolhidos:
            relatorio.append({"Grupo": cat, "ID FGV": c.id_fgv, "Origem": c.dados["Origem"],
                              "Empresa": c.dados["Nome Empresa"], "Situação": "incluída",
                              "Preço": c.preco, "Chave": c.chave})
        for c in nao_usados:
            relatorio.append({"Grupo": cat, "ID FGV": c.id_fgv, "Origem": c.dados["Origem"],
                              "Empresa": c.dados["Nome Empresa"], "Chave": c.chave, "Preço": c.preco,
                              "Situação": "aprovada, não usada (sem vaga, CNPJ já no insumo ou "
                                          "link já usado)"})

        # Ordem: por insumo, linhas com preço da base, depois candidatos, depois coluna P.
        mantidas.sort(key=lambda t: (str(t[0][C_ID]), bool(t[0][C_P]), t[1] != "base"))
        linhas = [_com_obs(t[0]) for t in mantidas]
        p_por_id: dict[str, int] = {}
        prints: list[tuple[Path, str]] = []
        for linha, origem, n_base in mantidas:
            if linha[C_P]:
                continue
            i = str(linha[C_ID])
            p_por_id[i] = p_por_id.get(i, 0) + 1
            destino = f"{i}_GO_{p_por_id[i]}.png"
            if origem == "base":
                fonte = _print_base(pasta, sub, i, n_base)
            else:
                fonte = DIR_MERGE / origem.dados["Print"]
            if not fonte.exists():
                raise FileNotFoundError(f"Print não encontrado: {fonte}")
            prints.append((fonte, destino))

        resumo = []
        for i in ids:
            n = contagem.get(i, 0)
            manual = sum(1 for linha in linhas if str(linha[C_ID]) == i and linha[C_P])
            resumo.append({"ID FGV": i, "Grupo": cat, "UF": UF_DESTINO, "Preços coletados": n,
                           "Faltam": max(PRECOS_POR_INSUMO - n, 0),
                           "Sem preço visível (coluna P)": manual})
        resumo_geral[cat] = {r["ID FGV"]: r for r in resumo}
        log.info("%s: %d preços (%d da base, %d novos), %d insumos completos.", cat,
                 sum(contagem.values()), sum(contagem.values()) - len(escolhidos), len(escolhidos),
                 sum(1 for r in resumo if r["Faltam"] == 0))
        if simular:
            continue
        destino_pasta = DIR_ENTREGA / pasta
        saida.escrever_planilha(linhas, cab, destino_pasta / NOME_SAIDA)
        with open(destino_pasta / "resumo_coleta.csv", "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUNAS_RESUMO, delimiter=";")
            w.writeheader()
            w.writerows(resumo)
        _publicar_prints(destino_pasta / "prints" / sub, prints,
                         DIR_PRINTS_SUBSTITUIDOS / carimbo / pasta / sub)

    with open(pasta_montagem / "resumo.csv", "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS_RESUMO, delimiter=";")
        w.writeheader()
        for por_id in resumo_geral.values():
            w.writerows(por_id.values())
    with open(pasta_montagem / "relatorio.csv", "w", encoding="utf-8-sig", newline="") as fh:
        campos = ["Grupo", "ID FGV", "Origem", "Empresa", "Situação", "Preço", "Chave"]
        w = csv.DictWriter(fh, fieldnames=campos, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(relatorio)
    if not simular:
        atualizar_dashboard(resumo_geral)
    return pasta_montagem


def _publicar_prints(pasta: Path, prints: list[tuple[Path, str]], arquivo_morto: Path) -> None:
    """Deixa na Entrega exatamente os prints da montagem.

    O print que já está lá e é igual ao novo (mesmo tamanho e data) fica; os demais
    antigos vão para ``arquivo_morto`` (nada é apagado) e os novos são copiados.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    novos = {nome: fonte for fonte, nome in prints}
    for antigo in pasta.glob("*.png"):
        fonte = novos.get(antigo.name)
        if fonte is not None and filecmp.cmp(fonte, antigo, shallow=True):
            novos.pop(antigo.name)
            continue
        arquivo_morto.mkdir(parents=True, exist_ok=True)
        shutil.move(str(antigo), arquivo_morto / antigo.name)
    for nome, fonte in novos.items():
        shutil.copy2(fonte, pasta / nome)


def atualizar_dashboard(resumo: dict[str, dict], arquivo: Path = ARQ_DASHBOARD) -> None:
    """Atualiza a aba Dados do dashboard (só o XML dela; gráficos e fórmulas ficam)."""
    dados = {i: r for por_id in resumo.values() for i, r in por_id.items()}
    with zipfile.ZipFile(arquivo) as z:
        nomes = {n: z.read(n) for n in z.namelist()}
        infos = z.infolist()
    xml = nomes["xl/worksheets/sheet3.xml"].decode("utf-8")
    vistos = set()

    def celula(ref: str, estilo: str, valor) -> str:
        return (f'<c r="{ref}" s="{estilo}" t="n"><v>{valor}</v></c>' if valor is not None
                else f'<c r="{ref}" s="{estilo}" t="n"></c>')

    def troca(m: re.Match) -> str:
        linha, r = m.group(0), m.group(1)
        a = re.search(rf'<c r="A{r}"[^>]*><v>(\d+)</v></c>', linha)
        if not a or a.group(1) not in dados:
            return linha
        d = dados[a.group(1)]
        vistos.add(a.group(1))
        for col, val in (("D", d["Preços coletados"]), ("E", d["Faltam"]), ("H", None),
                         ("I", d["Sem preço visível (coluna P)"])):
            linha, n = re.subn(rf'<c r="{col}{r}" s="(\d+)"[^>]*?(?:/>|>.*?</c>)',
                               lambda mm, col=col, val=val: celula(f"{col}{r}", mm.group(1), val),
                               linha, count=1)
            if n != 1:
                raise ValueError(f"Dashboard: célula {col}{r} não encontrada")
        return linha

    xml = re.sub(r'<row r="(\d+)".*?</row>', troca, xml)
    if vistos != set(dados):
        raise ValueError(f"Dashboard sem os insumos {sorted(set(dados) - vistos)}")
    nota = ("• Fonte: resumo_coleta.csv de cada grupo, gerados por scripts/montar_merge.py a partir "
            f"de fnde_resultado_merge.xlsx (montagem de {datetime.now():%d/%m/%Y %H:%M}).")
    xml = re.sub(r'(<c r="A124"[^>]*><is><t>).*?(</t>)',
                 lambda m: m.group(1) + escape(nota) + m.group(2), xml)
    nomes["xl/worksheets/sheet3.xml"] = xml.encode("utf-8")
    tmp = arquivo.with_name(arquivo.stem + "_tmp.xlsx")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for info in infos:
            out.writestr(info, nomes[info.filename])
    tmp.replace(arquivo)
