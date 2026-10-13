# FGV IBRE – Pesquisa de fornecedores e preços

Repositório de apoio à coleta de preços de insumos (projeto FNDE). Este
primeiro módulo localiza **fornecedores atacadistas** por região. A etapa
seguinte, a coleta dos preços com prints, usa as planilhas geradas aqui.

## Estrutura

```
FGV/
├── FNDE/
│   └── Centro Oeste/
│       ├── Pesquisa_SEAD_GO_Limpeza_Predial.csv   # insumos (entrada)
│       ├── FNDE_output.csv                         # modelo da coleta de preços
│       ├── Fornecedores/                           # planilhas FNDE_<Grupo>.xlsx (saída)
│       └── Entrega/                                # resultado da raspagem de preços
│           ├── FNDE_output.xlsx
│           ├── resumo_coleta.csv
│           └── prints/<Grupo>/<ID FGV>_GO_<n>.png
├── data/
│   ├── raw/        # dumps da Receita Federal (não versionado, vários GB)
│   ├── interim/    # candidatos filtrados/verificados (não versionado)
│   └── curated/    # fornecedores conferidos manualmente (versionado)
├── logs/           # um .log por execução (não versionado)
├── scripts/
│   ├── buscar_fornecedores_centro_oeste.py         # etapa 1: fornecedores
│   └── raspar_precos_centro_oeste.py               # etapa 2: preços e fretes
├── src/fgv_precos/
│   ├── config.py                # TODAS as regras de negócio e caminhos
│   ├── precos.py                # leitura de valores "R$ 1.234,56" (sem parcelas/PIX)
│   ├── logging_config.py
│   └── fornecedores/
│       ├── cnae.py              # regras de CNAE/CNPJ (sem rede)
│       ├── cnpj_api.py          # BrasilAPI / CNPJ.ws / ReceitaWS
│       ├── receita_dump.py      # Dados Abertos do CNPJ (GO/DF + CNAE 46)
│       ├── site_checker.py      # marketplace, preço visível, itens do grupo
│       ├── insumos.py           # leitura da planilha de insumos
│       └── exportador.py        # geração dos .xlsx
│   └── raspagem/
│       ├── config_raspagem.py   # CEP de GO, 5 preços, pastas
│       ├── descricao.py         # leitura "inteligente" da Descrição
│       ├── coletor.py           # percorre insumos x fornecedores
│       ├── saida.py             # grava no layout do FNDE_output.csv
│       ├── plataformas/         # Loja Integrada, VTEX, WooCommerce, Shopify...
│       └── lojas/               # um arquivo por fornecedor (nome da empresa)
├── tests/
├── pyproject.toml               # pacote, pytest e ruff
├── requirements.txt             # instala o pacote (-e .) e as dependências
└── .gitignore
```

## Regras aplicadas (ver `src/fgv_precos/config.py`)

1. **CNAE atacadista**: qualquer subclasse da Divisão 46 (CNAE 2.0), principal
   **ou** secundária, conferida no cadastro do CNPJ.
2. **Sem marketplace**: Mercado Livre, Amazon, Shopee etc. não contam. Só vale
   o domínio próprio do fornecedor.
3. **Site com preço visível**: catálogo com preço em R$ sem login. Quem mostra
   "sob consulta"/orçamento vai para a aba *Sem preço (referência)*.
4. **Região**: prioridade para GO e DF, com meta de **5 fornecedores por UF**
   em cada grupo. Se a UF não atingir a meta, outros Estados completam, com a
   UF atendida registrada em *Observações* (coluna interna `Atende UF`).
5. **PASSAGEM** e **SAÚDE OCUPACIONAL** são serviços, sem CNAE atacadista que os
   cubra. As planilhas são geradas vazias, com observação.
6. **Nenhum dado inventado.** Campo não encontrado fica em branco. Fornecedor
   sem CNAE confirmado vai para *Pendentes de validação* e não é usado.

## Instalação (Windows)

```bat
cd "%USERPROFILE%\OneDrive\Área de Trabalho\FGV"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest
ruff check src scripts tests
```

