"""
Monta a Entrega (fnde_resultado_merge.xlsx, resumo_coleta.csv, prints e dashboard)
a partir da base de 13/10/2026, das correções e dos candidatos APROVADOS.

Ver src/fgv_precos/merge/montagem.py para os arquivos usados. Fluxo:
    1. revise _historico/merge/candidatos.xlsx (coluna "Situação": APROVADO,
       REPROVADO...; "Preço pela regra" quando o preço cheio do print for outro);
    2. python scripts/montar_merge.py montar            (grava a Entrega)
       python scripts/montar_merge.py montar --simular  (só o relatório)
    3. confira _historico/merge/montagens/<data_hora>/relatorio.csv.

Para levar uma coleta por link (scripts/coletar_links.py) à revisão:
    python scripts/montar_merge.py importar-coleta "_historico/merge/coleta_links/<pasta>"
Para gerar a lista de links a coletar (vagas abertas):
    python scripts/montar_merge.py gerar-links
Para buscar nos sites (inclusive dos fornecedores novos) só os insumos com vaga:
    python scripts/montar_merge.py ids-com-vaga
    python scripts/raspar_precos_centro_oeste.py --ids <IDs> --ver-navegador
    python scripts/montar_merge.py importar-robo
"""

from __future__ import annotations

import argparse
import logging
import sys

from fgv_precos.logging_config import configurar_logging
from fgv_precos.merge import montagem, revisao

log = logging.getLogger("montar_merge")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("montar", help="monta a Entrega")
    p.add_argument("--simular", action="store_true", help="só grava o relatório")
    sub.add_parser("gerar-links", help="gera _historico/merge/links_para_coletar.csv")
    p = sub.add_parser("importar-coleta", help="leva uma coleta por link para candidatos.xlsx")
    p.add_argument("pasta")
    sub.add_parser("importar-robo", help="leva _historico/coleta_bruta para candidatos.xlsx")
    sub.add_parser("ids-com-vaga", help="lista os IDs que ainda não têm 5 preços")
    args = parser.parse_args(argv)
    configurar_logging("montar_merge", logging.INFO)
    if args.comando == "montar":
        pasta = montagem.montar(simular=args.simular)
        log.info("Relatório: %s", pasta / "relatorio.csv")
    elif args.comando == "gerar-links":
        log.info("Lista gravada: %s", revisao.gerar_links())
    elif args.comando == "importar-coleta":
        log.info("Candidatos atualizados: %s", revisao.importar_coleta(args.pasta))
    elif args.comando == "importar-robo":
        log.info("Candidatos atualizados: %s", revisao.importar_robo())
    else:
        ids = revisao.ids_com_vaga()
        print(" ".join(ids))
        log.info("%d insumos com vaga.", len(ids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
