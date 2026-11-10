# Projeto SMP Seridó — Dimensionamento Celular e Backhaul PTP (UISP)

Simulador interativo (clone funcional do **Ubiquiti ISP Design Center**) e pipeline completo de dimensionamento para cobertura celular SMP (1800 MHz) e rede de transporte backhaul ponto a ponto (airFiber 11FX / 5XHD) na região do Seridó (RN), utilizando relevo real de alta resolução (**Copernicus DEM 30 m**).

## 🌐 Acessar Simulador Interativo (GitHub Pages)

O arquivo [`index.html`](./index.html) na raiz deste repositório contém o simulador completo com os perfis altimétricos reais já embutidos:

- **Top 3 Melhores Caminhos (100% Desobstruídos):**
  - **★ Solução #1 (Ótima Principal — Verde Neon):** Apenas 2 repetidoras (`Cume 05 - 689 m` e `Cume 17 - 668 m`) e menor distância total (**194,17 km** em 10 enlaces).
  - **Solução #2 (Torres Compactas ≤ 30 m — Azul Ciano):** Nenhuma torre ultrapassa 30 m de altura, usando 4 repetidoras.
  - **Solução #3 (Rota de Contingência — Âmbar):** Utiliza cumes 100% independentes da Solução #1.
- **Painel de Controle:** Ative ou desative individualmente cada solução ou todas as 3 de uma só vez.
- **Corte Altimétrico Real (Gaveta Inferior):** Clique em qualquer enlace para inspecionar o perfil real do terreno (Copernicus GLO-30), a curvatura terrestre ($k=4/3$), a 1ª Zona de Fresnel (60%) e o Link Budget.

## 🚀 Como Executar o Pipeline Localmente

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python orchestrator.py
python verificar_rotas.py
```
