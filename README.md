# Projeto SMP Seridó — Dimensionamento Celular, Backhaul PTP & Visada 3D (UISP)

Simulador interativo (inspirado no **Ubiquiti ISP Design Center**) e pipeline completo de engenharia para cobertura celular **SMP (1.800 MHz, Cluster 4×3)** e rede de transporte **backhaul micro-ondas PTP (Ubiquiti airFiber 11FX / 5XHD)** na região do Seridó (RN), interligando os 5 municípios ao **CCC Regional de Currais Novos** e ao **CCC Principal em Natal (Candelária/BR-101)** sobre relevo real **Copernicus DEM 30 m**.

📄 **Arquitetura dos Módulos Python:** [`GUIA_ARQUITETURA_E_METODOLOGIA.md`](./GUIA_ARQUITETURA_E_METODOLOGIA.md)

---

## 🌐 Simulador Web & Recursos (`index.html` / GitHub Pages)

O arquivo [`index.html`](./index.html) (espelhado em [`outputs/mapa_interativo.html`](./outputs/mapa_interativo.html)) roda direto no navegador com os perfis e corredores 3D do Copernicus DEM 30 m já embutidos, dividido em **3 interfaces**:

1. **🗺️ Simulador & Mapa (Top 3 Rotas + Gaveta UISP):**
   - **Top 3 Caminhos 100% Desobstruídos (torres únicas e fixas ≤ 50 m, sem saltos redundantes `< 12 km` entre repetidoras):**
     - **★ Solução #1 — Ótima Principal (Verde Neon):** **4 repetidoras** (`REP_CUME_06`, `REP_CUME_28`, `REP_CUME_46` Serra da Tapuia + `REP_CUME_69` crista norte do cânion de Carnaúba dos Dantas), **13 enlaces**, **286,40 km** totais, torres fixas até **30,0 m**, folga mínima **+8,26 m** acima de 0,6·F1.
     - **Solução #2 — Saltos ≤ 56 km (Azul Ciano):** **5 repetidoras**, **14 enlaces**, **287,04 km**, torres até **30,0 m**, folga mín **+8,26 m** (divide o tronco até Natal em 11 GHz licenciado).
     - **Solução #3 — Contingência Independente (Âmbar):** **5 repetidoras**, **14 enlaces**, **316,03 km**, torres até **50,0 m**, folga mín **+8,25 m** (100% disjunta dos cumes da #1).
   - **📡 Cobertura Celular SMP (`R = 1,808 km`):** botão no topo para ligar/desligar o raio celular de **1,808 km** (`8,5 km²/ERB`, 3 setores de 120°) nas **9 ERBs urbanas** (Caicó 3, Currais Novos 2, Santa Cruz 2, Jardim do Seridó 1 e Carnaúba dos Dantas 1 na encosta urbana do Monte do Galo).
   - **Corte Altimétrico Lateral (Gaveta Inferior):** perfil do terreno real, abaulamento terrestre (`k = 4/3`), elipse da **1ª Zona de Fresnel (60% e 100%)**, cálculo dinâmico ao trocar altura de torre (`±5 m`) ou banda (`5 GHz ↔ 11 GHz`) e atenuação por chuva (**ITU-R P.838-3 @ 50 mm/h**).

2. **🧮 Cálculos, Chuva & Orçamento (Apresentação):**
   - Memorial didático completo de **Erlang B**, **COST 231 Hata** (`R = 1,808 km`), **Interferência Co-Canal 4×3** (`S/I = 12,56 dB > 12 dB`), tabela de altura fixa única por torre, quadro de chuva ITU-R, diagrama lógico SVG e orçamento separado entre **Ativos de Telecom** e **Torres + Infraestrutura Civil** com links verificados por item:
     - **Solução #1 CAPEX:** Ativos **R$ 206.853,64** + Torres **R$ 203.062,50** + Infra **R$ 66.785,92** = **R$ 476.702,06**
     - **Solução #2 CAPEX:** **R$ 515.081,93**
     - **Solução #3 CAPEX:** **R$ 606.728,79**

3. **🏔️ Visada 3D (De Lado):**
   - Visualizador **WebGL (Three.js)** integrado com malha 3D real **Copernicus 30 m (`65 × 33` por enlace)** e textura **Esri Satellite** (ou relevo hipsométrico), torres em 3D, curvatura `k=4/3` e elipsoide **Fresnel 3D**, com câmeras rápidas **`📐 De Lado`**, **`🚁 Aérea 3/4`** e **`🗼 Torre TX→RX`** + exagero vertical ajustável.

---

## 🚀 Como Executar o Pipeline Localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -u orchestrator.py
python verificar_rotas.py
```

* `orchestrator.py` executa as Etapas 1 a 7 e gera o simulador web (`index.html` e `outputs/mapa_interativo.html`) além do KML (`outputs/backhaul_serido_uisp.kml`).
* `verificar_rotas.py` audita os **25 enlaces** das 3 soluções diretamente nos GeoTIFFs da pasta `dem/`.
