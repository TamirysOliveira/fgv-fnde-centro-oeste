"""
Descoberta de candidatos a partir dos Dados Abertos do CNPJ (Receita Federal).

Fluxo:
    1. Baixa (ou reaproveita) os arquivos ``Estabelecimentos*.zip``,
       ``Empresas*.zip`` e ``Municipios.zip`` da competência escolhida.
    2. Lê os estabelecimentos em blocos (os arquivos têm vários GB) e mantém
       só os que estão ATIVOS, nas UFs desejadas e com ao menos um CNAE da
       Divisão 46 (principal ou secundário).
    3. Junta a razão social (Empresas) e o nome do município (Municipios).
    4. Grava ``data/interim/candidatos_<UFs>.csv``.

Os arquivos da Receita não têm cabeçalho, usam ``;`` e codificação latin-1.
O layout oficial está em:
https://www.gov.br/receitafederal/dados/cnpj-metadados.pdf
"""

from __future__ import annotations

import logging
import re
import zipfile
from collections.abc import Iterable
from pathlib import Path

import pandas as pd
import requests

from fgv_precos.config import (
    DIR_DADOS_BRUTOS,
    DIR_DADOS_INTERMEDIARIOS,
    HTTP_TIMEOUT_S,
    HTTP_USER_AGENT,
    PREFIXO_CNAE_ATACADISTA,
    SITUACAO_ATIVA_RECEITA,
    URL_BASE_DADOS_ABERTOS_CNPJ,
)
from fgv_precos.fornecedores.cnae import formatar_cnpj

log = logging.getLogger(__name__)

# Layout oficial (ordem das colunas) do arquivo de Estabelecimentos.
COLUNAS_ESTABELECIMENTOS = [
    "cnpj_basico", "cnpj_ordem", "cnpj_dv", "matriz_filial", "nome_fantasia",
    "situacao_cadastral", "data_situacao", "motivo_situacao", "cidade_exterior",
    "pais", "data_inicio", "cnae_principal", "cnae_secundaria", "tipo_logradouro",
    "logradouro", "numero", "complemento", "bairro", "cep", "uf", "municipio",
    "ddd1", "telefone1", "ddd2", "telefone2", "ddd_fax", "fax", "email",
    "situacao_especial", "data_situacao_especial",
]
COLUNAS_EMPRESAS = [
    "cnpj_basico", "razao_social", "natureza_juridica", "qualificacao_responsavel",
    "capital_social", "porte", "ente_federativo",
]
TAMANHO_BLOCO = 500_000  # linhas por bloco de leitura (ajuste se faltar memória)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------
def listar_competencias(url_base: str = URL_BASE_DADOS_ABERTOS_CNPJ) -> list[str]:
    """Lista as pastas de competência (AAAA-MM) publicadas pela Receita."""
    try:
        resp = requests.get(url_base, timeout=HTTP_TIMEOUT_S,
                            headers={"User-Agent": HTTP_USER_AGENT})
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(
            f"Não foi possível acessar {url_base}: {exc}. Baixe os .zip manualmente "
            "e rode com --dump-dir apontando para a pasta deles."
        ) from exc
    return sorted(set(re.findall(r'href="(\d{4}-\d{2})/?"', resp.text)))


def baixar_arquivo(url: str, destino: Path) -> Path:
    """Baixa um arquivo grande em streaming; pula se já existir completo."""
    if destino.exists() and destino.stat().st_size > 0:
        log.info("Já baixado, reaproveitando: %s", destino.name)
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_suffix(destino.suffix + ".part")
    log.info("Baixando %s", url)
    try:
        with requests.get(url, stream=True, timeout=HTTP_TIMEOUT_S,
                          headers={"User-Agent": HTTP_USER_AGENT}) as resp:
            resp.raise_for_status()
            with open(temporario, "wb") as fh:
                for pedaco in resp.iter_content(chunk_size=1 << 20):
                    fh.write(pedaco)
        temporario.replace(destino)
    except (requests.RequestException, OSError) as exc:
        temporario.unlink(missing_ok=True)
        raise RuntimeError(f"Falha ao baixar {url}: {exc}") from exc
    return destino


