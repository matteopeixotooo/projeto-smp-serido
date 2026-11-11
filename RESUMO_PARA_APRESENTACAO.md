# Roteiro e Resumo para Apresentação — Projeto 07 (SMP Seridó + Backhaul Natal)
---

## 1. Tecnologias e Ferramentas que Usamos (e Para Que Serve Cada Uma)

### 📡 A. Tecnologias de Telecomunicações (Rede Celular e Rádio)
1. **SMP / GSM em 1.800 MHz com TDMA (Acesso Múltiplo por Divisão de Tempo):**
   - **Para que serve:** É a tecnologia que conecta a **ERB (torre celular)** ao **celular do usuário (EM)**.
   - **Como funciona:** Cada canal de rádio tem largura de **200 kHz** e é dividido no tempo em **8 fatias (time slots)**. Ou seja, 1 frequência atende até 8 chamadas ao mesmo tempo (na prática, tiramos 1 slot da célula para controle/sinalização e ficam **63 canais de voz** por setor).
2. **Cluster 4x3 (Reuso de Frequência com Setorização $120^\circ$):**
   - **Para que serve:** Para que as torres não interfiram umas nas outras usando a mesma frequência.
   - **Como funciona:** Agrupamos as ERBs de **4 em 4 ($K=4$)** e dividimos cada torre em **3 setores de $120^\circ$** (como uma pizza cortada em 3 fatias: Norte, Sudeste e Sudoeste). Assim, dividimos todos os canais da operadora entre $4 \times 3 = 12$ setores diferentes antes de repetir a mesma frequência mais adiante.
3. **Micro-ondas Ponto a Ponto (Ubiquiti airFiber 11FX e 5XHD):**
   - **Para que serve:** É o **Backhaul** (o "cabo invisível" de alta velocidade pelo ar) que leva as chamadas de todas as ERBs do interior até a **CCC de Currais Novos** e de lá até a **CCC Principal em Natal (NTL)**.
   - **Por que usamos duas frequências no Backhaul?**
     - **5 GHz (`airFiber 5XHD`):** Usado **dentro da mesma cidade** (saltos curtos de 2 a 3 km, ex.: ERB Caicó 02 $\rightarrow$ ERB Caicó 01). Antenas pequenas de 38 cm.
     - **11 GHz Licenciado (`airFiber 11FX`):** Usado **entre as cidades e nas serras** (saltos longos de 15 a 55 km). É uma faixa licenciada pela Anatel, livre de interferência de Wi-Fi urbano, usando pratos parabólicos de 0,9 m ($35\text{ dBi}$) e 1,2 m ($38{,}5\text{ dBi}$).

---

### 💻 B. Modelos Matemáticos e Tecnologias de Software
1. **Fórmula de Erlang B (`etapa1`):** Modelo clássico de teoria de filas para descobrir **quantas pessoas conseguem ligar ao mesmo tempo** com no máximo 2% de chance de dar "rede ocupada" ($GoS = 2\%$).
2. **Modelo COST 231 Hata (`etapa2`):** Fórmula empírica de propagação para 1.800 MHz que calcula o **quão longe o sinal do celular chega** ($R = 2{,}096\text{ km}$) antes de ficar fraco demais para a torre ouvir ($-105\text{ dBm}$).
3. **Imagens de Satélite Copernicus DEM 30m + Biblioteca `rasterio` (`etapa5`):**
   - Baixamos 5 arquivos `.tif` oficiais da Agência Espacial Europeia (pasta `dem/`) que têm a **altura real de cada quadrado de $30\times 30$ metros do solo do RN**. Isso garante que nenhum enlace atravesse uma serra.
4. **Algoritmo de Busca em Grade (*Grid Search*) + Dijkstra (`etapa5`):**
   - O Python quadricula o mapa, acha sozinho os topos das serras mais altas e usa o **Algoritmo de Dijkstra** (o mesmo que o Waze/Google Maps usa para achar o caminho mais rápido) para encontrar as **3 melhores rotas** sem obstrução.
5. **Leaflet.js + HTML5 Canvas (`mapa_interativo.py` / `index.html`):**
   - Geramos um site interativo inspirado no **Ubiquiti UISP Design Center** que roda direto no navegador (GitHub Pages) mostrando o mapa, as 3 rotas e o desenho da serra com a Zona de Fresnel embaixo.

---

## 2. Como Cada Dado do Enunciado Foi Usado (Passo a Passo das Contas)

Se alguém perguntar *"De onde saiu esse número?"*, aqui está a cola exata de como cada dado do professor entrou na conta:

