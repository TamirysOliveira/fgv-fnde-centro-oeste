"""Conferência da regra de 13/10/2026: a observação e a quantidade da Embalagem são obrigatórias.

Para cada insumo, as características concretas da observação (material, cor, medida, acessório,
teor, quantidade) viram testes sobre o nome do produto. Finalidades ("para limpeza geral",
"uso profissional" etc.) não entram. Resultado por linha:
    ATENDE          todas as características aparecem no nome
    RETIRAR         o nome contraria uma característica, ou falta a quantidade da Embalagem
    NÃO INFORMADO   o nome não contraria, mas não mostra alguma característica
    DÚVIDA          medida "aproximadamente" diferente (tolerância não definida)
Uso: python conferir_observacao.py  (grava conferencia_observacao_2026-10-13.xlsx ao lado)
"""
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ / "src"))
from fgv_precos.merge.montagem import DIR_ENTREGA, GRUPOS, NOME_SAIDA, ler_candidatos, ler_insumos  # noqa: E402


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t)


L5 = r"\b5\s*(l|lt|lts|litros?)\b"
ML500 = r"\b500\s*ml\b"
CHEIRO = r"lavanda|floral|fragr|perfum|petalas|morango|erva doce|jasmim|lotus|coco|eucalipto|limao|pinho|marine|tutti|algas|lavander|flores|citrus|campestre|bebe|talco|primavera|canela|maca|pessego|herbal|cereja|baunilha"

