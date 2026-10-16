"""Leitor da loja Mais Segurança (NPC Store, página em JavaScript) - 16/10/2026."""

import pytest

from fgv_precos.raspagem.lojas import REGISTRO
from fgv_precos.raspagem.lojas.mais_seguranca import MaisSeguranca, interpretar_pagina
from fgv_precos.raspagem.modelos import Fornecedor


def test_registrada_pelo_cnpj():
    assert REGISTRO["43903641000169"] is MaisSeguranca


def test_interpretar_pagina():
    nome, preco, ok = interpretar_pagina(
        "RESPIRADOR PFF2 AZ S/VALV PRO SAFETY  - DELTA PLUS CA.38504 Ref: MS1123", " V: R$ 1,00",
        ["UN (13)"])
    assert (nome, preco, ok) == ("RESPIRADOR PFF2 AZ S/VALV PRO SAFETY - DELTA PLUS CA.38504", 1.0, True)
    # sapato: um tamanho sem estoque, outro com estoque -> disponível
    assert interpretar_pagina("SAPATO X Ref: .", "V: R$ 78,00", ["41 (0)", "ESTQ (7)"])[1:] == (78.0, True)
    # R$ 0,00 e estoque zerado/negativo: sem preço e esgotado
    assert interpretar_pagina("CALCA BRIM Ref: .", "V: R$ 0,00", ["PC (0)"])[1:] == (None, False)
    assert interpretar_pagina("BRILHA INOX Ref: .", "V: R$ 0,00", ["UN (-5)"])[1:] == (None, False)


HTML = """<html><body><div id=app><div class=grid><div class=col-12><div class=ml-2>
<span class="w-full titulo">RESPIRADOR PFF2 AZ S/VALV PRO SAFETY  - DELTA PLUS CA.38504 Ref: MS1123</span>
</div><div class="text-right mr-4"><span class=w-full><span class=titulo-valor> V: R$ 1,00</span></span></div>
<div class="adicionar-carrinho-tamanho selecionado"><span class=p-2>UN <span>(13)</span></span></div>
<button>adicionar</button></div></div></div></body></html>"""


def test_ler_produto_no_navegador(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    try:
        pw = sync_api.sync_playwright().start()
        navegador = pw.chromium.launch()
    except Exception as exc:  # noqa: BLE001 - sem navegador instalado
        pytest.skip(f"sem navegador: {exc}")
    try:
        page = navegador.new_page()
        arquivo = tmp_path / "produto.html"
        arquivo.write_text(HTML, encoding="utf-8")
        loja = MaisSeguranca(page, Fornecedor("Mais Segurança EPI", "43.903.641/0001-69",
                                              "https://maisseguranca.online"))
        loja.abrir = lambda url: bool(page.goto(arquivo.as_uri())) or True
        p = loja.ler_produto("https://maisseguranca.online/#/produto-detalhes/x/y")
        assert p.nome == "RESPIRADOR PFF2 AZ S/VALV PRO SAFETY - DELTA PLUS CA.38504"
        assert p.preco_final == 1.0 and p.disponivel and not p.motivo_sem_preco
        assert loja.tirar_print(str(tmp_path / "print.png"))
    finally:
        navegador.close()
        pw.stop()