def baixar_dump(competencia: str | None = None, destino: Path = DIR_DADOS_BRUTOS) -> Path:
    """Baixa Estabelecimentos, Empresas e Municipios de uma competência.

    Args:
        competencia: "AAAA-MM". Se None, usa a mais recente publicada.
        destino: pasta base para os arquivos.

    Returns:
        Pasta com os .zip da competência.
    """
    if competencia is None:
        competencias = listar_competencias()
        if not competencias:
            raise RuntimeError("Nenhuma competência encontrada no site da Receita.")
        competencia = competencias[-1]
    log.info("Competência dos dados abertos: %s", competencia)
    pasta = destino / f"cnpj_{competencia}"
    url = f"{URL_BASE_DADOS_ABERTOS_CNPJ}{competencia}/"
    nomes = ([f"Estabelecimentos{i}.zip" for i in range(10)]
             + [f"Empresas{i}.zip" for i in range(10)] + ["Municipios.zip"])
    for nome in nomes:
        baixar_arquivo(url + nome, pasta / nome)
    return pasta


# ---------------------------------------------------------------------------
# Leitura e filtro
# ---------------------------------------------------------------------------
ERROS_LEITURA = (zipfile.BadZipFile, pd.errors.ParserError, UnicodeDecodeError, OSError)


def _falhar_se_incompleto(com_erro: list[str]) -> None:
    """Um arquivo ilegível deixaria a lista de candidatos incompleta sem aviso.

    Raises:
        RuntimeError: com os arquivos que falharam, para baixá-los de novo.
    """
    if com_erro:
        raise RuntimeError(
            f"Arquivos da Receita ilegíveis (corrompidos ou incompletos): {com_erro}. "
            "Apague-os e rode de novo para baixar outra vez (ou baixe manualmente).")


def _ler_zip_csv(caminho_zip: Path, colunas: list[str], **kwargs) -> Iterable[pd.DataFrame]:
    """Lê o CSV de dentro de um .zip da Receita em blocos."""
    with zipfile.ZipFile(caminho_zip) as zf:
        nome_interno = zf.namelist()[0]
        with zf.open(nome_interno) as fh:
            yield from pd.read_csv(
                fh, sep=";", header=None, names=colunas, dtype=str,
                encoding="latin-1", chunksize=TAMANHO_BLOCO, keep_default_na=False,
                **kwargs,
            )


def _tem_cnae_atacadista(principal: pd.Series, secundaria: pd.Series) -> pd.Series:
    """Máscara booleana: algum CNAE (principal ou secundário) começa com 46."""
    p = principal.str.startswith(PREFIXO_CNAE_ATACADISTA)
    # Secundários vêm separados por vírgula: "4649408,4686902"
    s = secundaria.str.contains(rf"(?:^|,){PREFIXO_CNAE_ATACADISTA}\d{{5}}", regex=True)
    return p | s


def filtrar_estabelecimentos(pasta_dump: Path, ufs: tuple[str, ...]) -> pd.DataFrame:
    """Filtra estabelecimentos ativos, nas UFs pedidas e com CNAE atacadista."""
    arquivos = sorted(pasta_dump.glob("Estabelecimentos*.zip"))
    if not arquivos:
        raise FileNotFoundError(f"Nenhum Estabelecimentos*.zip em {pasta_dump}")
    partes: list[pd.DataFrame] = []
    com_erro: list[str] = []
    for arq in arquivos:
        log.info("Lendo %s", arq.name)
        try:
            for bloco in _ler_zip_csv(arq, COLUNAS_ESTABELECIMENTOS):
                mascara = (
                    bloco["uf"].isin(ufs)
                    & (bloco["situacao_cadastral"] == SITUACAO_ATIVA_RECEITA)
                    & _tem_cnae_atacadista(bloco["cnae_principal"], bloco["cnae_secundaria"])
                )
                if mascara.any():
                    partes.append(bloco.loc[mascara].copy())
        except ERROS_LEITURA as exc:
            log.error("Erro ao ler %s: %s", arq.name, exc)
            com_erro.append(arq.name)
    _falhar_se_incompleto(com_erro)
    if not partes:
        return pd.DataFrame(columns=COLUNAS_ESTABELECIMENTOS)
    df = pd.concat(partes, ignore_index=True)
    log.info("Estabelecimentos atacadistas ativos em %s: %d", "/".join(ufs), len(df))
    return df


