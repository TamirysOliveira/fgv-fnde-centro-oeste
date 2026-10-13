"""
Configuração de logs do projeto.

Cada execução grava um arquivo próprio em ``logs/`` (nome com data e hora)
e também escreve no terminal. Assim é possível auditar depois o que foi
consultado, aceito ou descartado em cada rodada.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

from fgv_precos.config import DIR_LOGS

FORMATO_LOG = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


def configurar_logging(nome_execucao: str, nivel: int = logging.INFO,
                       dir_logs: Path = DIR_LOGS) -> Path:
    """Configura o logger raiz para arquivo + console.

    Args:
        nome_execucao: prefixo do arquivo de log (ex.: "fornecedores_co").
        nivel: nível mínimo de log (padrão INFO).
        dir_logs: pasta onde o arquivo de log será criado.

    Returns:
        Caminho do arquivo de log criado.
    """
    dir_logs.mkdir(parents=True, exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    arquivo_log = dir_logs / f"{nome_execucao}_{carimbo}.log"

    raiz = logging.getLogger()
    raiz.setLevel(nivel)
    # Evita handlers duplicados se a função for chamada mais de uma vez.
    for handler in list(raiz.handlers):
        raiz.removeHandler(handler)

    formatador = logging.Formatter(FORMATO_LOG, datefmt=FORMATO_DATA)

    handler_arquivo = logging.FileHandler(arquivo_log, encoding="utf-8")
    handler_arquivo.setFormatter(formatador)
    raiz.addHandler(handler_arquivo)

    handler_console = logging.StreamHandler(sys.stdout)
    handler_console.setFormatter(formatador)
    raiz.addHandler(handler_console)

    # Bibliotecas de rede são muito verbosas em DEBUG.
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.getLogger(__name__).info("Log desta execução: %s", arquivo_log)
    return arquivo_log
