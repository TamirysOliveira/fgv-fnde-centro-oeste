"""Atualiza a aba Dados de dashboard_resumo_coleta.xlsx com os resumo_coleta.csv recalculados a partir
de fnde_resultado_merge.xlsx. Edita só o XML da aba Dados (gráficos e fórmulas ficam intactos)."""
import csv, re, zipfile, shutil
from pathlib import Path
from xml.sax.saxutils import escape
ENT=Path("FNDE/Centro Oeste/Entrega"); ARQ=ENT/"dashboard_resumo_coleta.xlsx"
res={}
for p in ["EPI UNIFORME","LIMPEZA E HIGIENE","LIMPEZA PREDIAL"]:
    for r in csv.DictReader(open(ENT/p/"resumo_coleta.csv",encoding="utf-8-sig"),delimiter=";"):
        res[r["ID FGV"]]=r
z=zipfile.ZipFile(ARQ); xml=z.read("xl/worksheets/sheet3.xml").decode("utf-8")
def num(ref,v,s):
    return f'<c r="{ref}" s="{s}" t="n"><v>{v}</v></c>' if v is not None else f'<c r="{ref}" s="{s}" t="n"></c>'
vistos=set()
def troca_linha(m):
    row=m.group(0); r=int(m.group(1))
    a=re.search(rf'<c r="A{r}"[^>]*><v>(\d+)</v></c>',row)
    if not a: return row
    i=a.group(1); d=res[i]; vistos.add(i)
    for col,val in [("D",d["Preços coletados"]),("E",d["Faltam"]),("H",None),("I",d["Sem preço visível (coluna P)"])]:
        row,n=re.subn(rf'<c r="{col}{r}" s="(\d+)"[^>]*?(?:/>|>.*?</c>)',lambda mm: num(f"{col}{r}",val,mm.group(1)),row,count=1)
        assert n==1,(col,r)
    return row
xml=re.sub(r'<row r="(\d+)".*?</row>',troca_linha,xml)
assert vistos==set(res),(set(res)-vistos,vistos-set(res))
nota_fonte="• Fonte: arquivos resumo_coleta.csv de FNDE/Centro Oeste/Entrega (EPI UNIFORME, LIMPEZA E HIGIENE, LIMPEZA PREDIAL), recalculados em 13/10/2026 a partir de fnde_resultado_merge.xlsx (sua coleta + linhas aproveitadas da entrega do William)."
nota_hi="• Meta = Preços coletados + Faltam (5 por item). Coluna I = linhas na coluna P (link aproveitável, sem preço visível) do fnde_resultado_merge. Coluna H fica vazia: os resumos agora usam só a coluna padrão “Sem preço visível (coluna P)”."
xml=re.sub(r'(<c r="A124"[^>]*><is><t>).*?(</t>)',lambda m:m.group(1)+escape(nota_fonte)+m.group(2),xml)
xml=re.sub(r'(<c r="A125"[^>]*><is><t>).*?(</t>)',lambda m:m.group(1)+escape(nota_hi)+m.group(2),xml)
xml=re.sub(r'(<c r="A126"[^>]*><is><t>).*?(</t>)',lambda m:m.group(1)+escape("• Os resumos de cada grupo agora trazem só os insumos do próprio grupo (1000 e 1056 saíram do resumo de EPI UNIFORME).")+m.group(2),xml)
tmp=ARQ.with_suffix(".tmp.xlsx")
with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as out:
    for it in z.infolist():
        out.writestr(it, xml.encode("utf-8") if it.filename=="xl/worksheets/sheet3.xml" else z.read(it.filename))
z.close(); shutil.move(tmp,ARQ); print("ok",len(vistos))
