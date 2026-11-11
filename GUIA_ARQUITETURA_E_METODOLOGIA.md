# Guia Completo da Arquitetura, Estrutura de Pastas e Metodologia dos Algoritmos

Este documento detalha toda a arquitetura de software do **Projeto SMP Seridó (Projeto 07)**, explicando o papel de cada pasta e arquivo, o fluxo passo a passo de execução de cada módulo e, em especial, a **metodologia matemática e computacional utilizada para escolher a localização das ERBs nas cidades e das repetidoras nas serras**.

---

## 1. Mapeamento da Estrutura de Pastas e Arquivos

```text
projeto_smp_serido/
├── orchestrator.py                     # Script principal que executa todo o pipeline (Etapas 1 a 8) em sequência
├── mapa_interativo.py                  # Gerador do simulador web interativo (clone do Ubiquiti UISP Design Center)
├── verificar_rotas.py                  # Auditor independente que testa todos os enlaces direto nos GeoTIFFs brutos
├── index.html                          # Simulador interativo standalone na raiz (pronto para o GitHub Pages)
├── requirements.txt                    # Dependências Python (numpy, pandas, rasterio, etc.)
├── README.md                           # Resumo rápido do repositório e instruções de execução
├── GUIA_ARQUITETURA_E_METODOLOGIA.md   # Este documento detalhado de arquitetura e metodologia
│
├── dem/                                # Modelos Digitais de Elevação (Copernicus GLO-30, resolução de 30 metros)
│   ├── Copernicus_DSM_COG_10_S06_00_W036_00_DEM.tif   # Quadrante Lat -6° a -5°, Lon -36° a -35° (Natal / Agreste)
│   ├── Copernicus_DSM_COG_10_S06_00_W037_00_DEM.tif   # Quadrante Lat -6° a -5°, Lon -37° a -36° (Norte do Seridó)
│   ├── Copernicus_DSM_COG_10_S07_00_W036_00_DEM.tif   # Quadrante Lat -7° a -6°, Lon -36° a -35° (Santa Cruz / Trairi / Leste)
│   ├── Copernicus_DSM_COG_10_S07_00_W037_00_DEM.tif   # Quadrante Lat -7° a -6°, Lon -37° a -36° (Currais Novos / Carnaúba / Jardim)
│   └── Copernicus_DSM_COG_10_S07_00_W038_00_DEM.tif   # Quadrante Lat -7° a -6°, Lon -38° a -37° (Caicó / Oeste do Seridó)
│
├── src/                                # Módulos de engenharia de telecomunicações (Pipeline Etapas 1 a 7)
│   ├── config.py                       # Parâmetros normativos fixos do Projeto 07 (1800 MHz, 4x3, potências, ganhos)
│   ├── etapa1_dimensionamento_trafego.py # Cálculo demográfico (IBGE), tráfego em Erlangs e fórmula de Erlang B
│   ├── etapa2_cobertura.py             # Link Budget SMP (Uplink/Downlink), modelo COST 231 Hata e nº final de ERBs
│   ├── etapa3_interferencia.py         # Validação analítica de interferência co-canal (S/I > 12 dB no cluster 4x3)
│   ├── etapa4_geolocacao.py            # Posicionamento geográfico das ERBs urbanas, ajustes de terreno e CCCs
│   ├── etapa5_topografia.py            # Varredura do DEM 30m, busca de cumes, simulação Fresnel e Dijkstra Top 3
│   ├── etapa6_microondas.py            # Seleção ótima de rádios e pratos Ubiquiti (airFiber 11FX e 5XHD)
│   └── etapa7_exportador_uisp.py       # Exportação da topologia para arquivo KML compatível com Google Earth/UISP
│
└── outputs/                            # Artefatos gerados automaticamente pelo pipeline
    ├── demanda_capacidade.json         # Saída da Etapa 1 (assinantes, Erlangs, portadoras RF e ERBs por tráfego)
    ├── dimensionamento_cobertura.json  # Saída da Etapa 2 (raio de célula, área de cobertura e ERBs finais por cidade)
    ├── relatorio_interferencia.json    # Saída da Etapa 3 (relação S/I para vários expoentes de perda de percurso)
    ├── sites_candidatos.json           # Saída da Etapa 4 (coordenadas das ERBs urbanas + CCC Currais Novos + CCC Natal)
    ├── sites_candidatos.geojson        # Saída da Etapa 4 em formato GIS padrão (GeoJSON)
    ├── solucoes_topologia.json         # Saída das Etapas 5 e 6 com os dados completos das Top 3 Soluções de Backhaul
    ├── enlaces_validados.json          # Enlaces da Solução #1 validados no terreno real
    ├── enlaces_com_antenas.json        # Enlaces da Solução #1 enriquecidos com o hardware Ubiquiti e Fade Margin
    ├── todos_sitios.json               # Lista consolidada de todas as ERBs, CCCs e Repetidoras usadas nas 3 soluções
    ├── perfis_enlaces.json             # Vetores de distância e elevação real (passo 15m) de todos os enlaces das 3 soluções
    ├── perfis_enlaces.html             # Relatório visual estático com gráficos SVG de todos os perfis de enlaces
    ├── backhaul_serido_uisp.kml        # Arquivo KML 3D para visualização em ferramentas de geoprocessamento
    └── mapa_interativo.html            # Simulador interativo idêntico ao index.html da raiz
```

