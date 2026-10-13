"""
Raspagem de preços e fretes (GO, CEP 74933-130) nos sites dos fornecedores - FNDE Centro-Oeste.

Lê:
    FNDE/Centro Oeste/Pesquisa_SEAD_GO_Limpeza_Predial.csv   (insumos)
    FNDE/Centro Oeste/Fornecedores/FNDE_<Grupo>.xlsx         (aba "Fornecedores")
Grava em FNDE/Centro Oeste/Entrega:
    FNDE_output.xlsx      (mesmas colunas de FNDE_output.csv; FONTE e
                           "Link aproveitável" clicáveis)
    resumo_coleta.csv     (preços coletados por insumo, o que faltou e quantos
                           ficaram para coleta manual na coluna P)
    prints/<Grupo>/<ID FGV>_GO_<n>.png

Rodar de novo SOBRESCREVE o resultado dos insumos coletados (linhas na
planilha, linhas no resumo e prints desses IDs). Os resultados de outros
insumos que já estavam na pasta Entrega são mantidos.

Exemplos (na raiz do repositório):
    python scripts/raspar_precos_centro_oeste.py --ids 1000 1056 1104
    python scripts/raspar_precos_centro_oeste.py --ids 1000 --ver-navegador
    python scripts/raspar_precos_centro_oeste.py            (todos os insumos de produto)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fgv_precos.config import GRUPOS_SERVICO  # noqa: E402
from fgv_precos.logging_config import configurar_logging  # noqa: E402
from fgv_precos.raspagem import saida  # noqa: E402
from fgv_precos.raspagem.coletor import (  # noqa: E402
    Coletor,
    ler_insumos_selecionados,
    resumo_para_df,
)
from fgv_precos.raspagem.config_raspagem import DIR_ENTREGA  # noqa: E402

log = logging.getLogger("raspar_precos")


def gravar_resumo(novo: pd.DataFrame, ids: list[str]) -> None:
    """Atualiza Entrega/resumo_coleta.csv: substitui os IDs coletados, mantém os demais."""
    arquivo = DIR_ENTREGA / "resumo_coleta.csv"
    if arquivo.exists():
        try:
            antigo = pd.read_csv(arquivo, sep=";", dtype=str, encoding="utf-8-sig")
            antigo = antigo[~antigo["ID FGV"].astype(str).isin(ids)]
            novo = pd.concat([antigo, novo.astype(str)], ignore_index=True)
        except (OSError, ValueError, KeyError) as exc:
            log.warning("Resumo anterior ilegível (%s); será recriado.", exc)
    novo = novo.sort_values(["ID FGV", "UF"])
    try:
        novo.to_csv(arquivo, sep=";", index=False, encoding="utf-8-sig")
    except PermissionError as exc:
        raise PermissionError(f"Feche o arquivo no Excel e rode de novo: {arquivo}") from exc
    log.info("Resumo gravado: %s", arquivo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", nargs="+", help="IDs FGV a coletar (padrão: todos de produto)")
    parser.add_argument("--ver-navegador", action="store_true",
                        help="mostra o navegador trabalhando (útil para conferir)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    configurar_logging("raspagem_precos_co", logging.DEBUG if args.verbose else logging.INFO)
    try:
        insumos = [i for i in ler_insumos_selecionados(args.ids) if i.grupo not in GRUPOS_SERVICO]
        if not insumos:
            log.error("Nenhum insumo de produto selecionado.")
            return 1
        log.info("Insumos a coletar: %s", [i.id_fgv for i in insumos])

        coletas, resumo = Coletor(headless=not args.ver_navegador).coletar(insumos)
        ids = [i.id_fgv for i in insumos]
        saida.gravar(coletas, ids)
        gravar_resumo(resumo_para_df(resumo), ids)
        return 0
    except KeyboardInterrupt:
        log.warning("Interrompido pelo usuário.")
        return 130
    except Exception:  # noqa: BLE001
        log.exception("Falha na raspagem")
        return 1


if __name__ == "__main__":
    sys.exit(main())
