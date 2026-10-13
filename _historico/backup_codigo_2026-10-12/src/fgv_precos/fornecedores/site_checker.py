"""
Verificação do site do fornecedor (regras 2 e 3 de ``config.py``).

Para cada site candidato, o verificador:
    1. Recusa domínios de marketplace (Mercado Livre, Amazon...).
    2. Baixa a página inicial e até N páginas internas cujo link/texto
       contenha palavras-chave do grupo (ex.: "detergente", "luva").
    3. Procura preço visível (padrão ``R$ 12,90``) e frases de preço oculto
       ("sob consulta", "solicite orçamento").
    4. Conta palavras-chave de cada Grupo de Insumo encontradas no site.

Limitação conhecida (registrada no log): sites que montam a vitrine via
JavaScript podem não exibir preço no HTML bruto. Nesses casos o resultado é
``SEM_PRECO_DETECTADO`` e o site deve ser conferido manualmente. Mesmo o
status ``PRECO_DETECTADO`` é só um indício (o "R$" pode ser, por exemplo, o
valor mínimo para frete grátis): nenhum fornecedor é aceito automaticamente
sem a conferência humana do preço do item.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from fgv_precos.config import (
    DOMINIOS_EMAIL_GRATUITO,
    DOMINIOS_MARKETPLACE,
    FRASES_PRECO_OCULTO,
    HTTP_TIMEOUT_S,
    HTTP_USER_AGENT,
    PALAVRAS_CHAVE_GRUPO,
    REGEX_PRECO,
)

log = logging.getLogger(__name__)
_RE_PRECO = re.compile(REGEX_PRECO)

# Status possíveis
PRECO_DETECTADO = "PRECO_DETECTADO"        # preço no HTML + itens do grupo (conferir)
SEM_PRECO_DETECTADO = "SEM_PRECO_DETECTADO"  # catálogo sem preço no HTML
MARKETPLACE = "MARKETPLACE"
SEM_SITE = "SEM_SITE"
ERRO_ACESSO = "ERRO_ACESSO"


@dataclass
class ResultadoSite:
    url: str
    status: str
    tem_preco: bool = False
    preco_oculto: bool = False
    exemplos_preco: list[str] = field(default_factory=list)
    palavras_por_grupo: dict[str, int] = field(default_factory=dict)
    paginas_lidas: list[str] = field(default_factory=list)
    detalhe: str = ""

    def grupos_atendidos(self, minimo_palavras: int = 2) -> list[str]:
        """Grupos com pelo menos ``minimo_palavras`` palavras-chave no site."""
        return [g for g, n in self.palavras_por_grupo.items() if n >= minimo_palavras]


def dominio(url: str) -> str:
    """Extrai o domínio sem ``www.`` (ex.: ``loja.com.br``)."""
    netloc = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def eh_marketplace(url: str) -> bool:
    d = dominio(url)
    return any(d == m or d.endswith("." + m) for m in DOMINIOS_MARKETPLACE)


def site_a_partir_do_email(email: str) -> str | None:
    """Sugere o site a partir do domínio do e-mail corporativo.

    Retorna None para e-mails gratuitos (gmail, hotmail...), que não indicam
    site próprio. O site sugerido ainda precisa ser verificado.
    """
    if not email or "@" not in email:
        return None
    dom = email.rsplit("@", 1)[1].strip().lower()
    if not dom or dom in DOMINIOS_EMAIL_GRATUITO:
        return None
    return f"https://{dom}"


class VerificadorSite:
    """Baixa e analisa páginas de um site com uma sessão HTTP reutilizável."""

    def __init__(self, max_paginas_internas: int = 5) -> None:
        self.max_paginas_internas = max_paginas_internas
        self._sessao = requests.Session()
        self._sessao.headers.update({"User-Agent": HTTP_USER_AGENT})

    def _baixar(self, url: str) -> str | None:
        try:
            resp = self._sessao.get(url, timeout=HTTP_TIMEOUT_S, allow_redirects=True)
            resp.raise_for_status()
            if eh_marketplace(resp.url):
                log.info("Redirecionou para marketplace: %s -> %s", url, resp.url)
                return None
            return resp.text
        except requests.RequestException as exc:
            log.debug("Falha ao acessar %s: %s", url, exc)
            return None

    @staticmethod
    def _links_relevantes(html: str, base: str) -> list[str]:
        """Links internos cujo texto/URL contém alguma palavra-chave."""
        todas = {p for ps in PALAVRAS_CHAVE_GRUPO.values() for p in ps}
        sopa = BeautifulSoup(html, "lxml")
        dom_base = dominio(base)
        encontrados: list[str] = []
        for a in sopa.find_all("a", href=True):
            alvo = urljoin(base, a["href"])
            if dominio(alvo) != dom_base:
                continue
            texto = f"{a.get_text(' ', strip=True)} {alvo}".lower()
            if any(p in texto for p in todas) and alvo not in encontrados:
                encontrados.append(alvo)
        return encontrados

    def verificar(self, url: str) -> ResultadoSite:
        """Executa a verificação completa de um site."""
        if not url:
            return ResultadoSite(url="", status=SEM_SITE)
        if not url.startswith("http"):
            url = f"https://{url}"
        if eh_marketplace(url):
            return ResultadoSite(url=url, status=MARKETPLACE, detalhe="domínio de marketplace")

        html_inicial = self._baixar(url)
        if html_inicial is None:
            return ResultadoSite(url=url, status=ERRO_ACESSO, detalhe="site não respondeu")

        paginas = [(url, html_inicial)]
        for link in self._links_relevantes(html_inicial, url)[: self.max_paginas_internas]:
            html = self._baixar(link)
            if html:
                paginas.append((link, html))

        resultado = ResultadoSite(url=url, status=SEM_PRECO_DETECTADO)
        contagem = {g: 0 for g in PALAVRAS_CHAVE_GRUPO}
        for link, html in paginas:
            texto = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
            texto_min = texto.lower()
            precos = _RE_PRECO.findall(texto)
            if precos:
                resultado.tem_preco = True
                resultado.exemplos_preco.extend(precos[:3])
            if any(f in texto_min for f in FRASES_PRECO_OCULTO):
                resultado.preco_oculto = True
            for grupo, palavras in PALAVRAS_CHAVE_GRUPO.items():
                contagem[grupo] += sum(1 for p in palavras if p in texto_min)
            resultado.paginas_lidas.append(link)

        resultado.palavras_por_grupo = contagem
        resultado.exemplos_preco = resultado.exemplos_preco[:5]
        if resultado.tem_preco and resultado.grupos_atendidos():
            resultado.status = PRECO_DETECTADO
        log.info("Site %s -> %s (preço=%s, grupos=%s)", url, resultado.status,
                 resultado.tem_preco, resultado.grupos_atendidos())
        return resultado
