"""Merge da entrega com outras fontes de preço (entrega do William, coleta por link, robô).

A Entrega (FNDE/Centro Oeste/Entrega/<Grupo>/fnde_resultado_merge.xlsx, resumo e
prints) é sempre MONTADA a partir de:
    1. a base (_historico/merge/base_entrega_2026-10-13/<Grupo>/FNDE_output.xlsx
       e os prints dela), que nunca é alterada;
    2. as correções da base (_historico/merge/correcoes_entrega.csv);
    3. os candidatos APROVADOS na revisão (_historico/merge/candidatos.xlsx),
       que só preenchem as vagas até 5 preços por insumo.
Ver scripts/montar_merge.py.
"""
