"""Observações que vão na coluna L ("OBS") da Entrega e no Detalhe da conferência.

Decisões de 13/10/2026 (Tamirys):
    * a coluna L deixa de ser "OBS Desconto" e passa a ser "OBS", com qualquer observação
      pertinente sobre a linha (o desconto continua não sendo considerado);
    * equivalências aceitas, sempre com observação: malha PV = malha fria (1104);
      sarja ou lona = brim ou equivalente (1105); PVC = impermeável (1108, 1116);
    * "aproximadamente": tolerância de 10% para mais ou para menos;
    * 1001: o insumo é álcool 46,2°, e "46°" no nome também vale;
    * característica "NÃO INFORMADO" no nome e não confirmada na página do produto: a linha
      fica, com observação ("Característica não confirmada na página do produto: ...").
      A conferência está em _historico/merge/evidencias_observacao.csv.
"""

from __future__ import annotations

import csv
import re
from functools import lru_cache
from pathlib import Path

from fgv_precos.config import DIR_HISTORICO
from fgv_precos.raspagem.descricao import normalizar, teores

# Conferência linha a linha das características "NÃO INFORMADO" na página do produto
# (13/10/2026). Decisão: a linha fica mesmo sem a característica na página, com observação.
ARQ_EVIDENCIAS = DIR_HISTORICO / "merge" / "evidencias_observacao.csv"

TOLERANCIA_APROXIMADAMENTE = 0.10

# (ID, regex do termo equivalente, regex do termo original, observação)
EQUIVALENCIAS = [
    ("1104", r"malha pv\b", r"malha fria", "Malha PV aceita como malha fria (equivalência)."),
    ("1105", r"\bsarja", r"\bbrim", "Sarja aceita como brim ou equivalente (equivalência)."),
    ("1105", r"\blona", r"\bbrim", "Lona aceita como brim ou equivalente (equivalência)."),
    ("1108", r"\bpvc\b", r"imperme", "PVC aceito como impermeável (equivalência)."),
    ("1116", r"\bpvc\b", r"imperme", "PVC aceito como impermeável (equivalência)."),
]

# Medidas "aproximadamente" com duas dimensões: pares aceitos (menor, maior), em cm.
# 1036 tem faixa (20–23 x 20–21): valem as pontas, cada uma com a tolerância.
RX_2D = r"\b(\d+(?:[,.]\d+)?)\s*(?:cm)?\s*x\s*(\d+(?:[,.]\d+)?)"
MEDIDA_2D = {
    "1022": ("40 x 60 cm", [(40, 60)]),
    "1032": ("60 x 80 cm", [(60, 80)]),
    "1036": ("20–23 x 20–21 cm", [(20, 20), (20, 21), (20, 23), (21, 23)]),
}
# Medidas "aproximadamente" com uma dimensão: (rótulo, regex do número, valor pedido).
MEDIDA_1D = {
    "1069": ("cabo de 60 cm", r"\b(\d+(?:[,.]\d+)?)\s*cm\b", 60.0),
    "1097": ("13 cm", r"\b(\d+(?:[,.]\d+)?)\s*cm\b", 13.0),
    "1070": ("rolo de 300 m", r"\b(\d+(?:[,.]\d+)?)\s*(?:m|mt|mts|metros)\b", 300.0),
}
# Medidas em que "mais longo" também serve (decisão de 13/10/2026: desentupidor 1069 com
# cabo de 90 cm fica, porque também é "cabo longo"). Aceita do pedido - 10% para cima.
MEDIDA_1D_OU_MAIOR = {"1069"}
# Teores aceitos que ganham observação na coluna OBS: {ID: [(teores, nota), ...]}.
TEOR_EQUIVALENTE_NOTA = {"1001": [
    ({46.0}, "Álcool 46° aceito para o insumo de 46,2°."),
    # 15/10/2026 (William): o 54% da descrição original também serve.
    ({54.0}, "Álcool 54% aceito para o insumo de 46,2° (descrição original; decisão de 15/10/2026)."),
]}


def _perto(valor: float, pedido: float) -> bool:
    return abs(valor - pedido) <= TOLERANCIA_APROXIMADAMENTE * pedido + 1e-9


