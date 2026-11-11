# Projeto SMP Seridó — Dimensionamento Celular e Backhaul PTP (UISP)

Simulador interativo (clone funcional do **Ubiquiti ISP Design Center**) e pipeline completo de dimensionamento para cobertura celular SMP (1800 MHz, Cluster 4x3) e rede de transporte backhaul ponto a ponto (airFiber 11FX / 5XHD) na região do Seridó (RN) interligando **Currais Novos (CCC Regional)** e **Natal (CCC Principal NTL)**, utilizando relevo real de alta resolução (**Copernicus DEM 30 m**).

📄 **Documentação Completa da Arquitetura e Metodologia:** Consulte [`GUIA_ARQUITETURA_E_METODOLOGIA.md`](./GUIA_ARQUITETURA_E_METODOLOGIA.md) para o mapeamento detalhado de pastas/arquivos e a explicação passo a passo dos algoritmos de posicionamento de ERBs, varredura em grade (*Spatial Grid Search*) e otimização em grafo (*Dijkstra Multi-Critério*).

## 🌐 Acessar Simulador Interativo (GitHub Pages)

O arquivo [`index.html`](./index.html) na raiz deste repositório contém o simulador completo com os perfis altimétricos reais já embutidos:

- **Top 3 Melhores Caminhos (100% Desobstruídos no Relevo Real):**
  - **★ Solução #1 (Ótima Principal — Verde Neon):** Apenas 4 repetidoras no total (2 no Seridó + 2 no tronco até Natal) e menor distância acumulada (**300,86 km** em 13 enlaces).
  - **Solução #2 (Torres Compactas — Azul Ciano):** Prioriza torres de menor porte estrutural em toda a rede (5 repetidoras, **328,91 km**).
  - **Solução #3 (Rota de Contingência — Âmbar):** Utiliza cumes 100% independentes da Solução #1 (6 repetidoras, **365,54 km**).
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
