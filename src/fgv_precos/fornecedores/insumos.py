"""
Leitura da planilha de insumos (CSV exportado do Excel, separador ``;``).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

COLUNA_GRUPO = "Grupo de Insumo"
COLUNA_DESCRICAO = "Descrição"
# O Excel em português costuma exportar CSV em cp1252; tentamos as mais comuns.
CODIFICACOES = ("utf-8-sig", "cp1252", "latin-1")


def ler_insumos(caminho: Path) -> pd.DataFrame:
    """Lê o CSV de insumos tentando as codificações usuais do Excel.

    Raises:
        FileNotFoundError: se o arquivo não existir.
        ValueError: se a coluna "Grupo de Insumo" não for encontrada.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"Planilha de insumos não encontrada: {caminho}")
    ultimo_erro: Exception | None = None
    for cod in CODIFICACOES:
        try:
            df = pd.read_csv(caminho, sep=";", dtype=str, encoding=cod,
                             keep_default_na=False)
            if COLUNA_GRUPO in df.columns:
                log.info("Insumos lidos (%s): %d linhas", cod, len(df))
                df[COLUNA_GRUPO] = df[COLUNA_GRUPO].str.strip()
                return df
        except UnicodeDecodeError as exc:
            ultimo_erro = exc
    raise ValueError(f"Coluna '{COLUNA_GRUPO}' não encontrada em {caminho} "
                     f"(último erro: {ultimo_erro})")


def resumo_por_grupo(df: pd.DataFrame) -> dict[str, list[str]]:
    """Dicionário {grupo: [descrições dos insumos]} na ordem da planilha."""
    return {g: sub[COLUNA_DESCRICAO].tolist()
            for g, sub in df.groupby(COLUNA_GRUPO, sort=False)}