# ID: [(rótulo, regex que atende)]
CARACT = {
    "1104": [("malha fria", r"malha fria"), ("gola redonda/esporte", r"gola (redonda|esporte|careca)")],
    "1105": [("brim ou equivalente", r"brim|tecido"), ("bolsos", r"bolso"), ("fechamento frontal", r"ziper|braguilha|botao|fechamento")],
    "1107": [("antiderrapante", r"antiderrap")],
    "1108": [("impermeável", r"imperme"), ("solado antiderrapante", r"antiderrap"), ("cano médio ou longo", r"cano (medio|longo)")],
    "1109": [("cano médio ou longo", r"cano (medio|longo)|\b(3[5-9]|[4-9]\d)\s*cm")],
    "1110": [("forrada", r"forrad|com forro|c/ ?forro"), ("cano curto", r"cano curto")],
    "1112": [("algodão", r"algodao|cotton"), ("pigmentada", r"pigment")],
    "1113": [("incolor", r"incolor")],
    "1114": [("descartável", r"descart")],
    "1116": [("impermeável", r"imperme")],
    "1117": [("PVC", r"\bpvc\b"), ("capuz", r"capuz"), ("costuras seladas", r"costura")],
    "1119": [("FPS 30 ou 50", r"fps ?(30|50)|(30|50) ?fps")],
    "1000": [("teor de cloro 2% a 2,5%", r"2[,.]?0? ?(%|a|-|e) ?2[,.]5")],
    "1002": [("70%", r"\b70"), ("líquido", r"liquid")],
    "1003": [("70%", r"\b70"), ("gel", r"\bgel\b"), ("antisséptico/mãos", r"antissep|maos")],
    "1004": [("70%", r"\b70"), ("gel", r"\bgel\b"), ("refil", r"refil")],
    "1005": [("aerossol", r"aeross|aerosol|spray"), ("com fragrância", CHEIRO), ("300–400 ml", r"\b(3\d\d|400)\s*ml")],
    "1006": [("líquido", r"liquid"), ("neutralizador de odores", r"neutraliz"), ("com fragrância", CHEIRO), ("5 L", L5)],
    "1007": [("aço inox", r"inox")],
    "1008": [("acrílica", r"acril"), ("incolor", r"incolor"), ("autobrilhante/impermeabilizante", r"autobrilh|auto brilh|imperme")],
    "1009": [("madeira", r"madeira|taco"), ("autobrilhante", r"autobrilh|auto brilh"), ("impermeabilizante", r"imperme")],
    "1010": [("ação bactericida", r"bacteric|germic"), ("5 L", L5)],
    "1011": [("quaternário de amônio", r"quaternar|amonio"), ("concentrado", r"concentra"), ("5 L", L5)],
    "1012": [("rede protetora", r"\brede"), ("gancho", r"gancho")],
    "1014": [("5 L", L5)],
    "1015": [("ácido", r"acid"), ("5 L", L5)],
    "1016": [("neutro", r"neutr"), ("líquido", r"liquid"), ("500 ml", ML500)],
    "1017": [("neutro", r"neutr"), ("concentrado", r"concentra"), ("biodegradável", r"biodegrad"), ("5 L", L5)],
    "1018": [("pacote c/ 8", r"(c/|com|pct|pacote)\s*(com\s*)?8\b|\b8\s*(un|unid)")],
    "1019": [("espuma", r"espuma"), ("fibra abrasiva", r"fibra|abrasiv")],
    "1020": [("branca", r"branc"), ("não abrasiva", r"nao abrasiv"), ("pacote c/ 10", r"(c/|com|pct|pacote)\s*(com\s*)?10\b|\b10\s*(un|unid)")],
    "1021": [("verde", r"verde"), ("abrasiva", r"abrasiv"), ("pacote c/ 10", r"(c/|com|pct|pacote)\s*(com\s*)?10\b|\b10\s*(un|unid)")],
    "1022": [("algodão", r"algodao"), ("amarela ou branca", r"amarel|branc")],
    "1023": [("branca", r"branc"), ("fios longos", r"fios longos")],
    "1024": [("aço carbono", r"carbono"), ("pacote", r"pct|pacote|\bc/\s*\d|com \d+ un")],
    "1025": [("líquido", r"liquid"), ("500 ml", ML500)],
    "1026": [("5 L", L5)],
    "1027": [("líquido", r"liquid"), ("5 L", L5)],
    "1028": [("desengordurante", r"desengord"), ("500 ml", ML500)],
    "1029": [("concentrado", r"concentra"), ("5 L", L5)],
    "1031": [("500 ml", ML500)],
    "1032": [("alvejado", r"alvejad"), ("100% algodão", r"algodao")],
    "1033": [("100% algodão", r"algodao"), ("branco", r"branc"), ("absorvente", r"absorv")],
    "1034": [("folha dupla", r"folha dupla"), ("100% celulose/não reciclado", r"celulos|nao reciclad"),
             ("metragem por rolo", r"\d\s*(m|mt|mts|metros)\b"), ("pacote/fardo", r"pct|pacote|fardo|\bc/\s*\d|com \d+ rolos|\d+ rolos|\b\d+\s*x\s*\d+\s*m")],
    "1035": [("folha simples", r"folha simples"), ("300 m", r"\b300\s*(m|mt|mts|metros)\b"), ("extra branco", r"extra branc"),
             ("mínimo 8 rolos (fardo)", r"(c/|com|fardo|pct)\s*(com\s*)?([89]|\d\d)\s*(rl|rolos?)?\b|\b([89]|\d\d)\s*rolos")],
    "1036": [("100% celulose", r"celulos"), ("fardo c/ 1.000 folhas", r"1\.?000")],
    "1037": [("alcalino", r"alcalin"), ("5 L", L5)],
    "1038": [("neutro", r"neutr"), ("biodegradável", r"biodegrad")],
    "1039": [("biodegradável", r"biodegrad")],
    "1040": [("concentrado", r"concentra"), ("5 L", L5)],
    "1041": [("com fragrância", CHEIRO), ("5 L", L5)],
    "1042": [("pacote c/ 100", r"(c/|com|pct)\s*(com\s*)?100\b|\b100\s*(un|unid)")],
    "1043": [("pacote c/ 100", r"(c/|com|pct)\s*(com\s*)?100\b|\b100\s*(un|unid)")],
    "1044": [("reforçado", r"reforc"), ("pacote c/ 100", r"(c/|com|pct)\s*(com\s*)?100\b|\b100\s*(un|unid)")],
    "1045": [("reforçado", r"reforc"), ("pacote c/ 100", r"(c/|com|pct)\s*(com\s*)?100\b|\b100\s*(un|unid)")],
    "1046": [("reforçado", r"reforc"), ("pacote c/ 100", r"(c/|com|pct)\s*(com\s*)?100\b|\b100\s*(un|unid)")],
    "1047": [("cor preta", r"pret"), ("pacote c/ 100", r"(c/|com|pct)\s*(com\s*)?100\b|\b100\s*(un|unid)")],
    "1048": [("reforçado", r"reforc"), ("pacote c/ 100", r"(c/|com|pct)\s*(com\s*)?100\b|\b100\s*(un|unid)")],
    "1050": [("abrasivo", r"abrasiv")],
    "1051": [("base acrílica/polietilênica", r"acril|polietil"), ("5 L", L5)],
    "1053": [("350 mm", r"350")],
    "1054": [("350 mm", r"350")],
    "1055": [("em escamas", r"escama"), ("mínimo 96%", r"\b9[6-9]\s*%")],
    "1056": [("com alça", r"\balca")],
    "1058": [("com alça", r"\balca")],
    "1059": [("alça metálica", r"alca metal")],
    "1060": [("com alça", r"\balca")],
    "1061": [("plástico", r"plastic|pet\b"), ("gatilho", r"gatilho")],
    "1062": [("alumínio", r"alumin")],
    "1063": [("balde espremedor", r"espremedor"), ("compartimentos água limpa/suja", r"limpa.*suja|compartiment"), ("pá", r"\bpa\b")],
    "1064": [("rodas", r"roda"), ("tampa", r"tampa")],
    "1065": [("plástico PP", r"\bpp\b|polipropileno"), ("rodas", r"roda"), ("tampa", r"tampa"), ("pedal", r"pedal")],
    "1066": [("tampa", r"tampa"), ("pedal", r"pedal")],
    "1067": [("polietileno", r"polietil")],
    "1068": [("borracha", r"borracha"), ("cabo ergonômico", r"ergonom")],
    "1069": [("borracha", r"borracha"), ("cabo longo ~60 cm", r"cabo longo|(5[5-9]|6[0-5])\s*cm")],
    "1070": [("rolão ~300 m", r"rolao|300")],
    "1071": [("interfolhado", r"interfolh")],
    "1072": [("sabonete e/ou álcool gel", r"sabonete|alcool")],
    "1073": [("automático", r"automat"), ("refil", r"refil")],
    "1074": [("articulada", r"articulad|multifuncional"), ("alumínio", r"alumin")],
    "1076": [("com suporte", r"suporte")],
    "1077": [("cerdas de nylon", r"nylon|nailon")],
    "1078": [("cabo mínimo 50 cm", r"\b([5-9]\d|1\d\d)\s*cm")],
    "1079": [("30 m", r"\b30\s*(m|mt|mts|metros)\b")],
    "1080": [("uso profissional", r"profission|industrial")],
    "1081": [("uso profissional", r"profission|industrial")],
    "1082": [("mínimo 1.600 W", r"\b(1\.?[6-9]\d\d|[2-9]\.?\d{3})\s*w")],
    "1086": [("bico/esguicho", r"bico|esguicho|complet")],
    "1087": [("bico/esguicho", r"bico|esguicho|complet")],
    "1088": [("plástica ou metálica", r"plastic|metal|aco")],
    "1089": [("cabo longo", r"cabo longo")],
    "1090": [("tampa basculante", r"basculante|tampa"), ("cabo longo", r"cabo longo")],
    "1091": [("dobrável/portátil", r"dobrav|portat|cavalete")],
    "1092": [("dobrável/portátil", r"dobrav|portat|cavalete")],
    "1093": [("borracha", r"borracha"), ("cabo longo", r"cabo longo")],
    "1094": [("borracha dupla", r"borracha dupla"), ("cabo longo", r"cabo longo")],
    "1095": [("com cabo", r"cabo")],
    "1096": [("cabo extensível", r"extensi|extensor|telescop")],
    "1097": [("plástico", r"plastic"), ("~13 cm", r"\b1[2-4]\s*cm")],
    "1098": [("cerdas duras", r"dura")],
    "1099": [("cerdas naturais/palha", r"palha|piacava|natura")],
    "1100": [("pelo sintético", r"sintetic")],
    "1101": [("pelo sintético", r"sintetic")],
    "1102": [("pelo sintético", r"sintetic")],
    "1103": [("cerdas de nylon", r"nylon"), ("cabo longo", r"cabo longo")],
}
# Rótulos que vêm da coluna Embalagem (faltando no nome → RETIRAR).
EMBALAGEM = {"pacote c/ 8", "pacote c/ 10", "pacote c/ 100", "pacote", "pacote/fardo", "fardo c/ 1.000 folhas",
             "mínimo 8 rolos (fardo)", "5 L", "500 ml", "300–400 ml"}
