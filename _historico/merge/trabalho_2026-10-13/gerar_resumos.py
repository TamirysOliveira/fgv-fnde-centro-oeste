"""Recalcula resumo_coleta.csv de cada grupo a partir de fnde_resultado_merge.xlsx
(mesma lógica de _gravar_resumo em scripts/corrigir_entrega_2026_10_12.py)."""
import csv
from collections import Counter
import openpyxl
from pathlib import Path
ENT=Path("FNDE/Centro Oeste/Entrega")
COL=["ID FGV","Grupo","UF","Preços coletados","Faltam","Sem preço visível (coluna P)"]
for cat,pasta in {"EPI / UNIFORME":"EPI UNIFORME","LIMPEZA E HIGIENE":"LIMPEZA E HIGIENE","LIMPEZA PREDIAL":"LIMPEZA PREDIAL"}.items():
    ws=openpyxl.load_workbook(ENT/pasta/"fnde_resultado_merge.xlsx").active
    rows=[[c.value for c in r] for r in ws.iter_rows(min_row=2)]
    precos=Counter(str(r[1]) for r in rows if not r[15]); manuais=Counter(str(r[1]) for r in rows if r[15])
    arq=ENT/pasta/"resumo_coleta.csv"
    antigo=list(csv.DictReader(open(arq,encoding="utf-8-sig",newline=""),delimiter=";"))
    novo=[]
    for r in antigo:
        if r.get("Grupo")!=cat: continue
        n=precos[r["ID FGV"]]
        novo.append({"ID FGV":r["ID FGV"],"Grupo":cat,"UF":r.get("UF") or "GO","Preços coletados":str(n),"Faltam":str(max(5-n,0)),"Sem preço visível (coluna P)":str(manuais[r["ID FGV"]])})
    ids={r["ID FGV"] for r in novo}; assert set(precos)|set(manuais) <= ids, (pasta, (set(precos)|set(manuais))-ids)
    with open(arq,"w",encoding="utf-8-sig",newline="") as fh:
        w=csv.DictWriter(fh,fieldnames=COL,delimiter=";"); w.writeheader(); w.writerows(novo)
    print(pasta,len(novo),"preços",sum(precos.values()),"P",sum(manuais.values()),"completos",sum(1 for r in novo if r["Faltam"]=="0"),"sem preço",sum(1 for r in novo if r["Preços coletados"]=="0"))
