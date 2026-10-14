"""Testes das regras do merge (src/fgv_precos/merge/regras.py)."""

from fgv_precos.merge.regras import Candidato, normalizar_url, obs_frete_go, reais, selecionar


def cand(id_fgv, cnpj, uf, link, preco, frete=None, chave=""):
    return Candidato(id_fgv=id_fgv, cnpj=cnpj, uf=uf, link=link, preco=preco, frete=frete,
                     chave=chave or link)


def test_obs_frete_go():
    assert obs_frete_go(None) == "Frete não calculado (GO para GO)"
    assert obs_frete_go(51.59) == "Frete não calculado (GO para GO) | frete real: R$ 51,59"
    assert reais(1687.82) == "R$ 1.687,82"


def test_go_primeiro_depois_menor_preco_mais_frete():
    cs = [cand("1", "11", "SP", "a.com/1", 10, 5),     # 15
          cand("1", "22", "PR", "b.com/1", 8, 20),     # 28
          cand("1", "33", "GO", "c.com/1", 40, None),  # GO: frete não entra
          cand("1", "44", "SP", "d.com/1", 12, 1)]     # 13
    esc = selecionar({"1": 3}, cs, {}, set())
    assert [c.cnpj for c in esc] == ["33", "44", "11"]


def test_respeita_vagas_cnpj_e_link_ja_usados():
    cs = [cand("1", "11", "SP", "https://www.a.com/x?y=1", 1, 1),
          cand("1", "22", "SP", "b.com/x", 2, 1),
          cand("1", "33", "SP", "c.com/x", 3, 1),
          cand("2", "44", "SP", "a.com/x/", 5, 1)]          # mesmo link do primeiro
    esc = selecionar({"1": 1, "2": 1}, cs, {"1": {"22"}}, {"c.com/x"})
    assert [c.cnpj for c in esc] == ["11"]                   # 2 fica sem: link já usado no 1


def test_sem_vaga_nao_entra():
    assert selecionar({"1": 0}, [cand("1", "11", "SP", "a.com", 1)], {}, set()) == []


def test_normalizar_url():
    assert normalizar_url("https://www.Loja.com.br/p/1/?a=b") == "loja.com.br/p/1"


def test_observacoes_obs():
    """Coluna L "OBS" (13/10/2026): equivalência, tolerância de 10% e teor equivalente."""
    from fgv_precos.merge.observacoes import medida_1d, medida_2d, observacoes
    pv = observacoes("1104", "Camiseta Malha PV Cinza")
    assert pv == ["Malha PV aceita como malha fria (equivalência)."]
    assert observacoes("1104", "Camiseta Malha Fria Gola Redonda") == []
    pvc = observacoes("1116", "Avental de PVC 1,20 x 0,70")
    assert pvc == ["PVC aceito como impermeável (equivalência)."]
    assert medida_2d("1022", "Flanela 38x58cm")[0] == "ok"
    assert medida_2d("1022", "Flanela 40x60cm")[0] == "exata"
    assert medida_2d("1032", "Pano de chão 48x72")[0] == "fora"
    assert medida_2d("1036", "Papel Interfolha 22,5x21cm")[0] == "ok"
    assert medida_1d("1097", "Rodo de pia 14cm")[0] == "ok"
    assert medida_1d("1097", "Rodo de pia 20cm")[0] == "fora"
    assert medida_1d("1069", "Desentupidor com cabo 90CM")[0] == "ok"       # cabo maior serve (1069)
    assert medida_1d("1069", "Desentupidor com cabo 40CM")[0] == "fora"
    assert observacoes("1001", "Álcool Líquido Audax 46° 5L") == ["Álcool 46° aceito para o insumo de 46,2°."]
    assert observacoes("1001", "Álcool Etílico 46,2° 5L") == []


def test_aproximadamente_robo():
    from fgv_precos.raspagem.descricao import interpretar, pontuar
    i = interpretar("1067", "X", "LIXEIRA PLÁSTICA – APROXIMADAMENTE 20 L - POLIETILENO.")
    assert pontuar(i, "Lixeira Plástica 21 Litros") > 0
    assert pontuar(i, "Lixeira Plástica 25 Litros") == 0


def test_obs_evidencia(tmp_path):
    from fgv_precos.merge import observacoes as ob
    arq = tmp_path / "ev.csv"
    arq.write_text("ID FGV;Link;Características;Situação na página;Evidência\n"
                   "1000;https://www.x.com.br/agua#P=1;teor 2 ou 2,5;NÃO CONFIRMADA;não informa\n"
                   "1002;https://x.com.br/alcool;teor 70;CONFIRMADA;70% INPM\n", encoding="utf-8-sig")
    ob.ler_evidencias.cache_clear()
    orig = ob.ARQ_EVIDENCIAS
    try:
        ob.ler_evidencias.__wrapped__  # noqa: B018
        ev = ob.ler_evidencias(arq)
        assert ev[("1000", "x.com.br/agua")][0] == "NÃO CONFIRMADA"
    finally:
        ob.ARQ_EVIDENCIAS = orig
        ob.ler_evidencias.cache_clear()


def test_link_coluna_p_livre_para_o_mesmo_fornecedor():
    from types import SimpleNamespace

    from fgv_precos.merge import montagem as m
    linha = [None] * 16
    linha[m.C_ID], linha[m.C_CNPJ], linha[m.C_P] = "1093", "07.964.337/0001-68", "https://x.com/rodo"
    outro = list(linha)
    outro[m.C_ID] = "1096"
    cand = SimpleNamespace(id_fgv="1093", cnpj="07964337000168", link="https://x.com/rodo")
    mantidas = [(linha, "base", None)]
    assert m._links_coluna_p_do_candidato(mantidas, [cand], {"G": [linha]}, set())
    # o mesmo link em outro insumo da base: continua bloqueado
    assert not m._links_coluna_p_do_candidato(mantidas, [cand], {"G": [linha, outro]}, set())
    # ... a não ser que a outra linha seja retirada por correção
    assert m._links_coluna_p_do_candidato(mantidas, [cand], {"G": [linha, outro]},
                                          {("1096", "07964337000168")})