def anexar_razao_social(df: pd.DataFrame, pasta_dump: Path) -> pd.DataFrame:
    """Junta a razão social a partir dos arquivos Empresas*.zip."""
    basicos = set(df["cnpj_basico"])
    nomes: list[pd.DataFrame] = []
    com_erro: list[str] = []
    for arq in sorted(pasta_dump.glob("Empresas*.zip")):
        log.info("Lendo %s", arq.name)
        try:
            for bloco in _ler_zip_csv(arq, COLUNAS_EMPRESAS):
                sel = bloco[bloco["cnpj_basico"].isin(basicos)]
                if not sel.empty:
                    nomes.append(sel[["cnpj_basico", "razao_social"]])
        except ERROS_LEITURA as exc:
            log.error("Erro ao ler %s: %s", arq.name, exc)
            com_erro.append(arq.name)
    _falhar_se_incompleto(com_erro)
    if nomes:
        df = df.merge(pd.concat(nomes).drop_duplicates("cnpj_basico"),
                      on="cnpj_basico", how="left")
    else:
        df["razao_social"] = ""
    return df


def anexar_municipio(df: pd.DataFrame, pasta_dump: Path) -> pd.DataFrame:
    """Troca o código do município (tabela da Receita) pelo nome."""
    arq = pasta_dump / "Municipios.zip"
    if not arq.exists():
        log.warning("Municipios.zip não encontrado; cidade ficará como código.")
        df["cidade"] = df["municipio"]
        return df
    mun = pd.concat(_ler_zip_csv(arq, ["municipio", "cidade"]))
    return df.merge(mun, on="municipio", how="left")


def montar_campos_contato(df: pd.DataFrame) -> pd.DataFrame:
    """CNPJ formatado, telefone, endereço e e-mail no formato da planilha.

    Vetorizado (sem ``apply`` linha a linha): rápido com milhares de linhas e
    correto também quando o filtro não encontra nenhum estabelecimento.
    """
    df = df.copy()
    df["cnpj"] = (df["cnpj_basico"] + df["cnpj_ordem"] + df["cnpj_dv"]).map(formatar_cnpj)
    tem_telefone = df["telefone1"].str.strip() != ""
    df["telefone"] = ("(" + df["ddd1"] + ") " + df["telefone1"]).where(tem_telefone, "")
    logradouro = (df["tipo_logradouro"]
                  .str.cat(df[["logradouro", "numero", "complemento", "bairro"]], sep=" ")
                  .str.split().str.join(" "))
    df["endereco"] = logradouro + (" - CEP " + df["cep"]).where(df["cep"].str.strip() != "", "")
    df["email"] = df["email"].str.lower().str.strip()
    return df


def gerar_candidatos(pasta_dump: Path, ufs: tuple[str, ...],
                     destino: Path = DIR_DADOS_INTERMEDIARIOS) -> Path:
    """Pipeline completo: filtra, enriquece e grava o CSV de candidatos."""
    df = filtrar_estabelecimentos(pasta_dump, ufs)
    df = anexar_razao_social(df, pasta_dump)
    df = anexar_municipio(df, pasta_dump)

    df = montar_campos_contato(df)

    saida = df[["uf", "cidade", "cnpj", "razao_social", "nome_fantasia", "cnae_principal",
                "cnae_secundaria", "telefone", "email", "endereco"]]
    destino.mkdir(parents=True, exist_ok=True)
    arq_saida = destino / f"candidatos_{'_'.join(ufs)}.csv"
    saida.to_csv(arq_saida, index=False, sep=";", encoding="utf-8-sig")
    log.info("Candidatos gravados em %s (%d linhas)", arq_saida, len(saida))
    return arq_saida
