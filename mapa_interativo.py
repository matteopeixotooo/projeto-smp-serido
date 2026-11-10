"""
mapa_interativo.py - Clone Funcional do Ubiquiti ISP Design Center (UISP)
Plota as 3 melhores soluções de topologia calculadas sobre o relevo real (DEM Copernicus 30 m),
com destaque para a Solução #1 (Melhor Caso), notas comparativas detalhadas, controle para
ativar/desativar individualmente ou todas as 3 soluções de uma vez, e corte altimétrico real.
"""
import os
import json
import webbrowser

ARQ_SITIOS = "outputs/todos_sitios.json"
ARQ_ENLACES = "outputs/enlaces_com_antenas.json"
ARQ_SOLUCOES = "outputs/solucoes_topologia.json"

sitios_otimos = []
enlaces_otimos = []
solucoes_topologia = []
perfis_reais = []

if os.path.exists("outputs/perfis_enlaces.json"):
    with open("outputs/perfis_enlaces.json", "r", encoding="utf-8") as f:
        perfis_reais = [
            {"a": [p["lat_a"], p["lon_a"]], "b": [p["lat_b"], p["lon_b"]],
             "elev": [round(v, 1) for v in p["elev"]]}
            for p in json.load(f)
        ]

if os.path.exists(ARQ_SITIOS):
    with open(ARQ_SITIOS, "r", encoding="utf-8") as f:
        sitios_otimos = json.load(f)

if os.path.exists(ARQ_ENLACES):
    with open(ARQ_ENLACES, "r", encoding="utf-8") as f:
        enlaces_otimos = json.load(f)

if os.path.exists(ARQ_SOLUCOES):
    with open(ARQ_SOLUCOES, "r", encoding="utf-8") as f:
        solucoes_topologia = json.load(f)