---

## 2. Como Foi Definido o Melhor Local em Cada Cidade e nas Serras? (Explicação Metodológica)

Uma dúvida muito comum em bancas e debates é: **"Vocês usaram uma Rede Neural Artificial (RNA) dividindo a cidade em pequenas áreas, posicionando a antena e iterando?"**

A resposta técnica exata é: **Não utilizamos Rede Neural Artificial (RNA), pois em engenharia de RF o posicionamento celular e o roteamento de micro-ondas possuem modelos físicos determinísticos e algoritmos de otimização exata em grafos.** Contudo, **a ideia de dividir a região em uma grade de pequenas áreas, posicionar antenas candidatas, simular a propagação física e iterar alturas/rotas foi exatamente o que fizemos**, porém usando **Tesselação Hexagonal + Busca em Grade Espacial (*Spatial Grid Search*) + Subida de Encosta (*Hill Climbing*) + Algoritmo de Dijkstra Multi-Critério**.

Veja a divisão exata entre o que é feito **dentro das cidades (ERBs)** e o que é feito **no relevo entre as cidades (Repetidoras e Enlaces)**:

### Parte A: Como definimos a quantidade e o local das ERBs dentro de cada cidade (`etapa1`, `etapa2` e `etapa4`)

1. **Quantidade de ERBs por Cidade (Duplo Critério: Tráfego vs. Cobertura):**
   - **Pelo Tráfego (`etapa1_dimensionamento_trafego.py`):** Pegamos a população do Censo IBGE 2022, dividimos por 3 (nossa operadora + 2 concorrentes) e multiplicamos por $0{,}015\text{ Erl/usuário}$. Como cada setor suporta no máximo $8\text{ canais de RF} \times 8\text{ time slots} - 1\text{ slot de controle (BCCH)} = 63\text{ canais de tráfego}$, aplicamos a **Fórmula de Erlang B invertida via busca binária** para 2% de probabilidade de bloqueio ($GoS = 2\%$), obtendo a capacidade máxima de **$52{,}48\text{ Erlangs por setor}$** ($157{,}44\text{ Erlangs por ERB tri-setorizada}$).
   - **Pela Área de Cobertura (`etapa2_cobertura.py`):** Calculamos o Balanço de Potência nos sentidos Uplink (EM de $0{,}8\text{ W}$ $\rightarrow$ ERB com limiar $-105\text{ dBm}$) e Downlink (ERB de $10\text{ W}$ $\rightarrow$ EM). O gargalo é o **Uplink**, que permite uma perda máxima de percurso $PL_{\text{máx}} = 141{,}53\text{ dB}$. Invertendo a equação empírica **COST 231 Hata** em $1800\text{ MHz}$ ($h_{\text{ERB}} = 45\text{ m}$, $h_{\text{EM}} = 1{,}5\text{ m}$), encontramos o raio máximo da célula **$R = 2{,}096\text{ km}$**, o que dá uma área hexagonal por ERB de:
     $$A_{\text{ERB}} = \frac{3\sqrt{3}}{2} \cdot R^2 \approx 11{,}42\text{ km}^2$$
   - Dividindo a área da mancha urbana consolidada de cada município por $11{,}42\text{ km}^2$, obtemos o número de ERBs por cobertura. Adota-se o maior valor entre Tráfego e Cobertura:
     - **Caicó ($22{,}5\text{ km}^2$, $305{,}73\text{ Erl}$):** Exige **3 ERBs** (2 por tráfego, 3 para cobrir toda a mancha urbana).
     - **Currais Novos ($14{,}8\text{ km}^2$, $206{,}55\text{ Erl}$):** Exige **2 ERBs** (tanto por tráfego quanto por área).
     - **Santa Cruz ($12{,}0\text{ km}^2$, $186{,}57\text{ Erl}$):** Exige **2 ERBs** (tanto por tráfego quanto por área).
     - **Jardim do Seridó ($5{,}2\text{ km}^2$, $58{,}27\text{ Erl}$):** Exige **1 ERB**.
     - **Carnaúba dos Dantas ($3{,}8\text{ km}^2$, $39{,}96\text{ Erl}$):** Exige **1 ERB**.

