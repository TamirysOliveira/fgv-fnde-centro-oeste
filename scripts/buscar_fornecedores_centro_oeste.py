"""
Busca de fornecedores atacadistas em Goiás (GO) e Distrito Federal (DF)
para a pesquisa de preços FNDE - Centro-Oeste.

Etapas (subcomandos), na ordem em que normalmente são usados:

    descobrir   Filtra os Dados Abertos do CNPJ (Receita Federal): empresas
                ATIVAS em GO/DF com CNAE da Divisão 46 (principal ou
                secundário). Saída: data/interim/candidatos_GO_DF.csv

    verificar   Para cada candidato com e-mail corporativo, testa o site do
                domínio: marketplace? preço visível? vende itens de qual
                Grupo de Insumo? Saída: data/interim/candidatos_verificados.csv
                (é uma lista PARA CONFERÊNCIA HUMANA, nada é aceito sozinho).

    validar     Revalida CNPJ/CNAE dos fornecedores do arquivo curado em APIs
                públicas (BrasilAPI, CNPJ.ws, ReceitaWS) e grava um relatório.

    exportar    Gera as planilhas FNDE_<Grupo>.xlsx a partir do arquivo
                curado data/curated/fornecedores_centro_oeste.csv.

Exemplos (rodar na raiz do repositório):

    python scripts/buscar_fornecedores_centro_oeste.py descobrir --competencia 2026-09
    python scripts/buscar_fornecedores_centro_oeste.py descobrir --dump-dir D:/receita/2026-09
    python scripts/buscar_fornecedores_centro_oeste.py verificar --limite 300
    python scripts/buscar_fornecedores_centro_oeste.py validar
    python scripts/buscar_fornecedores_centro_oeste.py exportar
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from fgv_precos.config import (
    ARQ_FORNECEDORES_CURADOS,
    ARQ_INSUMOS_PADRAO,
    DIR_DADOS_INTERMEDIARIOS,
    DIR_SAIDA_FORNECEDORES,
    UFS_PRIORITARIAS,
)
from fgv_precos.fornecedores import exportador, receita_dump
from fgv_precos.fornecedores.cnpj_api import ConsultaCNPJ
from fgv_precos.fornecedores.insumos import ler_insumos, resumo_por_grupo
from fgv_precos.fornecedores.site_checker import (
    VerificadorSite,
    site_a_partir_do_email,
)
from fgv_precos.logging_config import configurar_logging

log = logging.getLogger("buscar_fornecedores")


# ---------------------------------------------------------------------------
# Subcomandos
# ---------------------------------------------------------------------------
def cmd_descobrir(args: argparse.Namespace) -> int:
    """Gera a lista de candidatos atacadistas a partir do dump da Receita."""
    ufs = tuple(u.upper() for u in args.ufs)
    if args.dump_dir:
        pasta = Path(args.dump_dir)
        if not pasta.is_dir():
            log.error("Pasta do dump não existe: %s", pasta)
            return 1
    else:
        pasta = receita_dump.baixar_dump(args.competencia)
    receita_dump.gerar_candidatos(pasta, ufs)
    return 0


def cmd_verificar(args: argparse.Namespace) -> int:
    """Verifica o site (via domínio do e-mail) de cada candidato."""
    entrada = Path(args.candidatos)
    if not entrada.exists():
        log.error("Arquivo de candidatos não encontrado: %s (rode 'descobrir' antes)", entrada)
        return 1
    df = pd.read_csv(entrada, sep=";", dtype=str, keep_default_na=False)
    df["site_sugerido"] = df["email"].map(site_a_partir_do_email)
    com_site = df[df["site_sugerido"].notna()].drop_duplicates("site_sugerido")
    log.info("%d de %d candidatos têm e-mail corporativo (site sugerido).",
             len(com_site), len(df))
    if args.limite:
        com_site = com_site.head(args.limite)

    verificador = VerificadorSite()
    linhas = []
    for i, (_, cand) in enumerate(com_site.iterrows(), start=1):
        try:
            res = verificador.verificar(cand["site_sugerido"])
        except Exception:  # noqa: BLE001 - um site com problema não pode parar o lote
            log.exception("Erro inesperado ao verificar %s", cand["site_sugerido"])
            continue
        linhas.append({
            **cand.to_dict(),
            "status_site": res.status,
            "tem_preco": res.tem_preco,
            "preco_oculto": res.preco_oculto,
            "exemplos_preco": " | ".join(res.exemplos_preco),
            "grupos_sugeridos": " | ".join(res.grupos_atendidos()),
            "paginas_lidas": " | ".join(res.paginas_lidas),
        })
        if i % 25 == 0:
            log.info("Progresso: %d/%d sites verificados", i, len(com_site))

    saida = DIR_DADOS_INTERMEDIARIOS / "candidatos_verificados.csv"
    pd.DataFrame(linhas).to_csv(saida, index=False, sep=";", encoding="utf-8-sig")
    log.info("Resultado (para conferência humana) gravado em %s", saida)
    return 0


def cmd_validar(args: argparse.Namespace) -> int:
    """Revalida CNPJ e CNAE atacadista dos fornecedores curados."""
    curados = _ler_curados(Path(args.curados))
    consulta = ConsultaCNPJ()
    relatorio = []
    for cnpj in sorted(set(curados["CNPJ"]) - {""}):
        res = consulta.consultar(cnpj)
        relatorio.append({
            "CNPJ": cnpj, "status_consulta": res.status, "razao_social": res.razao_social,
            "situacao": res.situacao, "uf": res.uf, "municipio": res.municipio,
            "cnaes_atacadistas": " ; ".join(res.cnaes_atacadistas),
            "atacadista": res.eh_atacadista, "fonte": res.fonte,
        })
        if res.status == "OK" and not res.eh_atacadista:
            log.warning("ATENÇÃO: %s (%s) não tem CNAE da Divisão 46.", cnpj, res.razao_social)
    saida = DIR_DADOS_INTERMEDIARIOS / "validacao_cnpj_curados.csv"
    saida.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(relatorio).to_csv(saida, index=False, sep=";", encoding="utf-8-sig")
    log.info("Relatório de validação gravado em %s", saida)
    return 0


def cmd_exportar(args: argparse.Namespace) -> int:
    """Gera as planilhas FNDE_<Grupo>.xlsx."""
    # Confere se os grupos do arquivo de insumos batem com os configurados.
    try:
        grupos_planilha = resumo_por_grupo(ler_insumos(Path(args.insumos)))
        log.info("Grupos na planilha de insumos: %s",
                 {g: len(itens) for g, itens in grupos_planilha.items()})
    except (FileNotFoundError, ValueError) as exc:
        log.warning("Não foi possível conferir a planilha de insumos: %s", exc)

    curados = _ler_curados(Path(args.curados))
    arquivos = exportador.exportar_todos(curados, Path(args.saida))
    for arq in arquivos:
        log.info("OK: %s", arq)
    return 0


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def _ler_curados(caminho: Path) -> pd.DataFrame:
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo curado não encontrado: {caminho}")
    df = pd.read_csv(caminho, sep=";", dtype=str, keep_default_na=False,
                     encoding="utf-8-sig")
    obrigatorias = {"Grupo de Insumo", "Situação", "Atende UF", "Nome da Empresa", "CNPJ"}
    faltando = obrigatorias - set(df.columns)
    if faltando:
        raise ValueError(f"Colunas ausentes em {caminho.name}: {sorted(faltando)}")
    log.info("Fornecedores curados: %d linhas", len(df))
    return df


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-v", "--verbose", action="store_true", help="log em nível DEBUG")
    sub = parser.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("descobrir", help="filtra o dump da Receita (GO/DF, CNAE 46)")
    p.add_argument("--ufs", nargs="+", default=list(UFS_PRIORITARIAS))
    grupo = p.add_mutually_exclusive_group()
    grupo.add_argument("--competencia", help="AAAA-MM (padrão: a mais recente)")
    grupo.add_argument("--dump-dir", help="pasta com os .zip já baixados")
    p.set_defaults(func=cmd_descobrir)

    p = sub.add_parser("verificar", help="verifica os sites dos candidatos")
    p.add_argument("--candidatos",
                   default=str(DIR_DADOS_INTERMEDIARIOS / "candidatos_GO_DF.csv"))
    p.add_argument("--limite", type=int, default=0, help="máximo de sites (0 = todos)")
    p.set_defaults(func=cmd_verificar)

    p = sub.add_parser("validar", help="revalida CNPJ/CNAE do arquivo curado")
    p.add_argument("--curados", default=str(ARQ_FORNECEDORES_CURADOS))
    p.set_defaults(func=cmd_validar)

    p = sub.add_parser("exportar", help="gera as planilhas FNDE_<Grupo>.xlsx")
    p.add_argument("--curados", default=str(ARQ_FORNECEDORES_CURADOS))
    p.add_argument("--insumos", default=str(ARQ_INSUMOS_PADRAO))
    p.add_argument("--saida", default=str(DIR_SAIDA_FORNECEDORES))
    p.set_defaults(func=cmd_exportar)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = montar_parser().parse_args(argv)
    configurar_logging(f"fornecedores_co_{args.comando}",
                       logging.DEBUG if args.verbose else logging.INFO)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        log.warning("Execução interrompida pelo usuário.")
        return 130
    except Exception:  # noqa: BLE001 - registra qualquer erro no log antes de sair
        log.exception("Falha na execução do comando '%s'", args.comando)
        return 1


if __name__ == "__main__":
    sys.exit(main())
