# Merge da Entrega – FNDE Centro-Oeste (desde 13/10/2026)

A Entrega (`FNDE/Centro Oeste/Entrega/<Grupo>/fnde_resultado_merge.xlsx`, `resumo_coleta.csv`,
`prints/` e o `dashboard_resumo_coleta.xlsx`) não é mais editada à mão nem pelo `incorporar`.
Ela é **montada** por `scripts/montar_merge.py` a partir dos arquivos desta pasta.

| Arquivo / pasta | O que é |
|---|---|
| `base_entrega_2026-10-13/<Grupo>/` | A entrega da Aline de 13/10 (FNDE_output.xlsx + prints). **Nunca é alterada.** |
| `correcoes_entrega.csv` | Linhas da base que saem do merge, com o motivo e quem apontou. |
| `evidencias_observacao.csv` | Conferência na página do produto das características "NÃO INFORMADO" (13/10/2026): CONFIRMADA, NÃO CONFIRMADA ou DÚVIDA, com o trecho da página. A montagem usa este arquivo para a coluna OBS. |
| `candidatos.xlsx` | Linhas de outras fontes (William, coleta por link, robô) e a revisão de cada uma. Só entra quem está **APROVADO**. |
| `prints_candidatos/` | Prints dos candidatos (os do William foram extraídos das planilhas dele). |
| `links_para_coletar.csv` | Links que podem preencher vagas, gerados por `montar_merge.py gerar-links`. |
| `coleta_links/<data_hora>/` | Resultado de cada `coletar_links.py` (situacao.csv, prints, diagnostico). |
| `montagens/<data_hora>/` | Relatório e resumo de cada montagem. |
| `prints_substituidos/` | Prints que saíram da Entrega (nada é apagado). |
| `entregas_william/` | As planilhas recebidas do William. |
| `trabalho_2026-10-13/` | Análise, consulta à Receita e scripts avulsos do primeiro merge. |

## Regras da montagem (combinadas em 13/10/2026)
- As linhas da base ficam, exceto as de `correcoes_entrega.csv`; os candidatos aprovados só completam as vagas até 5 preços.
- Prioridade: fornecedor de GO primeiro; depois o menor preço + frete. Duplicado = mesmo CNPJ no mesmo insumo; o mesmo produto (link) não entra em dois insumos.
- Fornecedor de GO: o frete não é calculado. VALOR FRETE fica vazio e OBS FRETE recebe "Frete não calculado (GO para GO)"; quando o frete real é conhecido, recebe também "| frete real: R$ X". As linhas que já tinham frete grátis ficam como estavam.
- Observação e quantidade da Embalagem são obrigatórias (13/10/2026). A conferência de todas as linhas (Entrega e candidatos) é feita por `trabalho_2026-10-13/conferir_observacao.py`, que grava `conferencia_observacao_2026-10-13.xlsx` (ATENDE · RETIRAR · NÃO INFORMADO), com a aba **Legenda** explicando cada regra. As linhas RETIRAR da base vão para `correcoes_entrega.csv`; as de candidatos ficam REPROVADO. As NÃO INFORMADO só ficam se o print ou a página mostrar a característica.
- Coluna L da Entrega = **"OBS"** (antes "OBS Desconto", 13/10/2026): observações pertinentes da linha (equivalência aceita, medida aceita pela tolerância de 10%, teor equivalente), geradas por `src/fgv_precos/merge/observacoes.py`.
- Alterações de 13/10 à tarde (1001 → 46,2°, regras de teor, faixa, atributo, tolerância): cópias de antes em `trabalho_2026-10-13/backup_alteracao_1001_2026-10-13/`.
- Preço = preço cheio, sem desconto por forma de pagamento. Quando o preço do print for outro, ele vai na coluna "Preço pela regra" de `candidatos.xlsx`.

## Situações em `candidatos.xlsx`
APROVADO · REPROVADO (motivo) · A REVISAR (falta conferir o print) · A COLETAR (falta print/frete: vai para a lista de links) · FORA DA REGRA DE ADERÊNCIA (aguarda decisão; ver "Sugestão") · DUPLICADO · SUBSTITUÍDO PELA COLETA.

## Comandos (na pasta FGV, com `.venv\Scripts\activate`)
1. Coleta por link (print, preço e frete das linhas que ainda não têm print válido):
   `python scripts/coletar_links.py --ver-navegador`
   `python scripts/montar_merge.py importar-coleta "_historico/merge/coleta_links/<pasta>"`
2. Busca nos sites (inclusive nos 24 fornecedores novos) só do que falta:
   `python scripts/raspar_precos_centro_oeste.py --completar-merge --ver-navegador`
   `python scripts/montar_merge.py importar-robo`