def _fmt(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def medida_2d(id_fgv: str, produto: str) -> tuple[str, str] | None:
    """('ok'|'exata'|'fora'|'ausente', texto) para os insumos de MEDIDA_2D; None nos demais."""
    if id_fgv not in MEDIDA_2D:
        return None
    rot, pares = MEDIDA_2D[id_fgv]
    m = re.search(RX_2D, normalizar(produto))
    if not m:
        return "ausente", f"medida {rot}"
    x, y = sorted(float(v.replace(",", ".")) for v in m.groups())
    if (x, y) in pares:
        return "exata", ""
    if any(_perto(x, a) and _perto(y, b) for a, b in pares):
        return "ok", (f"Medida {_fmt(x)} x {_fmt(y)} cm aceita como aproximadamente {rot} "
                      f"(tolerância de 10%).")
    return "fora", f"medida {m.group(0)}; o insumo pede aproximadamente {rot} (fora da tolerância de 10%)"


def medida_1d(id_fgv: str, produto: str) -> tuple[str, str] | None:
    if id_fgv not in MEDIDA_1D:
        return None
    rot, rx, pedido = MEDIDA_1D[id_fgv]
    achadas = [float(v.replace(",", ".")) for v in re.findall(rx, normalizar(produto))]
    if not achadas:
        return "ausente", f"medida {rot}"
    if pedido in achadas:
        return "exata", ""
    perto = [v for v in achadas if _perto(v, pedido)]
    if perto:
        return "ok", f"Medida {_fmt(perto[0])} aceita como aproximadamente {rot} (tolerância de 10%)."
    maiores = [v for v in achadas if v > pedido]
    if id_fgv in MEDIDA_1D_OU_MAIOR and maiores:
        return "ok", (f"{rot.capitalize().replace(' de 60 cm', '')} de {_fmt(maiores[0])} cm aceito como "
                      f"cabo longo (insumo: aproximadamente 60 cm; decisão de 13/10/2026).")
    return "fora", (f"medida {', '.join(_fmt(v) for v in achadas)}; o insumo pede aproximadamente {rot} "
                    f"(fora da tolerância de 10%)")


def _chave_link(link: str) -> str:
    return re.sub(r"[#?].*$", "", str(link or "").strip().lower()).rstrip("/").removeprefix("https://") \
        .removeprefix("http://").removeprefix("www.")


@lru_cache(maxsize=4)
def ler_evidencias(arquivo: Path = ARQ_EVIDENCIAS) -> dict[tuple[str, str], tuple[str, str, str]]:
    """{(ID FGV, link): (situação, características, evidência)} da conferência na página."""
    if not Path(arquivo).exists():
        return {}
    with open(arquivo, encoding="utf-8-sig", newline="") as fh:
        return {(r["ID FGV"].strip(), _chave_link(r["Link"])):
                (r["Situação na página"].strip(), r["Características"].strip(), r["Evidência"].strip())
                for r in csv.DictReader(fh, delimiter=";")}


def obs_evidencia(id_fgv: str, link: str) -> str:
    """Observação da conferência na página: só quando a característica não foi confirmada."""
    ev = ler_evidencias().get((str(id_fgv), _chave_link(link)))
    if not ev:
        return ""
    situacao, caracteristicas, evidencia = ev
    if situacao == "NÃO CONFIRMADA":
        return f"Característica não confirmada na página do produto: {caracteristicas}."
    if situacao == "CONFIRMADA COM OBSERVAÇÃO":
        return evidencia
    if situacao == "DÚVIDA":
        return (f"Característica a confirmar ({caracteristicas}): a página diz "
                f"{evidencia.split(' (vale')[0].split(' [')[0]}.")
    return ""


def observacoes(id_fgv: str, produto: str, link: str = "") -> list[str]:
    """Observações pertinentes da linha (vão na coluna L "OBS" da Entrega)."""
    n = normalizar(produto)
    obs = [nota for i, rx_eq, rx_orig, nota in EQUIVALENCIAS
           if i == id_fgv and re.search(rx_eq, n) and not re.search(rx_orig, n)]
    for res in (medida_2d(id_fgv, produto), medida_1d(id_fgv, produto)):
        if res and res[0] == "ok":
            obs.append(res[1])
    do_prod = teores(produto) if id_fgv in TEOR_EQUIVALENTE_NOTA else set()
    for aceitos, nota in TEOR_EQUIVALENTE_NOTA.get(id_fgv, []):
        if do_prod and do_prod <= aceitos:
            obs.append(nota)
    if link:
        ev = obs_evidencia(id_fgv, link)
        if ev:
            obs.append(ev)
    return obs