### Passo 1: Quantos clientes e quanto tráfego nós temos? (Etapa 1)
* **Dados do Enunciado usados aqui:**
  - *Cidades:* Caicó, Currais Novos, Jardim do Seridó, Carnaúba dos Dantas e Santa Cruz.
  - *Concorrentes:* **2 empresas concorrendo com a sua** $\rightarrow$ São 3 empresas no total, então nossa operadora fica com **$1/3$ ($33{,}3\%$) da população** do IBGE de cada cidade.
  - *Tráfego médio por usuário:* **$0{,}015\text{ Erlang}$**.
  - *Configuração do Canal:* **8 time slots por canal de RF (200 kHz)** e **máximo de 8 canais de RF por setor**.
* **A Conta:**
  - Cada setor tem no máximo $8\text{ canais RF} \times 8\text{ slots} = 64\text{ slots}$. Tirando 1 slot de controle, sobram **63 canais de voz por setor**.
  - Jogando 63 canais na tabela de **Erlang B (bloqueio de 2%)**, descobrimos que **1 setor aguenta até $52{,}48\text{ Erlangs}$**.
  - Como cada torre (ERB) tem **3 setores**, **1 ERB inteira aguenta $3 \times 52{,}48 = 157{,}44\text{ Erlangs}$**.
  - Exemplo de **Caicó** (População: $61.146$):
    - Nossos clientes: $61.146 / 3 = 20.382\text{ clientes}$.
    - Tráfego de Caicó: $20.382 \times 0{,}015 = 305{,}73\text{ Erlangs}$.
    - Quantas ERBs Caicó precisa só pelo tráfego? $305{,}73 / 157{,}44 = 1{,}94 \rightarrow$ **2 ERBs por tráfego**.

---

### Passo 2: Qual é o Raio de Cobertura da ERB e quantas ERBs cabem na cidade? (Etapa 2)
* **Dados do Enunciado usados aqui:**
  - *Frequência:* **1.800 MHz**
  - *Potência Tx no Celular (EM):* **$0{,}8\text{ W}$** ($= 29{,}03\text{ dBm}$)
  - *Ganho da Antena no Celular (EM):* **$0\text{ dBi}$**
  - *Potência Tx na Torre (ERB):* **$10\text{ W}$** ($= 40\text{ dBm}$)
  - *Ganho da Antena na Torre (ERB):* **$18\text{ dBi}$**
  - *Limiar de Recepção na ERB:* **$-105\text{ dBm}$**
* **A Conta:**
  - Quem é mais fraco: a torre gritando com $10\text{ W}$ para o celular, ou o celular gritando com apenas $0{,}8\text{ W}$ para a torre? **O celular (Uplink)!** Então é o celular que limita o tamanho da célula.
  - Calculamos a perda máxima que o sinal do celular pode sofrer no caminho até chegar em $-105\text{ dBm}$ na torre (descontando $2\text{ dB}$ de cabo, $1{,}5\text{ dB}$ do corpo humano e $6\text{ dB}$ de margem de sombra):
    $$PL_{\text{máx}} = 29{,}03\text{ dBm} + 0\text{ dBi} + 18\text{ dBi} - 2 - 1{,}5 - 6 - (-105\text{ dBm}) = \mathbf{141{,}53\text{ dB}}$$
  - Jogamos esses $141{,}53\text{ dB}$ e a frequência de $1.800\text{ MHz}$ na fórmula **COST 231 Hata** (com torre padrão de $45\text{ m}$). O resultado é o **Raio de Cobertura**:
    $$\mathbf{R = 2{,}096\text{ km}}$$
  - Um hexágono de raio $2{,}096\text{ km}$ cobre uma área de **$11{,}42\text{ km}^2$**.
  - Agora olhamos o tamanho da área urbana de cada cidade e comparamos com o número de ERBs do tráfego (sempre ganha o maior número):
    - **Caicó ($22{,}5\text{ km}^2$):** $22{,}5 / 11{,}42 = 1{,}97 \rightarrow$ **3 ERBs** (para cobrir todos os bairros com folga).
    - **Currais Novos ($14{,}8\text{ km}^2$):** **2 ERBs** (1 delas já é o **CCC Regional**).
    - **Santa Cruz ($12{,}0\text{ km}^2$):** **2 ERBs**.
    - **Jardim do Seridó ($5{,}2\text{ km}^2$):** **1 ERB**.
    - **Carnaúba dos Dantas ($3{,}8\text{ km}^2$):** **1 ERB** (posicionada em `06.52181S, 036.59170W`).
    - **Total no Seridó = 9 ERBs.**

---

