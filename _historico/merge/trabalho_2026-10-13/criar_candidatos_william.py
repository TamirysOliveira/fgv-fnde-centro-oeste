"""Cria _historico/merge/candidatos.xlsx com as linhas da entrega do William de 13/10/2026
e a revisão de prints já feita (decisoes_prints.json). Extrai os prints embutidos."""
import io, json, re, sys
from pathlib import Path
import openpyxl, pandas as pd
from PIL import Image
sys.path.insert(0, "src")
from fgv_precos.merge.montagem import (ARQ_CANDIDATOS, COLUNAS_CANDIDATOS, DIR_BASE, DIR_MERGE,
                                       DIR_PRINTS_CANDIDATOS, ler_correcoes)
from fgv_precos.merge.regras import normalizar_url, somente_digitos
from fgv_precos.raspagem.descricao import interpretar, pontuar

T = DIR_MERGE / "trabalho_2026-10-13"
W = DIR_MERGE / "entregas_william" / "2026-10-13"
ARQ = {"EPIS": ("[william] EPIS_E_UNIFORMES 1.xlsx", "EPI / UNIFORME", "EPI UNIFORME"),
       "MATE": ("[william] MATERIAIS_DE_CONSUMO 1.xlsx", "LIMPEZA E HIGIENE", "LIMPEZA E HIGIENE"),
       "FERR": ("[william] FERRAMENTAS_E_EQUIPAMENTOS 1.xlsx", "LIMPEZA PREDIAL", "LIMPEZA PREDIAL")}
dec = {(d["pref"], d["linha"]): d for d in json.load(open(T / "decisoes_prints.json", encoding="utf-8"))}
receita = json.load(open(T / "receita_fornecedores_william_2026-10-13.json", encoding="utf-8"))
ins = pd.read_csv("FNDE/Centro Oeste/Pesquisa_SEAD_GO_Limpeza_Predial.csv", sep=";", dtype=str,
                  encoding="cp1252").fillna("").set_index("ID FGV")
uf = {}
for f in Path("FNDE/Centro Oeste/Fornecedores").glob("FNDE_*.xlsx"):
    for sh, v in pd.read_excel(f, sheet_name=None, dtype=str).items():
        if "CNPJ" in v:
            for _, r in v.dropna(subset=["CNPJ", "Estado"]).iterrows():
                uf[somente_digitos(r["CNPJ"])] = r["Estado"].strip()
correcoes = ler_correcoes()
base = {}
for _, (_, cat, pasta) in ARQ.items():
    b = pd.read_excel(DIR_BASE / pasta / "FNDE_output.xlsx", dtype=str)
    for i, c in zip(b["Código FGV"], b["CNPJ"]):
        if (i, somente_digitos(c)) not in correcoes:
            base[(i, somente_digitos(c))] = True
pdir = DIR_PRINTS_CANDIDATOS / "william_2026-10-13"
pdir.mkdir(parents=True, exist_ok=True)
todos = pd.concat([pd.read_excel(W / a, dtype=str).fillna("") for a, _, _ in ARQ.values()])
contagem_url = todos.groupby(todos["FONTE"].map(normalizar_url))["Código FGV"].nunique()
linhas = []
for pref, (arq, cat, _) in ARQ.items():
    wb = openpyxl.load_workbook(W / arq)
    ws = wb.active
    imgs = {im.anchor._from.row + 1: im for im in ws._images}
    df = pd.read_excel(W / arq, dtype=str).fillna("")
    for k, r in df.iterrows():
        linha = k + 2
        i, cn = r["Código FGV"], somente_digitos(r["CNPJ"])
        nome_print = f"{pref}_{linha:03d}.png"
        Image.open(io.BytesIO(imgs[linha]._data())).save(pdir / nome_print)
        insumo = interpretar(i, ins.loc[i, "Grupo de Insumo"], ins.loc[i, "Descrição"], ins.loc[i, "Embalagem"])
        obs = r["OBS FRETE"]
        d = dec.get((pref, linha))
        sit, motivo, preco_regra = "A REVISAR", "", ""
        if (i, cn) in base:
            sit, motivo = "DUPLICADO", "Fornecedor (CNPJ) já está no insumo na entrega."
        elif not r["PRODUTO PESQUISADO"].strip() or "Conhecimento em cada entrega" in r["PRODUTO PESQUISADO"]:
            sit, motivo = "REPROVADO", "Nome do produto vazio ou com o slogan do site."
        elif contagem_url[normalizar_url(r["FONTE"])] > 1:
            sit, motivo = "REPROVADO", "Mesmo link usado em mais de um insumo na entrega do William."
        elif pontuar(insumo, r["PRODUTO PESQUISADO"]) == 0:
            sit, motivo = "FORA DA REGRA DE ADERÊNCIA", "A regra de aderência recusa o nome do produto."
        elif d and d["status"] == "SELECIONADA":
            sit, preco_regra = "APROVADO", str(d["preco_regra"])
        elif d and d["status"] == "REPROVADA":
            sit, motivo = "REPROVADO", d["motivo"]
        elif "FRETE A COLETAR" in obs or "SUL E SUDESTE" in obs or "credenciado" in obs or \
                (r["VALOR FRETE"] and float(r["VALOR FRETE"]) > 100000):
            sit, motivo = "A COLETAR", "Frete não calculado ou inválido na entrega do William."
        u = uf.get(cn) or receita[cn][1]
        linhas.append({"Chave": f"W13|{pref}|{linha}", "Origem": "William 13/10/2026", "Grupo": cat,
                       "ID FGV": i, "Nome Empresa": r["Nome Empresa"], "CNPJ": r["CNPJ"], "UF": u,
                       "Data coleta": r["Data coleta"], "FONTE": r["FONTE"],
                       "PRODUTO PESQUISADO": r["PRODUTO PESQUISADO"], "Preço lido": r["Preço PRODUTO"],
                       "Preço pela regra": preco_regra, "VALOR FRETE": r["VALOR FRETE"],
                       "OBS FRETE (origem)": obs, "Print": f"prints_candidatos/william_2026-10-13/{nome_print}",
                       "Situação": sit, "Motivo": motivo, "Sugestão": ""})
out = pd.DataFrame(linhas, columns=COLUNAS_CANDIDATOS)
with pd.ExcelWriter(ARQ_CANDIDATOS, engine="openpyxl") as w:
    out.to_excel(w, sheet_name="Candidatos", index=False)
    ws = w.book["Candidatos"]
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for col, larg in zip("ABCDEFGHIJKLMNOPQR", [16, 18, 18, 8, 28, 20, 5, 11, 40, 45, 10, 10, 10, 40, 30, 22, 45, 45]):
        ws.column_dimensions[col].width = larg
print(out["Situação"].value_counts().to_dict())
