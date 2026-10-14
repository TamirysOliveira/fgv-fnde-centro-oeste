"""Lista de links a coletar e importação da coleta por link para a revisão."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

import pandas as pd

from fgv_precos.merge import montagem
from fgv_precos.merge.montagem import ARQ_CANDIDATOS, COLUNAS_CANDIDATOS, DIR_BASE, DIR_MERGE, GRUPOS
from fgv_precos.merge.regras import normalizar_url, somente_digitos

log = logging.getLogger(__name__)

ARQ_LINKS = DIR_MERGE / "links_para_coletar.csv"
COLUNAS_LINKS = ["ID FGV", "Grupo", "Nome Empresa", "CNPJ", "UF", "Link", "Origem", "Chave", "Motivo"]
# Reprovações de print que uma nova coleta resolve (o produto está certo).
MOTIVOS_REFAZER = ("encoberto", "Print reduzido", "CEP errado", "Pop-up", "Frete não aparece",
                   "Frete coberto", "CEP não preenchido", "Print sem preço", "Preço do print diferente",
                   "Frete da planilha não aparece", "Preço em faixa")


def _faltam_por_id() -> dict[str, int]:
    pasta = montagem.montar(simular=True)
    df = pd.read_csv(pasta / "resumo.csv", sep=";", dtype=str, encoding="utf-8-sig")
    return {r["ID FGV"]: int(r["Faltam"]) for _, r in df.iterrows()}


def gerar_links(incluir_aprovados: bool = False) -> Path:
    """Links que podem preencher vagas: candidatos sem print/frete válido e linhas da
    coluna P da base de fornecedor de GO cujo único problema era o frete."""
    faltam = _faltam_por_id()
    cand = montagem.ler_candidatos()
    linhas = []
    for _, c in cand.iterrows():
        if faltam.get(c["ID FGV"], 0) <= 0:
            continue
        refazer = c["Situação"] == "REPROVADO" and any(m in c["Motivo"] for m in MOTIVOS_REFAZER)
        if c["Situação"] == "A COLETAR" or refazer or (incluir_aprovados and c["Situação"] == "APROVADO"):
            linhas.append({k: c[k] for k in ("ID FGV", "Grupo", "Nome Empresa", "CNPJ", "UF", "Origem",
                                             "Chave", "Motivo")} | {"Link": c["FONTE"]})
    correcoes = montagem.ler_correcoes()
    for cat, (pasta, _) in GRUPOS.items():
        base = pd.read_excel(DIR_BASE / pasta / "FNDE_output.xlsx", dtype=str).fillna("")
        for _, b in base.iterrows():
            i = b["Código FGV"]
            if (b["Link aproveitável"] and b["UF"] == "GO" and faltam.get(i, 0) > 0
                    and (i, somente_digitos(b["CNPJ"])) not in correcoes
                    and b["OBS FRETE"].startswith("Frete a coletar manualmente")):
                linhas.append({"ID FGV": i, "Grupo": cat, "Nome Empresa": b["Nome Empresa"],
                               "CNPJ": b["CNPJ"], "UF": "GO", "Link": b["Link aproveitável"],
                               "Origem": "Entrega (coluna P)", "Chave": "",
                               "Motivo": "Fornecedor de GO: frete não calculado (GO para GO)."})
    vistos, unicas = set(), []
    for linha in sorted(linhas, key=lambda x: (x["ID FGV"], x["Origem"])):
        chave = (linha["ID FGV"], normalizar_url(linha["Link"]))
        if chave not in vistos:
            vistos.add(chave)
            unicas.append(linha)
    with open(ARQ_LINKS, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS_LINKS, delimiter=";")
        w.writeheader()
        w.writerows(unicas)
    log.info("%d links em %d insumos com vaga.", len(unicas), len({x['ID FGV'] for x in unicas}))
    return ARQ_LINKS


def importar_coleta(pasta: str | Path) -> Path:
    """Leva as linhas com preço de uma coleta por link para candidatos.xlsx ("A REVISAR").

    O candidato de origem (mesma chave) passa a "SUBSTITUÍDO PELA COLETA", para não
    entrar duas vezes. Rodar de novo com a mesma pasta não duplica as linhas.
    """
    pasta = Path(pasta)
    if not pasta.is_absolute():
        pasta = Path.cwd() / pasta
    sit = pd.read_csv(pasta / "situacao.csv", sep=";", dtype=str, encoding="utf-8-sig").fillna("")
    cand = montagem.ler_candidatos()
    rel = pasta.relative_to(DIR_MERGE.resolve()) if pasta.resolve().is_relative_to(DIR_MERGE.resolve()) \
        else pasta
    novas = []
    for _, s in sit.iterrows():
        if not s["Situação"].startswith("OK"):
            continue
        chave = f"L|{pasta.name}|{s['Seq']}"
        if (cand["Chave"] == chave).any():
            continue
        if s["Chave origem"]:
            cand.loc[cand["Chave"] == s["Chave origem"], "Situação"] = "SUBSTITUÍDO PELA COLETA"
        novas.append({"Chave": chave, "Origem": f"Coleta por link {pasta.name}", "Grupo": s["Grupo"],
                      "ID FGV": s["ID FGV"], "Nome Empresa": s["Nome Empresa"], "CNPJ": s["CNPJ"],
                      "UF": s["UF"], "Data coleta": s["Data coleta"], "FONTE": s["Link final"],
                      "PRODUTO PESQUISADO": s["Produto"], "Preço lido": s["Preço"],
                      "Preço pela regra": "", "VALOR FRETE": s["Frete"], "OBS FRETE (origem)": s["OBS frete"],
                      "Print": str(Path(rel) / s["Print"]).replace("\\", "/"), "Situação": "A REVISAR",
                      "Motivo": "", "Sugestão": s["Aviso"]})
    cand = pd.concat([cand, pd.DataFrame(novas, columns=COLUNAS_CANDIDATOS)], ignore_index=True)
    salvar_candidatos(cand)
    log.info("%d linhas novas para revisar.", len(novas))
    return ARQ_CANDIDATOS


def salvar_candidatos(df: pd.DataFrame) -> None:
    with pd.ExcelWriter(ARQ_CANDIDATOS, engine="openpyxl") as w:
        df[COLUNAS_CANDIDATOS].to_excel(w, sheet_name="Candidatos", index=False)
        ws = w.book["Candidatos"]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for col, larg in zip("ABCDEFGHIJKLMNOPQR",
                             [16, 18, 18, 8, 28, 20, 5, 11, 40, 45, 10, 10, 10, 40, 30, 22, 45, 45],
                             strict=True):
            ws.column_dimensions[col].width = larg


def importar_robo() -> Path:
    """Leva o resultado da coleta normal do robô (_historico/coleta_bruta, gerado por
    scripts/raspar_precos_centro_oeste.py) para candidatos.xlsx ("A REVISAR").

    Os prints são copiados para prints_candidatos/robo_<data_hora>/, porque a
    coleta_bruta é sobrescrita na próxima execução do robô.
    """
    import shutil
    from datetime import datetime

    from fgv_precos.raspagem.config_raspagem import ARQ_SAIDA, DIR_PRINTS, PASTA_PRINT_POR_GRUPO

    bruto = pd.read_excel(ARQ_SAIDA, dtype=str).fillna("")
    cand = montagem.ler_candidatos()
    carimbo = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = montagem.DIR_PRINTS_CANDIDATOS / f"robo_{carimbo}"
    existentes = {(r["ID FGV"], normalizar_url(r["FONTE"])) for _, r in cand.iterrows()}
    ordem: dict[str, int] = {}
    novas = []
    for _, r in bruto.iterrows():
        if r["Link aproveitável"]:
            continue
        i = r["Código FGV"]
        ordem[i] = ordem.get(i, 0) + 1
        if (i, normalizar_url(r["FONTE"])) in existentes:
            continue
        fonte = DIR_PRINTS / PASTA_PRINT_POR_GRUPO[r["Categoria"]] / f"{i}_GO_{ordem[i]}.png"
        if not fonte.exists():
            log.warning("Print não encontrado para %s (%s); linha ignorada.", i, fonte.name)
            continue
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fonte, destino / fonte.name)
        novas.append({"Chave": f"R|{carimbo}|{i}|{ordem[i]}", "Origem": f"Robô {carimbo}",
                      "Grupo": r["Categoria"], "ID FGV": i, "Nome Empresa": r["Nome Empresa"],
                      "CNPJ": r["CNPJ"], "UF": r["UF"], "Data coleta": r["Data coleta"][:10],
                      "FONTE": r["FONTE"], "PRODUTO PESQUISADO": r["PRODUTO PESQUISADO"],
                      "Preço lido": r["Preço PRODUTO"], "Preço pela regra": "",
                      "VALOR FRETE": r["VALOR FRETE"], "OBS FRETE (origem)": r["OBS FRETE"],
                      "Print": f"prints_candidatos/robo_{carimbo}/{fonte.name}",
                      "Situação": "A REVISAR", "Motivo": "", "Sugestão": ""})
    cand = pd.concat([cand, pd.DataFrame(novas, columns=COLUNAS_CANDIDATOS)], ignore_index=True)
    salvar_candidatos(cand)
    log.info("%d linhas do robô para revisar.", len(novas))
    return ARQ_CANDIDATOS


def ids_com_vaga() -> list[str]:
    """IDs FGV que ainda não têm 5 preços (pela simulação da montagem)."""
    return sorted(i for i, n in _faltam_por_id().items() if n > 0)
