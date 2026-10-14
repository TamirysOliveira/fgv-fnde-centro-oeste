"""
Coleta preço, frete (GO, CEP 74933-130) e print a partir de links prontos.

Entrada: CSV com separador ";" e as colunas
    ID FGV;Grupo;Nome Empresa;CNPJ;UF;Link;Origem;Chave;Motivo
(gerado por "python scripts/montar_merge.py gerar-links" em
_historico/merge/links_para_coletar.csv). Saída: uma pasta nova em
_historico/merge/coleta_links/<data_hora>/ com situacao.csv, prints/ e
diagnostico/ (prints das páginas em que o frete não pôde ser lido).
Nada é gravado na Entrega: depois de conferir os prints, rode
    python scripts/montar_merge.py importar-coleta "<pasta>"
e revise as linhas em _historico/merge/candidatos.xlsx.

Exemplos (na raiz do repositório, com .venv ativado):
    python scripts/coletar_links.py
    python scripts/coletar_links.py --ver-navegador
    python scripts/coletar_links.py --lista minha_lista.csv --ids 1018 1036
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from fgv_precos.logging_config import configurar_logging
from fgv_precos.merge.montagem import DIR_MERGE
from fgv_precos.raspagem.coleta_links import coletar

log = logging.getLogger("coletar_links")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lista", default=str(DIR_MERGE / "links_para_coletar.csv"))
    parser.add_argument("--ids", nargs="+", help="coleta só estes IDs FGV")
    parser.add_argument("--ver-navegador", action="store_true")
    args = parser.parse_args(argv)
    configurar_logging("coletar_links", logging.INFO)
    lista = Path(args.lista)
    if args.ids:
        with open(lista, encoding="utf-8-sig", newline="") as fh:
            leitor = csv.DictReader(fh, delimiter=";")
            linhas = [r for r in leitor if r["ID FGV"] in set(args.ids)]
            campos = leitor.fieldnames
        tmp = Path(tempfile.mkstemp(suffix=".csv")[1])
        with open(tmp, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=campos, delimiter=";")
            w.writeheader()
            w.writerows(linhas)
        lista = tmp
    saida = DIR_MERGE / "coleta_links" / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    saida.mkdir(parents=True)
    try:
        log.info("Resultado: %s", coletar(lista, saida, headless=not args.ver_navegador))
    except KeyboardInterrupt:
        log.warning("Interrompido. O que já foi coletado está em %s", saida)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