3. Revisar os prints das linhas "A REVISAR" e marcar APROVADO/REPROVADO em `candidatos.xlsx`; rodar `python _historico/merge/trabalho_2026-10-13/conferir_observacao.py` e tratar as linhas RETIRAR.
4. `python scripts/montar_merge.py montar --simular` (confere) e `python scripts/montar_merge.py montar` (grava a Entrega).

## Revisão da coleta por link de 13/10/2026 (2026-10-13_163721)
- Os 32 prints foram revistos em `candidatos.xlsx`: 21 APROVADO (3 com "Preço pela regra" corrigido para o preço no cartão: 1055 LF 28,82; 1059 LF 19,89; 1075 LF 926,21), 10 REPROVADO (frete/preço encoberto, só PIX no print, produto em embalagem diferente, preço lido inválido) e 1 A REVISAR (1053 LF: a página diz "Cor: Vermelho"; o insumo é disco branco).
- Cópia anterior: `trabalho_2026-10-13/candidatos_antes_revisao_coleta_163721.xlsx`.
- **Correção no código (`montagem.py`):** o link da coluna P agora pode ser usado pelo candidato com preço do mesmo insumo e do mesmo CNPJ (era recusado como "link já usado"). Cópia anterior: `trabalho_2026-10-13/montagem_antes_fix_link_coluna_p.py`. Teste: `test_link_coluna_p_livre_para_o_mesmo_fornecedor`.
- **1096:** a linha da coluna P da Casa da Limpeza (Rodo Eco 40 cm, rodo de piso) saiu (em `correcoes_entrega.csv` e `produtos_recusados.csv`); o produto fica no 1093 (um produto, um insumo).
- 9 linhas novas conferidas na página e acrescentadas a `evidencias_observacao.csv` (cópia anterior: `trabalho_2026-10-13/evidencias_antes_coleta_163721.csv`). Ficaram como DÚVIDA: 1008 "transparente" = incolor? e "cabo longo" dos rodos 1093 (1,4 m), 1094 (1,20 m) e 1103 (2 m).
- **Decisões de 13/10, 18h29:** 1053 LF aprovado (preço no cartão 34,31); 1008 "transparente" aceito como incolor (CONFIRMADA COM OBSERVAÇÃO); cabo de 1,4 m (1093), 1,20 m (1094) e 2 m (1103) aceitos como cabo longo. Montagem refeita: 349 preços (57 / 162 / 130), 33 na coluna P, 29 insumos completos, 10 sem preço, faltam 251.

## Robô `--completar-merge` (13–14/10/2026) – interrompido
- Rodou de 13/10, 18h32, a 14/10, 04h36 (Ctrl+C), no notebook. Fez 76 dos 91 insumos com vaga; o resultado está em `_historico/coleta_bruta/` (ainda não importado com `importar-robo`).
- Para continuar (em qualquer computador), só com os que faltam:
  `python scripts/raspar_precos_centro_oeste.py --completar-merge --ver-navegador --ids 1098 1100 1101 1102 1103 1104 1105 1106 1107 1109 1110 1112 1113 1114 1117`
  Não rodar sem `--ids`: a lista do que falta vem da Entrega, que só muda depois do `importar-robo`.
- Em 14/10 o `.gitignore` deixou de ignorar os prints de `_historico` (coleta_bruta, merge) para o projeto ir inteiro ao GitHub. Cópia anterior: `trabalho_2026-10-13/gitignore_antes_push_2026-10-14`.

## Revisão do robô (14/10/2026, EPMUDA 428)
- O robô terminou os 15 insumos que faltavam; `importar-robo` levou 83 linhas para `candidatos.xlsx` (Origem "Robô 2026-10-14_105308").
- Revisão dos prints: 34 APROVADO e 49 REPROVADO, todos com o motivo na coluna Motivo. Preço corrigido: 1098 PreveOeste 33,90 (o lido era o "De" riscado).
- Decisões de 14/10: 1028 limpador multiuso automotivo aceito; 1082 Ridgid recusado (1390 W de trabalho < 1.600 W); 1086/1087 tubo de polietileno aceito como mangueira; 1093 EVA aceito como borracha; 1103 recusado (sem cabo, cerdas naturais); 1114 Astro fica com R$ 10,42.
- Evidências das linhas novas acrescentadas a `evidencias_observacao.csv`.
- **Linhas antigas do William (14/10):** as 27 "A REVISAR" foram revistas: 18 APROVADO (preço no cartão em 1108 A Master 52,00 e Multiseg 117,40; 1113 Pica-Pau 16,10; 1063 Plásticos Ipiranga 1.173,10; 1092 Calçados para Trabalhar 55,81) e 9 REPROVADO, com motivo. Decisões: 1109 Marchio recusado (26 cm = cano curto); 1115 Multiseg aceito (frete com 20 unidades no carrinho); 1034 Cauê interfolhado recusado. Só o 1109 tinha vaga; a Entrega não mudou.