html_code = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <title>UISP Design Center - Simulador Seridó (Top 3 Soluções)</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background: #0f1117; color: #e1e4ea; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}
    
    /* TOPO / HEADER UISP */
    #header {{ height: 48px; background: #161822; border-bottom: 1px solid #282b3c; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; z-index: 2000; }}
    .logo-box {{ display: flex; align-items: center; gap: 10px; font-weight: bold; font-size: 1.05rem; color: #fff; }}
    .logo-badge {{ background: #0070f3; color: white; padding: 2px 7px; border-radius: 4px; font-size: 0.8rem; font-weight: 800; }}
    .header-info {{ font-size: 0.85rem; color: #8a8f9d; display: flex; gap: 20px; align-items: center; }}
    .header-info b {{ color: #00ff55; }}

    /* ÁREA DO MAPA */
    #map-wrapper {{ flex: 1; position: relative; width: 100%; }}
    #map {{ width: 100%; height: 100%; }}

    /* BARRA DE FERRAMENTAS FLUTUANTE */
    #toolbar {{ position: absolute; top: 16px; left: 16px; background: rgba(22, 24, 34, 0.94); border: 1px solid #2d3142; border-radius: 8px; display: flex; flex-direction: column; gap: 4px; padding: 6px; z-index: 1500; box-shadow: 0 4px 16px rgba(0,0,0,0.6); }}
    .tool-btn {{ width: 42px; height: 42px; background: transparent; border: 1px solid transparent; border-radius: 6px; color: #a4a9b6; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 1.25rem; transition: all 0.2s; }}
    .tool-btn:hover {{ background: #282c3f; color: #fff; }}
    .tool-btn.active {{ background: #0070f3; color: #fff; border-color: #3291ff; }}
    .tool-sep {{ height: 1px; background: #2d3142; margin: 4px 0; }}

    /* PAINEL FLUTUANTE DAS 3 MELHORES SOLUÇÕES */
    #solutions-panel {{ position: absolute; top: 16px; left: 72px; width: 430px; max-height: calc(100vh - 80px); background: rgba(18, 20, 30, 0.95); border: 1px solid #2e3348; border-radius: 10px; z-index: 1500; box-shadow: 0 8px 28px rgba(0,0,0,0.75); display: flex; flex-direction: column; overflow: hidden; backdrop-filter: blur(8px); transition: all 0.2s ease; }}
    #solutions-panel.minimized {{ width: 290px; max-height: 44px; }}
    .sol-panel-header {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: #161927; border-bottom: 1px solid #282d42; cursor: pointer; user-select: none; }}
    .sol-panel-title {{ font-size: 0.9rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; }}
    .sol-panel-body {{ padding: 10px 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }}
    .sol-bulk-actions {{ display: flex; gap: 6px; }}
    .bulk-btn {{ flex: 1; padding: 6px 8px; background: #222638; border: 1px solid #363c56; color: #d5d9e6; border-radius: 6px; font-size: 0.76rem; font-weight: 600; cursor: pointer; transition: all 0.15s; }}
    .bulk-btn:hover {{ background: #2e344d; color: #fff; border-color: #4f587d; }}
    .bulk-btn.primary {{ background: rgba(0, 255, 85, 0.14); border-color: #00ff55; color: #00ff55; }}
    .bulk-btn.primary:hover {{ background: rgba(0, 255, 85, 0.24); }}

    .sol-card {{ background: #171a28; border: 1px solid #2a2f45; border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; transition: all 0.15s; }}
    .sol-card.best-case {{ background: linear-gradient(180deg, rgba(0, 255, 85, 0.10) 0%, rgba(23, 26, 40, 0.95) 100%); border: 1.5px solid #00ff55; box-shadow: 0 0 14px rgba(0, 255, 85, 0.18); }}
    .sol-card.inactive {{ opacity: 0.52; }}
    .sol-card-top {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
    .sol-check-label {{ display: flex; align-items: center; gap: 8px; cursor: pointer; font-weight: 700; font-size: 0.84rem; color: #fff; }}
    .sol-check-label input[type="checkbox"] {{ width: 16px; height: 16px; cursor: pointer; accent-color: #00ff55; }}
    .sol-swatch {{ width: 14px; height: 5px; border-radius: 3px; display: inline-block; }}
    .sol-badge-best {{ background: #00ff55; color: #09130c; font-size: 0.68rem; font-weight: 900; padding: 2px 6px; border-radius: 4px; letter-spacing: 0.3px; }}
    .sol-badge-alt {{ background: #262b40; color: #b5bdd0; font-size: 0.68rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; }}
    .sol-metrics {{ display: flex; flex-wrap: wrap; gap: 6px; font-size: 0.74rem; color: #c5cbe0; background: #121520; padding: 5px 8px; border-radius: 5px; border: 1px solid #222638; }}
    .sol-metrics span b {{ color: #fff; }}
    .sol-note {{ font-size: 0.75rem; line-height: 1.38; color: #b8bfd4; }}
    .sol-note b {{ color: #e2e6f3; }}
    .sol-why-win {{ font-size: 0.74rem; line-height: 1.35; color: #9dfcc0; background: rgba(0, 255, 85, 0.08); border-left: 3px solid #00ff55; padding: 5px 8px; border-radius: 4px; }}
    .sol-why-lose {{ font-size: 0.73rem; line-height: 1.35; color: #ffd591; background: rgba(255, 171, 0, 0.08); border-left: 3px solid #ffab00; padding: 4px 8px; border-radius: 4px; }}

    /* PAINEL INFERIOR GAVETA (RÉPLICA UISP) */
    #bottom-drawer {{ position: absolute; bottom: 0; left: 0; right: 0; background: rgba(18, 20, 29, 0.96); border-top: 1px solid #2c3042; backdrop-filter: blur(8px); display: none; flex-direction: column; z-index: 1600; box-shadow: 0 -8px 24px rgba(0,0,0,0.7); max-height: 390px; transition: transform 0.25s ease; }}
    #drawer-header {{ display: flex; justify-content: space-between; align-items: center; padding: 6px 16px; background: #13151f; border-bottom: 1px solid #242736; font-size: 0.85rem; gap: 12px; }}
    #drawer-title {{ display: flex; align-items: center; gap: 10px; font-weight: 600; flex-wrap: wrap; }}
    .badge-rota {{ padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: bold; }}
    .rota-otima {{ background: rgba(0, 255, 85, 0.15); color: #00ff55; border: 1px solid #00ff55; }}
    .rota-sol2 {{ background: rgba(0, 212, 255, 0.15); color: #00d4ff; border: 1px solid #00d4ff; }}
    .rota-sol3 {{ background: rgba(255, 171, 0, 0.15); color: #ffab00; border: 1px solid #ffab00; }}
    .rota-custom {{ background: rgba(0, 180, 255, 0.15); color: #00b4ff; border: 1px solid #00b4ff; }}
    #drawer-note {{ font-size: 0.76rem; color: #a9b2c7; flex: 1; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .close-btn {{ cursor: pointer; background: transparent; border: none; color: #8e94a5; font-size: 1.2rem; }}
    .close-btn:hover {{ color: #fff; }}

    #drawer-body {{ display: grid; grid-template-columns: 310px 1fr 310px; gap: 12px; padding: 12px 16px; }}
    .card-station {{ background: #181a26; border: 1px solid #272a3b; border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 8px; }}
    .card-title {{ font-size: 0.85rem; font-weight: bold; color: #fff; display: flex; justify-content: space-between; }}
    .field-row {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #9da3b4; }}
    .field-row select, .field-row input[type="text"] {{ background: #222534; border: 1px solid #363b52; color: #fff; padding: 3px 6px; border-radius: 4px; font-size: 0.8rem; width: 55%; }}
    .stepper {{ display: flex; align-items: center; gap: 4px; }}
    .step-btn {{ width: 26px; height: 24px; background: #282c3e; border: 1px solid #3a3f58; color: #fff; border-radius: 4px; cursor: pointer; font-weight: bold; display: flex; align-items: center; justify-content: center; }}
    .step-btn:hover {{ background: #383e58; }}
    .step-val {{ font-size: 0.85rem; color: #00ff55; font-weight: bold; width: 48px; text-align: center; }}

    /* SINAL RECEBIDO GAUGE */
    .signal-box {{ margin-top: auto; padding-top: 6px; border-top: 1px solid #242738; }}
    .signal-val {{ font-size: 1.15rem; font-weight: 800; color: #00ff55; display: flex; justify-content: space-between; align-items: baseline; }}
    .signal-bar-wrap {{ height: 6px; background: #222534; border-radius: 3px; overflow: hidden; margin-top: 4px; }}
    .signal-bar-fill {{ height: 100%; width: 75%; background: linear-gradient(90deg, #ff4444, #ffbb00, #00ff55); }}

    /* CENTRO: CAPACIDADE E CORTE ALTIMÉTRICO */
    .card-center {{ display: flex; flex-direction: column; gap: 6px; }}
    .center-top {{ display: flex; justify-content: space-between; align-items: center; background: #181a26; padding: 6px 12px; border-radius: 6px; border: 1px solid #272a3b; }}
    .capacity-tag {{ font-size: 1.05rem; font-weight: bold; color: #fff; display: flex; align-items: baseline; gap: 6px; }}
    .capacity-val {{ color: #3291ff; font-size: 1.25rem; font-weight: 900; }}
    .status-badge {{ font-size: 0.8rem; padding: 3px 8px; border-radius: 4px; font-weight: bold; }}
    .status-clear {{ background: rgba(0, 255, 85, 0.15); color: #00ff55; }}
    .status-obstr {{ background: rgba(255, 68, 68, 0.2); color: #ff4444; }}

    #canvas-container {{ flex: 1; height: 175px; background: #13151f; border-radius: 6px; border: 1px solid #242736; position: relative; }}
    canvas {{ width: 100%; height: 100%; display: block; }}
  </style>
</head>
<body>

  <!-- HEADER -->
  <div id="header">
    <div class="logo-box">
      <span class="logo-badge">UISP</span>
      <span>Design Center - Projeto SMP Seridó</span>
    </div>
    <div class="header-info">
      <span>Destaque Principal: <b>Solução #1 (Verde Neon ★)</b></span>
      <span>Núcleo: Currais Novos (CCC)</span>
      <span>DEM: <b>Copernicus 30m Offline (100% Desobstruído)</b></span>
    </div>
  </div>

  <!-- CONTAINER DO MAPA -->
  <div id="map-wrapper">
    <div id="map"></div>

    <!-- TOOLBAR FLUTUANTE -->
    <div id="toolbar">
      <button class="tool-btn active" id="btn-select" title="Mãozinha: Selecionar e Inspecionar" onclick="setModo('select')">🖐️</button>
      <div class="tool-sep"></div>
      <button class="tool-btn" id="btn-site" title="Adicionar Antena / Sítio Livre" onclick="setModo('add_site')">📍</button>
      <button class="tool-btn" id="btn-rep" title="Adicionar Repetidora Livre" onclick="setModo('add_rep')">⚡</button>
      <button class="tool-btn" id="btn-ptp" title="Criar Enlace PtP (Clique Ponto 1 e depois Ponto 2)" onclick="setModo('add_ptp')">🔗</button>
      <div class="tool-sep"></div>
      <button class="tool-btn" id="btn-del" title="Excluir Elemento Selecionado" onclick="excluirSelecionado()">🗑️</button>
    </div>

    <!-- PAINEL DE CONTROLE E NOTAS DAS 3 MELHORES SOLUÇÕES -->
    <div id="solutions-panel">
      <div class="sol-panel-header" onclick="alternarPainelSolucoes()">
        <div class="sol-panel-title">
          <span>🏆 Top 3 Melhores Caminhos (Relevo Real)</span>
        </div>
        <span id="sol-panel-toggle-icon" style="color:#9da3b4; font-size:0.85rem;">▼ Minimizar</span>
      </div>
      <div class="sol-panel-body" id="sol-panel-body">
        <div class="sol-bulk-actions">
          <button class="bulk-btn primary" onclick="definirTodasSolucoes([true, false, false])">★ Só Melhor (#1)</button>
          <button class="bulk-btn" onclick="definirTodasSolucoes([true, true, true])">👁️ Ativar Todas (3)</button>
          <button class="bulk-btn" onclick="definirTodasSolucoes([false, false, false])">🚫 Desativar Todas</button>
        </div>
        <div id="sol-cards-container" style="display:flex; flex-direction:column; gap:8px;"></div>
      </div>
    </div>

    <!-- GAVETA INFERIOR (LINK DRAWER ESTILO UBIQUITI) -->
    <div id="bottom-drawer">
      <div id="drawer-header">
        <div id="drawer-title">
          <span id="label-enlace-nome">Enlace Selecionado</span>
          <span class="badge-rota rota-otima" id="badge-tipo-enlace">SOLUÇÃO #1 (ÓTIMA)</span>
        </div>
        <div id="drawer-note"></div>
        <button class="close-btn" onclick="fecharGaveta()">✕</button>
      </div>

      <div id="drawer-body">
        <!-- ESTAÇÃO 1 (TX) -->
        <div class="card-station">
          <div class="card-title">
            <span id="st1-nome">Estação 1</span>
            <span style="color: #6c7284; font-size: 0.75rem;">TX</span>
          </div>
          <div class="field-row">
            <span>Coordenadas:</span>
            <span id="st1-coords" style="font-family: monospace; color: #fff;">-6.000, -36.000</span>
          </div>
          <div class="field-row">
            <span>Produto / Rádio:</span>
            <select id="st1-radio" onchange="atualizarHardware()">
              <option value="airFiber 11FX">airFiber 11FX (11 GHz)</option>
              <option value="airFiber 5XHD">airFiber 5XHD (5 GHz)</option>
            </select>
          </div>
          <div class="field-row">
            <span>Antena / Prato:</span>
            <select id="st1-antena" onchange="atualizarHardware()">
              <option value="35.0">AF-11G35 (0.9m / 35 dBi)</option>
              <option value="38.5">Dish 1.2m (38.5 dBi)</option>
              <option value="30.0">AF-5G30 (0.65m / 30 dBi)</option>
              <option value="23.0">AF-5G23 (0.38m / 23 dBi)</option>
            </select>
          </div>
          <div class="field-row">
            <span>Altura da Torre:</span>
            <div class="stepper">
              <button class="step-btn" onclick="ajustarTorre('st1', -5)">-</button>
              <span class="step-val" id="st1-h-torre">35 m</span>
              <button class="step-btn" onclick="ajustarTorre('st1', +5)">+</button>
            </div>
          </div>
          <div class="field-row">
            <span>Azimute / Tilt:</span>
            <span id="st1-azim-tilt" style="color: #3291ff;">45° / -0.2°</span>
          </div>
          <div class="signal-box">
            <div class="signal-val">
              <span style="font-size: 0.8rem; color: #9da3b4;">Sinal Esperado:</span>
              <span id="st1-rsl">-41 dBm</span>
            </div>
            <div class="signal-bar-wrap">
              <div class="signal-bar-fill" id="st1-signal-bar"></div>
            </div>
          </div>
        </div>

        <!-- CENTRO: GRÁFICO E CAPACIDADE -->
        <div class="card-center">
          <div class="center-top">
            <div class="capacity-tag">
              <span>Throughput:</span>
              <span class="capacity-val" id="txt-capacity">860 Mbps</span>
            </div>
            <div style="font-size: 0.85rem; color: #a4a9b6;">
              Distância: <b id="txt-dist" style="color: #fff;">32.5 km</b> | 
              Canal: 
              <select id="sel-channel-width" style="background: #242738; color: #00ff55; border: 1px solid #363b52; border-radius: 4px; padding: 2px 4px;" onchange="atualizarHardware()">
                <option value="20">20 MHz</option>
                <option value="28" selected>28 MHz (ANATEL 11G)</option>
                <option value="40">40 MHz</option>
                <option value="56">56 MHz (ANATEL 11G)</option>
                <option value="80">80 MHz (5G)</option>
              </select>
            </div>
            <div class="status-badge status-clear" id="badge-obstrucao">VISADA LIMPA</div>
          </div>

          <div id="canvas-container">
            <canvas id="profileCanvas"></canvas>
          </div>
        </div>

        <!-- ESTAÇÃO 2 (RX) -->
        <div class="card-station">
          <div class="card-title">
            <span id="st2-nome">Estação 2</span>
            <span style="color: #6c7284; font-size: 0.75rem;">RX</span>
          </div>
          <div class="field-row">
            <span>Coordenadas:</span>
            <span id="st2-coords" style="font-family: monospace; color: #fff;">-6.000, -36.000</span>
          </div>
          <div class="field-row">
            <span>Produto / Rádio:</span>
            <select id="st2-radio" onchange="atualizarHardware()">
              <option value="airFiber 11FX">airFiber 11FX (11 GHz)</option>
              <option value="airFiber 5XHD">airFiber 5XHD (5 GHz)</option>
            </select>
          </div>
          <div class="field-row">
            <span>Antena / Prato:</span>
            <select id="st2-antena" onchange="atualizarHardware()">
              <option value="35.0">AF-11G35 (0.9m / 35 dBi)</option>
              <option value="38.5">Dish 1.2m (38.5 dBi)</option>
              <option value="30.0">AF-5G30 (0.65m / 30 dBi)</option>
              <option value="23.0">AF-5G23 (0.38m / 23 dBi)</option>
            </select>
          </div>
          <div class="field-row">
            <span>Altura da Torre:</span>
            <div class="stepper">
              <button class="step-btn" onclick="ajustarTorre('st2', -5)">-</button>
              <span class="step-val" id="st2-h-torre">45 m</span>
              <button class="step-btn" onclick="ajustarTorre('st2', +5)">+</button>
            </div>
          </div>
          <div class="field-row">
            <span>Fade Margin (FM):</span>
            <b id="txt-fade-margin" style="color: #00ff55;">32.1 dB</b>
          </div>
          <div class="signal-box">
            <div class="signal-val">
              <span style="font-size: 0.8rem; color: #9da3b4;">Sinal Esperado:</span>
              <span id="st2-rsl">-41 dBm</span>
            </div>
            <div class="signal-bar-wrap">
              <div class="signal-bar-fill" id="st2-signal-bar"></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    // DADOS INJETADOS DO MOTOR PYTHON
    const SITIOS_FIXOS = {json.dumps(sitios_otimos, ensure_ascii=False)};
    const ENLACES_FIXOS = {json.dumps(enlaces_otimos, ensure_ascii=False)};
    const SOLUCOES = {json.dumps(solucoes_topologia, ensure_ascii=False)};
    const PERFIS_REAIS = {json.dumps(perfis_reais)};

    // ESTADO DA APLICAÇÃO
    let modoAtual = 'select';
    let pontoOrigemPtp = null;
    let enlaceSelecionado = null;
    let elementoSelecionado = null;

    let sitesCustom = [];
    let linksCustom = [];
    let contadores = {{ site: 1, rep: 1 }};

    // Estado de visibilidade das 3 soluções (por padrão todas ativas, com #1 em destaque no topo)
    const solucaoAtiva = {{ 1: true, 2: true, 3: true }};
    const camadasSolucao = {{ 1: [], 2: [], 3: [] }};
    const marcadoresFixos = {{}};

    // INICIALIZAÇÃO DO MAPA LEAFLET
    const map = L.map('map', {{
      center: [-6.40, -36.65],
      zoom: 10,
      zoomControl: false
    }});

    L.control.zoom({{ position: 'topright' }}).addTo(map);

    const layerSatelite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      maxZoom: 18, attribution: 'Esri Satellite'
    }}).addTo(map);

    const layerTopo = L.tileLayer('https://{{s}}.tile.opentopomap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 17, attribution: 'OpenTopoMap'
    }});

    L.control.layers({{"🛰️ Satélite": layerSatelite, "🏔️ Relevo / Topo": layerTopo}}, null, {{ position: 'topright' }}).addTo(map);

    function getSiteIcon(tipo, fixo=true, solucoesDoNo=[1]) {{
      let cor = '#00e5ff'; // ERB azul ciano
      let border = '#ffffff';
      let raio = 8;

      if (tipo.includes('CCC')) {{
        cor = '#ff1744';
        raio = 11;
      }} else if (tipo.includes('REPETIDORA')) {{
        if (solucoesDoNo.includes(1)) {{
          cor = '#00ff55'; // Repetidora da Solução #1 destacada em verde-limão
          raio = 10;
        }} else if (solucoesDoNo.includes(2)) {{
          cor = '#00d4ff'; // Repetidora da Solução #2 em azul ciano
          raio = 9;
        }} else {{
          cor = '#ffab00'; // Repetidora da Solução #3 em âmbar
          raio = 9;
        }}
      }}
      if (!fixo) {{
        border = '#00ff55';
      }}

      return L.divIcon({{
        className: 'custom-site-marker',
        html: `<div style="width: ${{raio*2}}px; height: ${{raio*2}}px; background: ${{cor}}; border: 2px solid ${{border}}; border-radius: 50%; box-shadow: 0 0 10px ${{cor}};"></div>`,
        iconSize: [raio*2, raio*2],
        iconAnchor: [raio, raio]
      }});
    }}

    // MAPAS DE ACESSO RÁPIDO AOS SÍTIOS FIXOS
    const dictSitiosFixos = {{}};
    SITIOS_FIXOS.forEach(s => {{
      dictSitiosFixos[s.id] = s;
      const sols = s.solucoes || [1];
      const mk = L.marker([s.latitude, s.longitude], {{
        icon: getSiteIcon(s.tipo, true, sols)
      }}).addTo(map);

      mk.dados = {{ ...s, fixo: true, solucoes: sols }};
      const tagSols = s.tipo.includes('REPETIDORA') ? `<br>Usada na(s) Solução(ões): <b>#${{sols.join(', #')}}</b>` : '';
      mk.bindTooltip(`<b>${{s.nome}}</b><br>Torre máx: ${{s.altura_torre_m}}m | Cota terreno: ${{s.altitude_terreno_m}}m${{tagSols}}`, {{ direction: 'top' }});
      mk.on('click', () => tratarCliqueNoNo(mk));
      marcadoresFixos[s.id] = mk;
    }});

    // RENDERIZAÇÃO DAS 3 SOLUÇÕES (desenha #3, depois #2, e por último #1 por cima em destaque)
    const estiloPorRank = {{
      1: {{ color: '#00ff55', weight: 5.5, opacity: 0.98, dashArray: null }},
      2: {{ color: '#00d4ff', weight: 3.5, opacity: 0.88, dashArray: '8, 6' }},
      3: {{ color: '#ffab00', weight: 3.5, opacity: 0.88, dashArray: '3, 7' }},
    }};

    // Desenha da #3 para a #1 para que a #1 fique sempre no topo visual
    [...SOLUCOES].sort((a, b) => b.rank - a.rank).forEach(sol => {{
      const rk = sol.rank;
      const est = estiloPorRank[rk] || estiloPorRank[1];

      sol.enlaces.forEach(l => {{
        const stA = dictSitiosFixos[l.id_origem];
        const stB = dictSitiosFixos[l.id_destino];
        if (!stA || !stB) return;

        // Pequeno deslocamento visual nas soluções 2 e 3 quando compartilham o mesmo par de nós,
        // para que todas as 3 soluções possam ser vistas simultaneamente no mapa
        let latOffset = 0, lonOffset = 0;
        if (rk === 2) {{ latOffset = 0.0014; lonOffset = -0.0014; }}
        if (rk === 3) {{ latOffset = -0.0014; lonOffset = 0.0014; }}

        const coords = [
          [stA.latitude + latOffset, stA.longitude + lonOffset],
          [stB.latitude + latOffset, stB.longitude + lonOffset]
        ];

        const poly = L.polyline(coords, {{
          color: est.color,
          weight: est.weight,
          opacity: est.opacity,
          dashArray: est.dashArray
        }}).addTo(map);

        poly.dados = {{
          ...l,
          rank_solucao: rk,
          nome_solucao: sol.titulo,
          nota_solucao: sol.nota_curta,
          fixo: true,
          origem_obj: stA,
          destino_obj: stB
        }};

        poly.bindTooltip(
          `<b>[Solução #${{rk}}] ${{l.origem}} ⇄ ${{l.destino}}</b><br>` +
          `Dist: ${{l.distancia_km}} km | Torres: ${{l.h_torre_origem_m}}m / ${{l.h_torre_destino_m}}m | Folga Fresnel: +${{l.folga_fresnel_m}}m<br>` +
          `<i>${{sol.nota_curta}}</i>`,
          {{ sticky: true }}
        );

        poly.on('click', (e) => {{
          L.DomEvent.stopPropagation(e);
          selecionarEnlace(poly);
        }});

        camadasSolucao[rk].push(poly);
      }});
    }});

    // RENDERIZAR CARTÕES E CONTROLES DAS 3 SOLUÇÕES
    function renderizarPainelSolucoes() {{
      const cont = document.getElementById('sol-cards-container');
      cont.innerHTML = '';

      SOLUCOES.forEach(sol => {{
        const rk = sol.rank;
        const ativa = solucaoAtiva[rk];
        const card = document.createElement('div');
        card.className = `sol-card ${{sol.destaque ? 'best-case' : ''}} ${{ativa ? '' : 'inactive'}}`;
        card.id = `sol-card-${{rk}}`;

        const dashStyle = rk === 1 ? 'solid' : (rk === 2 ? 'dashed' : 'dotted');
        const badgeHtml = sol.destaque
          ? `<span class="sol-badge-best">★ MELHOR CASO (#1)</span>`
          : `<span class="sol-badge-alt">OPÇÃO #${{rk}}</span>`;

        const comparacaoHtml = sol.destaque
          ? `<div class="sol-why-win"><b>Por que a #1 é a melhor:</b> ${{sol.por_que_n1_vence}}</div>`
          : `<div class="sol-why-lose"><b>Por que a #1 vence esta:</b> ${{sol.comparacao_n1}}</div>`;

        card.innerHTML = `
          <div class="sol-card-top">
            <label class="sol-check-label">
              <input type="checkbox" id="chk-sol-${{rk}}" ${{ativa ? 'checked' : ''}} onchange="alternarSolucao(${{rk}}, this.checked)">
              <span class="sol-swatch" style="background:${{sol.cor}}; border-bottom: 2px ${{dashStyle}} ${{sol.cor}};"></span>
              <span>${{sol.titulo}}</span>
            </label>
            ${{badgeHtml}}
          </div>
          <div class="sol-metrics">
            <span>Repetidoras: <b>${{sol.num_repetidoras}}</b></span>
            <span>Enlaces: <b>${{sol.num_enlaces}}</b></span>
            <span>Dist. Total: <b>${{sol.distancia_total_km}} km</b></span>
            <span>Torre Máx: <b>${{sol.altura_max_torre_m}} m</b></span>
            <span>Folga Mín: <b>+${{sol.folga_minima_m}} m</b></span>
          </div>
          <div class="sol-note"><b>Motivo da escolha:</b> ${{sol.justificativa}}</div>
          ${{comparacaoHtml}}
        `;
        cont.appendChild(card);
      }});
    }}

    function atualizarVisibilidadeMapa() {{
      [1, 2, 3].forEach(rk => {{
        const mostrar = solucaoAtiva[rk];
        camadasSolucao[rk].forEach(poly => {{
          if (mostrar) {{
            if (!map.hasLayer(poly)) poly.addTo(map);
          }} else {{
            if (map.hasLayer(poly)) map.removeLayer(poly);
          }}
        }});
        const card = document.getElementById(`sol-card-${{rk}}`);
        const chk = document.getElementById(`chk-sol-${{rk}}`);
        if (card) card.classList.toggle('inactive', !mostrar);
        if (chk) chk.checked = mostrar;
      }});

      // Garante que a Solução #1 fique sempre desenhada por cima quando ativa
      if (solucaoAtiva[1]) {{
        camadasSolucao[1].forEach(poly => poly.bringToFront());
      }}

      // Mostra/oculta repetidoras exclusivas das soluções desativadas
      Object.values(marcadoresFixos).forEach(mk => {{
        const sols = mk.dados.solucoes || [1, 2, 3];
        const algumAtivo = sols.some(r => solucaoAtiva[r]);
        if (algumAtivo) {{
          if (!map.hasLayer(mk)) mk.addTo(map);
        }} else {{
          if (map.hasLayer(mk)) map.removeLayer(mk);
        }}
      }});
    }}

    function alternarSolucao(rk, estado) {{
      solucaoAtiva[rk] = estado;
      atualizarVisibilidadeMapa();
      // Se ativou uma solução, seleciona o primeiro enlace interurbano dela para mostrar o relevo
      if (estado && camadasSolucao[rk].length > 0) {{
        const linkDestaque = camadasSolucao[rk].find(p => p.dados.distancia_km > 10) || camadasSolucao[rk][0];
        selecionarEnlace(linkDestaque);
      }}
    }}

    function definirTodasSolucoes(estados) {{
      solucaoAtiva[1] = estados[0];
      solucaoAtiva[2] = estados[1];
      solucaoAtiva[3] = estados[2];
      atualizarVisibilidadeMapa();
    }}

    function alternarPainelSolucoes() {{
      const panel = document.getElementById('solutions-panel');
      const icon = document.getElementById('sol-panel-toggle-icon');
      panel.classList.toggle('minimized');
      icon.textContent = panel.classList.contains('minimized') ? '▲ Expandir' : '▼ Minimizar';
    }}

    renderizarPainelSolucoes();

    // CONTROLE DE MODO DA TOOLBAR
    function setModo(modo) {{
      modoAtual = modo;
      document.querySelectorAll('.tool-btn').forEach(b => b.classList.remove('active'));
      pontoOrigemPtp = null;

      if (modo === 'select') {{
        document.getElementById('btn-select').classList.add('active');
        map.getContainer().style.cursor = 'grab';
      }} else if (modo === 'add_site') {{
        document.getElementById('btn-site').classList.add('active');
        map.getContainer().style.cursor = 'crosshair';
      }} else if (modo === 'add_rep') {{
        document.getElementById('btn-rep').classList.add('active');
        map.getContainer().style.cursor = 'crosshair';
      }} else if (modo === 'add_ptp') {{
        document.getElementById('btn-ptp').classList.add('active');
        map.getContainer().style.cursor = 'pointer';
      }}
    }}

    // CLIQUE NO MAPA (SANDBOX PARA ADICIONAR NÓS)
    map.on('click', function(e) {{
      if (modoAtual === 'add_site' || modoAtual === 'add_rep') {{
        const ehRep = modoAtual === 'add_rep';
        const prefixo = ehRep ? 'Repetidora ' : 'Antena / Sítio ';
        const num = ehRep ? contadores.rep++ : contadores.site++;
        const nome = `${{prefixo}}${{num}} (Custom)`;

        const novoSite = {{
          id: 'CUST_' + Date.now(),
          nome: nome,
          tipo: ehRep ? 'REPETIDORA' : 'ERB',
          latitude: e.latlng.lat,
          longitude: e.latlng.lng,
          altura_torre_m: ehRep ? 30.0 : 45.0,
          altitude_terreno_m: 300.0,
          fixo: false
        }};

        const mk = L.marker([e.latlng.lat, e.latlng.lng], {{
          icon: getSiteIcon(novoSite.tipo, false),
          draggable: true
        }}).addTo(map);

        mk.dados = novoSite;
        mk.bindTooltip(`<b>${{nome}}</b><br>(Arraste livremente)`, {{ direction: 'top' }});
        
        mk.on('drag', () => atualizarConexoesDoNo(mk));
        mk.on('dragend', () => {{
          novoSite.latitude = mk.getLatLng().lat;
          novoSite.longitude = mk.getLatLng().lng;
          if (enlaceSelecionado && (enlaceSelecionado.dados.origem_obj === mk.dados || enlaceSelecionado.dados.destino_obj === mk.dados)) {{
            recalcularPerfilGrafico();
          }}
        }});

        mk.on('click', () => tratarCliqueNoNo(mk));
        sitesCustom.push(mk);
        setModo('select');
      }}
    }});

    function tratarCliqueNoNo(mk) {{
      if (modoAtual === 'select') {{
        elementoSelecionado = mk;
      }} else if (modoAtual === 'add_ptp') {{
        if (!pontoOrigemPtp) {{
          pontoOrigemPtp = mk;
          mk._icon.style.filter = 'drop-shadow(0 0 8px #fff)';
        }} else {{
          if (pontoOrigemPtp !== mk) {{
            criarNovoEnlacePtP(pontoOrigemPtp, mk);
          }}
          pontoOrigemPtp._icon.style.filter = '';
          pontoOrigemPtp = null;
          setModo('select');
        }}
      }}
    }}

    function criarNovoEnlacePtP(mkA, mkB) {{
      const stA = mkA.dados;
      const stB = mkB.dados;

      const poly = L.polyline([[stA.latitude, stA.longitude], [stB.latitude, stB.longitude]], {{
        color: '#00b4ff',
        weight: 4.5,
        opacity: 0.95
      }}).addTo(map);

      poly.dados = {{
        id: 'LINK_' + Date.now(),
        origem: stA.nome,
        destino: stB.nome,
        id_origem: stA.id,
        id_destino: stB.id,
        origem_obj: stA,
        destino_obj: stB,
        mk_a: mkA,
        mk_b: mkB,
        h_torre_origem_m: stA.altura_torre_m || 45.0,
        h_torre_destino_m: stB.altura_torre_m || 45.0,
        frequencia_ghz: 11.0,
        ganho_tx_dbi: 35.0,
        ganho_rx_dbi: 35.0,
        radio_tx: 'airFiber 11FX',
        radio_rx: 'airFiber 11FX',
        channel_width_mhz: 80,
        fixo: false
      }};

      poly.on('click', (e) => {{
        L.DomEvent.stopPropagation(e);
        selecionarEnlace(poly);
      }});

      linksCustom.push(poly);
      selecionarEnlace(poly);
    }}

    function atualizarConexoesDoNo(mk) {{
      linksCustom.forEach(poly => {{
        if (poly.dados.mk_a === mk || poly.dados.mk_b === mk) {{
          poly.setLatLngs([poly.dados.mk_a.getLatLng(), poly.dados.mk_b.getLatLng()]);
        }}
      }});
    }}

    // SELEÇÃO E ABERTURA DO PAINEL INFERIOR
    function selecionarEnlace(poly) {{
      enlaceSelecionado = poly;
      elementoSelecionado = poly;

      const d = poly.dados;
      document.getElementById('bottom-drawer').style.display = 'flex';

      document.getElementById('label-enlace-nome').textContent = `${{d.origem_obj.nome}}  ➔  ${{d.destino_obj.nome}}`;
      const badge = document.getElementById('badge-tipo-enlace');
      const noteEl = document.getElementById('drawer-note');

      if (d.fixo) {{
        const rk = d.rank_solucao || 1;
        if (rk === 1) {{
          badge.textContent = '★ SOLUÇÃO #1 — MELHOR CAMINHO';
          badge.className = 'badge-rota rota-otima';
        }} else if (rk === 2) {{
          badge.textContent = 'SOLUÇÃO #2 — TORRES COMPACTAS (≤30m)';
          badge.className = 'badge-rota rota-sol2';
        }} else {{
          badge.textContent = 'SOLUÇÃO #3 — ROTA DE CONTINGÊNCIA';
          badge.className = 'badge-rota rota-sol3';
        }}
        noteEl.textContent = d.nota_solucao || '';
      }} else {{
        badge.textContent = 'ENLACE CUSTOMIZADO (LIVRE)';
        badge.className = 'badge-rota rota-custom';
        noteEl.textContent = '';
      }}

      document.getElementById('st1-nome').textContent = d.origem_obj.nome;
      document.getElementById('st1-coords').textContent = `${{d.origem_obj.latitude.toFixed(4)}}, ${{d.origem_obj.longitude.toFixed(4)}}`;
      document.getElementById('st1-h-torre').textContent = `${{d.h_torre_origem_m}} m`;

      document.getElementById('st2-nome').textContent = d.destino_obj.nome;
      document.getElementById('st2-coords').textContent = `${{d.destino_obj.latitude.toFixed(4)}}, ${{d.destino_obj.longitude.toFixed(4)}}`;
      document.getElementById('st2-h-torre').textContent = `${{d.h_torre_destino_m}} m`;

      recalcularPerfilGrafico();
    }}

    function fecharGaveta() {{
      document.getElementById('bottom-drawer').style.display = 'none';
      enlaceSelecionado = null;
    }}

    function ajustarTorre(st, delta) {{
      if (!enlaceSelecionado) return;
      if (st === 'st1') {{
        let h = (enlaceSelecionado.dados.h_torre_origem_m || 45) + delta;
        h = Math.max(10, Math.min(100, h));
        enlaceSelecionado.dados.h_torre_origem_m = h;
        document.getElementById('st1-h-torre').textContent = `${{h}} m`;
      }} else {{
        let h = (enlaceSelecionado.dados.h_torre_destino_m || 45) + delta;
        h = Math.max(10, Math.min(100, h));
        enlaceSelecionado.dados.h_torre_destino_m = h;
        document.getElementById('st2-h-torre').textContent = `${{h}} m`;
      }}
      recalcularPerfilGrafico();
    }}

    function atualizarHardware() {{
      if (!enlaceSelecionado) return;
      enlaceSelecionado.dados.ganho_tx_dbi = parseFloat(document.getElementById('st1-antena').value);
      enlaceSelecionado.dados.ganho_rx_dbi = parseFloat(document.getElementById('st2-antena').value);
      enlaceSelecionado.dados.channel_width_mhz = parseInt(document.getElementById('sel-channel-width').value);
      recalcularPerfilGrafico();
    }}

    function excluirSelecionado() {{
      if (elementoSelecionado) {{
        if (elementoSelecionado.dados && elementoSelecionado.dados.fixo) {{
          alert("Para ocultar as rotas calculadas, use as caixas de seleção no painel 'Top 3 Melhores Caminhos' à esquerda.");
          return;
        }}
        map.removeLayer(elementoSelecionado);
        if (elementoSelecionado === enlaceSelecionado) {{
          fecharGaveta();
        }}
        elementoSelecionado = null;
      }}
    }}

    // MATEMÁTICA GEODÉSICA E LINK BUDGET
    function haversineDist(lat1, lon1, lat2, lon2) {{
      const R = 6371.0;
      const dLat = (lat2 - lat1) * Math.PI / 180.0;
      const dLon = (lon2 - lon1) * Math.PI / 180.0;
      const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                Math.cos(lat1*Math.PI/180.0) * Math.cos(lat2*Math.PI/180.0) *
                Math.sin(dLon/2) * Math.sin(dLon/2);
      return R * 2.0 * Math.atan2(Math.sqrt(a), Math.sqrt(1.0 - a));
    }}

    function calcularAzimute(lat1, lon1, lat2, lon2) {{
      const p1 = lat1 * Math.PI / 180;
      const p2 = lat2 * Math.PI / 180;
      const dL = (lon2 - lon1) * Math.PI / 180;
      const y = Math.sin(dL) * Math.cos(p2);
      const x = Math.cos(p1)*Math.sin(p2) - Math.sin(p1)*Math.cos(p2)*Math.cos(dL);
      let az = Math.atan2(y, x) * 180 / Math.PI;
      return (az + 360) % 360;
    }}

    // CACHE DE ELEVAÇÃO E PERFIS REAIS EMBUTIDOS
    const cacheElev = {{}};
    function perfilEmbutido(lat1, lon1, lat2, lon2) {{
      const eq = (a, b) => Math.abs(a - b) < 1e-4;
      for (const p of PERFIS_REAIS) {{
        if (eq(p.a[0], lat1) && eq(p.a[1], lon1) && eq(p.b[0], lat2) && eq(p.b[1], lon2)) return p.elev;
        if (eq(p.a[0], lat2) && eq(p.a[1], lon2) && eq(p.b[0], lat1) && eq(p.b[1], lon1)) return p.elev.slice().reverse();
      }}
      return null;
    }}

    async function getPerfilTerreno(lat1, lon1, lat2, lon2, N=60) {{
      const emb = perfilEmbutido(lat1, lon1, lat2, lon2);
      if (emb) return emb;
      const k = `${{lat1.toFixed(3)}},${{lon1.toFixed(3)}}_${{lat2.toFixed(3)}},${{lon2.toFixed(3)}}`;
      if (cacheElev[k]) return cacheElev[k];
      const lats = [], lons = [];
      for (let i = 0; i < N; i++) {{
        lats.push(lat1 + (i / (N - 1)) * (lat2 - lat1));
        lons.push(lon1 + (i / (N - 1)) * (lon2 - lon1));
      }}
      try {{
        const url = `https://api.open-meteo.com/v1/elevation?latitude=${{lats.map(x=>x.toFixed(4)).join(',')}}&longitude=${{lons.map(x=>x.toFixed(4)).join(',')}}`;
        const resp = await fetch(url);
        const d = await resp.json();
        if (!d.elevation) return null;
        cacheElev[k] = d.elevation;
        return d.elevation;
      }} catch (err) {{
        return null;
      }}
    }}

    // ATUALIZAÇÃO DO GRÁFICO 2D NO ESTILO UBIQUITI
    async function recalcularPerfilGrafico() {{
      if (!enlaceSelecionado) return;
      const d = enlaceSelecionado.dados;
      const st1 = d.origem_obj;
      const st2 = d.destino_obj;

      const distTotal = haversineDist(st1.latitude, st1.longitude, st2.latitude, st2.longitude);
      document.getElementById('txt-dist').textContent = `${{distTotal.toFixed(2)}} km`;

      const az1 = calcularAzimute(st1.latitude, st1.longitude, st2.latitude, st2.longitude);
      document.getElementById('st1-azim-tilt').textContent = `${{az1.toFixed(0)}}° / 0.1°`;

      const h1 = d.h_torre_origem_m || 45;
      const h2 = d.h_torre_destino_m || 45;
      const gTx = d.ganho_tx_dbi || 35.0;
      const gRx = d.ganho_rx_dbi || 35.0;
      const freq = d.frequencia_ghz || 11.0;
      const bw = d.channel_width_mhz || (freq === 11.0 ? 28 : 20);
      document.getElementById('sel-channel-width').value = String(bw);

      // Link Budget
      const fspl = 92.45 + 20 * Math.log10(distTotal) + 20 * Math.log10(freq);
      const rsl = 26.0 + gTx + gRx - fspl - 1.5;
      const fadeMargin = rsl - (-73.0);

      document.getElementById('st1-rsl').textContent = `${{rsl.toFixed(1)}} dBm`;
      document.getElementById('st2-rsl').textContent = `${{rsl.toFixed(1)}} dBm`;
      document.getElementById('txt-fade-margin').textContent = `${{fadeMargin.toFixed(1)}} dB`;

      let capacityMbps = Math.round(bw * 10.5 * Math.min(1.0, Math.max(0.2, (fadeMargin / 35.0))));
      document.getElementById('txt-capacity').textContent = `${{capacityMbps}} Mbps`;

      // Relevo e Fresnel
      const elevs = await getPerfilTerreno(st1.latitude, st1.longitude, st2.latitude, st2.longitude);
      if (!elevs) {{
        const b = document.getElementById('badge-obstrucao');
        b.textContent = 'SEM DADOS DE RELEVO (API indisponível)';
        b.className = 'status-badge status-obstr';
        return;
      }}
      const N = elevs.length;
      const Re_eff = 6371.0 * (4.0/3.0) * 1000.0;

      const cota1 = elevs[0] + h1;
      const cota2 = elevs[N - 1] + h2;

      let piorFolga = 9999;
      const dadosTerreno = [];
      const dadosFresnel = [];
      const dadosLos = [];

      for (let i = 0; i < N; i++) {{
        const distKm = (i / (N - 1)) * distTotal;
        const curv = ((distKm * 1000) * ((distTotal - distKm) * 1000)) / (2 * Re_eff);
        const terr = elevs[i] + curv;
        dadosTerreno.push(terr);

        const los = cota1 + (cota2 - cota1) * (i / (N - 1));
        dadosLos.push(los);

        let f06 = 0;
        if (i > 0 && i < N - 1) {{
          f06 = 0.6 * (17.32 * Math.sqrt((distKm * (distTotal - distKm)) / (freq * distTotal)));
          const folga = los - (terr + f06);
          if (folga < piorFolga) piorFolga = folga;
        }}
        dadosFresnel.push(terr + f06);
      }}

      const obstruido = piorFolga < 0;
      const badgeObs = document.getElementById('badge-obstrucao');
      if (obstruido) {{
        badgeObs.textContent = `LINK OBSTRUÍDO (${{piorFolga.toFixed(1)}} m)`;
        badgeObs.className = 'status-badge status-obstr';
        if (!d.fixo) enlaceSelecionado.setStyle({{ color: '#ff1744' }});
      }} else {{
        badgeObs.textContent = `VISADA LIMPA (Folga +${{piorFolga.toFixed(1)}} m acima de 0.6·F1)`;
        badgeObs.className = 'status-badge status-clear';
        if (!d.fixo) enlaceSelecionado.setStyle({{ color: '#00b4ff' }});
      }}

      desenharCanvasPerfil(dadosTerreno, dadosFresnel, dadosLos, cota1, cota2, h1, h2, obstruido);
    }}

    function desenharCanvasPerfil(terr, fresnel, los, cota1, cota2, h1, h2, obstruido) {{
      const cv = document.getElementById('profileCanvas');
      const container = document.getElementById('canvas-container');
      cv.width = container.clientWidth;
      cv.height = container.clientHeight;
      const ctx = cv.getContext('2d');

      const W = cv.width;
      const H = cv.height;
      const N = terr.length;

      const minAlt = Math.min(...terr) - 20;
      const maxAlt = Math.max(...los, ...fresnel, ...terr) + 30;
      const range = maxAlt - minAlt;

      function getY(val) {{
        return H - ((val - minAlt) / range) * (H - 30) - 15;
      }}
      function getX(i) {{
        return (i / (N - 1)) * (W - 60) + 30;
      }}

      ctx.clearRect(0, 0, W, H);

      // 1. TERRENO COM GRADIENTE ESCURO
      ctx.beginPath();
      ctx.moveTo(getX(0), H);
      for (let i = 0; i < N; i++) {{
        ctx.lineTo(getX(i), getY(terr[i]));
      }}
      ctx.lineTo(getX(N - 1), H);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, '#363d52');
      grad.addColorStop(1, '#1a1c26');
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.strokeStyle = '#5a627d';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // 2. FRESNEL 0.6·F1 (Linha tracejada laranja)
      ctx.beginPath();
      ctx.setLineDash([4, 4]);
      for (let i = 0; i < N; i++) {{
        if (i === 0) ctx.moveTo(getX(i), getY(fresnel[i]));
        else ctx.lineTo(getX(i), getY(fresnel[i]));
      }}
      ctx.strokeStyle = '#ffa94d';
      ctx.lineWidth = 1.2;
      ctx.stroke();
      ctx.setLineDash([]);

      // 3. LINHA DE VISADA DIRETA
      ctx.beginPath();
      ctx.moveTo(getX(0), getY(cota1));
      ctx.lineTo(getX(N - 1), getY(cota2));
      ctx.strokeStyle = obstruido ? '#ff3838' : '#00ff55';
      ctx.lineWidth = 2.5;
      ctx.stroke();

      // 4. POSTES DAS TORRES
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(getX(0), getY(terr[0]));
      ctx.lineTo(getX(0), getY(cota1));
      ctx.moveTo(getX(N - 1), getY(terr[N - 1]));
      ctx.lineTo(getX(N - 1), getY(cota2));
      ctx.stroke();

      // Rótulos de Cota
      ctx.fillStyle = '#8a8f9d';
      ctx.font = '10px monospace';
      ctx.fillText(`${{Math.round(terr[0])}}m`, getX(0) - 25, getY(terr[0]));
      ctx.fillText(`${{Math.round(terr[N-1])}}m`, getX(N-1) + 6, getY(terr[N-1]));
    }}

    // SELECIONA O ENLACE TRONCO DE CAICÓ DA SOLUÇÃO #1 POR PADRÃO AO ABRIR
    setTimeout(() => {{
      if (camadasSolucao[1] && camadasSolucao[1].length > 0) {{
        const caicoLink = camadasSolucao[1].find(p => p.dados.distancia_km > 40) || camadasSolucao[1][0];
        selecionarEnlace(caicoLink);
      }}
    }}, 400);
  </script>
</body>
</html>
"""

caminho_saida = os.path.abspath("outputs/mapa_interativo.html")
with open(caminho_saida, "w", encoding="utf-8") as f:
    f.write(html_code)

# Cria também index.html na raiz do repositório para publicação direta no GitHub Pages
caminho_index = os.path.abspath("index.html")
with open(caminho_index, "w", encoding="utf-8") as f:
    f.write(html_code)

print("=" * 80)
print(" UISP DESIGN CENTER - VERSÃO STANDALONE (TOP 3 SOLUÇÕES) GERADA COM SUCESSO!")
print(f" Arquivo: file://{caminho_saida}")
print("=" * 80)

webbrowser.open(f"file://{caminho_saida}")
