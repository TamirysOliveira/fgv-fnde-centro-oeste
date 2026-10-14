"""
Raspagem de preços e fretes (GO, CEP 74933-130) nos sites dos fornecedores - FNDE Centro-Oeste.

Lê:
    FNDE/Centro Oeste/Pesquisa_SEAD_GO_Limpeza_Predial.csv   (insumos)
    FNDE/Centro Oeste/Fornecedores/FNDE_<Grupo>.xlsx         (aba "Fornecedores")
    FNDE/Centro Oeste/produtos_recusados.csv                 (links recusados na revisão)
Grava em _historico/coleta_bruta (fora da Entrega; para levar o resultado à
Entrega, use "corrigir_entrega_2026_10_12.py incorporar"):
    FNDE_output.xlsx      (mesmas colunas de FNDE_output.csv; FONTE e
                           "Link aproveitável" clicáveis)
    resumo_coleta.csv     (preços coletados por insumo, o que faltou e quantos
                           ficaram para coleta manual na coluna P)
    prints/<Grupo>/<ID FGV>_GO_<n>.png

O resultado é gravado ao fim de CADA insumo: se a execução for interrompida,
o que já foi coletado fica salvo. Rodar de novo SOBRESCREVE o resultado dos
insumos coletados (linhas na planilha, no resumo e prints desses IDs). Os
resultados de outros insumos que já estavam em _historico/coleta_bruta são mantidos.

Exemplos (na raiz do repositório):
    python scripts/raspar_precos_centro_oeste.py --ids 1000 1056 1104
    python scripts/raspar_precos_centro_oeste.py --ids 1000 --ver-navegador
    python scripts/raspar_precos_centro_oeste.py --ids 1105 1108 --fornecedor singular
    python scripts/raspar_precos_centro_oeste.py            (todos os insumos de produto)
    python scripts/raspar_precos_centro_oeste.py --completar-merge --ver-navegador
        (só os insumos com vaga no fnde_resultado_merge, pulando os fornecedores que
        já estão no insumo; depois: python scripts/montar_merge.py importar-robo)
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from fgv_precos.config import GRUPOS_SERVICO
from fgv_precos.logging_config import configurar_logging
from fgv_precos.raspagem import saida
from fgv_precos.raspagem.coletor import COLUNAS_RESUMO, Coletor, ler_insumos_selecionados
from fgv_precos.raspagem.config_raspagem import PRECOS_POR_UF

log = logging.getLogger("raspar_precos")


def ler_situacao_merge() -> dict[str, tuple[int, set[str]]]:
    """{ID FGV: (preços no merge, CNPJs com preço)} lido da Entrega montada."""
    from fgv_precos.merge.montagem import DIR_ENTREGA, GRUPOS, NOME_SAIDA
    from fgv_precos.merge.regras import somente_digitos

    situacao: dict[str, tuple[int, set[str]]] = {}
    for pasta, _ in GRUPOS.values():
        df = pd.read_excel(DIR_ENTREGA / pasta / NOME_SAIDA, dtype=str).fillna("")
        for _, r in df[df["Link aproveitável"] == ""].iterrows():
            n, cnpjs = situacao.get(r["Código FGV"], (0, set()))
            situacao[r["Código FGV"]] = (n + 1, cnpjs | {somente_digitos(r["CNPJ"])})
    return situacao


def montar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", nargs="+", help="IDs FGV a coletar (padrão: todos de produto)")
    parser.add_argument("--fornecedor", default="",
                        help="coleta só nos fornecedores cujo nome contém este texto "
                             "(ex.: singular) ou com este CNPJ")
    parser.add_argument("--ver-navegador", action="store_true",
                        help="mostra o navegador trabalhando (útil para conferir)")
    parser.add_argument("--completar-merge", action="store_true",
                        help="busca só o que falta para 5 preços no fnde_resultado_merge da Entrega, "
                             "pulando os fornecedores que já têm preço no insumo")
    parser.add_argument("-v", "--verbose", action="store_true", help="log em nível DEBUG")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = montar_parser().parse_args(argv)
    configurar_logging("raspagem_precos_co", logging.DEBUG if args.verbose else logging.INFO)

    completos, incompletos, com_erro, manuais = [], [], [], 0
    try:
        insumos = [i for i in ler_insumos_selecionados(args.ids) if i.grupo not in GRUPOS_SERVICO]
        if not insumos:
            log.error("Nenhum insumo de produto selecionado.")
            return 1
        log.info("Insumos a coletar: %s", [i.id_fgv for i in insumos])

        situacao_merge = ler_situacao_merge() if args.completar_merge else {}
        if args.completar_merge:
            insumos = [i for i in insumos if situacao_merge.get(i.id_fgv, (0, set()))[0] < PRECOS_POR_UF]
            log.info("Completar o merge: %d insumos com vaga.", len(insumos))
        with Coletor(headless=not args.ver_navegador) as coletor:
            for n, insumo in enumerate(insumos, start=1):
                log.info("--- %d/%d", n, len(insumos))
                try:
                    if args.completar_merge:
                        tem, cnpjs = situacao_merge.get(insumo.id_fgv, (0, set()))
                        coletas, resumo = coletor.coletar_insumo(
                            insumo, args.fornecedor, meta=PRECOS_POR_UF - tem,
                            pular_cnpjs=frozenset(cnpjs))
                    else:
                        coletas, resumo = coletor.coletar_insumo(insumo, args.fornecedor)
                    saida.gravar(coletas, [insumo.id_fgv])
                    saida.gravar_resumo(pd.DataFrame(resumo, columns=COLUNAS_RESUMO),
                                        [insumo.id_fgv])
                except PermissionError:
                    raise              # arquivo aberto no Excel: não adianta seguir
                except Exception:      # noqa: BLE001 - um insumo com problema não para os demais
                    log.exception("Insumo %s não foi gravado por erro inesperado.", insumo.id_fgv)
                    com_erro.append(insumo.id_fgv)
                    continue
                manuais += sum(r["Sem preço visível (coluna P)"] for r in resumo)
                completo = all(r["Preços coletados"] >= PRECOS_POR_UF for r in resumo)
                (completos if completo else incompletos).append(insumo.id_fgv)
    except KeyboardInterrupt:
        log.warning("Interrompido pelo usuário. Os insumos já concluídos estão gravados.")
        return 130
    except Exception:  # noqa: BLE001 - registra qualquer erro no log antes de sair
        log.exception("Falha na raspagem")
        return 1
    finally:
        log.info("RESUMO DA EXECUÇÃO: %d insumos com %d preços, %d incompletos %s, "
                 "%d linhas para coleta manual (coluna P), %d com erro %s",
                 len(completos), PRECOS_POR_UF, len(incompletos), incompletos or "",
                 manuais, len(com_erro), com_erro or "")
    return 1 if com_erro else 0


if __name__ == "__main__":
    sys.exit(main())