2. **Geometria de Posicionamento Urbano (`etapa4_geolocacao.py`):**
   - **Municípios com 1 ERB (*Jardim do Seridó* e *Carnaúba dos Dantas*):** A ERB única é alocada no centroide urbano ou em elevação adjacente estratégica que ilumine toda a cidade com folga dentro do raio de $2{,}096\text{ km}$ (em Carnaúba dos Dantas, foi posicionada na coordenada elevada `06.52181S, 036.59170W`, a $495\text{ m}$ de altitude, que ilumina a cidade e ainda fecha visada direta com o CCC de Currais Novos).
   - **Municípios com 2 ERBs (*Currais Novos* e *Santa Cruz*):** A malha urbana é dividida em 2 zonas simétricas posicionadas a uma distância de $0{,}75 \cdot R \approx 1{,}57\text{ km}$ do centroide nos ângulos do eixo principal de urbanização ($120^\circ$ e $300^\circ$ em Currais Novos; $0^\circ$ Norte e $180^\circ$ Sul em Santa Cruz). Essa distância de $1{,}57\text{ km}$ entre o centro e cada ERB garante a zona de interseção (sobreposição de *handover*) sem buracos de cobertura.
   - **Município com 3 ERBs (*Caicó*):** A cidade é dividida em 3 zonas em **tesselação triangular equilátera** ($90^\circ$ Leste, $210^\circ$ Sudoeste e $330^\circ$ Noroeste) a uma distância de $0{,}65 \cdot R \approx 1{,}36\text{ km}$ do centroide urbano.
   - **Refinamento de Uso do Solo (*Site Survey* Digital — `AJUSTES_TERRENO_FIRME`):** Coordenadas puramente trigonométricas podem cair sobre rios, açudes ou no meio de rodovias. Por isso, aplicamos um filtro de inspeção geográfica sobre a base hidrográfica/viária (OpenStreetMap + DEM Copernicus), deslocando:
     - `ERB_CAICO_02`: $+260\text{ m}$ para sudeste (saindo de dentro do espelho d'água do Rio Barra Nova para terreno seco);
     - `ERB_CAICO_03`: $+410\text{ m}$ para nordeste no bairro Vila do Príncipe (saindo do leito do Rio Seridó para terreno seco);
     - `ERB_SANTA_CRUZ_02`: $+125\text{ m}$ na encosta do Monte Santa Rita (saindo de cima do asfalto da via de acesso).
     - Como esses micro-ajustes ($125\text{ m}$ a $410\text{ m}$) representam menos de $15\%$ do raio da célula ($2.096\text{ m}$), a mancha de cobertura celular permanece intacta e a torre fica em terreno 100% construtível.

---

### Parte B: Divisão em Grade (*Grid*), Simulação Iterativa de Antenas e Roteamento (`etapa5_topografia.py`)

O processo que você mencionou de **"dividir o mapa em pequenas áreas, colocar a antena, simular e iterar"** acontece de forma intensiva na **Etapa 5 (`src/etapa5_topografia.py`)** para descobrir onde instalar as **Repetidoras de Micro-ondas** e qual a **Altura Exata das Torres**:

1. **Passo 1 — Divisão do Território em Malha de Pequenas Áreas (*Spatial Grid Search*):**
   - O algoritmo cria uma grade (*grid*) retangular cobrindo desde Caicó (`-37.12°W`) até Natal (`-35.19°W`) com passo de $0{,}005^\circ$ ($\approx 550\text{ m} \times 550\text{ m}$), gerando **80.388 pequenas áreas** ($198 \times 406$ células) lidas diretamente dos 5 arquivos GeoTIFF do satélite **Copernicus GLO-30**.
2. **Passo 2 — Detecção de Cristas por Janela Deslizante e Sub-Grade Fina (*Hill Climbing*):**
   - Em cada célula $(i, j)$ da grade, uma janela $13 \times 13$ verifica se aquele ponto é o topo local da serra e calcula sua **proeminência topográfica** (quantos metros ele se destaca acima da mediana do terreno ao redor).
   - O território é dividido em 4 faixas longitudinais (Seridó Oeste, Borborema Central, Agreste e Litoral/Natal) para garantir candidatos em todo o percurso.
   - Para cada pico selecionado, o código cria uma **segunda sub-grade ultrafina de $17 \times 17$ áreas de $\approx 55\text{ m}$** ao redor do pico e faz um *hill climbing* (subida de encosta) até cravar o pixel exato de maior altitude real da montanha, gerando **60 cumes candidatos** (`REP_CUME_01` a `REP_CUME_60`).
3. **Passo 3 — Simulação Iterativa de Antenas e Alturas de Torre (`melhores_alturas`):**
   - Para cada enlace candidato entre dois sítios (com distância $\le 57{,}5\text{ km}$ para garantir *Fade Margin* $> 30\text{ dB}$), o programa extrai o perfil topográfico real de **$15\text{ em } 15\text{ metros}$** (usando o máximo das 4 células vizinhas do DEM 30m para jamais subestimar uma crista rochosa).
   - Em seguida, **simula e itera todas as combinações de alturas de torre** $(h_{\text{TX}}, h_{\text{RX}})$ de $10\text{ m}$ até $100\text{ m}$ (de $5\text{ em } 5\text{ m}$), calculando em cada ponto $x$ do percurso:
     $$\text{Folga}(x) = \text{LOS}(x) - \left[\text{Terreno}(x) + \text{Curvatura}_{k=4/3}(x) + 0{,}6 \cdot F_1(x)\right]$$
   - O algoritmo escolhe o par $(h_{\text{TX}}, h_{\text{RX}})$ de **menor soma de alturas** que mantenha $\min(\text{Folga}) \ge +8{,}0\text{ m}$ acima de $60\%$ da 1ª Zona de Fresnel. Se nem com torres de $100\text{ m}$ houver visada limpa, o enlace é descartado.
4. **Passo 4 — Otimização Global de Caminhos via Algoritmo de Dijkstra Multi-Critério (`caminho_minimo`):**
   - Com todos os enlaces viáveis simulados, montamos um grafo onde cada aresta tem custo parametrizado por:
     $$\text{Custo} = w_{\text{dist}} \cdot d_{\text{km}} + w_{\text{salto}} + w_{\text{altura}} \cdot \left(h_{\text{TX}} + h_{\text{RX}} + 3 \cdot \max(0, h_{\text{máx}} - 45)\right)$$
   - Variando os pesos dessa função objetivo no algoritmo de **Dijkstra**, o código extrai automaticamente as **Top 3 Melhores Soluções**:
     - **Solução #1 (Ótima Principal — Destaque Verde Neon):** Minimiza o número de repetidoras e a distância total ($4$ repetidoras no total: $2$ no Seridó + $2$ no tronco até Natal; $300{,}86\text{ km}$).
     - **Solução #2 (Torres Compactas — Azul Ciano):** Penaliza fortemente a altura das torres ($w_{\text{altura}} = 0{,}60$), trocando torres altas por saltos intermediários com torres mais baixas ($5$ repetidoras; $328{,}91\text{ km}$).
     - **Solução #3 (Rota de Contingência — Âmbar):** Bloqueia todos os cumes usados na Solução #1 (`cumes_bloqueados = cumes_sol1`) e roda o Dijkstra novamente para encontrar uma rota 100% independente ($6$ repetidoras; $365{,}54\text{ km}$).

---

## 3. Passo a Passo do Que Cada Arquivo Faz no Pipeline

### 3.1. [`orchestrator.py`](file:///home/matteo/Downloads/projeto_smp_serido/orchestrator.py)
É o maestro do projeto. Quando você executa `python orchestrator.py`, ele chama sequencialmente as Etapas 1 a 7 dentro da pasta `src/` e, ao final (Etapa 8), executa o `mapa_interativo.py` para regenerar os arquivos HTML (`outputs/mapa_interativo.html` e `index.html`).

---

### 3.2. [`src/config.py`](file:///home/matteo/Downloads/projeto_smp_serido/src/config.py)
Centraliza todas as constantes exigidas pelo enunciado do Projeto 07:
- `FREQ_SMP_MHZ = 1800.0` (Faixa de operación SMP de $1{,}8\text{ GHz}$)
- `BW_CANAL_RF_KHZ = 200.0` e `TIME_SLOTS_POR_RF = 8` (TDMA padrão GSM 1800)
- `POT_TX_ERB_W = 10.0` ($40\text{ dBm}$) e `POT_TX_EM_W = 0.8` ($29{,}03\text{ dBm}$)
- `GANHO_ANTENA_ERB_DBI = 18.0` e `GANHO_ANTENA_EM_DBI = 0.0`
- `LIMIAR_RX_ERB_DBM = -105.0` e `LIMIAR_RX_EM_DBM = -102.0`
- `CLUSTER_K = 4`, `SETORES_POR_ERB = 3` (Configuração $4\times 3$), `MAX_CANAIS_RF_SETOR = 8`
- `TRAFEGO_USUARIO_ERL = 0.015`, `NUM_CONCORRENTES = 2` (Fração de mercado $= 1/3$)
- `EXIGENCIA_SI_MIN_DB = 12.0` e `ALTURA_MAX_TORRE_M = 100.0`

---

### 3.3. [`src/etapa1_dimensionamento_trafego.py`](file:///home/matteo/Downloads/projeto_smp_serido/src/etapa1_dimensionamento_trafego.py)
**O que faz passo a passo:**
1. Define a população oficial (IBGE 2022) dos 5 municípios: Caicó ($61.146$), Currais Novos ($41.311$), Santa Cruz ($37.313$), Jardim do Seridó ($11.655$) e Carnaúba dos Dantas ($7.992$).
2. Implementa a função `erlang_b(canais, trafego)` por recorrência numericamente estável:
   $$B(N, A) = \frac{A \cdot B(N-1, A)}{N + A \cdot B(N-1, A)}$$
3. Implementa `erlang_b_capacidade(canais, gos_alvo=0.02)`, que usa **busca binária** (50 iterações) para encontrar quantos Erlangs um setor aguenta com $2\%$ de bloqueio.
4. Para cada cidade, calcula os assinantes ($1/3$ da população), o tráfego total em Erlangs, a quantidade mínima de ERBs necessárias por tráfego e quantas portadoras de RF de $200\text{ kHz}$ cada setor precisa ativar.
5. Salva o resultado em `demanda_capacidade.json`.

---

### 3.4. [`src/etapa2_cobertura.py`](file:///home/matteo/Downloads/projeto_smp_serido/src/etapa2_cobertura.py)
**O que faz passo a passo:**
1. Converte as potências de Watts para dBm ($10\text{ W} \rightarrow 40\text{ dBm}$; $0{,}8\text{ W} \rightarrow 29{,}03\text{ dBm}$).
2. Calcula o **Link Budget (Balanço de Potência)** nos dois sentidos descontando perdas de cabo ($2\text{ dB}$), corpo do usuário ($1{,}5\text{ dB}$) e margem de sombreamento log-normal ($6\text{ dB}$):
   - $PL_{\text{máx, Uplink}} = 29{,}03 + 0 - 1{,}5 + 18 - 2 - 6 - (-105) = 141{,}53\text{ dB}$ (Gargalo restritivo).
   - $PL_{\text{máx, Downlink}} = 40 + 18 - 2 + 0 - 1{,}5 - 6 - (-102) = 150{,}50\text{ dB}$.
3. Aplica a inversão algébrica do modelo **COST 231 Hata** para $1800\text{ MHz}$ (`calcular_raio_cost231_hata`), obtendo o raio celular $R = 2{,}096\text{ km}$ e a área hexagonal por ERB de $11{,}42\text{ km}^2$.
4. Compara as ERBs exigidas por tráfego (Etapa 1) com as exigidas pela área urbana de cada município, adotando o maior valor (`max(erbs_capacidade, erbs_cobertura)`), totalizando **9 ERBs no Seridó**.
5. Salva o resultado em `outputs/dimensionamento_cobertura.json`.

---

### 3.5. [`src/etapa3_interferencia.py`](file:///home/matteo/Downloads/projeto_smp_serido/src/etapa3_interferencia.py)
**O que faz passo a passo:**
1. Calcula o fator de redução co-canal para o cluster $K = 4$:
   $$Q = \frac{D}{R} = \sqrt{3K} = \sqrt{12} \approx 3{,}4641$$
2. Modela a interferência co-canal de primeira camada considerando antenas setoriais de $120^\circ$ (que reduzem as 6 interferentes omnidirecionais para apenas **2 células interferentes ativas** iluminando a borda do setor).
3. Avalia 3 modelos geométricos (Nominal Equidistante $[D, D]$, Rappaport Padrão $[D, D+0{,}7R]$ e **Pior Caso Extremo $[D-R, D]$**) variando o expoente de perda de percurso $\gamma \in \{3{,}0; 3{,}3; 3{,}5; 3{,}8; 4{,}0\}$.
4. Comprova que, para o expoente típico urbano/suburbano ($\gamma = 3{,}5$), mesmo no **Pior Caso Extremo** a relação $S/I = 12{,}45\text{ dB} > 12{,}0\text{ dB}$ (e $15{,}22\text{ dB}$ no caso Rappaport padrão), aprovando o cluster $4\times 3$.
5. Salva o laudo em `outputs/relatorio_interferencia.json`.

---

### 3.6. [`src/etapa4_geolocacao.py`](file:///home/matteo/Downloads/projeto_smp_serido/src/etapa4_geolocacao.py)
**O que faz passo a passo:**
1. Lê a quantidade final de ERBs de cada cidade gerada na Etapa 2.
2. Distribui espacialmente as ERBs a partir dos centroides municipais usando conversão trigonométrica geodésica (`deslocamento_geografico`, convertendo deslocamentos quilométricos $\Delta x, \Delta y$ em graus de latitude e longitude corrigidos por $\cos(\text{lat})$).
3. Aplica a tabela `AJUSTES_TERRENO_FIRME` (garantindo que nenhuma ERB caia em açudes/rios ou estradas e posicionando `ERB_CARNAUBA_DOS_DANTAS_01` exatamente em `-6.52181, -36.59170`).
4. Define `ERB_CURRAIS_NOVOS_01` como o **CCC Regional do Seridó** (`ERB_CCC`) e adiciona o nó `CCC_NATAL_01` no bairro Tirol, em Natal (`-5.808500, -35.203500`), para cumprir a exigência de interconexão de núcleo em Natal (NTL).
5. Exporta os 10 sítios ativos (9 ERBs do Seridó + 1 CCC Natal) para `outputs/sites_candidatos.json` e `outputs/sites_candidatos.geojson`.

---

### 3.7. [`src/etapa5_topografia.py`](file:///home/matteo/Downloads/projeto_smp_serido/src/etapa5_topografia.py)
**O que faz passo a passo:**
1. Carrega na memória os 5 arquivos GeoTIFF da pasta `dem/` (Copernicus GLO-30) através da biblioteca `rasterio`.
2. Atualiza a altitude exata da base de todas as ERBs e CCCs consultando o DEM real.
3. Executa `encontrar_cumes(sitios)`: varre a grade de $80.388$ pontos, filtra por proeminência nas 4 faixas longitudinais até Natal e faz o refinamento fino para encontrar os **60 melhores picos reais** para possíveis repetidoras.
4. Instancia a classe `Grafo`, que testa enlaces sob demanda (*lazy evaluation* com memoização):
   - Faz primeiro uma amostragem rápida de 24 pontos; se passar com torres de $100\text{ m}$, extrai o perfil completo de **$15\text{ em } 15\text{ m}$** e roda `melhores_alturas()` para encontrar as menores torres que garantam **folga $\ge +8{,}0\text{ m}$ acima de $60\%$ da 1ª Zona de Fresnel + curvatura terrestre ($k=4/3$)**.
5. Roda o Dijkstra Multi-Critério 3 vezes para construir as **Top 3 Soluções de Backhaul** (consolidando os enlaces locais urbanos em $5\text{ GHz}$ e os troncos interurbanos em $11\text{ GHz}$ até Currais Novos e Natal).
6. Executa um `assert` de segurança em cada enlace das 3 soluções e grava `outputs/solucoes_topologia.json`, `outputs/enlaces_validados.json`, `outputs/todos_sitios.json`, `outputs/perfis_enlaces.json` e `outputs/perfis_enlaces.html`.

---

### 3.8. [`src/etapa6_microondas.py`](file:///home/matteo/Downloads/projeto_smp_serido/src/etapa6_microondas.py)
**O que faz passo a passo:**
1. Contém o catálogo oficial de rádios e antenas do Ubiquiti UISP Design Center (`CATALOGO_UBIQUITI`):
   - **Troncos de Longa Distância ($11\text{ GHz}$ — `airFiber 11FX`, $P_{\text{TX}} = 30\text{ dBm}$, sensibilidade $-73\text{ dBm}$):** Pratos `AF-11G35` ($0{,}9\text{ m}$, $35\text{ dBi}$) e `High-Gain Dish 1.2m` ($38{,}5\text{ dBi}$).
   - **Enlaces Locais Urbanos ($5\text{ GHz}$ — `airFiber 5XHD`, $P_{\text{TX}} = 26\text{ dBm}$, sensibilidade $-74\text{ dBm}$):** Pratos `AF-5G23-S45` ($0{,}38\text{ m}$, $23\text{ dBi}$), `AF-5G30-S45` ($0{,}65\text{ m}$, $30\text{ dBi}$) e `AF-5G34-S45` ($1{,}05\text{ m}$, $34\text{ dBi}$).
2. Calcula a perda no espaço livre ($FSPL = 92{,}45 + 20\log_{10}(d_{\text{km}}) + 20\log_{10}(f_{\text{GHz}})$), o nível de sinal recebido ($RSL$) e a margem de desvanecimento (*Fade Margin* $= RSL - \text{Sensibilidade}$).
3. Escolhe para cada enlace das 3 soluções a combinação de **menor custo e menor diâmetro de prato** que atinja **$\text{Fade Margin} \ge 30\text{ dB}$**.
4. Salva os enlaces dimensionados em `outputs/enlaces_com_antenas.json` e atualiza `outputs/solucoes_topologia.json`.

---

### 3.9. [`src/etapa7_exportador_uisp.py`](file:///home/matteo/Downloads/projeto_smp_serido/src/etapa7_exportador_uisp.py)
**O que faz passo a passo:**
1. Lê os sítios e enlaces validados da Solução #1.
2. Constrói uma árvore XML no padrão **OGC KML 2.2** com duas pastas (*Sítios e Torres* e *Enlaces PTP de Micro-ondas*), configurando as altitudes em modo `relativeToGround` (altura real da torre acima do solo).
3. Exporta o arquivo `outputs/backhaul_serido_uisp.kml` para abertura no Google Earth Pro ou QGIS.

---

### 3.10. [`mapa_interativo.py`](file:///home/matteo/Downloads/projeto_smp_serido/mapa_interativo.py)
**O que faz passo a passo:**
1. Lê todos os arquivos JSON gerados pelas Etapas 1 a 6 (`solucoes_topologia.json`, `todos_sitios.json`, `perfis_enlaces.json`, `relatorio_interferencia.json`, `demanda_capacidade.json`, `dimensionamento_cobertura.json`).
2. Embute diretamente no código JavaScript (`PERFIS_REAIS`, `SOLUCOES`, `SITES`) todos os vetores altimétricos reais do Copernicus 30m — garantindo que o gráfico de perfil de elevação e zona de Fresnel funcione **100% offline e no GitHub Pages**, sem depender de APIs externas que bloqueiam por limite de requisições (erro 429).
3. Renderiza a interface visual inspirada no **Ubiquiti UISP Design Center** com:
   - Card flutuante dos **Top 3 Melhores Caminhos**, destacando a **Solução #1 (Verde Neon ★)**, notas explicativas do porquê de cada escolha e botões para ativar/desativar cada solução ou todas as 3 de uma vez;
   - Gaveta inferior interativa que desenha em `<canvas>` o corte topográfico real, a curvatura da Terra ($k=4/3$), o elipsoide de $60\%$ da 1ª Zona de Fresnel e o cálculo dinâmico de *Link Budget* e *Throughput* quando o usuário troca pratos, largura de canal ($20/40/80\text{ MHz}$) ou altura de torres;
   - Painel de especificações completas do **Projeto 07 (SMP 1800 MHz + Erlang B + COST 231 Hata + S/I Cluster 4x3)**.
4. Grava o resultado simultaneamente em `outputs/mapa_interativo.html` e no `index.html` da raiz do projeto.

---

### 3.11. [`verificar_rotas.py`](file:///home/matteo/Downloads/projeto_smp_serido/verificar_rotas.py)
**O que faz passo a passo:**
- É um script de **auditoria independente** de 21 linhas: ele ignora qualquer cache intermediário, abre diretamente os 5 arquivos `.tif` da pasta `dem/`, faz um mosaico (`rasterio.merge`) e testa ponto a ponto (a cada $15\text{ m}$) todos os 30 enlaces únicos das 3 soluções.
- Imprime no terminal a distância e a folga mínima real acima de $0{,}6 \cdot F_1 + \text{curvatura}$, confirmando `OK` em 100% dos enlaces.
