"""
Loja genérica: comportamento padrão usado por todas as plataformas.

Cada plataforma (Loja Integrada, VTEX, WooCommerce, Shopify...) herda daqui e
sobrescreve só o que for diferente. Cada fornecedor com particularidades
ganha um arquivo próprio em ``raspagem/lojas/<empresa>.py``.

Fluxo de uma coleta (chamado pelo ``coletor``):
    1. ``buscar(termo)``        -> lista de candidatos (nome + link)
    2. ``ler_produto(url)``     -> nome, preço, disponibilidade
    3. ``calcular_frete(cep)``  -> valor / grátis / falha
    4. ``tirar_print(caminho)`` -> página com nome, preço e frete visíveis
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote_plus, urlencode, urlparse

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeout

from fgv_precos.fornecedores.cnae import somente_digitos
from fgv_precos.precos import todos_valores, valores_de_preco
from fgv_precos.raspagem.config_raspagem import (
    ESPERA_FRETE_MS,
    MAX_RESULTADOS_BUSCA,
    PAUSA_ENTRE_ACOES_MS,
    TIMEOUT_NAVEGACAO_MS,
)
from fgv_precos.raspagem.modelos import Candidato, Fornecedor, Frete, Produto, limpar_nome

log = logging.getLogger(__name__)

# Seletores de campo de CEP mais comuns no e-commerce brasileiro.
SELETORES_CEP = [
    "input[name*='cep' i]", "input[id*='cep' i]", "input[placeholder*='cep' i]",
    "input[class*='cep' i]", "input[name*='postal' i]", "input[id*='postal' i]",
    "input[name*='zip' i]", "input[id*='zip' i]", "input[placeholder*='frete' i]",
]
TEXTO_BOTAO_FRETE = re.compile(r"calcular|ok|consultar|simular|buscar|aplicar", re.I)
# Linhas de "retirada na loja" não são frete de entrega.
RE_RETIRADA = re.compile(r"retir|retirada|buscar na loja|pick ?up", re.I)
# Avisos de preço exclusivo para cliente logado.
RE_PRECO_LOGIN = re.compile(
    r"(fa[cç]a|efetue|realize) (o )?(seu )?login para (ver|visualizar|consultar)|"
    r"entre (na sua conta )?para (ver|visualizar)|"
    r"(pre[cç]os?|valores?) (exclusivos? |dispon[ií]ve(l|is) )?(somente |apenas )?(para|a) "
    r"(clientes? )?(cadastrados?|logados?)|"
    r"cadastre-se para (ver|visualizar)|login para ver (o )?pre[cç]o|"
    r"(necess[aá]rio|precisa) (fazer|efetuar) (o )?login para .{0,40}(ver|visualizar) (os )?pre[cç]os?",
    re.I)
# Frete que só aparece para quem está logado/cadastrado (regra de 09/10/2026:
# vai para a coluna P, "Link aproveitável", com o motivo em OBS FRETE).
RE_FRETE_LOGIN = re.compile(r"login|entre na sua conta|fa[cç]a seu cadastro|identifique-se", re.I)
MOTIVO_FRETE_LOGIN = "frete exige login/cadastro"
# Preço sob consulta / orçamento.
RE_SOB_CONSULTA = re.compile(r"sob consulta|solicit(e|ar) (um |seu )?or[cç]amento|"
                             r"consulte (o )?pre[cç]o|pre[cç]o a combinar", re.I)
# Produto claramente esgotado (único caso sem preço que é descartado).
RE_ESGOTADO = re.compile(r"produto esgotado|fora de estoque|sem estoque|"
                         r"avise-me quando (chegar|estiver dispon[ií]vel)", re.I)

MOTIVO_LOGIN = "Preço só com login"
MOTIVO_CONSULTA = "Preço sob consulta/orçamento"
MOTIVO_DESCONHECIDO = "Preço não exibido (motivo não identificado)"
RE_GRATIS = re.compile(r"gr[aá]tis|frete free|sem custo", re.I)
# Avisos de política de frete, que não são o resultado do cálculo.
RE_CONDICAO = re.compile(r"acima de|a partir de|faltam|compras? (?:de|superiores)", re.I)
# Palavras que indicam que um valor é de frete/entrega.
RE_CHAVE_FRETE = re.compile(r"dia|útil|util|entrega|frete|sedex|pac|transport|jadlog|correios|"
                            r"envio|expresso|econ[oô]mico|normal|padr[aã]o|motoboy|loggi", re.I)
# Botões e links vizinhos da calculadora, que não descrevem a opção de entrega.
RE_LIXO_FRETE = re.compile(r"lista de desejos|adicionar aos desejos|favorit|compartilhar|"
                           r"adicionar ao carrinho|comprar|quantidade|n[aã]o sei meu cep", re.I)
# O que sobra de uma linha de opção sem o valor, o prazo e "frete grátis":
# se ainda houver uma palavra, a linha tem rótulo próprio (transportadora etc.).
RE_SEM_ROTULO = re.compile(r"R\$\s*[\d.,]+|\d+|frete|gr[aá]tis|dias?|\(s\)|[úu]teis|[úu]til|"
                           r"\(eis\)|at[ée]|em|prazo|aviso|avisos|entrega|\ba\b|[^\w\s]", re.I)
RE_TEM_ROTULO = re.compile(r"[^\W\d_]{3,}")
RE_PRAZO = re.compile(r"dia|[úu]til|[úu]teis|prazo|hora", re.I)
# Quantos níveis acima do campo de CEP formam o bloco onde o resultado aparece.
# O MESMO bloco é lido antes e depois do cálculo, para comparar só o que mudou.
NIVEIS_REGIAO_FRETE = 8

RE_NAO_ENTREGA = re.compile(r"n[aã]o (existem|h[aá]) (fretes?|op[cç][oõ]es)|n[aã]o entregamos|"
                            r"n[aã]o (realizamos|fazemos) entregas?|cep (inv[aá]lido|n[aã]o atendido)|"
                            r"entregas? apenas para|nenhuma (forma|op[cç][aã]o) de (envio|entrega|frete)|"
                            r"n[aã]o foram encontrad[ao]s (formas|op[cç][oõ]es|m[ée]todos) de "
                            r"(envio|entrega|frete)", re.I)
RE_GRATIS_BRASIL = re.compile(r"frete gr[aá]tis para todo (o )?brasil", re.I)
RE_ITENS_INUTEIS = re.compile(r"^\(?\d+\)?$|R\$|adicionar|comprar|ver detalhes|esgotado|"
                              r"^\W+$", re.I)


def melhor_linha(texto: str) -> str:
    """Do texto de um card de produto, escolhe a linha que é o nome do produto."""
    for linha in (trecho.strip() for trecho in (texto or "").splitlines()):
        if len(linha) >= 6 and not RE_ITENS_INUTEIS.search(linha):
            return linha
    return (texto or "").strip().split("\n")[0]


class LojaBase:
    """Implementação genérica (usada quando a plataforma não é reconhecida)."""

    plataforma = "genérica"

    def __init__(self, page: Page, fornecedor: Fornecedor) -> None:
        self.page = page
        self.fornecedor = fornecedor
        self.base = self._base_url(fornecedor.site)
        self.insumo = None                     # definido pelo coletor (ajuda a escolher variação)
        self._modelo_busca: str | None = None  # descoberto no formulário de busca do site
        # Texto do bloco do frete antes e depois do cálculo (para diagnóstico no log).
        self.texto_frete: tuple[str, str] = ("", "")

    # ------------------------------------------------------------------ util
    @staticmethod
    def _base_url(site: str) -> str:
        site = site.split(" / ")[0].strip()
        if not site.startswith("http"):
            site = "https://" + site
        p = urlparse(site)
        return f"{p.scheme}://{p.netloc}"

    def abrir(self, url: str) -> bool:
        """Abre uma URL; devolve False em caso de erro (já registrado)."""
        try:
            self.page.goto(url, timeout=TIMEOUT_NAVEGACAO_MS, wait_until="domcontentloaded")
            try:
                self.page.wait_for_load_state("networkidle", timeout=10_000)
            except PlaywrightTimeout:
                pass  # sites com rastreadores nunca ficam "ociosos"; seguimos
            self.page.wait_for_timeout(PAUSA_ENTRE_ACOES_MS)
            self._fechar_avisos()
            return True
        except (PlaywrightTimeout, PlaywrightError) as exc:
            log.warning("[%s] Falha ao abrir %s: %s", self.fornecedor.nome, url, exc)
            return False

    def _fechar_avisos(self) -> None:
        """Fecha banners de cookies/LGPD que cobririam o print."""
        for texto in ("Aceitar", "Entendi", "Concordo", "OK, entendi", "Aceitar e Fechar"):
            try:
                botao = self.page.get_by_role("button", name=re.compile(f"^{texto}", re.I))
                if botao.count() and botao.first.is_visible():
                    botao.first.click(timeout=2_000)
                    return
            except PlaywrightError:
                continue

    # ----------------------------------------------------------------- busca
    def _descobrir_busca(self) -> str:
        """Lê o formulário de busca da página inicial e monta um modelo de URL.

        Resolve lojas com parâmetros próprios, como a Tray
        (``/loja/busca.php?loja=123&palavra_busca=``), a Magento
        (``/catalogsearch/result/?q=``) e outras (``/pesquisa?t=``).
        """
        if self._modelo_busca is not None:
            return self._modelo_busca
        self._modelo_busca = ""
        if not self.abrir(self.base):
            return ""
        try:
            info = self.page.evaluate(
                """() => {
                    for (const f of document.querySelectorAll('form')) {
                        if ((f.method || 'get').toLowerCase() !== 'get') continue;
                        const campo = f.querySelector('input[type=search], input[name=q], input[name=s],'
                            + ' input[name*=busca i], input[name*=search i], input[name=t], input[type=text]');
                        if (!campo || !campo.name) continue;
                        const extras = [...f.querySelectorAll('input[type=hidden]')]
                            .filter(i => i.name).map(i => [i.name, i.value]);
                        return {acao: f.action, campo: campo.name, extras};
                    }
                    return null;
                }""")
        except PlaywrightError:
            info = None
        if info and info.get("acao"):
            self._modelo_busca = self.modelo_de_busca(info)
            log.info("[%s] Busca descoberta no site: %s", self.fornecedor.nome, self._modelo_busca)
        return self._modelo_busca

    @staticmethod
    def modelo_de_busca(info: dict) -> str:
        """Monta ``<ação>?<campos ocultos>&<campo>={termo}`` a partir do formulário."""
        # O JavaScript devolve listas [nome, valor] e o urlencode só aceita
        # tuplas. Era o "TypeError: not a valid non-string sequence" que
        # derrubava as lojas Tray (Lojas 360, DMS, TR EPIs) no log de 09/10/2026.
        extras = urlencode([tuple(par) for par in info.get("extras") or []])
        sep = "&" if "?" in info["acao"] else "?"
        return f"{info['acao']}{sep}{extras + '&' if extras else ''}{info['campo']}={{termo}}"

    def url_busca(self, termo: str) -> str:
        modelo = self._descobrir_busca()
        if modelo:
            return modelo.replace("{termo}", quote_plus(termo))
        return f"{self.base}/busca?q={quote_plus(termo)}"

    def extrair_resultados(self) -> list[Candidato]:
        """Genérico: links internos do conteúdo (fora de menu, cabeçalho e rodapé).

        A aderência ao insumo é decidida depois, pela pontuação do nome, e a
        página aberta só é aceita se for de fato uma página de produto.
        """
        itens = self.page.evaluate(
            """() => [...document.querySelectorAll('a[href]')]
                .filter(a => !a.closest('header, nav, footer, [class*=menu i], [id*=menu i]'))
                .map(a => ({n: (a.innerText || a.title || a.getAttribute('aria-label') || '').trim(),
                            u: a.href.split('#')[0]}))""")
        dominio = urlparse(self.base).netloc.removeprefix("www.")
        vistos, saida = set(), []
        for it in itens:
            nome, url = melhor_linha(it["n"]), it["u"]
            if len(nome) < 6 or url in vistos or dominio not in urlparse(url).netloc:
                continue
            vistos.add(url)
            saida.append(Candidato(nome=nome, url=url))
        return saida

    def buscar(self, termo: str) -> list[Candidato]:
        if not self.abrir(self.url_busca(termo)):
            return []
        try:
            return self.extrair_resultados()[: MAX_RESULTADOS_BUSCA * 4]
        except PlaywrightError as exc:
            log.warning("[%s] Erro lendo resultados de '%s': %s", self.fornecedor.nome, termo, exc)
            return []

    # --------------------------------------------------------------- produto
    def _json_ld_produto(self) -> dict | None:
        """Lê o bloco schema.org/Product, presente na maioria das lojas."""
        try:
            blocos = self.page.eval_on_selector_all(
                "script[type='application/ld+json']", "els => els.map(e => e.textContent)")
        except PlaywrightError:
            return None
        for bruto in blocos:
            try:
                dado = json.loads(bruto)
            except (json.JSONDecodeError, TypeError):
                continue
            pilha = dado if isinstance(dado, list) else [dado]
            while pilha:
                item = pilha.pop()
                if isinstance(item, dict):
                    if item.get("@type") in ("Product", ["Product"]):
                        return item
                    pilha.extend(item.get("@graph", []))
        return None

    def ler_preco_pagina(self) -> tuple[float | None, float | None]:
        """Preço final e preço 'de' lidos do HTML (fallback do JSON-LD)."""
        for sel in ("[itemprop='price']", ".price ins", ".price", "[class*='price' i]",
                    "[class*='preco' i]"):
            try:
                el = self.page.locator(sel).first
                if el.count() and el.is_visible():
                    conteudo = el.get_attribute("content") or el.inner_text()
                    valores = valores_de_preco(conteudo) or (
                        [float(conteudo)] if re.fullmatch(r"\d+(\.\d+)?", conteudo or "") else [])
                    if valores:
                        final = min(valores)
                        de = max(valores) if max(valores) > final else None
                        return final, de
            except (PlaywrightError, ValueError):
                continue
        return None, None

    def eh_pagina_de_produto(self, dado_ld: dict) -> bool:
        """Evita tratar página de categoria/institucional como produto."""
        if dado_ld:
            return True
        try:
            return self.page.locator(
                "button, input[type=submit], a").filter(
                has_text=re.compile(r"comprar|adicionar (ao|à) (carrinho|sacola)|add to cart", re.I)
            ).count() > 0
        except PlaywrightError:
            return False

    def ler_produto(self, url: str) -> Produto | None:
        if not self.abrir(url):
            return None
        dado = self._json_ld_produto() or {}
        if not self.eh_pagina_de_produto(dado):
            log.info("[%s] %s não é página de produto; ignorada.", self.fornecedor.nome, url)
            return None
        nome = limpar_nome(dado.get("name"))
        if not nome:
            try:
                nome = limpar_nome(self.page.locator("h1").first.inner_text(timeout=3_000))
            except PlaywrightError:
                nome = ""
        oferta = dado.get("offers") or {}
        if isinstance(oferta, list):
            oferta = oferta[0] if oferta else {}
        if oferta.get("@type") == "AggregateOffer":
            oferta = {**oferta, "price": oferta.get("lowPrice")}
        try:
            preco = float(str(oferta.get("price")).replace(",", ".")) if oferta.get("price") else None
        except ValueError:
            preco = None
        final_html, de_html = self.ler_preco_pagina()
        preco_final = preco if preco is not None else final_html
        disponivel = "OutOfStock" not in str(oferta.get("availability", ""))
        motivo = ""
        if preco_final is None:
            # Regra (09/10/2026): produto correspondente sem preço visível vai
            # para a coluna P, com o motivo; só o esgotado claro é descartado.
            texto = self.page.locator("body").inner_text()[:30_000]
            if not disponivel or RE_ESGOTADO.search(texto):
                disponivel = False
            elif RE_PRECO_LOGIN.search(texto):
                motivo = MOTIVO_LOGIN
            elif RE_SOB_CONSULTA.search(texto):
                motivo = MOTIVO_CONSULTA
            else:
                motivo = MOTIVO_DESCONHECIDO
        return Produto(nome=nome, url=self.page.url, preco_final=preco_final,
                       preco_de=de_html if de_html and preco_final and de_html > preco_final else None,
                       disponivel=disponivel, motivo_sem_preco=motivo)

    # ----------------------------------------------------------------- frete
    def _campo_cep(self):
        for sel in SELETORES_CEP:
            campos = self.page.locator(sel)
            for i in range(campos.count()):
                campo = campos.nth(i)
                try:
                    if campo.is_visible() and campo.is_editable():
                        return campo
                except PlaywrightError:
                    continue
        return None

    def preencher_cep(self, campo, cep: str) -> str:
        """Digita o CEP e CONFERE o que ficou no campo. Devolve '' ou o problema.

        Na coleta de 10/10/2026 a máscara do campo da Loja do EPI (Singular)
        jogou o primeiro dígito para o fim: 74933-130 virou 49331-307 e o frete
        saiu calculado para Sergipe. Se a digitação falhar, tenta colar o valor
        de uma vez; se ainda assim o campo não tiver o CEP certo, o frete não vale.
        """
        ficou = ""
        for modo in ("digitar", "colar"):
            campo.click()
            campo.fill("")
            if modo == "digitar":
                campo.press_sequentially(cep, delay=60)
            else:
                campo.fill(cep)
            ficou = somente_digitos(campo.input_value())
            if ficou == cep:
                return ""
            log.info("[%s] Campo de CEP ficou com '%s' ao %s %s.",
                     self.fornecedor.nome, ficou, modo, cep)
        return f"o campo de CEP ficou com '{ficou}' em vez de {cep}"

    def _aviso_frete_gratis_visivel(self) -> str:
        """Texto de frete grátis incondicional VISÍVEL na página atual, ou ''.

        Não vale aviso com condição ("acima de R$ 200", "a partir de") nem
        texto escondido (menus fechados, pop-ups).
        """
        try:
            avisos = self.page.get_by_text(re.compile(r"frete gr[aá]tis", re.I))
            for i in range(min(avisos.count(), 20)):
                el = avisos.nth(i)
                if not el.is_visible():
                    continue
                texto = " ".join(el.inner_text().split())
                if len(texto) <= 120 and not RE_CONDICAO.search(texto) and \
                        RE_GRATIS_BRASIL.search(texto):
                    return texto
        except PlaywrightError:
            return ""
        return ""

    def _texto_regiao(self, campo, niveis: int = NIVEIS_REGIAO_FRETE) -> str:
        """Texto do bloco ao redor do campo de CEP (onde o resultado aparece)."""
        return campo.evaluate(
            "(el, n) => { let c = el; for (let i = 0; i < n && c.parentElement; i++) c = c.parentElement;"
            " return c.innerText; }", niveis)

    @staticmethod
    def _eh_retirada(linhas: list[str], i: int) -> bool:
        """Retirada na loja não é frete.

        O rótulo pode estar na própria linha do valor ou, quando a linha só tem
        valor/prazo, na vizinha ("Retirada em loja" / "R$ 0,00"). Uma linha com
        rótulo próprio ("Frete Grátis Goiânia  FRETE GRÁTIS  1 a 2 dias") é
        uma opção de entrega, mesmo que a linha ao lado seja de retirada.
        """
        if RE_RETIRADA.search(linhas[i]):
            return True
        if RE_TEM_ROTULO.search(RE_SEM_ROTULO.sub(" ", linhas[i])):
            return False
        return any(RE_RETIRADA.search(v) for v in linhas[max(0, i - 1): i + 2])

    @staticmethod
    def _descrever_opcao(linhas: list[str], i: int) -> str:
        """Texto da opção para OBS FRETE: a linha do valor, o rótulo anterior
        (só quando a linha tem apenas o valor) e as linhas seguintes até o
        próximo valor, sem botões como "Lista de Desejos"."""
        def util(v: str) -> bool:
            return not (todos_valores(v) or RE_LIXO_FRETE.search(v) or RE_RETIRADA.search(v)
                        or RE_CONDICAO.search(v))

        partes = [linhas[i]]
        so_valor = not re.sub(r"R\$\s*[\d.,]+", "", linhas[i]).strip()
        rotulo_antes = so_valor and i > 0 and util(linhas[i - 1])
        if rotulo_antes:
            partes.insert(0, linhas[i - 1])
        for seguinte in linhas[i + 1: i + 3]:
            # Com o rótulo antes do valor ("Pac" / "R$ 25,47" / "7 dias"), depois
            # só vem o prazo; a linha seguinte já é o rótulo da próxima opção.
            if not util(seguinte) or (rotulo_antes and not RE_PRAZO.search(seguinte)):
                break
            partes.append(seguinte)
        return " ".join(" ".join(partes).split())[:150]

    @classmethod
    def interpretar_frete(cls, texto: str, antes: str = "") -> Frete:
        """Escolhe a opção de entrega mais barata no texto do resultado.

        ``antes`` é o texto do bloco antes de informar o CEP: as linhas que já
        existiam (ex.: o preço do produto) são ignoradas. As opções podem vir
        numa linha só ("R$ 45,04 10 dias úteis Jadlog") ou quebradas em várias
        ("R$ 59,10" / "7 dias úteis" / "Correios PAC"). Retirada na loja e
        avisos de condição ("grátis acima de R$ X") nunca contam.
        """
        ja_existiam = {v.strip() for v in antes.splitlines() if v.strip()}
        linhas = [v.strip() for v in texto.splitlines() if v.strip() and v.strip() not in ja_existiam]
        if RE_NAO_ENTREGA.search("\n".join(linhas)):
            return Frete(ok=False, motivo="a loja não entrega neste CEP")
        opcoes, valores, gratis = [], [], False
        for i, linha in enumerate(linhas):
            if RE_RETIRADA.search(linha) or RE_CONDICAO.search(linha):
                continue
            contexto = " ".join(linhas[max(0, i - 1): i + 3])   # linha + vizinhas
            vals = todos_valores(linha)
            eh_gratis = RE_GRATIS.search(linha) or (vals and max(vals) == 0)
            if eh_gratis and RE_CHAVE_FRETE.search(contexto) and not cls._eh_retirada(linhas, i):
                gratis = True
                opcoes.append(cls._descrever_opcao(linhas, i))
                continue
            if vals and min(vals) > 0 and (RE_CHAVE_FRETE.search(contexto) or len(linhas) <= 4):
                descricao = cls._descrever_opcao(linhas, i)
                valores.append((min(vals), descricao))
                opcoes.append(descricao)
        if gratis:
            return Frete(ok=True, gratis=True, modalidade="Frete grátis", opcoes=opcoes)
        if valores:
            valor, descricao = min(valores)
            return Frete(ok=True, valor=valor, modalidade=descricao, opcoes=opcoes)
        return Frete(ok=False, motivo="nenhuma opção de frete encontrada após informar o CEP")

    def calcular_frete(self, cep: str, uf: str) -> Frete:
        """Genérico: preenche o campo de CEP da página do produto e lê o resultado."""
        campo = self._campo_cep()
        if campo is None:
            # Regra (09/10/2026): sem calculadora, o frete só vale se a PRÓPRIA
            # página do produto (a que vai para o print) mostrar frete grátis
            # sem condição (ex.: "FRETE GRÁTIS PARA TODO BRASIL").
            aviso = self._aviso_frete_gratis_visivel()
            if aviso:
                return Frete(ok=True, gratis=True,
                             modalidade=f'Frete grátis informado na página do produto: "{aviso}"')
            return Frete(ok=False, motivo="página do produto sem calculadora de frete")
        try:
            antes = self._texto_regiao(campo, NIVEIS_REGIAO_FRETE)
            problema = self.preencher_cep(campo, cep)
            if problema:
                return Frete(ok=False, motivo=problema)
            campo.press("Enter")
            # Também clica no botão vizinho (alguns sites ignoram o Enter).
            botao = campo.locator("xpath=ancestor::*[position()<=3]").locator(
                "button, input[type=submit], input[type=button], a, span, div[role=button]"
            ).filter(has_text=TEXTO_BOTAO_FRETE)
            if botao.count():
                try:
                    botao.first.click(timeout=3_000)
                except PlaywrightError:
                    pass
            # Espera aparecer valor ou "grátis" no bloco.
            prazo = ESPERA_FRETE_MS
            texto = antes
            while prazo > 0:
                self.page.wait_for_timeout(500)
                prazo -= 500
                texto = self._texto_regiao(campo, NIVEIS_REGIAO_FRETE)
                if texto != antes and (todos_valores(texto) or RE_GRATIS.search(texto)):
                    self.page.wait_for_timeout(1_000)   # deixa terminar de montar a lista
                    texto = self._texto_regiao(campo, NIVEIS_REGIAO_FRETE)
                    break
            self.texto_frete = (antes, texto)
            frete = self.interpretar_frete(texto, antes)
            if not frete.ok and RE_FRETE_LOGIN.search(texto):
                frete.motivo = MOTIVO_FRETE_LOGIN
            return frete
        except PlaywrightError as exc:
            return Frete(ok=False, motivo=f"erro ao calcular frete: {exc}")

    # ----------------------------------------------------------------- print
    def tirar_print(self, caminho: str) -> bool:
        try:
            self.page.screenshot(path=caminho, full_page=True)
            return True
        except PlaywrightError as exc:
            log.warning("[%s] Falha no print %s: %s", self.fornecedor.nome, caminho, exc)
            return False


def detectar_plataforma(page: Page) -> str:
    """Reconhece a plataforma pela página inicial já carregada."""
    try:
        sinais = page.evaluate(
            """() => ({
                gen: [...document.querySelectorAll('meta[name=generator]')].map(m => m.content).join(' '),
                vtex: !!window.vtex || !!document.querySelector('[class*="vtex-"]'),
                shopify: !!window.Shopify,
                woo: document.body.className.includes('woocommerce') || !!window.wc_add_to_cart_params,
                li: !!document.querySelector('script[src*="awsli.com.br"]'),
                tray: !!document.querySelector('script[src*="tcdn.com.br"], script[src*="tray"]'),
                nuvem: !!window.LS && !!document.querySelector('[data-store]'),
            })""")
    except PlaywrightError:
        return "generica"
    if sinais["li"] or "Loja Integrada" in sinais["gen"]:
        return "loja_integrada"
    if sinais["vtex"] or "vtex" in sinais["gen"].lower():
        return "vtex"
    if sinais["shopify"]:
        return "shopify"
    if sinais["woo"] or "WooCommerce" in sinais["gen"]:
        return "woocommerce"
    if sinais["tray"]:
        return "tray"
    if sinais["nuvem"]:
        return "nuvemshop"
    return "generica"
