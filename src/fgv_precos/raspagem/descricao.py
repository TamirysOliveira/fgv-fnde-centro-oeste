"""
Leitura "inteligente" da coluna Descrição e comparação com o nome do produto
encontrado no site.

A descrição é lida da esquerda para a direita:

    "BALDE PLÁSTICO – 5 L - COM ALÇA."
     └──── nome ───┘ └┬┘   └─ observação (só ajuda a desempatar)
                  atributo obrigatório

1. Tudo depois do primeiro " - " (hífen entre espaços) ou do primeiro ";"
   é observação.
2. Na parte principal, o travessão "–" separa o nome do atributo
   (ex.: "5 L", "300 M", "MÍNIMO 120 L").
3. "/" entre palavras indica alternativas: "CAMISETA/CAMISA DE UNIFORME"
   vira as buscas "CAMISETA DE UNIFORME" e "CAMISA DE UNIFORME".
4. A coluna Embalagem (ex.: "GALÃO 5 L", "FRASCO 500 ML") também vira
   atributo de quantidade, quando informada.

Para aceitar um produto do site:
    * o nome do produto não pode começar por "tecido", "kit", "suporte",
      "refil", "organizador", "jogo de", "capa para" ou "peça", a não ser que
      a descrição do insumo use essa palavra;
    * a 1ª palavra relevante do nome (ex.: "balde", "camiseta") precisa ser
      a 1ª palavra do nome do produto;
    * pelo menos ``PALAVRAS_EXTRAS_MINIMAS`` das demais palavras do nome
      também precisam aparecer (evita "Carro Guia Maçarico" para
      "Carro Funcional para Limpeza");
    * os atributos de medida (5 L, 500 ML, 20 L...) precisam bater;
    * as palavras restantes e a observação só aumentam a pontuação.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from fgv_precos.raspagem.config_raspagem import PALAVRAS_EXTRAS_MINIMAS

PALAVRAS_VAZIAS = {
    "de", "da", "do", "das", "dos", "e", "em", "para", "com", "a", "o", "as", "os",
    "uso", "geral", "tipo", "ou", "na", "no", "aproximadamente", "minimo", "maximo",
    # qualificadores genéricos, que quase nunca aparecem no nome do produto no site
    "limpeza", "uniforme", "manual", "profissional", "piso", "pisos",
}
# Nomes de produto que começam assim são outro produto (acessório, peça, kit,
# matéria-prima), a não ser que a própria descrição do insumo use a palavra
# (ex.: 1004 "ÁLCOOL ... – REFIL", 1117 "CAPA DE CHUVA").
PREFIXOS_RECUSADOS = ("tecido", "kit", "suporte", "refil", "organizador", "jogo de",
                      "capa para", "peca")
# Nomes diferentes para o mesmo produto (comparados já sem acento).
SINONIMOS = {"dispenser": "dispensador", "auditivo": "auricular"}
# Medidas reconhecidas no texto: número + unidade.
_RE_MEDIDA = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(ml|l|litros?|lts?|kg|g|m|cm|mm|w)\b", re.IGNORECASE
)
_UNIDADE_PADRAO = {"litro": "l", "litros": "l", "lt": "l", "lts": "l"}


def normalizar(texto: str) -> str:
    """Minúsculas, sem acentos e com espaços simples."""
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto or "")
                         if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def medidas(texto: str) -> set[tuple[float, str]]:
    """Extrai medidas normalizadas: {(5.0, 'l'), (500.0, 'ml')}."""
    achadas = set()
    for num, unid in _RE_MEDIDA.findall(normalizar(texto)):
        unid = _UNIDADE_PADRAO.get(unid, unid)
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", num):   # "1.600" = mil e seiscentos
            num = num.replace(".", "")
        valor = float(num.replace(",", "."))
        # Converte para uma unidade base, para "1000 ml" bater com "1 l".
        if unid == "ml":
            valor, unid = valor / 1000, "l"
        elif unid == "g":
            valor, unid = valor / 1000, "kg"
        elif unid in ("cm", "mm"):
            valor, unid = (valor / 100 if unid == "cm" else valor / 1000), "m"
        achadas.add((round(valor, 4), unid))
    return achadas


@dataclass
class Insumo:
    """Um insumo interpretado a partir da linha da planilha."""

    id_fgv: str
    grupo: str
    descricao: str
    embalagem: str = ""
    nomes_busca: list[str] = field(default_factory=list)   # alternativas
    medidas_obrigatorias: set[tuple[float, str]] = field(default_factory=set)
    observacao: str = ""
    medida_minima: bool = False      # atributo "MÍNIMO 120 L": aceita >= 120 L

    @property
    def termos_de_busca(self) -> list[str]:
        """Ordem de tentativa na busca do site: nomes completos e, por fim, só a
        palavra principal (muitas buscas exigem todas as palavras e voltam vazias)."""
        termos = list(self.nomes_busca)
        for nome in self.nomes_busca:
            palavras = nome.split()
            if palavras and palavras[0] not in termos:
                termos.append(palavras[0])
        return termos


def _expandir_barras(nome: str) -> list[str]:
    """Gera as alternativas indicadas por "/".

    * Troca de palavra: 'CAMISETA/CAMISA DE UNIFORME' ->
      ['CAMISETA DE UNIFORME', 'CAMISA DE UNIFORME']
    * Troca de expressão: 'DESODORIZADOR SANITÁRIO/PEDRA SANITÁRIA' ->
      ['DESODORIZADOR SANITÁRIO', 'PEDRA SANITÁRIA']
    A troca de expressão só é usada quando os dois lados da barra têm o
    mesmo número de palavras (duas ou mais), e vem primeiro. Nos demais casos
    um lado sozinho não é um nome de produto: 'BOTA DE PVC/BORRACHA' não pode
    gerar a busca 'BORRACHA', nem 'DISPENSADOR PARA SABONETE LÍQUIDO/ÁLCOOL
    GEL' a busca 'ÁLCOOL GEL'.
    """
    m = re.search(r"(\S+)/(\S+)", nome)
    if not m:
        return [nome]
    antes, depois = nome[: m.start()], nome[m.end():]
    por_palavra = [f"{antes}{m.group(1)}{depois}".strip(), f"{antes}{m.group(2)}{depois}".strip()]
    esquerda, direita = (x.strip() for x in nome.split("/", 1))
    n_esq, n_dir = len(esquerda.split()), len(direita.split())
    ordem = [esquerda, direita, *por_palavra] if n_esq == n_dir >= 2 else por_palavra
    return list(dict.fromkeys(alt for alt in ordem if alt))


def interpretar(id_fgv: str, grupo: str, descricao: str, embalagem: str = "") -> Insumo:
    """Interpreta a descrição da esquerda para a direita (ver docstring do módulo)."""
    texto = (descricao or "").strip().rstrip(".")
    # 1) separa a observação: primeiro " - " ou ";"
    corte = re.search(r"\s-\s|;", texto)
    principal = texto[: corte.start()] if corte else texto
    observacao = texto[corte.end():].strip() if corte else ""

    # 2) travessão separa nome e atributo
    partes = re.split(r"\s*[–—]\s*", principal, maxsplit=1)
    nome = partes[0].strip()
    atributo = partes[1].strip() if len(partes) > 1 else ""

    # Remove explicações entre parênteses do nome de busca.
    nome = re.sub(r"\(.*?\)", "", nome).strip()

    obrig = medidas(atributo) | medidas(embalagem)
    # Se o próprio nome tem medida (ex.: "ÁLCOOL ETÍLICO 70%"), ela fica no nome.
    return Insumo(
        id_fgv=str(id_fgv), grupo=grupo, descricao=descricao, embalagem=embalagem,
        nomes_busca=[n.title() for n in _expandir_barras(nome)],
        medidas_obrigatorias=obrig, observacao=observacao,
        medida_minima="minimo" in normalizar(atributo),
    )


def _palavras(texto: str) -> list[str]:
    return [SINONIMOS.get(p, p) for p in re.findall(r"[a-z0-9%]+", normalizar(texto))
            if p not in PALAVRAS_VAZIAS]


def _radical(palavra: str) -> str:
    """Ignora plural e gênero: baldes/balde, sanitária/sanitário, plástica/plástico."""
    p = palavra.removesuffix("s")
    return p[:-1] if len(p) > 4 and p[-1] in "ao" else p


def _contem(palavra: str, alvo: set[str]) -> bool:
    return palavra in alvo or _radical(palavra) in {_radical(a) for a in alvo}


def _nome_produto_normalizado(nome_produto: str) -> str:
    """Sem acento, 'p/' -> 'para', 'c/' -> 'com' e sem números/símbolos no começo."""
    t = normalizar(nome_produto)
    t = re.sub(r"\bp/\s*", "para ", t)
    t = re.sub(r"\bc/\s*", "com ", t)
    return re.sub(r"^[\W\d_]+", "", t)


def prefixo_recusado(insumo: Insumo, nome_produto: str) -> str | None:
    """Devolve o prefixo proibido com que o nome do produto começa, se houver."""
    texto = _nome_produto_normalizado(nome_produto)
    da_descricao = set(re.findall(r"[a-z0-9%]+", normalizar(insumo.descricao)))
    for prefixo in PREFIXOS_RECUSADOS:
        if re.match(rf"{prefixo}\b", texto) and prefixo.split()[0] not in da_descricao:
            return prefixo
    return None


def pontuar(insumo: Insumo, nome_produto: str) -> float:
    """Pontuação de aderência (0 = rejeitado). Quanto maior, melhor."""
    # "Tecido Meia Malha" não é meia; "Kit 10 Luva" não é 1 par; "Suporte de Escova" não é escova.
    if prefixo_recusado(insumo, nome_produto):
        return 0.0
    palavras_produto = [p for p in _palavras(_nome_produto_normalizado(nome_produto))
                        if not p.isdigit()]
    alvo = set(palavras_produto)
    # A palavra principal precisa ser a PRIMEIRA palavra do nome (antes: entre as 3 primeiras).
    inicio = set(palavras_produto[:1])
    melhor = 0.0
    for nome in insumo.nomes_busca:
        palavras = _palavras(nome)
        # A palavra principal é obrigatória e precisa abrir o nome:
        # "Balde Plástico 5L" sim; "Conjunto Mop (Balde 5L ...)" e "Óculos Meia" não.
        if not palavras or not _contem(palavras[0], inicio):
            continue
        extras = sum(1 for p in palavras[1:] if _contem(p, alvo))
        if extras < min(PALAVRAS_EXTRAS_MINIMAS, len(palavras) - 1):
            continue    # só a palavra principal bateu: produto de outro tipo
        pontos = 10.0 + 3 * extras
        pontos += sum(1 for p in set(_palavras(insumo.observacao)) if _contem(p, alvo))
        melhor = max(melhor, pontos)
    if melhor and insumo.medidas_obrigatorias:
        # Pelo menos uma das medidas exigidas precisa aparecer no nome do produto.
        do_produto = medidas(nome_produto)
        if insumo.medida_minima:
            ok = any(u == u2 and v2 >= v for v, u in insumo.medidas_obrigatorias
                     for v2, u2 in do_produto)
        else:
            ok = bool(insumo.medidas_obrigatorias & do_produto)
        if not ok:
            return 0.0
        melhor += 5
    return melhor


def palavras_faltantes(insumo: Insumo, nome_produto: str) -> list[str]:
    """Palavras do nome do insumo que não aparecem no nome do produto.

    Usa a alternativa de nome mais próxima. Serve para explicar, numa revisão
    humana, por que ``pontuar`` recusou o produto.
    """
    alvo = set(_palavras(nome_produto))
    melhor: list[str] | None = None
    for nome in insumo.nomes_busca:
        faltam = [p for p in _palavras(nome) if not _contem(p, alvo)]
        if melhor is None or len(faltam) < len(melhor):
            melhor = faltam
    return melhor or []
