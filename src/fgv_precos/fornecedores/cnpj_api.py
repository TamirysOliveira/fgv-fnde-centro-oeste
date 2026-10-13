"""
Consulta de CNPJ em APIs públicas, para confirmar CNAE atacadista.

Fontes (em ordem de tentativa): BrasilAPI, publica.cnpj.ws e ReceitaWS.
Todas espelham o cadastro da Receita Federal e têm limite de requisições,
por isso há intervalo mínimo entre chamadas e novas tentativas com espera.

Nada é inferido: se nenhuma API responder, o resultado volta com
``status="PENDENTE"`` e o fornecedor não pode ser aceito até ser validado.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import requests

from fgv_precos.config import (
    CNPJ_API_INTERVALO_S,
    CNPJ_API_MAX_TENTATIVAS,
    HTTP_TIMEOUT_S,
    HTTP_USER_AGENT,
)
from fgv_precos.fornecedores.cnae import cnaes_atacadistas, somente_digitos, validar_cnpj

log = logging.getLogger(__name__)


@dataclass
class ResultadoCNPJ:
    """Dados mínimos de um CNPJ, normalizados entre as diferentes APIs."""

    cnpj: str
    status: str = "PENDENTE"            # OK | PENDENTE | INVALIDO
    razao_social: str = ""
    situacao: str = ""
    uf: str = ""
    municipio: str = ""
    endereco: str = ""
    telefone: str = ""
    email: str = ""
    cnae_principal: str = ""
    cnaes_secundarios: list[str] = field(default_factory=list)
    fonte: str = ""

    @property
    def cnaes_atacadistas(self) -> list[str]:
        return cnaes_atacadistas(self.cnae_principal, self.cnaes_secundarios)

    @property
    def eh_atacadista(self) -> bool:
        return bool(self.cnaes_atacadistas)


# ---------------------------------------------------------------------------
# Adaptadores: cada função converte o JSON de uma API em ResultadoCNPJ.
# ---------------------------------------------------------------------------
def montar_endereco(dados: dict[str, Any], chaves: tuple[str, ...], cep: Any = None) -> str:
    """Junta as partes do endereço que existirem, com " - CEP ..." no fim."""
    endereco = " ".join(" ".join(str(dados.get(k) or "") for k in chaves).split())
    return endereco + (f" - CEP {cep}" if cep else "")


def _de_brasilapi(cnpj: str, js: dict[str, Any]) -> ResultadoCNPJ:
    return ResultadoCNPJ(
        cnpj=cnpj, status="OK",
        razao_social=js.get("razao_social") or "",
        situacao=js.get("descricao_situacao_cadastral") or "",
        uf=js.get("uf") or "", municipio=js.get("municipio") or "",
        endereco=montar_endereco(js, ("descricao_tipo_de_logradouro", "logradouro", "numero",
                                      "complemento", "bairro"), js.get("cep")),
        telefone=js.get("ddd_telefone_1") or "",
        email=js.get("email") or "",
        cnae_principal=str(js.get("cnae_fiscal") or ""),
        cnaes_secundarios=[str(c.get("codigo")) for c in js.get("cnaes_secundarios") or []
                           if c.get("codigo")],
        fonte=f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}",
    )


def _de_cnpjws(cnpj: str, js: dict[str, Any]) -> ResultadoCNPJ:
    est = js.get("estabelecimento") or {}
    tel = f"({est.get('ddd1')}) {est.get('telefone1')}" if est.get("telefone1") else ""
    return ResultadoCNPJ(
        cnpj=cnpj, status="OK",
        razao_social=js.get("razao_social") or "",
        situacao=est.get("situacao_cadastral") or "",
        uf=(est.get("estado") or {}).get("sigla", ""),
        municipio=(est.get("cidade") or {}).get("nome", ""),
        endereco=montar_endereco(est, ("tipo_logradouro", "logradouro", "numero", "complemento",
                                       "bairro"), est.get("cep")),
        telefone=tel, email=est.get("email") or "",
        cnae_principal=(est.get("atividade_principal") or {}).get("id", ""),
        cnaes_secundarios=[a.get("id", "") for a in est.get("atividades_secundarias") or []],
        fonte=f"https://publica.cnpj.ws/cnpj/{cnpj}",
    )


def _de_receitaws(cnpj: str, js: dict[str, Any]) -> ResultadoCNPJ:
    if js.get("status") == "ERROR":
        raise ValueError(js.get("message", "erro ReceitaWS"))
    principal = (js.get("atividade_principal") or [{}])[0].get("code", "")
    return ResultadoCNPJ(
        cnpj=cnpj, status="OK",
        razao_social=js.get("nome") or "", situacao=js.get("situacao") or "",
        uf=js.get("uf") or "", municipio=js.get("municipio") or "",
        endereco=montar_endereco(js, ("logradouro", "numero", "complemento", "bairro"),
                                 js.get("cep")),
        telefone=js.get("telefone") or "", email=js.get("email") or "",
        cnae_principal=principal,
        cnaes_secundarios=[a.get("code", "") for a in js.get("atividades_secundarias") or []],
        fonte=f"https://www.receitaws.com.br/v1/cnpj/{cnpj}",
    )


_FONTES: list[tuple[str, str, Callable[[str, dict[str, Any]], ResultadoCNPJ]]] = [
    ("BrasilAPI", "https://brasilapi.com.br/api/cnpj/v1/{cnpj}", _de_brasilapi),
    ("CNPJ.ws", "https://publica.cnpj.ws/cnpj/{cnpj}", _de_cnpjws),
    ("ReceitaWS", "https://www.receitaws.com.br/v1/cnpj/{cnpj}", _de_receitaws),
]


class ConsultaCNPJ:
    """Cliente com cache em memória e respeito ao limite das APIs públicas."""

    def __init__(self, intervalo_s: float = CNPJ_API_INTERVALO_S,
                 max_tentativas: int = CNPJ_API_MAX_TENTATIVAS) -> None:
        self.intervalo_s = intervalo_s
        self.max_tentativas = max_tentativas
        self._ultima_chamada: dict[str, float] = {}
        self._cache: dict[str, ResultadoCNPJ] = {}
        self._sessao = requests.Session()
        self._sessao.headers.update({"User-Agent": HTTP_USER_AGENT})

    def _aguardar_vez(self, fonte: str) -> None:
        """Garante o intervalo mínimo entre chamadas à mesma API."""
        decorrido = time.monotonic() - self._ultima_chamada.get(fonte, 0.0)
        if decorrido < self.intervalo_s:
            time.sleep(self.intervalo_s - decorrido)
        self._ultima_chamada[fonte] = time.monotonic()

    def consultar(self, cnpj: str) -> ResultadoCNPJ:
        """Consulta um CNPJ, tentando cada API até uma responder."""
        digitos = somente_digitos(cnpj)
        if not validar_cnpj(digitos):
            log.warning("CNPJ com dígito verificador inválido: %s", cnpj)
            return ResultadoCNPJ(cnpj=digitos, status="INVALIDO")
        if digitos in self._cache:
            return self._cache[digitos]

        for nome, url_modelo, adaptador in _FONTES:
            for tentativa in range(1, self.max_tentativas + 1):
                self._aguardar_vez(nome)
                url = url_modelo.format(cnpj=digitos)
                try:
                    resp = self._sessao.get(url, timeout=HTTP_TIMEOUT_S)
                    if resp.status_code == 429:
                        espera = self.intervalo_s * tentativa
                        log.info("%s limitou requisições (429). Aguardando %.0fs.", nome, espera)
                        time.sleep(espera)
                        continue
                    if resp.status_code == 404:
                        log.info("%s: CNPJ %s não encontrado.", nome, digitos)
                        break  # tenta a próxima fonte
                    resp.raise_for_status()
                    resultado = adaptador(digitos, resp.json())
                    log.info("CNPJ %s validado via %s (%s).", digitos, nome,
                             "atacadista" if resultado.eh_atacadista else "SEM CNAE 46")
                    self._cache[digitos] = resultado
                    return resultado
                except (requests.RequestException, ValueError, KeyError) as exc:
                    log.warning("%s falhou para %s (tentativa %d/%d): %s",
                                nome, digitos, tentativa, self.max_tentativas, exc)
        log.error("Nenhuma API respondeu para o CNPJ %s. Marcado como PENDENTE.", digitos)
        pendente = ResultadoCNPJ(cnpj=digitos, status="PENDENTE")
        self._cache[digitos] = pendente
        return pendente
