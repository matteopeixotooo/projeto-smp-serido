# Projeto SMP Seridó — Dimensionamento Celular, Backhaul PTP & Visada 3D (UISP)

Simulador interativo (inspirado no **Ubiquiti ISP Design Center**) e pipeline completo de engenharia para cobertura celular **SMP (1.800 MHz, Cluster 4×3)** e rede de transporte **backhaul micro-ondas PTP (Ubiquiti airFiber 11FX / 5XHD)** na região do Seridó (RN), interligando os 5 municípios ao **CCC Regional de Currais Novos** e ao **CCC Principal em Natal (Candelária/BR-101)** sobre relevo real **Copernicus DEM 30 m**.

📄 **Arquitetura dos Módulos Python:** [`GUIA_ARQUITETURA_E_METODOLOGIA.md`](./GUIA_ARQUITETURA_E_METODOLOGIA.md)

---

## 🌐 Simulador Web & Recursos (`index.html` / GitHub Pages)

O arquivo [`index.html`](./index.html) (espelhado em [`outputs/mapa_interativo.html`](./outputs/mapa_interativo.html)) roda direto no navegador com os perfis e corredores 3D do Copernicus DEM 30 m já embutidos, dividido em **3 interfaces**:

1. **🗺️ Simulador & Mapa (Top 3 Rotas + Gaveta UISP):**
   - **Top 3 Caminhos 100% Desobstruídos (torres únicas e fixas de 20 m a 50 m, sem saltos redundantes `< 12 km` entre repetidoras):**
     - **★ Solução #1 — Ótima Principal (Verde Neon):** **3 repetidoras** (`REP_CUME_69` no cume norte de **666 m** concentrando Carnaúba + Jardim do Seridó + Caicó, `REP_CUME_28` a 681 m e `REP_CUME_46` Serra da Tapuia a 381 m), **12 enlaces**, **276,13 km** totais, torres fixas de **20 m a 45 m**, folga mínima **+16,64 m** acima de 0,6·F1.
     - **Solução #2 — Saltos ≤ 56 km (Azul Ciano):** **4 repetidoras**, **13 enlaces**, **276,77 km**, torres de **20 m a 45 m**, folga mín **+16,64 m** (divide o tronco até Natal em 11 GHz licenciado).
     - **Solução #3 — Contingência Independente (Âmbar):** **5 repetidoras**, **14 enlaces**, **295,92 km**, torres de **20 m a 50 m**, folga mín **+16,05 m** (100% disjunta dos cumes da #1).
   - **📡 Cobertura Celular SMP (`R = 1,808 km`):** botão no topo para ligar/desligar o raio celular de **1,808 km** (`8,5 km²/ERB`, 3 setores de 120°) nas **9 ERBs urbanas** (Caicó 3, Currais Novos 2, Santa Cruz 2, Jardim do Seridó 1 e Carnaúba dos Dantas 1 na encosta urbana do Monte do Galo) e também em sítios customizados marcados como **Torre ERB** (alternável entre ERB e Repetidora PTP).
   - **🗺️ Camadas de Mapa:** seletor no canto superior direito entre **Satélite Limpo (Esri)**, **Satélite Híbrido (Google — estradas e cidades)** e **Relevo / Topo (OpenTopoMap)**.
   - **Corte Altimétrico Lateral (Gaveta Inferior):** perfil do terreno real (Copernicus 30 m nos enlaces fixos e **AWS Terrarium DEM `z=12`** sob demanda nos enlaces customizados), abaulamento terrestre (`k = 4/3`), elipse da **1ª Zona de Fresnel (60% e 100%)**, estimativa de **vegetação/clutter** via satélite (`🌿 Veg: Auto`), difração **ITU-R P.526** (Deygout + atenuação de maciço rochoso espesso, exibindo **`--- (Sem Sinal)` / `0 Mbps`** quando 100% bloqueado), cálculo dinâmico ao trocar altura de torre ou banda (`5 GHz ↔ 11 GHz`), atenuação por chuva (**ITU-R P.838-3 @ 50 mm/h**) e botão **`⇄ Inverter (TX ↔ RX)`** para espelhar o perfil lateral.

2. **🧮 Cálculos, Chuva & Orçamento (Apresentação):**
   - Memorial didático completo de **Erlang B**, **COST 231 Hata** (`R = 1,808 km`), **Interferência Co-Canal 4×3** (`S/I = 12,56 dB > 12 dB`), tabela de altura fixa única por torre, quadro de chuva ITU-R, diagrama lógico SVG e orçamento separado entre **Ativos de Telecom** e **Torres + Infraestrutura Civil** com links verificados por item:
     - **Solução #1 CAPEX:** Ativos **R$ 187.868,42** + Torres **R$ 284.287,50** + Infra **R$ 55.557,09** = **R$ 527.713,01**
     - **Solução #2 CAPEX:** **R$ 575.117,88**
     - **Solução #3 CAPEX:** **R$ 687.953,79**

3. **🏔️ Visada 3D (De Lado):**
   - Visualizador **WebGL (Three.js)** com fallback multi-CDN, malha 3D real **Copernicus 30 m (`65 × 33` por enlace fixo)** e **AWS Terrarium `z=12`** para enlaces customizados, textura **Esri Satellite** (ou relevo hipsométrico), camada opcional de **🌿 Vegetação 3D**, torres em 3D, curvatura `k=4/3` e elipsoide **Fresnel 3D**, com câmeras rápidas **`📐 De Lado`**, **`🚁 Aérea 3/4`** e **`🗼 Torre TX→RX`** + exagero vertical ajustável.

---

## 🚀 Como Executar o Pipeline Localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -u orchestrator.py
python verificar_rotas.py
```

* `orchestrator.py` executa as Etapas 1 a 7 e gera o simulador web (`index.html` e `outputs/mapa_interativo.html`) além do KML (`outputs/backhaul_serido_uisp.kml`). Para regenerar apenas o simulador HTML após ajustes de interface, basta rodar `python mapa_interativo.py`.
* `verificar_rotas.py` audita os **24 enlaces únicos** das 3 soluções diretamente nos GeoTIFFs da pasta `dem/`.