# Contradições explícitas: (ID, regex no nome) → motivo
CONTRARIA = [
    ("1104", r"\bbrim\b", "camisa de brim; o insumo pede malha fria"),
    ("1104", r"gola italiana|gola polo|gola v\b", "gola diferente de redonda/esporte"),
    ("1109", r"cano curto|\b2\d\s*cm", "cano curto (até 29 cm); o insumo pede cano médio ou longo"),
    ("1110", r"sem forro|s/ ?forro", "sem forro; o insumo pede forrada"),
    ("1110", r"cano (medio|longo)", "cano médio/longo; o insumo pede cano curto"),
    ("1012", r"adesiv|disco", "desodorizador adesivo/discos; o insumo pede pedra com rede e gancho"),
    ("1033", r"estampad|xadrez", "estampado; o insumo pede branco"),
    ("1032", r"cinza", "cinza; o insumo pede pano alvejado"),
    ("1022", r"\b28\s*x\s*38", "28x38 cm; o insumo pede aproximadamente 40x60 cm"),
    ("1103", r"s/ ?cabo|sem cabo", "sem cabo; o insumo pede cabo longo"),
    ("1088", r"cabo longo", "cabo longo; o insumo pede cabo curto"),
]
# Quantidade diferente de 1 em insumo vendido por unidade/par (sem Embalagem).
QTD_OUTRA = r"(kit|caixa|cx|pct|pacote)\s*(com|c/)?\s*\d+|\(\s*\d+\s*unidades\s*\)|\b([2-9]|\d\d+)\s*unidades"
DUVIDA_MEDIDA = {
    "1022": (r"\b(\d+)\s*(?:cm)?\s*x\s*(\d+)", (40, 60)),
    "1032": (r"\b(\d+)\s*(?:cm)?\s*x\s*(\d+)", (60, 80)),
    "1036": (r"\b(\d+[,.]?\d*)\s*x\s*(\d+[,.]?\d*)", (21.5, 20.5)),
}


