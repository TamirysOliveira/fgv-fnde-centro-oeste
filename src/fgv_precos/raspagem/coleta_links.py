"""
Coleta a partir de um link pronto: abre a página do produto, lê nome e preço,
calcula o frete para GO (CEP 74933-130) e tira o print. Não busca produtos.

Regras (as mesmas da coleta normal, ver config_raspagem.py):
    * Preço = o preço visível lido na página; o print vai para revisão humana
      antes de entrar no merge (o preço cheio, sem desconto de PIX/boleto,
      é conferido no print).
    * Fornecedor de GO: o frete NÃO é calculado (decisão de 13/10/2026); o
      print mostra nome e preço.
    * Frete que exige login -> coluna P; frete que não pode ser calculado ->
      linha descartada, com print de diagnóstico.
    * Produto sem preço visível -> coluna P (sem print); esgotado -> descartado.
O resultado (situacao.csv + prints) vai para revisão; nada é gravado na Entrega.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import replace
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError

from fgv_precos.fornecedores.cnae import somente_digitos
from fgv_precos.raspagem.coletor import Coletor, ler_fornecedores, ler_insumos_selecionados
from fgv_precos.raspagem.config_raspagem import CEPS
from fgv_precos.raspagem.descricao import pontuar
from fgv_precos.raspagem.lojas import loja_para
from fgv_precos.raspagem.modelos import Fornecedor
from fgv_precos.raspagem.plataformas.base import MOTIVO_FRETE_LOGIN

log = logging.getLogger(__name__)

COLUNAS_SITUACAO = ["Seq", "ID FGV", "Grupo", "Nome Empresa", "CNPJ", "UF", "Link pedido",
                    "Link final", "Produto", "Preço", "Preço de", "Frete", "OBS frete",
                    "Aderência", "Situação", "Aviso", "Print", "Data coleta", "Chave origem"]
OBS_GO = "Frete não calculado (GO para GO)"


def ler_lista(arquivo: Path) -> list[dict]:
    with open(arquivo, encoding="utf-8-sig", newline="") as fh:
        return [r for r in csv.DictReader(fh, delimiter=";") if (r.get("Link") or "").strip()]


def _fornecedor(item: dict) -> Fornecedor:
    """Da planilha de fornecedores (pelo CNPJ); senão, do próprio item da lista."""
    cnpj = somente_digitos(item.get("CNPJ"))
    for f in ler_fornecedores(item["Grupo"]):
        if somente_digitos(f.cnpj) == cnpj:
            return f
    link = urlparse(item["Link"].strip())
    return Fornecedor(nome=item.get("Nome Empresa", ""), cnpj=item.get("CNPJ", ""),
                      site=f"{link.scheme}://{link.netloc}", estado=item.get("UF", ""))


def coletar(lista: Path, saida: Path, headless: bool = True,
            insumos: dict | None = None) -> Path:
    """Coleta cada link de ``lista`` e grava ``saida/situacao.csv`` e ``saida/prints``."""
    itens = ler_lista(lista)
    if insumos is None:
        insumos = {i.id_fgv: i for i in ler_insumos_selecionados(None)}
    pasta_prints = saida / "prints"
    pasta_prints.mkdir(parents=True, exist_ok=True)
    (saida / "diagnostico").mkdir(exist_ok=True)
    cep = CEPS["GO"]
    linhas = []
    with Coletor(headless=headless) as coletor:
        for seq, item in enumerate(itens, start=1):
            id_fgv, link = item["ID FGV"].strip(), item["Link"].strip()
            reg = {"Seq": seq, "ID FGV": id_fgv, "Grupo": item["Grupo"],
                   "Nome Empresa": item.get("Nome Empresa", ""), "CNPJ": item.get("CNPJ", ""),
                   "UF": item.get("UF", ""), "Link pedido": link, "Chave origem": item.get("Chave", ""),
                   "Data coleta": date.today().isoformat()}
            log.info("--- %d/%d: %s %s", seq, len(itens), id_fgv, link)
            try:
                reg |= _coletar_um(coletor, item, insumos.get(id_fgv), pasta_prints, saida, seq, cep)
            except PlaywrightError as exc:
                reg |= {"Situação": "ERRO", "Aviso": f"erro de navegador: {exc}"[:300]}
            except Exception as exc:   # noqa: BLE001 - um link com problema não para os demais
                log.exception("Erro inesperado em %s", link)
                reg |= {"Situação": "ERRO", "Aviso": str(exc)[:300]}
            linhas.append(reg)
            _gravar(saida / "situacao.csv", linhas)   # grava a cada link
    ok = sum(1 for r in linhas if str(r.get("Situação", "")).startswith("OK"))
    log.info("RESUMO DA EXECUÇÃO: %d links, %d com preço e print, %d sem.", len(linhas), ok, len(linhas) - ok)
    return saida / "situacao.csv"


def _coletar_um(coletor: Coletor, item: dict, insumo, pasta_prints: Path, saida: Path,
                seq: int, cep: str) -> dict:
    fornecedor = _fornecedor(item)
    loja = loja_para(coletor.page, replace(fornecedor, site=item["Link"]))
    loja.insumo = insumo
    produto = loja.ler_produto(item["Link"].strip())
    if produto is None:
        return {"Situação": "SEM PRODUTO", "Aviso": "a página não abriu ou não é página de produto"}
    reg = {"Link final": produto.url, "Produto": produto.nome,
           "Preço": f"{produto.preco_final:.2f}" if produto.preco_final else "",
           "Preço de": f"{produto.preco_de:.2f}" if produto.preco_de else ""}
    if insumo is not None:
        reg["Aderência"] = f"{pontuar(insumo, produto.nome):.0f}"
        if reg["Aderência"] == "0":
            reg["Aviso"] = "CONFERIR: a regra de aderência recusa o nome do produto"
    if not produto.disponivel:
        return reg | {"Situação": "ESGOTADO"}
    if produto.motivo_sem_preco:
        return reg | {"Situação": "COLUNA P", "OBS frete": produto.motivo_sem_preco}
    uf = (item.get("UF") or fornecedor.estado or "").strip().upper()
    print_nome = f"{seq:03d}_{item['ID FGV']}.png"
    if uf == "GO":
        if not loja.tirar_print(str(pasta_prints / print_nome)):
            return reg | {"Situação": "SEM PRINT"}
        return reg | {"Situação": "OK (GO: frete não calculado)", "OBS frete": OBS_GO,
                      "Print": f"prints/{print_nome}"}
    frete = loja.calcular_frete(cep, "GO")
    if not frete.ok:
        diag = saida / "diagnostico" / print_nome
        loja.tirar_print(str(diag))
        situacao = "COLUNA P (frete só com login)" if frete.motivo == MOTIVO_FRETE_LOGIN else "SEM FRETE"
        return reg | {"Situação": situacao, "Aviso": f"{frete.motivo} (print em diagnostico/)"}
    if not loja.tirar_print(str(pasta_prints / print_nome)):
        return reg | {"Situação": "SEM PRINT"}
    cep_fmt = f"{cep[:5]}-{cep[5:]}"
    obs = (f"Frete grátis para o CEP {cep_fmt}" if frete.gratis
           else f"Opção mais barata para o CEP {cep_fmt}: {frete.modalidade}")
    return reg | {"Situação": "OK", "Frete": "" if frete.gratis else f"{frete.valor:.2f}",
                  "OBS frete": obs, "Print": f"prints/{print_nome}"}


def _gravar(arquivo: Path, linhas: list[dict]) -> None:
    with open(arquivo, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUNAS_SITUACAO, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(linhas)