### Passo 3: A Interferência Co-Canal passa no teste? (Etapa 3)
* **Dados do Enunciado usados aqui:**
  - *Configuração:* **4x3 (Cluster com 4 ERBs e 3 células setorizadas cada)**
  - *Exigência:* **$S/I > 12\text{ dB}$ no pior caso**
* **A Conta:**
  - No cluster de $K = 4$, o fator de distância de reuso é $Q = \sqrt{3 \times K} = \sqrt{12} = \mathbf{3{,}464}$. Isso significa que a próxima torre que usa a mesma frequência está a uma distância $D = 3{,}464 \times R$.
  - Como usamos antenas de $120^\circ$ (3 setores), cada setor só "enxerga" **2 torres interferentes** na primeira camada (em vez de 6 se fosse antena omnidirecional).
  - No **Pior Caso Extremo** (usuário na borda da célula, a distância $R$ da própria torre, a $D-R$ da 1ª interferente e a $D$ da 2ª interferente), com atenuação típica urbana ($\gamma = 3{,}5$):
    $$S/I = 10 \cdot \log_{10}\left( \frac{1}{(2{,}464)^{-3{,}5} + (3{,}464)^{-3{,}5}} \right) = \mathbf{12{,}45\text{ dB}}$$
  - Como **$12{,}45\text{ dB} > 12\text{ dB}$**, o sistema está **APROVADO** mesmo no pior cenário possível (e dá **$15{,}22\text{ dB}$** no modelo padrão de Rappaport!).

---

## 3. Como o Programa Escolheu os Lugares das Antenas? (Explicação Fácil)

Se perguntarem: *"Como vocês escolheram onde colocar cada torre na cidade e nas serras? Foi Inteligência Artificial / Rede Neural?"*

Você pode responder exatamente assim:

> *"Não precisamos usar Rede Neural porque em Telecom nós temos a equação física exata da onda e o mapa real de altitude da região. Em vez de uma 'caixa-preta' de IA, nós criamos um algoritmo em 3 passos:"*

1. **Nas Cidades (Divisão Geométrica + Filtro de Terreno Seco):**
   - Onde só precisava de **1 ERB** (*Jardim do Seridó* e *Carnaúba dos Dantas*), colocamos no ponto central/alto da cidade.
   - Onde precisava de **2 ERBs** (*Currais Novos* e *Santa Cruz*), abrimos as duas torres a $1{,}57\text{ km}$ para cada lado do centro.
   - Onde precisava de **3 ERBs** (*Caicó*), formamos um **triângulo equilátero** ao redor do centro (Leste, Sudoeste e Noroeste).
   - Por fim, conferimos no mapa real se alguma coordenada tinha caído dentro de rio/açude ou em cima de rodovia, e arredamos de 125 m a 410 m para terreno firme e seco.

2. **Nas Serras (Dividindo o Mapa em 80 mil Quadradinhos para achar os Picos):**
   - Como o Seridó é cheio de serras de 600 m a 700 m (Serra de Santana / Borborema), uma cidade não enxerga a outra direto.
   - Nosso código dividiu o mapa de Caicó até Natal em **80.388 pequenas áreas** de $550\times 550$ metros e leu a altura de cada uma no satélite de 30 metros.
   - Onde ele achava um topo de serra, ele dava um "zoom" dividindo o topo do morro em quadradinhos menores ainda (**55 metros**) e ia subindo até achar o ponto mais alto exato da pedra. Assim ele achou os **60 melhores picos do RN**.

3. **Simulando as Torres (até 100 m) e Rodando o Dijkstra (Top 3 Caminhos):**
   - Respeitando a regra do professor de **torres de no máximo 100 metros**, o computador testou ligar as cidades aos picos das serras testando alturas de torre de **5 em 5 metros** (10m, 15m, 20m... até 100m), checando de 15 em 15 metros se o feixe de micro-ondas passava livre da serra, da **curvatura da Terra** e de **60% da Zona de Fresnel**.
   - Depois, rodou o algoritmo de **Dijkstra** para gerar as **3 Melhores Soluções** no mapa:
     - **★ Solução #1 (A Campeã - Verde):** Usa o **menor número possível de repetidoras** (apenas 2 no Seridó + 2 no caminho até Natal = **4 repetidoras**) e a menor distância total (**300,86 km**). É a mais barata de construir e manter.
     - **Solução #2 (Torres Mais Baixas - Azul):** Usa 1 repetidora a mais (5 repetidoras) para diminuir a altura das torres onde for difícil levantar torre alta.
     - **Solução #3 (Rota Reserva - Amarela):** Proíbe usar qualquer morro da Solução #1, criando um caminho 100% diferente caso o dono do terreno de alguma serra da Solução #1 não deixe instalar a torre lá.