O `requirements.txt` instala também o próprio pacote (`pip install -e .`), por
isso os scripts encontram `fgv_precos` sem ajustes de caminho. Quem já tinha
o `.venv` criado antes de 12/10/2026 precisa rodar `pip install -r
requirements.txt` uma vez de novo.

## Uso

```bat
:: 1) Candidatos atacadistas ativos em GO/DF a partir dos Dados Abertos do CNPJ
::    (baixa cerca de 6 GB; ou use --dump-dir com os .zip já baixados)
python scripts\buscar_fornecedores_centro_oeste.py descobrir --competencia 2026-09

:: 2) Testa os sites (domínio do e-mail corporativo): preço visível? itens de qual grupo?
python scripts\buscar_fornecedores_centro_oeste.py verificar --limite 300

:: 3) Depois da conferência humana, os aprovados entram em
::    data\curated\fornecedores_centro_oeste.csv. Revalide o CNPJ/CNAE:
python scripts\buscar_fornecedores_centro_oeste.py validar

:: 4) Gera as planilhas em FNDE\Centro Oeste\Fornecedores
python scripts\buscar_fornecedores_centro_oeste.py exportar
```

> O endereço dos Dados Abertos do CNPJ muda de tempos em tempos. Se o
> `descobrir` não conseguir baixar, faça o download manual dos arquivos
> `Estabelecimentos0..9.zip`, `Empresas0..9.zip` e `Municipios.zip` e rode
> com `--dump-dir`.

### Limitações conhecidas

* A etapa `verificar` lê o HTML bruto. Lojas que carregam o preço via
  JavaScript aparecem como `SEM_PRECO_DETECTADO` e precisam de conferência
  manual. `PRECO_DETECTADO` também é só um indício (o "R$" pode ser, por
  exemplo, o valor mínimo para frete grátis). Nada é aceito automaticamente.
* As APIs públicas de CNPJ limitam cerca de 3 consultas por minuto. O cliente
  espera entre as chamadas, então validar muitos CNPJs leva tempo.

## Arquivo curado (`data/curated/fornecedores_centro_oeste.csv`)

Separador `;`, UTF-8. Colunas: `Grupo de Insumo`, `Situação`
(`VALIDO` | `REFERENCIA_SEM_PRECO` | `PENDENTE_VALIDACAO`), `Atende UF` e as
colunas de saída (`Estado`, `Cidade`, `Nome da Empresa`, `CNPJ`,
`CNAE atacadista`, `Site Oficial`, `Link (clicável)`, `Telefone`,
`E-mail Comercial`, `Endereço`, `Observações`, `Fonte`).

## Raspagem de preços e fretes (etapa 2)

```bat
pip install -r requirements.txt
python -m playwright install chromium

:: teste com 3 insumos (um de cada grupo de produto)
python scripts\raspar_precos_centro_oeste.py --ids 1000 1056 1104

:: para acompanhar o navegador trabalhando
python scripts\raspar_precos_centro_oeste.py --ids 1000 --ver-navegador
```

Regras (revisadas em 09/10/2026):
- Só GO (CEP 74933-130). Cada insumo precisa de 5 preços com frete.
- O print mostra nome completo do produto, preço e frete para GO. É a página
  do produto ou, no WooCommerce, o carrinho.
- Preço = o preço visível na página. Cupom, PIX e outros descontos não entram,
  então VALOR DESCONTO e OBS Desconto ficam vazios.
- Frete grátis: VALOR FRETE vazio e a observação em OBS FRETE.
- Retirada na loja não é frete (nem quando aparece como "R$ 0,00").
- Frete mais de 3x maior que o preço gera um aviso "CONFERIR" no log.
- Site sem calculadora de CEP: o frete só vale se a própria página do produto
  (a do print) mostrar frete grátis sem condição, por exemplo "FRETE GRÁTIS
  PARA TODO BRASIL". Aviso com condição ("acima de R$ X") não vale.
- Login/cadastro (preço, frete ou carrinho que só aparecem logado): a linha
  entra com o link na coluna P ("Link aproveitável"), para coleta manual, com
  o motivo em OBS FRETE ("Preço só com login" ou "Frete só com login"), e não
  conta entre os 5. Outro frete que não pode ser calculado descarta o
  fornecedor.