def avaliar(id_fgv, produto, emb):
    n = norm(produto)
    contra = [m for i, rx, m in CONTRARIA if i == id_fgv and re.search(rx, n)]
    falta = [r for r, rx in CARACT.get(id_fgv, []) if not re.search(rx, n)]
    if not emb and re.search(QTD_OUTRA, n) and id_fgv not in ("1038",):
        contra.append("o nome traz outra quantidade; o insumo é por unidade")
    falta_emb = [f for f in falta if f in EMBALAGEM]
    if contra or falta_emb:
        return "RETIRAR", "; ".join(contra + [f"falta no nome: {f}" for f in falta_emb])
    duv = ""
    if id_fgv in DUVIDA_MEDIDA:
        rx, (a, b) = DUVIDA_MEDIDA[id_fgv]
        m = re.search(rx, n)
        if m:
            x, y = sorted(float(v.replace(",", ".")) for v in m.groups())
            if abs(x - min(a, b)) > 0.1 * min(a, b) or abs(y - max(a, b)) > 0.1 * max(a, b):
                duv = f"medida {m.group(0)} (insumo: aproximadamente {a:g} x {b:g})"
    if duv:
        return "DÚVIDA", duv + (f"; não informado: {', '.join(falta)}" if falta else "")
    if falta:
        return "NÃO INFORMADO", "não informado no nome: " + ", ".join(falta)
    return "ATENDE", ""


def main():
    ins = ler_insumos()
    linhas = []
    for cat, (pasta, _) in GRUPOS.items():
        df = pd.read_excel(DIR_ENTREGA / pasta / NOME_SAIDA, dtype=str).fillna("")
        for _, r in df.iterrows():
            if r["Link aproveitável"].strip():
                continue
            linhas.append({"Onde": "Entrega (merge)", "Chave": "", "ID FGV": r["Código FGV"], "Grupo": cat,
                           "Nome Empresa": r["Nome Empresa"], "CNPJ": r["CNPJ"], "Produto": r["PRODUTO PESQUISADO"],
                           "Link": r["FONTE"], "Situação": ""})
    cand = ler_candidatos()
    sel = cand[cand["Situação"].isin(["APROVADO", "A REVISAR"]) | cand["Sugestão"].str.startswith("Corresponde")]
    for _, r in sel.iterrows():
        linhas.append({"Onde": "candidatos.xlsx", "Chave": r["Chave"], "ID FGV": r["ID FGV"], "Grupo": r["Grupo"],
                       "Nome Empresa": r["Nome Empresa"], "CNPJ": r["CNPJ"], "Produto": r["PRODUTO PESQUISADO"],
                       "Link": r["FONTE"], "Situação": r["Situação"]})
    out = pd.DataFrame(linhas)
    out = out[~out["ID FGV"].isin(["1083", "1084", "1085"])]
    res = [avaliar(r["ID FGV"], r["Produto"], ins.loc[r["ID FGV"], "Embalagem"].strip()) for _, r in out.iterrows()]
    out["Resultado"] = [a for a, _ in res]
    out["Detalhe"] = [b for _, b in res]
    out.insert(3, "Descrição do insumo", [ins.loc[i, "Descrição"] for i in out["ID FGV"]])
    out.insert(4, "Embalagem", [ins.loc[i, "Embalagem"] for i in out["ID FGV"]])
    arq = Path(__file__).with_name("conferencia_observacao_2026-10-13.xlsx")
    out.to_excel(arq, index=False)
    print(out.groupby(["Onde", "Resultado"]).size())
    return out


if __name__ == "__main__":
    main()
