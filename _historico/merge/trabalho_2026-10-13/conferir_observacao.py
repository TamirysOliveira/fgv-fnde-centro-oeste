"""Conferência da regra de 13/10/2026: a observação e a quantidade da Embalagem são obrigatórias.

Para cada insumo, as características concretas da observação (material, cor, medida, acessório,
teor, quantidade) viram testes sobre o nome do produto. Finalidades ("para limpeza geral",
"uso profissional" etc.) não entram. Resultado por linha:
    ATENDE          todas as características aparecem no nome
    RETIRAR         o nome contraria uma característica, ou falta a quantidade da Embalagem
    NÃO INFORMADO   o nome não contraria, mas não mostra alguma característica
                    (inclui o teor ausente no nome: decisão de 13/10/2026)
Regras de 13/10/2026 (tarde), iguais às do robô (``descricao.py``):
    * teor (álcool, cloro, soda): teor diferente no nome = RETIRAR; sem teor = NÃO INFORMADO;
    * atributo de texto depois do "–" (aerossol, cabo longo...) é obrigatório: faltou = RETIRAR;
    * faixa (300–400 ml, 6 a 8 L, 20–23 x 20–21 cm): valem só as pontas;
    * "aproximadamente": sem tolerância, a medida tem que ser exata;
    * finalidades e instruções ("uso geral", "antisséptico para higienização das mãos",
      "especificar metragem por rolo na cotação"...) não são conferidas.
A planilha gravada tem a aba "Legenda", que explica tudo isso para quem for ler.
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
from fgv_precos.raspagem.descricao import interpretar, normalizar, teores  # noqa: E402
from fgv_precos.raspagem.config_raspagem import ATRIBUTOS_CONFERIR_NO_PRINT  # noqa: E402
from fgv_precos.merge.observacoes import medida_1d, medida_2d, observacoes  # noqa: E402


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t)


L5 = r"\b5\s*(l|lt|lts|litros?)\b"
ML500 = r"\b500\s*ml\b"
CHEIRO = r"lavanda|floral|fragr|perfum|petalas|morango|erva doce|jasmim|lotus|coco|eucalipto|limao|pinho|marine|tutti|algas|lavander|flores|citrus|campestre|bebe|talco|primavera|canela|maca|pessego|herbal|cereja|baunilha"

# ID: [(rótulo, regex que atende)]
CARACT = {
    "1104": [("malha fria", r"malha fria|malha pv\b"), ("gola redonda/esporte", r"gola (redonda|esporte|careca)")],
    "1105": [("brim ou equivalente", r"brim|sarja|lona|tecido"), ("bolsos", r"bolso"), ("fechamento frontal", r"ziper|braguilha|botao|fechamento")],
    "1107": [("antiderrapante", r"antiderrap")],
    "1108": [("impermeável", r"imperme|\bpvc\b"), ("solado antiderrapante", r"antiderrap"), ("cano médio ou longo", r"cano (medio|longo)")],
    "1109": [("cano médio ou longo", r"cano (medio|longo)|\b(3[5-9]|[4-9]\d)\s*cm")],
    "1110": [("forrada", r"forrad|com forro|c/ ?forro"), ("cano curto", r"cano curto")],
    "1112": [("algodão", r"algodao|cotton"), ("pigmentada", r"pigment")],
    "1113": [("incolor", r"incolor")],
    "1114": [("descartável", r"descart")],
    "1116": [("impermeável", r"imperme|\bpvc\b")],
    "1117": [("PVC", r"\bpvc\b"), ("capuz", r"capuz"), ("costuras seladas", r"costura")],
    "1119": [("FPS 30 ou 50", r"fps ?(30|50)|(30|50) ?fps")],
    # 1000-1004 e 1055: o teor é conferido à parte (teor_do_insumo); 1004 "refil", 1005 "aerossol",
    # 1006 "líquido", 1074/1075 degraus, 1088/1089 cabo, 1091/1092 placa: ATRIBUTOS_TEXTO (obrigatório).
    "1002": [("líquido", r"liquid")],
    "1003": [("gel", r"\bgel\b")],      # "antisséptico para higienização das mãos" é finalidade
    "1004": [("gel", r"\bgel\b")],
    "1005": [("com fragrância", CHEIRO), ("300 ou 400 ml", r"\b(300|400)\s*ml")],
    "1006": [("com fragrância", CHEIRO), ("5 L", L5)],
    "1007": [("aço inox", r"inox")],
    "1008": [("acrílica", r"acril"), ("incolor", r"incolor"), ("autobrilhante/impermeabilizante", r"autobrilh|auto brilh|imperme")],
    "1009": [("madeira", r"madeira|taco"), ("autobrilhante", r"autobrilh|auto brilh"), ("impermeabilizante", r"imperme")],
    "1010": [("5 L", L5)],
    "1011": [("quaternário de amônio", r"quaternar|amonio"), ("concentrado", r"concentra"), ("5 L", L5)],
    "1012": [("rede protetora", r"\brede"), ("gancho", r"gancho")],
    "1014": [("5 L", L5)],
    "1015": [("ácido", r"acid"), ("5 L", L5)],
    "1016": [("neutro", r"neutr"), ("líquido", r"liquid"), ("500 ml", ML500)],
    "1017": [("neutro", r"neutr"), ("concentrado", r"concentra"), ("5 L", L5)],
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
    "1028": [("500 ml", ML500)],
    "1029": [("concentrado", r"concentra"), ("5 L", L5)],
    "1031": [("500 ml", ML500)],
    "1032": [("alvejado", r"alvejad"), ("100% algodão", r"algodao")],
    "1033": [("100% algodão", r"algodao"), ("branco", r"branc")],
    # 1034: "especificar metragem por rolo na cotação" é instrução, não é conferida.
    "1034": [("folha dupla", r"folha dupla"), ("100% celulose/não reciclado", r"celulos|nao reciclad"),
             ("pacote/fardo", r"pct|pacote|fardo|\bc/\s*\d|com \d+ rolos|\d+ rolos|\b\d+\s*x\s*\d+\s*m")],
    "1035": [("folha simples", r"folha simples"), ("300 m", r"\b300\s*(m|mt|mts|metros)\b"), ("extra branco", r"extra branc"),
             ("mínimo 8 rolos (fardo)", r"(c/|com|fardo|pct)\s*(com\s*)?([89]|\d\d)\s*(rl|rolos?)?\b|\b([89]|\d\d)\s*rolos")],
    "1036": [("100% celulose", r"celulos"), ("fardo c/ 1.000 folhas", r"1\.?000")],
    "1037": [("alcalino", r"alcalin"), ("5 L", L5)],
    "1038": [("neutro", r"neutr")],
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
    "1055": [("em escamas", r"escama")],
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
    "1069": [("borracha", r"borracha"), ("cabo longo de ~60 cm", r"cabo longo|\d\s*cm")],   # medida: observacoes.py
    "1070": [("rolão ~300 m", r"rolao|300")],
    "1071": [("interfolhado", r"interfolh")],
    "1072": [("sabonete e/ou álcool gel", r"sabonete|alcool")],
    "1073": [("automático", r"automat"), ("refil", r"refil")],
    "1074": [("articulada", r"articulad|multifuncional"), ("alumínio", r"alumin")],
    "1076": [("com suporte", r"suporte")],
    "1077": [("cerdas de nylon", r"nylon|nailon")],
    "1078": [("cabo mínimo 50 cm", r"\b([5-9]\d|1\d\d)\s*cm")],
    "1079": [("30 m", r"\b30\s*(m|mt|mts|metros)\b")],
    "1082": [("mínimo 1.600 W", r"\b(1\.?[6-9]\d\d|[2-9]\.?\d{3})\s*w")],
    "1086": [("bico/esguicho", r"bico|esguicho|complet")],
    "1087": [("bico/esguicho", r"bico|esguicho|complet")],
    "1088": [("plástica ou metálica", r"plastic|metal|aco")],
    "1090": [("tampa basculante", r"basculante|tampa"), ("cabo longo", r"cabo longo")],
    "1091": [("dobrável/portátil", r"dobrav|portat|cavalete")],
    "1092": [("dobrável/portátil", r"dobrav|portat|cavalete")],
    "1093": [("borracha", r"borracha"), ("cabo longo", r"cabo longo")],
    "1094": [("borracha dupla", r"borracha dupla"), ("cabo longo", r"cabo longo")],
    "1095": [("com cabo", r"cabo")],
    "1096": [("cabo extensível", r"extensi|extensor|telescop")],
    "1097": [("plástico", r"plastic")],   # 13 cm: observacoes.py
    "1098": [("cerdas duras", r"dura")],
    "1099": [("cerdas naturais/palha", r"palha|piacava|natura")],
    "1100": [("pelo sintético", r"sintetic")],
    "1101": [("pelo sintético", r"sintetic")],
    "1102": [("pelo sintético", r"sintetic")],
    "1103": [("cerdas de nylon", r"nylon"), ("cabo longo", r"cabo longo")],
}
# Rótulos que vêm da coluna Embalagem (faltando no nome → RETIRAR).
EMBALAGEM = {"pacote c/ 8", "pacote c/ 10", "pacote c/ 100", "pacote", "pacote/fardo", "fardo c/ 1.000 folhas",
             "mínimo 8 rolos (fardo)", "5 L", "500 ml", "300 ou 400 ml"}
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
def _fmt(valores):
    return " ou ".join(f"{v:g}".replace(".", ",") for v in sorted(valores))


LEGENDA = [
    ("Para que serve", "Confere se o nome de cada produto (Entrega e candidatos) atende à Descrição e à Embalagem "
     "do insumo (FNDE/Centro Oeste/Pesquisa_SEAD_GO_Limpeza_Predial.csv). Arquivo de trabalho: não vai para a Entrega."),
    ("Onde", "Entrega (merge) = linha que está hoje na Entrega; candidatos.xlsx = linha de outra fonte (William, "
     "coleta por link, robô) que ainda pode entrar."),
    ("ATENDE", "O nome mostra todas as características conferidas. A linha fica."),
    ("RETIRAR", "O nome contraria uma característica (outro teor, outra medida, outra cor...), ou falta a quantidade "
     "da coluna Embalagem, ou falta o atributo obrigatório depois do travessão \"–\". A linha sai: se é da Entrega, "
     "vai para correcoes_entrega.csv e produtos_recusados.csv; se é candidato, fica REPROVADO."),
    ("NÃO INFORMADO", "O nome não contraria, mas também não mostra alguma característica (coluna Detalhe). "
     "A página do produto foi conferida (colunas Situação/Evidência na página). A linha fica; se a característica "
     "não aparece na página, recebe observação na coluna OBS (decisão de 13/10/2026, tarde)."),
    ("Detalhe", "Qual característica faltou ou foi contrariada."),
    ("Situação na página", "Só nas linhas NÃO INFORMADO: CONFIRMADA (a página do produto mostra a característica), "
     "NÃO CONFIRMADA (não mostra) ou DÚVIDA (mostra algo parecido, a decidir). Conferido em 13/10/2026 lendo o texto "
     "completo da página (inclusive abas de especificação). Decisão de 13/10/2026: a linha fica mesmo NÃO CONFIRMADA, "
     "com observação na coluna OBS da Entrega."),
    ("Evidência na página", "Trecho da página que confirma, ou o motivo de não confirmar. Fonte: "
     "_historico/merge/evidencias_observacao.csv."),
    ("Observação", "Texto da Descrição depois do primeiro \" - \" ou \";\". Só se conferem características que "
     "dá para ver ou medir no produto (material, cor, medida, teor, formato, peças/acessórios). Finalidades e "
     "instruções não são conferidas: \"uso geral\", \"para limpeza geral\", \"antisséptico para higienização das "
     "mãos\", \"uso conforme risco/atividade\", \"livre de CFC quando aplicável\", \"identificação da empresa\", "
     "\"definir manga conforme posto\", \"especificar metragem por rolo na cotação\" etc."),
    ("Teor", "Álcool (1001-1004), cloro (1000) e soda (1055). Teor diferente no nome = RETIRAR; sem teor no nome = "
     "NÃO INFORMADO (conferir no print/página). °, º, % e INPM valem igualmente. 1001 = 46,2° (\"46°\" também vale, "
     "decisão de 13/10/2026; antes era 54%). 1000 = 2% ou 2,5%. 1055 = mínimo 96%."),
    ("Faixa de medida", "Valem só as pontas: 1005 = 300 ml ou 400 ml; 1066 = 6 L ou 8 L; 1000 = 2% ou 2,5%; "
     "1036 = 20 ou 23 x 20 ou 21 cm (decisão de 13/10/2026)."),
    ("\"Aproximadamente\"", "Tolerância de 10% para mais ou para menos (decisão de 13/10/2026, tarde): 1022 "
     "40 x 60 cm; 1032 60 x 80 cm; 1036 20–23 x 20–21 cm (pontas da faixa, cada uma com 10%); 1069 cabo de 60 cm (cabo maior também serve); "
     "1070 rolo de 300 m; 1097 13 cm. Medida aceita pela tolerância ganha observação na coluna OBS."),
    ("OBS", "Coluna L da Entrega (antes \"OBS Desconto\"): observações pertinentes da linha, como equivalência "
     "aceita, medida aceita pela tolerância ou teor equivalente (1001: 46° para 46,2°). No Detalhe desta planilha "
     "aparecem depois de \"OBS:\"."),
    ("Atributo obrigatório", "Texto depois do travessão \"–\" que não é medida, com os sinônimos aceitos: 1004 refil; "
     "1005 aerossol/aerosol/spray; 1006 líquido; 1074 12 degraus; 1075 5 ou 6 degraus; 1088 cabo curto; "
     "1089 cabo longo; 1091 banheiro interditado ou banheiro fora de uso; 1092 piso molhado ou escorregadio."),
    ("Pás 1088/1089", "Sem \"cabo curto\"/\"cabo longo\" no nome: NÃO INFORMADO (conferir no print/página), e não "
     "RETIRAR, porque quase nenhuma loja escreve isso no nome (decisão de 13/10/2026)."),
    ("Equivalência", "Aceita, com observação na coluna OBS da Entrega e no Detalhe: malha PV = malha fria (1104); sarja ou lona = brim ou equivalente "
     "(1105); PVC = impermeável (1108, 1116). Decisão de 13/10/2026."),
    ("Não conferidas (observações)", "Propriedades declaradas não são obrigatórias: biodegradável, ação bactericida, "
     "desengordurante, neutralizador de odores, absorvente; \"uso profissional\" é finalidade (13/10/2026)."),
    ("Fora da conferência", "1083/1084/1085 (enceradeiras: ficam como estão, decisão de 13/10/2026) e 1120-1123 "
     "(serviços)."),
]


def avaliar(id_fgv, produto, emb, ins=None):
    n = norm(produto)
    contra = [m for i, rx, m in CONTRARIA if i == id_fgv and re.search(rx, n)]
    falta = [r for r, rx in CARACT.get(id_fgv, []) if not re.search(rx, n)]
    obrig = []      # atributo de texto obrigatório que faltou (RETIRAR)
    if ins is not None:
        if ins.teores:
            u = "°" if id_fgv in ("1001", "1002", "1003", "1004") else "%"
            pedido = (f"mínimo {_fmt([min(ins.teores)])}%" if ins.teor_minimo
                      else " ou ".join(f"{_fmt([t])}{u}" for t in sorted(ins.teores)))
            do_prod = teores(produto)
            if not do_prod:
                falta.append(f"teor {pedido}")
            elif not (any(t >= min(ins.teores) for t in do_prod) if ins.teor_minimo else ins.teores & do_prod):
                contra.append(f"teor {_fmt(do_prod)} no nome; o insumo pede {pedido}")
        nn = normalizar(produto)
        for alternativas in ins.atributos_texto:
            if not any(re.search(rf"\b{re.escape(a)}\b", nn) for a in alternativas):
                if id_fgv in ATRIBUTOS_CONFERIR_NO_PRINT:
                    falta.append(" ou ".join(alternativas))
                else:
                    obrig.append(f"falta no nome o atributo obrigatório: {' ou '.join(alternativas)}")
    for res in (medida_2d(id_fgv, produto), medida_1d(id_fgv, produto)):
        if not res:
            continue
        estado, texto = res
        if estado == "fora":
            contra.append(texto)
        elif estado == "ausente" and id_fgv not in ("1069", "1070"):   # 1069/1070: CARACT
            falta.append(texto)
    equiv = observacoes(id_fgv, produto)
    falta_emb = [f for f in falta if f in EMBALAGEM]
    if contra or falta_emb or obrig:
        return "RETIRAR", "; ".join(contra + obrig + [f"falta no nome: {f}" for f in falta_emb])
    nota = (" | OBS: " + " ".join(equiv)) if equiv else ""
    if falta:
        return "NÃO INFORMADO", "não informado no nome: " + ", ".join(falta) + nota
    return "ATENDE", nota.removeprefix(" | ")


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
    interp = {i: interpretar(i, ins.loc[i, "Grupo de Insumo"], ins.loc[i, "Descrição"], ins.loc[i, "Embalagem"])
              for i in out["ID FGV"].unique()}
    res = [avaliar(r["ID FGV"], r["Produto"], ins.loc[r["ID FGV"], "Embalagem"].strip(), interp[r["ID FGV"]])
           for _, r in out.iterrows()]
    out["Resultado"] = [a for a, _ in res]
    out["Detalhe"] = [b for _, b in res]
    out.insert(3, "Descrição do insumo", [ins.loc[i, "Descrição"] for i in out["ID FGV"]])
    out.insert(4, "Embalagem", [ins.loc[i, "Embalagem"] for i in out["ID FGV"]])
    # Conferência na página (13/10/2026): evidência registrada em _historico/merge/evidencias_observacao.csv
    from fgv_precos.merge.observacoes import _chave_link, ler_evidencias
    ev = ler_evidencias()
    chaves = [(r["ID FGV"], _chave_link(r["Link"])) for _, r in out.iterrows()]
    out["Situação na página"] = [ev.get(k, ("", "", ""))[0] if res == "NÃO INFORMADO" else ""
                                 for k, res in zip(chaves, out["Resultado"])]
    out["Evidência na página"] = [ev.get(k, ("", "", ""))[2] if res == "NÃO INFORMADO" else ""
                                  for k, res in zip(chaves, out["Resultado"])]
    arq = Path(__file__).with_name("conferencia_observacao_2026-10-13.xlsx")
    with pd.ExcelWriter(arq) as xw:
        out.to_excel(xw, sheet_name="Conferência", index=False)
        pd.DataFrame(LEGENDA, columns=["Termo", "O que significa"]).to_excel(xw, sheet_name="Legenda", index=False)
    print(out.groupby(["Onde", "Resultado"]).size())
    return out


if __name__ == "__main__":
    main()