- Produto encontrado, mas sem preço visível: a linha entra com o link na
  coluna P ("Link aproveitável"), para coleta manual, e não conta entre os 5.
  O motivo vai em OBS FRETE: "Preço só com login", "Preço sob
  consulta/orçamento" ou "Preço não exibido (motivo não identificado)".
  Só o produto claramente esgotado é ignorado.
- FONTE (coluna H) = link clicável da página de onde o print saiu.
- Rodar de novo sobrescreve o resultado dos insumos coletados (linhas da
  planilha, do resumo e prints desses IDs). Os demais insumos já presentes em
  `Entrega` são mantidos.
- O resultado é gravado ao fim de cada insumo. Se a execução parar no meio,
  o que já foi coletado fica salvo, e os prints antigos de um insumo só são
  trocados quando a coleta dele termina.
- Se a planilha ou o resumo anteriores não puderem ser lidos, eles são
  renomeados para `*_ilegivel_<data>` (nunca sobrescritos) e o log avisa.
- No fim, o log traz um "RESUMO DA EXECUÇÃO" (insumos completos, incompletos,
  linhas para coleta manual e insumos com erro).

Leitura da Descrição, da esquerda para a direita: o texto depois do primeiro
" - " ou ";" é observação. O travessão "–" separa o nome do atributo
(ex.: "5 L"). Uma "/" gera nomes alternativos de busca. A medida do atributo
ou da coluna Embalagem precisa aparecer no nome do produto. Além da palavra
principal (entre as 3 primeiras do nome do produto), pelo menos mais uma
palavra do nome do insumo precisa aparecer: "Carro Guia Maçarico" não serve
para "Carro Funcional". Plural e gênero não importam (sanitária/sanitário) e
palavras genéricas ("limpeza", "uniforme", "manual", "profissional", "piso")
não contam. O mínimo fica em `PALAVRAS_EXTRAS_MINIMAS`
(`raspagem/config_raspagem.py`); 0 volta à regra antiga.

Como o código lida com os sites:
- **Navegador:** usa o Edge, ou o Chrome, instalado no computador. Alguns sites
  recusam o navegador de teste do Playwright.
- **Busca:** lê o formulário de busca da página inicial de cada site (Tray,
  Magento etc.). Se a busca pelo nome completo não trouxer nada, tenta só a
  palavra principal ("Balde", "Camiseta").
- **Variações:** em produtos com tamanho, cor etc. (Loja Integrada), escolhe a
  opção cuja medida bate com a do insumo ou a primeira disponível, e anota a
  escolha no nome do produto.
- **Fornecedor com dois sites** ("a.com.br / b.com.br"): tenta cada um.
- **WooCommerce:** o frete é calculado num carrinho novo (cookies limpos) e
  só vale se o carrinho tiver apenas o produto, com subtotal igual ao preço.

### Correção da entrega de 10/10/2026 (sem coletar de novo)

`scripts\corrigir_entrega_2026_10_12.py` registra as correções feitas na
pasta `Entrega` a partir dos prints (ver o cabeçalho do script). Ele guarda
uma cópia em `Entrega\_backup_2026-10-12`, nunca apaga prints (os que saem
vão para `prints\<Grupo>\_removidos`) e gera
`Entrega\revisao_aderencia_2026-10-12.xlsx`. Depois de preencher a coluna
"Manter? (S/N)" dessa lista:

```bat
python scripts\corrigir_entrega_2026_10_12.py aplicar-revisao
```

Para refazer só um fornecedor em alguns insumos e levar o resultado para a
entrega (ex.: Singular, cujo frete saiu para o CEP errado):

```bat
python scripts\raspar_precos_centro_oeste.py --ids 1105 1108 1109 1110 1112 1115 --fornecedor singular
python scripts\corrigir_entrega_2026_10_12.py incorporar --ids 1105 1108 1109 1110 1112 1115 --fornecedor singular
```

Fornecedores com módulo próprio ficam em `src/fgv_precos/raspagem/lojas/`, um
arquivo por empresa. Os demais têm a plataforma detectada automaticamente.
Quando um site mudar, ajuste só o arquivo daquela empresa.
