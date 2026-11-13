"""
mapa_interativo.py - Simulador UISP Design Center + Interface Didática de Cálculos & Orçamento.
Gera outputs/mapa_interativo.html e index.html (standalone offline para GitHub Pages).
"""
import os
import json
import math
import webbrowser
import numpy as np
from src.etapa2_cobertura import calcular_balanco_potencia
from src.etapa5_topografia import elevacoes

ARQ_SITIOS = "outputs/todos_sitios.json"
ARQ_ENLACES = "outputs/enlaces_com_antenas.json"
ARQ_SOLUCOES = "outputs/solucoes_topologia.json"
ARQ_DEMANDA = "outputs/demanda_capacidade.json" if os.path.exists("outputs/demanda_capacidade.json") else "demanda_capacidade.json"
ARQ_COBERTURA = "outputs/dimensionamento_cobertura.json"
ARQ_INTERFERENCIA = "outputs/relatorio_interferencia.json"

sitios_otimos = []
enlaces_otimos = []
solucoes_topologia = []
perfis_reais = []
corredores_3d = []
demanda_dados = []
cobertura_dados = []
interferencia_dados = {}
balanco_dados = calcular_balanco_potencia()

if os.path.exists("outputs/perfis_enlaces.json"):
    with open("outputs/perfis_enlaces.json", "r", encoding="utf-8") as f:
        _perfis_full = json.load(f)
        perfis_reais = [
            {"a": [p["lat_a"], p["lon_a"]], "b": [p["lat_b"], p["lon_b"]],
             "elev": [round(v, 1) for v in p["elev"]]}
            for p in _perfis_full
        ]
        for p in _perfis_full:
            la1, lo1, la2, lo2 = p["lat_a"], p["lon_a"], p["lat_b"], p["lon_b"]
            mid_lat = 0.5 * (la1 + la2)
            mid_lon = 0.5 * (lo1 + lo2)
            m_per_lat = 111139.0
            m_per_lon = 111139.0 * math.cos(math.radians(mid_lat))
            dx = (lo2 - lo1) * m_per_lon
            dy = (la2 - la1) * m_per_lat
            dist_m = math.hypot(dx, dy)
            if dist_m < 50.0:
                continue
            ux, uy = dx / dist_m, dy / dist_m
            px, py = -uy, ux
            # Alinha i=4 exatamente em TX (-dist_m/2) e i=60 em RX (+dist_m/2) com j=16 no eixo (v=0)
            pad = (dist_m / 56.0) * 4.0
            half_w = max(2200.0, min(8000.0, dist_m * 0.22))
            nu, nv = 65, 33
            us = np.linspace(-dist_m / 2 - pad, dist_m / 2 + pad, nu)
            vs = np.linspace(-half_w, half_w, nv)
            uu, vv = np.meshgrid(us, vs)
            pts_x = uu * ux + vv * px
            pts_y = uu * uy + vv * py
            lats = mid_lat + pts_y / m_per_lat
            lons = mid_lon + pts_x / m_per_lon
            coords = list(zip(lats.ravel().tolist(), lons.ravel().tolist()))
            z = np.round(elevacoes(coords)).astype(int).reshape(nv, nu)
            corredores_3d.append({
                "a": [round(la1, 5), round(lo1, 5)],
                "b": [round(la2, 5), round(lo2, 5)],
                "w_m": round(half_w),
                "pad_m": round(pad, 2),
                "nu": nu,
                "nv": nv,
                "z": z.ravel().tolist(),
            })

if os.path.exists(ARQ_SITIOS):
    with open(ARQ_SITIOS, "r", encoding="utf-8") as f:
        sitios_otimos = json.load(f)

if os.path.exists(ARQ_ENLACES):
    with open(ARQ_ENLACES, "r", encoding="utf-8") as f:
        enlaces_otimos = json.load(f)

if os.path.exists(ARQ_SOLUCOES):
    with open(ARQ_SOLUCOES, "r", encoding="utf-8") as f:
        solucoes_topologia = json.load(f)

if os.path.exists(ARQ_DEMANDA):
    with open(ARQ_DEMANDA, "r", encoding="utf-8") as f:
        demanda_dados = json.load(f)

if os.path.exists(ARQ_COBERTURA):
    with open(ARQ_COBERTURA, "r", encoding="utf-8") as f:
        cobertura_dados = json.load(f)

if os.path.exists(ARQ_INTERFERENCIA):
    with open(ARQ_INTERFERENCIA, "r", encoding="utf-8") as f:
        interferencia_dados = json.load(f)

html_code = f"""<!DOCTYPE html>
<html lang="pt-br">
<head>
  <meta charset="UTF-8">
  <title>UISP Design Center - Projeto SMP Seridó (Backhaul, Engenharia & Orçamento)</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/three@0.128.0/build/three.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    body {{ background: #0f1117; color: #e1e4ea; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }}

    /* TOPO / HEADER UISP */
    #header {{ height: 50px; background: #161822; border-bottom: 1px solid #282b3c; display: flex; align-items: center; justify-content: space-between; padding: 0 16px; z-index: 2000; flex-shrink: 0; }}
    .logo-box {{ display: flex; align-items: center; gap: 10px; font-weight: bold; font-size: 1.02rem; color: #fff; }}
    .logo-badge {{ background: #0070f3; color: white; padding: 2px 7px; border-radius: 4px; font-size: 0.78rem; font-weight: 800; }}
    .nav-tabs {{ display: flex; gap: 8px; align-items: center; }}
    .nav-tab {{ background: #202434; border: 1px solid #323850; color: #b7bfd4; padding: 6px 14px; border-radius: 6px; font-size: 0.84rem; font-weight: 700; cursor: pointer; transition: all 0.15s; }}
    .nav-tab:hover {{ background: #2a3046; color: #fff; }}
    .nav-tab.active {{ background: #0070f3; border-color: #3291ff; color: #fff; box-shadow: 0 0 12px rgba(0, 112, 243, 0.35); }}
    .nav-tab.cob-on {{ background: rgba(14, 165, 233, 0.22); border-color: #38bdf8; color: #7dd3fc; box-shadow: 0 0 12px rgba(56, 189, 248, 0.35); }}
    .header-info {{ font-size: 0.8rem; color: #8a8f9d; display: flex; gap: 16px; align-items: center; }}
    .header-info b {{ color: #00ff55; }}

    /* ÁREA DO MAPA */
    #map-wrapper {{ flex: 1; position: relative; width: 100%; display: block; }}
    #map {{ width: 100%; height: 100%; }}

    /* BARRA DE FERRAMENTAS FLUTUANTE */
    #toolbar {{ position: absolute; top: 16px; left: 16px; background: rgba(22, 24, 34, 0.94); border: 1px solid #2d3142; border-radius: 8px; display: flex; flex-direction: column; gap: 4px; padding: 6px; z-index: 1500; box-shadow: 0 4px 16px rgba(0,0,0,0.6); }}
    .tool-btn {{ width: 42px; height: 42px; background: transparent; border: 1px solid transparent; border-radius: 6px; color: #a4a9b6; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 1.2rem; transition: all 0.2s; }}
    .tool-btn:hover {{ background: #282c3f; color: #fff; }}
    .tool-btn.active {{ background: #0070f3; color: #fff; border-color: #3291ff; }}
    .tool-sep {{ height: 1px; background: #2d3142; margin: 4px 0; }}

    /* PAINEL FLUTUANTE DAS 3 MELHORES SOLUÇÕES */
    #solutions-panel {{ position: absolute; top: 16px; left: 72px; width: 430px; max-height: calc(100vh - 90px); background: rgba(18, 20, 30, 0.95); border: 1px solid #2e3348; border-radius: 10px; z-index: 1500; box-shadow: 0 8px 28px rgba(0,0,0,0.75); display: flex; flex-direction: column; overflow: hidden; backdrop-filter: blur(8px); transition: all 0.2s ease; }}
    #solutions-panel.minimized {{ width: 290px; max-height: 44px; }}
    .sol-panel-header {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 14px; background: #161927; border-bottom: 1px solid #282d42; cursor: pointer; user-select: none; }}
    .sol-panel-title {{ font-size: 0.88rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 8px; }}
    .sol-panel-body {{ padding: 10px 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; }}
    .sol-bulk-actions {{ display: flex; gap: 6px; }}
    .bulk-btn {{ flex: 1; padding: 6px 8px; background: #222638; border: 1px solid #363c56; color: #d5d9e6; border-radius: 6px; font-size: 0.75rem; font-weight: 600; cursor: pointer; transition: all 0.15s; }}
    .bulk-btn:hover {{ background: #2e344d; color: #fff; border-color: #4f587d; }}
    .bulk-btn.primary {{ background: rgba(0, 255, 85, 0.14); border-color: #00ff55; color: #00ff55; }}
    .bulk-btn.primary:hover {{ background: rgba(0, 255, 85, 0.24); }}

    .sol-card {{ background: #171a28; border: 1px solid #2a2f45; border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; transition: all 0.15s; }}
    .sol-card.best-case {{ background: linear-gradient(180deg, rgba(0, 255, 85, 0.10) 0%, rgba(23, 26, 40, 0.95) 100%); border: 1.5px solid #00ff55; box-shadow: 0 0 14px rgba(0, 255, 85, 0.18); }}
    .sol-card.inactive {{ opacity: 0.52; }}
    .sol-card-top {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
    .sol-check-label {{ display: flex; align-items: center; gap: 8px; cursor: pointer; font-weight: 700; font-size: 0.82rem; color: #fff; }}
    .sol-check-label input[type="checkbox"] {{ width: 16px; height: 16px; cursor: pointer; accent-color: #00ff55; }}
    .sol-swatch {{ width: 14px; height: 5px; border-radius: 3px; display: inline-block; }}
    .sol-badge-best {{ background: #00ff55; color: #09130c; font-size: 0.67rem; font-weight: 900; padding: 2px 6px; border-radius: 4px; }}
    .sol-badge-alt {{ background: #262b40; color: #b5bdd0; font-size: 0.67rem; font-weight: 700; padding: 2px 6px; border-radius: 4px; }}
    .sol-metrics {{ display: flex; flex-wrap: wrap; gap: 6px; font-size: 0.73rem; color: #c5cbe0; background: #121520; padding: 5px 8px; border-radius: 5px; border: 1px solid #222638; }}
    .sol-metrics span b {{ color: #fff; }}
    .sol-note {{ font-size: 0.74rem; line-height: 1.38; color: #b8bfd4; }}
    .sol-note b {{ color: #e2e6f3; }}
    .sol-why-win {{ font-size: 0.73rem; line-height: 1.35; color: #9dfcc0; background: rgba(0, 255, 85, 0.08); border-left: 3px solid #00ff55; padding: 5px 8px; border-radius: 4px; }}
    .sol-why-lose {{ font-size: 0.72rem; line-height: 1.35; color: #ffd591; background: rgba(255, 171, 0, 0.08); border-left: 3px solid #ffab00; padding: 4px 8px; border-radius: 4px; }}

    /* GAVETA INFERIOR (RÉPLICA UISP COM FRESNEL + ABAULAMENTO) */
    #bottom-drawer {{ position: absolute; bottom: 0; left: 0; right: 0; background: rgba(16, 18, 27, 0.97); border-top: 1px solid #2c3042; backdrop-filter: blur(8px); display: none; flex-direction: column; z-index: 1600; box-shadow: 0 -8px 24px rgba(0,0,0,0.75); max-height: 420px; }}
    #drawer-header {{ display: flex; justify-content: space-between; align-items: center; padding: 6px 16px; background: #12141e; border-bottom: 1px solid #242736; font-size: 0.84rem; gap: 12px; }}
    #drawer-title {{ display: flex; align-items: center; gap: 10px; font-weight: 600; flex-wrap: wrap; }}
    .badge-rota {{ padding: 2px 8px; border-radius: 4px; font-size: 0.74rem; font-weight: bold; }}
    .rota-otima {{ background: rgba(0, 255, 85, 0.15); color: #00ff55; border: 1px solid #00ff55; }}
    .rota-sol2 {{ background: rgba(0, 212, 255, 0.15); color: #00d4ff; border: 1px solid #00d4ff; }}
    .rota-sol3 {{ background: rgba(255, 171, 0, 0.15); color: #ffab00; border: 1px solid #ffab00; }}
    .rota-custom {{ background: rgba(0, 180, 255, 0.15); color: #00b4ff; border: 1px solid #00b4ff; }}
    #drawer-note {{ font-size: 0.75rem; color: #a9b2c7; flex: 1; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .close-btn {{ cursor: pointer; background: transparent; border: none; color: #8e94a5; font-size: 1.2rem; }}
    .close-btn:hover {{ color: #fff; }}

    #drawer-body {{ display: grid; grid-template-columns: 315px 1fr 315px; gap: 12px; padding: 10px 16px; }}
    .card-station {{ background: #181a26; border: 1px solid #272a3b; border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; }}
    .card-title {{ font-size: 0.84rem; font-weight: bold; color: #fff; display: flex; justify-content: space-between; align-items: center; gap: 6px; }}
    .tower-lock-pill {{ font-size: 0.68rem; background: rgba(0, 180, 255, 0.14); color: #67d4ff; border: 1px solid rgba(0, 180, 255, 0.35); padding: 1px 6px; border-radius: 4px; font-weight: 600; }}
    .field-row {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.78rem; color: #9da3b4; }}
    .field-row select {{ background: #222534; border: 1px solid #363b52; color: #fff; padding: 3px 6px; border-radius: 4px; font-size: 0.77rem; width: 58%; }}
    .stepper {{ display: flex; align-items: center; gap: 4px; }}
    .step-btn {{ width: 24px; height: 22px; background: #282c3e; border: 1px solid #3a3f58; color: #fff; border-radius: 4px; cursor: pointer; font-weight: bold; display: flex; align-items: center; justify-content: center; }}
    .step-btn:hover {{ background: #383e58; }}
    .step-val {{ font-size: 0.84rem; color: #00ff55; font-weight: bold; width: 46px; text-align: center; }}

    .signal-box {{ margin-top: auto; padding-top: 6px; border-top: 1px solid #242738; }}
    .signal-val {{ font-size: 1.08rem; font-weight: 800; color: #00ff55; display: flex; justify-content: space-between; align-items: baseline; }}
    .signal-bar-wrap {{ height: 6px; background: #222534; border-radius: 3px; overflow: hidden; margin-top: 4px; }}
    .signal-bar-fill {{ height: 100%; width: 75%; background: linear-gradient(90deg, #ff4444, #ffbb00, #00ff55); }}

    .card-center {{ display: flex; flex-direction: column; gap: 6px; }}
    .center-top {{ display: flex; justify-content: space-between; align-items: center; background: #181a26; padding: 6px 12px; border-radius: 6px; border: 1px solid #272a3b; flex-wrap: wrap; gap: 6px; }}
    .capacity-tag {{ font-size: 0.98rem; font-weight: bold; color: #fff; display: flex; align-items: baseline; gap: 6px; }}
    .capacity-val {{ color: #3291ff; font-size: 1.18rem; font-weight: 900; }}
    .status-badge {{ font-size: 0.76rem; padding: 3px 8px; border-radius: 4px; font-weight: bold; }}
    .status-clear {{ background: rgba(0, 255, 85, 0.15); color: #00ff55; }}
    .status-obstr {{ background: rgba(255, 68, 68, 0.2); color: #ff4444; }}
    .phys-strip {{ display: flex; justify-content: space-between; align-items: center; font-size: 0.72rem; color: #9fb0c9; background: #131622; padding: 4px 10px; border-radius: 5px; border: 1px solid #23273a; flex-wrap: wrap; gap: 8px; }}
    .phys-strip b {{ color: #e2e8f0; }}

    #canvas-container {{ flex: 1; height: 185px; background: #11141e; border-radius: 6px; border: 1px solid #242736; position: relative; cursor: crosshair; }}
    canvas {{ width: 100%; height: 100%; display: block; }}
    #canvas-tooltip {{ position: absolute; display: none; pointer-events: none; background: rgba(14, 17, 26, 0.95); border: 1px solid #38bdf8; border-radius: 6px; padding: 6px 9px; font-size: 0.72rem; color: #e2e8f0; line-height: 1.45; box-shadow: 0 4px 14px rgba(0,0,0,0.6); z-index: 50; min-width: 195px; }}

    /* SEGUNDA INTERFACE: CÁLCULOS, ENGENHARIA E ORÇAMENTO */
    #calc-view {{ flex: 1; display: none; overflow-y: auto; background: #0d1017; padding: 20px 18px 60px 18px; }}
    .calc-container {{ max-width: 1760px; width: 98%; margin: 0 auto; display: flex; flex-direction: column; gap: 22px; }}
    .calc-hero {{ background: linear-gradient(135deg, #131a2b 0%, #0f172a 100%); border: 1px solid #26324d; border-radius: 12px; padding: 22px 24px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }}
    .calc-hero h1 {{ font-size: 1.45rem; color: #fff; margin-bottom: 6px; }}
    .calc-hero p {{ font-size: 0.88rem; color: #9fb0c9; max-width: 1120px; line-height: 1.45; }}
    .kpi-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(195px, 1fr)); gap: 12px; }}
    .kpi-card {{ background: #151926; border: 1px solid #252c40; border-radius: 10px; padding: 14px 16px; }}
    .kpi-card.highlight {{ border-color: #00ff55; background: linear-gradient(180deg, rgba(0,255,85,0.09) 0%, #151926 100%); }}
    .kpi-label {{ font-size: 0.74rem; color: #8b96b0; text-transform: uppercase; letter-spacing: 0.4px; margin-bottom: 6px; }}
    .kpi-value {{ font-size: 1.38rem; font-weight: 800; color: #fff; }}
    .kpi-card.highlight .kpi-value {{ color: #00ff55; }}
    .kpi-sub {{ font-size: 0.75rem; color: #9fb0c9; margin-top: 4px; }}

    .section-card {{ background: #141824; border: 1px solid #242b3d; border-radius: 12px; padding: 18px 20px; display: flex; flex-direction: column; gap: 14px; }}
    .section-title {{ font-size: 1.08rem; font-weight: 800; color: #fff; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #22293b; padding-bottom: 10px; }}
    .section-tag {{ font-size: 0.72rem; background: rgba(0, 112, 243, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); padding: 2px 8px; border-radius: 999px; font-weight: 700; }}
    .two-col {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 14px; }}
    .formula-box {{ background: #0e121b; border: 1px solid #232a3d; border-left: 3px solid #38bdf8; border-radius: 8px; padding: 12px 14px; font-size: 0.83rem; line-height: 1.55; color: #cbd5e1; }}
    .formula-box code {{ background: #1b2234; color: #7dd3fc; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}

    table.eng-table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
    table.eng-table th {{ background: #1b2132; color: #cbd5e1; text-align: left; padding: 9px 12px; border-bottom: 1px solid #2d354c; font-weight: 700; white-space: nowrap; }}
    table.eng-table td {{ padding: 9px 12px; border-bottom: 1px solid #1e2436; color: #e2e8f0; vertical-align: middle; }}
    table.eng-table tr:hover td {{ background: rgba(255,255,255,0.025); }}
    .pill-ok {{ display: inline-block; white-space: nowrap; background: rgba(0,255,85,0.14); color: #00ff55; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 0.73rem; }}
    .pill-bad {{ display: inline-block; white-space: nowrap; background: rgba(255,68,68,0.18); color: #ff6b6b; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 0.73rem; }}
    .pill-info {{ display: inline-block; white-space: nowrap; background: rgba(56,189,248,0.14); color: #38bdf8; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 0.73rem; }}
    .nowrap {{ white-space: nowrap; }}

    .budget-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); gap: 14px; }}
    .budget-card {{ background: #10141f; border: 1px solid #262e42; border-radius: 10px; padding: 16px; display: flex; flex-direction: column; gap: 8px; }}
    .budget-card.win {{ border: 1.5px solid #00ff55; background: linear-gradient(180deg, rgba(0,255,85,0.08) 0%, #10141f 100%); }}
    .budget-total {{ font-size: 1.5rem; font-weight: 900; color: #fff; }}
    .budget-card.win .budget-total {{ color: #00ff55; }}
    .budget-split {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 4px 0; }}
    .split-pill {{ background: #161d2e; border: 1px solid #26314a; border-radius: 6px; padding: 7px 9px; font-size: 0.76rem; }}
    .split-pill b {{ display: block; font-size: 0.92rem; margin-top: 2px; }}
    .ref-link {{ color: #38bdf8; text-decoration: none; font-weight: 600; }}
    .ref-link:hover {{ text-decoration: underline; color: #7dd3fc; }}
    .diagram-box {{ background: #0c1018; border: 1px solid #22293b; border-radius: 10px; padding: 14px; overflow-x: auto; }}

    /* TERCEIRA INTERFACE: VISADA 3D LATERAL (RELEVO + SATÉLITE + FRESNEL 3D) */
    .btn-3d-open {{ background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%); border: 1px solid #38bdf8; color: #fff; font-size: 0.74rem; font-weight: 800; padding: 4px 10px; border-radius: 5px; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 0.15s; box-shadow: 0 2px 8px rgba(14,165,233,0.35); }}
    .btn-3d-open:hover {{ filter: brightness(1.12); transform: translateY(-1px); }}
    #view-3d {{ flex: 1; display: none; position: relative; width: 100%; overflow: hidden; background: radial-gradient(circle at 50% 25%, #162238 0%, #090d16 100%); }}
    #canvas-3d-host {{ width: 100%; height: 100%; cursor: grab; outline: none; }}
    #canvas-3d-host:active {{ cursor: grabbing; }}
    #hud-3d {{ position: absolute; top: 14px; left: 14px; width: 390px; max-width: calc(100vw - 28px); background: rgba(14, 18, 28, 0.92); border: 1px solid #2c3550; border-radius: 10px; padding: 12px 14px; z-index: 50; display: flex; flex-direction: column; gap: 10px; backdrop-filter: blur(8px); box-shadow: 0 8px 24px rgba(0,0,0,0.65); }}
    .hud3d-title {{ font-size: 0.88rem; font-weight: 800; color: #fff; display: flex; justify-content: space-between; align-items: center; }}
    .hud3d-row {{ display: flex; flex-direction: column; gap: 4px; font-size: 0.76rem; color: #cbd5e1; }}
    .hud3d-row select {{ background: #1e2436; border: 1px solid #364160; color: #fff; padding: 6px 8px; border-radius: 6px; font-size: 0.78rem; width: 100%; }}
    .hud3d-btns {{ display: flex; flex-wrap: wrap; gap: 6px; }}
    .hud3d-btn {{ flex: 1; min-width: 95px; background: #1d2436; border: 1px solid #334060; color: #cbd5e1; padding: 6px 8px; border-radius: 6px; font-size: 0.74rem; font-weight: 700; cursor: pointer; transition: all 0.15s; text-align: center; }}
    .hud3d-btn:hover {{ background: #29334d; color: #fff; }}
    .hud3d-btn.active {{ background: rgba(0, 255, 85, 0.16); border-color: #00ff55; color: #00ff55; }}
    .hud3d-btn.sky {{ background: rgba(56, 189, 248, 0.16); border-color: #38bdf8; color: #7dd3fc; }}
    #telemetry-3d {{ position: absolute; top: 14px; right: 14px; background: rgba(14, 18, 28, 0.92); border: 1px solid #2c3550; border-radius: 10px; padding: 10px 14px; z-index: 50; font-size: 0.78rem; color: #cbd5e1; backdrop-filter: blur(8px); max-width: 390px; box-shadow: 0 8px 24px rgba(0,0,0,0.65); line-height: 1.5; }}
    #telemetry-3d b {{ color: #fff; }}
    #hint-3d {{ position: absolute; bottom: 14px; left: 50%; transform: translateX(-50%); background: rgba(14, 18, 28, 0.86); border: 1px solid #2c3550; color: #9fb0c9; padding: 6px 14px; border-radius: 999px; font-size: 0.75rem; z-index: 50; white-space: nowrap; pointer-events: none; }}
  </style>
</head>
<body>

  <!-- HEADER -->
  <div id="header">
    <div class="logo-box">
      <span class="logo-badge">UISP</span>
      <span>Projeto SMP Seridó & Backhaul Natal</span>
    </div>
    <div class="nav-tabs">
      <button class="nav-tab active" id="tab-btn-map" onclick="alternarAba('map')">🗺️ Simulador</button>
      <button class="nav-tab" id="tab-btn-calc" onclick="alternarAba('calc')">🧮 Cálculos e Orçamento</button>
      <button class="nav-tab" id="tab-btn-3d" onclick="abrirVisada3D()">🏔️ Visão 3D</button>
      <button class="nav-tab" id="header-btn-cob" onclick="alternarCoberturaSMP()" title="Ativa/desativa o raio celular de 1,808 km (8,5 km² e 3 setores de 120°) nas 9 ERBs urbanas">📡 Raio ERBs (1,81 km): OFF</button>
    </div>
    <div class="header-info">
      <span>Torres: <b>Fixa ≤ 50 m</b></span>
      <span>DEM: <b>Copernicus 30m</b></span>
    </div>
  </div>

  <!-- ABA 1: SIMULADOR & MAPA -->
  <div id="map-wrapper">
    <div id="map"></div>

    <!-- TOOLBAR FLUTUANTE -->
    <div id="toolbar">
      <button class="tool-btn active" id="btn-select" title="Mãozinha: Selecionar e Inspecionar" onclick="setModo('select')">🖐️</button>
      <button class="tool-btn" id="btn-cob" title="Mostrar/Ocultar Cobertura Celular 1.800 MHz (R=1,81 km / 3 Setores)" onclick="alternarCoberturaSMP()">📡</button>
      <button class="tool-btn" id="btn-calc-shortcut" title="Abrir Aba de Cálculos & Orçamento" onclick="alternarAba('calc')">🧮</button>
      <div class="tool-sep"></div>
      <button class="tool-btn" id="btn-site" title="Adicionar Antena / Sítio Livre" onclick="setModo('add_site')">📍</button>
      <button class="tool-btn" id="btn-rep" title="Adicionar Repetidora Livre" onclick="setModo('add_rep')">⚡</button>
      <button class="tool-btn" id="btn-ptp" title="Criar Enlace PtP (Clique Ponto 1 e depois Ponto 2)" onclick="setModo('add_ptp')">🔗</button>
      <div class="tool-sep"></div>
      <button class="tool-btn" id="btn-del" title="Excluir Elemento Selecionado" onclick="excluirSelecionado()">🗑️</button>
    </div>

    <!-- PAINEL DE CONTROLE COM 3 MELHORES SOLUÇÕES -->
    <div id="solutions-panel">
      <div class="sol-panel-header" onclick="alternarPainelSolucoes()">
        <div class="sol-panel-title">
          <span>🏆 Os 3 Melhores Caminhos (com relevo real)</span>
        </div>
        <span id="sol-panel-toggle-icon" style="color:#9da3b4; font-size:0.84rem;">▼ Minimizar</span>
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
          <span class="badge-rota rota-otima" id="badge-tipo-enlace">SOLUÇÃO #1</span>
        </div>
        <div id="drawer-note"></div>
        <button class="close-btn" onclick="fecharGaveta()">✕</button>
      </div>

      <div id="drawer-body">
        <!-- ESTAÇÃO 1 (TX) -->
        <div class="card-station">
          <div class="card-title">
            <span id="st1-nome">Estação 1</span>
            <span class="tower-lock-pill" id="st1-grau-pill">Torre fixa • 1 enlace</span>
          </div>
          <div class="field-row">
            <span>Coordenadas:</span>
            <span id="st1-coords" style="font-family: monospace; color: #fff;">-6.000, -36.000</span>
          </div>
          <div class="field-row">
            <span>Banda / Rádio:</span>
            <select id="st1-radio" onchange="atualizarHardware('st1-radio')" title="Trocar entre 11 GHz e 5 GHz recalcula a Zona de Fresnel, FSPL e chuva">
              <option value="airFiber 11FX">airFiber 11FX (11 GHz)</option>
              <option value="airFiber 5XHD">airFiber 5XHD (5 GHz)</option>
            </select>
          </div>
          <div class="field-row">
            <span>Antena / Prato:</span>
            <select id="st1-antena" onchange="atualizarHardware('antena')">
              <option value="35.0">AF-11G35 (0.9m / 35 dBi)</option>
              <option value="38.5">Dish 1.2m (38.5 dBi)</option>
              <option value="34.0">AF-5G34 (1.05m / 34 dBi)</option>
              <option value="30.0">AF-5G30 (0.65m / 30 dBi)</option>
              <option value="23.0">AF-5G23 (0.38m / 23 dBi)</option>
            </select>
          </div>
          <div class="field-row">
            <span>Altura Única Torre:</span>
            <div class="stepper">
              <button class="step-btn" onclick="ajustarTorre('st1', -5)">-</button>
              <span class="step-val" id="st1-h-torre">15 m</span>
              <button class="step-btn" onclick="ajustarTorre('st1', +5)">+</button>
            </div>
          </div>
          <div class="field-row">
            <span>Azimute / Tilt:</span>
            <span id="st1-azim-tilt" style="color: #3291ff;">45° / -0.2°</span>
          </div>
          <div class="signal-box">
            <div class="signal-val">
              <span style="font-size: 0.78rem; color: #9da3b4;">Sinal Esperado (RSL):</span>
              <span id="st1-rsl">-41 dBm</span>
            </div>
            <div class="signal-bar-wrap">
              <div class="signal-bar-fill" id="st1-signal-bar"></div>
            </div>
          </div>
        </div>

        <!-- CENTRO: GRÁFICO COM FRESNEL ELÍPTICO E ABAULAMENTO -->
        <div class="card-center">
          <div class="center-top">
            <div class="capacity-tag">
              <span>Throughput:</span>
              <span class="capacity-val" id="txt-capacity">240 Mbps</span>
            </div>
            <div style="font-size: 0.82rem; color: #a4a9b6;">
              Distância: <b id="txt-dist" style="color: #fff;">32.5 km</b> | 
              Largura Canal: 
              <select id="sel-channel-width" style="background: #242738; color: #00ff55; border: 1px solid #363b52; border-radius: 4px; padding: 2px 4px;" onchange="atualizarHardware('canal')" title="Altera a largura do canal em MHz (capacidade/Throughput). Para recalcular Fresnel, troque a Banda/Rádio (5 GHz vs 11 GHz).">
                <option value="20">20 MHz (5G)</option>
                <option value="28" selected>28 MHz (ANATEL 11G)</option>
                <option value="40">40 MHz</option>
                <option value="56">56 MHz (ANATEL 11G)</option>
                <option value="80">80 MHz (5G)</option>
              </select>
            </div>
            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
              <div class="status-badge status-clear" id="badge-obstrucao">VISADA LIMPA</div>
              <button class="btn-3d-open" onclick="abrirVisada3D()" title="Visualizar este enlace em 3D com relevo real, torres e elipse de Fresnel de lado">🏔️ Ver em 3D (De Lado)</button>
            </div>
          </div>

          <div class="phys-strip">
            <span>🌍 Abaulamento (k=4/3): <b id="txt-abaulamento">+0.0 m</b> no centro</span>
            <span>🔵 Elipse 1ª Fresnel: <b id="txt-fresnel-r1">0.0 m</b> (60%: <b id="txt-fresnel-06">0.0 m</b>)</span>
            <span>🌧️ Chuva 50 mm/h: <b id="txt-chuva-loss">-0.0 dB</b></span>
          </div>

          <div id="canvas-container">
            <canvas id="profileCanvas"></canvas>
            <div id="canvas-tooltip"></div>
          </div>
        </div>

        <!-- ESTAÇÃO 2 (RX) -->
        <div class="card-station">
          <div class="card-title">
            <span id="st2-nome">Estação 2</span>
            <span class="tower-lock-pill" id="st2-grau-pill">Torre fixa • 1 enlace</span>
          </div>
          <div class="field-row">
            <span>Coordenadas:</span>
            <span id="st2-coords" style="font-family: monospace; color: #fff;">-6.000, -36.000</span>
          </div>
          <div class="field-row">
            <span>Banda / Rádio:</span>
            <select id="st2-radio" onchange="atualizarHardware('st2-radio')" title="Trocar entre 11 GHz e 5 GHz recalcula a Zona de Fresnel, FSPL e chuva">
              <option value="airFiber 11FX">airFiber 11FX (11 GHz)</option>
              <option value="airFiber 5XHD">airFiber 5XHD (5 GHz)</option>
            </select>
          </div>
          <div class="field-row">
            <span>Antena / Prato:</span>
            <select id="st2-antena" onchange="atualizarHardware('antena')">
              <option value="35.0">AF-11G35 (0.9m / 35 dBi)</option>
              <option value="38.5">Dish 1.2m (38.5 dBi)</option>
              <option value="34.0">AF-5G34 (1.05m / 34 dBi)</option>
              <option value="30.0">AF-5G30 (0.65m / 30 dBi)</option>
              <option value="23.0">AF-5G23 (0.38m / 23 dBi)</option>
            </select>
          </div>
          <div class="field-row">
            <span>Altura Única Torre:</span>
            <div class="stepper">
              <button class="step-btn" onclick="ajustarTorre('st2', -5)">-</button>
              <span class="step-val" id="st2-h-torre">15 m</span>
              <button class="step-btn" onclick="ajustarTorre('st2', +5)">+</button>
            </div>
          </div>
          <div class="field-row">
            <span>Fade Margin (Limpo / Chuva):</span>
            <b id="txt-fade-margin" style="color: #00ff55;">32.1 dB / 20.0 dB</b>
          </div>
          <div class="signal-box">
            <div class="signal-val">
              <span style="font-size: 0.78rem; color: #9da3b4;">Sinal Esperado (RSL):</span>
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

  <!-- ABA 2: CÁLCULOS, CHUVA & ORÇAMENTO (APRESENTAÇÃO EM SALA) -->
  <div id="calc-view">
    <div class="calc-container" id="calc-content"></div>
  </div>

  <!-- ABA 3: VISADA 3D LATERAL (RELEVO COPERNICUS 30M + SATÉLITE + FRESNEL 3D) -->
  <div id="view-3d">
    <div id="canvas-3d-host"></div>
    <div id="hud-3d">
      <div class="hud3d-title">
        <span>🏔️ Visada 3D — Relevo Copernicus 30m</span>
        <button class="hud3d-btn" style="flex:0; min-width:auto; padding:4px 10px;" onclick="alternarAba('map')">⬅️ Mapa</button>
      </div>
      <div class="hud3d-row">
        <label for="sel-link-3d"><b>Enlace visualizado:</b></label>
        <select id="sel-link-3d" onchange="selecionarLink3D(this.value)"></select>
      </div>
      <div class="hud3d-row">
        <span><b>Ângulo de Câmera:</b></span>
        <div class="hud3d-btns">
          <button class="hud3d-btn active" id="cam-btn-side" onclick="definirCamera3D('side')">📐 De Lado</button>
          <button class="hud3d-btn" id="cam-btn-aerial" onclick="definirCamera3D('aerial')">🚁 Aérea 3/4</button>
          <button class="hud3d-btn" id="cam-btn-tx" onclick="definirCamera3D('tx')">🗼 Torre TX→RX</button>
        </div>
      </div>
      <div class="hud3d-row">
        <div style="display:flex; justify-content:space-between;">
          <span><b>Aumento Vertical (altura x distância):</b></span>
          <b id="lbl-exag-3d" style="color:#38bdf8;">8×</b>
        </div>
        <input type="range" id="rng-exag-3d" min="1" max="20" step="1" value="8" oninput="atualizarExagero3D(this.value)" style="accent-color:#38bdf8; cursor:pointer;" />
      </div>
      <div class="hud3d-btns">
        <button class="hud3d-btn sky" id="btn-3d-sat" onclick="alternarCamadaSatelite3D()">🛰️ Satélite: ON</button>
        <button class="hud3d-btn active" id="btn-3d-fresnel" onclick="alternarFresnel3D()">🔵 Fresnel: ON</button>
        <button class="hud3d-btn active" id="btn-3d-bulge" onclick="alternarCurvatura3D()">🌍 Terra k=4/3: ON</button>
      </div>
    </div>
    <div id="telemetry-3d">Selecione um enlace para ver o relevo 3D lateral.</div>
    <div id="hint-3d">Arraste (esq.): Girar 3D • Botão direito / Shift+arraste: Mover • Scroll: Zoom</div>
  </div>

  <script>
    // DADOS INJETADOS DO MOTOR PYTHON
    const SITIOS_FIXOS = {json.dumps(sitios_otimos, ensure_ascii=False)};
    const ENLACES_FIXOS = {json.dumps(enlaces_otimos, ensure_ascii=False)};
    const SOLUCOES = {json.dumps(solucoes_topologia, ensure_ascii=False)};
    const PERFIS_REAIS = {json.dumps(perfis_reais)};
    const CORREDORES_3D = {json.dumps(corredores_3d)};
    const DEMANDA_SMP = {json.dumps(demanda_dados, ensure_ascii=False)};
    const COBERTURA_SMP = {json.dumps(cobertura_dados, ensure_ascii=False)};
    const INTERFERENCIA_SMP = {json.dumps(interferencia_dados, ensure_ascii=False)};
    const BALANCO_SMP = {json.dumps(balanco_dados, ensure_ascii=False)};

    // Mapa de altura física ÚNICA e FIXA por solução e ID de sítio: ALTURAS_SOL[rk][siteId]
    const ALTURAS_SOL = {{}};
    const GRAU_SOL = {{}};
    SOLUCOES.forEach(sol => {{
      ALTURAS_SOL[sol.rank] = {{ ...(sol.alturas_fixas_torres || {{}}) }};
      GRAU_SOL[sol.rank] = {{}};
      sol.enlaces.forEach(l => {{
        GRAU_SOL[sol.rank][l.id_origem] = (GRAU_SOL[sol.rank][l.id_origem] || 0) + 1;
        GRAU_SOL[sol.rank][l.id_destino] = (GRAU_SOL[sol.rank][l.id_destino] || 0) + 1;
      }});
    }});

    let modoAtual = 'select';
    let pontoOrigemPtp = null;
    let enlaceSelecionado = null;
    let elementoSelecionado = null;
    let coberturaVisivel = false;
    let camadaCoberturaSMP = L.layerGroup();

    let sitesCustom = [];
    let linksCustom = [];
    let contadores = {{ site: 1, rep: 1 }};

    const solucaoAtiva = {{ 1: true, 2: false, 3: false }};
    const camadasSolucao = {{ 1: [], 2: [], 3: [] }};
    const marcadoresFixos = {{}};

    // Estado do último desenho no canvas para tooltip interativo
    let ultimoPerfilCanvas = null;

    // ALTERNÂNCIA DE ABAS (MAPA <-> CÁLCULOS/ORÇAMENTO <-> VISADA 3D)
    function alternarAba(aba) {{
      const mapWrap = document.getElementById('map-wrapper');
      const calcView = document.getElementById('calc-view');
      const view3d = document.getElementById('view-3d');
      const btnMap = document.getElementById('tab-btn-map');
      const btnCalc = document.getElementById('tab-btn-calc');
      const btn3d = document.getElementById('tab-btn-3d');

      mapWrap.style.display = 'none';
      calcView.style.display = 'none';
      view3d.style.display = 'none';
      btnMap.classList.remove('active');
      btnCalc.classList.remove('active');
      if (btn3d) btn3d.classList.remove('active');

      if (aba === 'calc') {{
        calcView.style.display = 'block';
        btnCalc.classList.add('active');
        renderizarPainelCalculos();
      }} else if (aba === '3d') {{
        view3d.style.display = 'block';
        if (btn3d) btn3d.classList.add('active');
        redimensionarCena3D();
      }} else {{
        mapWrap.style.display = 'block';
        btnMap.classList.add('active');
        setTimeout(() => map.invalidateSize(), 100);
      }}
    }}

    // INICIALIZAÇÃO DO MAPA LEAFLET
    const map = L.map('map', {{
      center: [-6.25, -36.20],
      zoom: 9,
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
      let cor = '#00e5ff';
      let border = '#ffffff';
      let raio = 8;

      if (tipo.includes('CCC')) {{
        cor = '#ff1744';
        raio = 11;
      }} else if (tipo.includes('REPETIDORA')) {{
        if (solucoesDoNo.includes(1)) {{
          cor = '#00ff55';
          raio = 10;
        }} else if (solucoesDoNo.includes(2)) {{
          cor = '#00d4ff';
          raio = 9;
        }} else {{
          cor = '#ffab00';
          raio = 9;
        }}
      }}
      if (!fixo) border = '#00ff55';

      return L.divIcon({{
        className: 'custom-site-marker',
        html: `<div style="width: ${{raio*2}}px; height: ${{raio*2}}px; background: ${{cor}}; border: 2px solid ${{border}}; border-radius: 50%; box-shadow: 0 0 10px ${{cor}};"></div>`,
        iconSize: [raio*2, raio*2],
        iconAnchor: [raio, raio]
      }});
    }}

    function tooltipDoSitio(s) {{
      const sols = s.solucoes || [1];
      const rkRef = solucaoAtiva[1] && sols.includes(1) ? 1 : (solucaoAtiva[2] && sols.includes(2) ? 2 : (sols[0] || 1));
      const hAtual = (ALTURAS_SOL[rkRef] && ALTURAS_SOL[rkRef][s.id]) || s.altura_torre_m;
      const grau = (GRAU_SOL[rkRef] && GRAU_SOL[rkRef][s.id]) || 1;
      const tagSols = s.tipo.includes('REPETIDORA') ? `<br>Usada na(s) Solução(ões): <b>#${{sols.join(', #')}}</b>` : '';
      const cotaTerr = Number.isFinite(Number(s.altitude_terreno_m)) ? Number(s.altitude_terreno_m).toFixed(1) : s.altitude_terreno_m;
      return `<b>${{s.nome}}</b><br>Torre fixa (Sol. #${{rkRef}}): <b>${{hAtual}} m</b> (${{grau}} enlace(s))<br>Cota terreno: ${{cotaTerr}} m${{tagSols}}`;
    }}

    const dictSitiosFixos = {{}};
    SITIOS_FIXOS.forEach(s => {{
      dictSitiosFixos[s.id] = s;
      const sols = s.solucoes || [1];
      const mk = L.marker([s.latitude, s.longitude], {{
        icon: getSiteIcon(s.tipo, true, sols)
      }}).addTo(map);

      mk.dados = {{ ...s, fixo: true, solucoes: sols }};
      mk.bindTooltip(tooltipDoSitio(s), {{ direction: 'top' }});
      mk.on('click', () => tratarCliqueNoNo(mk));
      marcadoresFixos[s.id] = mk;
    }});

    // CAMADA DE COBERTURA CELULAR SMP 1800 MHz (R = 1.808 km, 3 Setores de 120°)
    function construirCoberturaSMP() {{
      camadaCoberturaSMP.clearLayers();
      SITIOS_FIXOS.filter(s => s.raio_celula_km > 0).forEach(s => {{
        const R_m = s.raio_celula_km * 1000.0;
        const circle = L.circle([s.latitude, s.longitude], {{
          radius: R_m,
          color: '#38bdf8',
          weight: 2.0,
          fillColor: '#0ea5e9',
          fillOpacity: 0.17,
          dashArray: '6, 5'
        }}).addTo(camadaCoberturaSMP);

        circle.bindTooltip(
          `<b>${{s.nome}}</b><br>Cobertura SMP 1.800 MHz (Cluster 4×3)<br>Raio: <b>${{s.raio_celula_km.toFixed(3)}} km</b> | Área: <b>8,5 km²</b> | 3 setores de 120°`,
          {{ sticky: true }}
        );

        // Desenha os 3 raios divisores de setores (0°, 120°, 240°)
        [0, 120, 240].forEach(ang => {{
          const rad = ang * Math.PI / 180.0;
          const dLat = (s.raio_celula_km * Math.cos(rad)) / 111.139;
          const dLon = (s.raio_celula_km * Math.sin(rad)) / (111.139 * Math.cos(s.latitude * Math.PI / 180.0));
          L.polyline([[s.latitude, s.longitude], [s.latitude + dLat, s.longitude + dLon]], {{
            color: '#7dd3fc', weight: 1.3, opacity: 0.72
          }}).addTo(camadaCoberturaSMP);
        }});

        // Etiqueta compacta do raio na borda norte da célula
        const dLatLabel = (s.raio_celula_km * 0.65) / 111.139;
        L.marker([s.latitude + dLatLabel, s.longitude], {{
          interactive: false,
          icon: L.divIcon({{
            className: 'smp-radius-tag',
            html: `<div style="background:rgba(12,18,32,0.86); border:1px solid #38bdf8; color:#7dd3fc; font-size:10px; font-weight:700; padding:1px 5px; border-radius:4px; white-space:nowrap; transform:translate(-50%,-50%);">R=${{s.raio_celula_km.toFixed(2)}} km</div>`,
            iconSize: [0, 0]
          }})
        }}).addTo(camadaCoberturaSMP);
      }});
    }}
    construirCoberturaSMP();

    function alternarCoberturaSMP() {{
      coberturaVisivel = !coberturaVisivel;
      document.getElementById('btn-cob').classList.toggle('active', coberturaVisivel);
      const hdrBtn = document.getElementById('header-btn-cob');
      if (hdrBtn) {{
        hdrBtn.classList.toggle('cob-on', coberturaVisivel);
        hdrBtn.textContent = coberturaVisivel
          ? '📡 Raio ERBs (1,81 km): ON'
          : '📡 Raio ERBs (1,81 km): OFF';
      }}
      if (coberturaVisivel) {{
        alternarAba('map');
        camadaCoberturaSMP.addTo(map);
      }} else {{
        map.removeLayer(camadaCoberturaSMP);
      }}
    }}

    // RENDERIZAÇÃO DAS 3 SOLUÇÕES
    const estiloPorRank = {{
      1: {{ color: '#00ff55', weight: 5.5, opacity: 0.98, dashArray: null }},
      2: {{ color: '#00d4ff', weight: 3.5, opacity: 0.88, dashArray: '8, 6' }},
      3: {{ color: '#ffab00', weight: 3.5, opacity: 0.88, dashArray: '3, 7' }},
    }};

    function tooltipDoEnlace(poly) {{
      const d = poly.dados;
      const rk = d.rank_solucao;
      const hA = ALTURAS_SOL[rk] ? ALTURAS_SOL[rk][d.id_origem] : d.h_torre_origem_m;
      const hB = ALTURAS_SOL[rk] ? ALTURAS_SOL[rk][d.id_destino] : d.h_torre_destino_m;
      return `<b>[Solução #${{rk}}] ${{d.origem}} ⇄ ${{d.destino}}</b><br>` +
             `Dist: ${{d.distancia_km}} km (${{d.frequencia_ghz}} GHz) | Torres fixas: <b>${{hA}}m / ${{hB}}m</b><br>` +
             `Folga Fresnel (60% + k=4/3): +${{d.folga_fresnel_m}}m | Chuva 50mm/h: -${{d.atenuacao_chuva_50mmh_db || 0}} dB`;
    }}

    [...SOLUCOES].sort((a, b) => b.rank - a.rank).forEach(sol => {{
      const rk = sol.rank;
      const est = estiloPorRank[rk] || estiloPorRank[1];

      sol.enlaces.forEach(l => {{
        const stA = dictSitiosFixos[l.id_origem];
        const stB = dictSitiosFixos[l.id_destino];
        if (!stA || !stB) return;

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
        }});
        if (solucaoAtiva[rk]) poly.addTo(map);

        poly.dados = {{
          ...l,
          rank_solucao: rk,
          nome_solucao: sol.titulo,
          nota_solucao: sol.nota_curta,
          fixo: true,
          origem_obj: stA,
          destino_obj: stB
        }};

        poly.bindTooltip(tooltipDoEnlace(poly), {{ sticky: true }});
        poly.on('click', (e) => {{
          L.DomEvent.stopPropagation(e);
          selecionarEnlace(poly);
        }});

        camadasSolucao[rk].push(poly);
      }});
    }});

    function formatarBRL(val) {{
      return Number(val || 0).toLocaleString('pt-BR', {{ style: 'currency', currency: 'BRL' }});
    }}

    // CARTÕES DAS 3 SOLUÇÕES
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

        const capex = sol.orcamento ? formatarBRL(sol.orcamento.custo_total_capex_brl) : '—';

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
            <span>Dist: <b>${{sol.distancia_total_km}} km</b></span>
            <span>Torre Máx: <b>${{sol.altura_max_torre_m}} m</b></span>
            <span>CAPEX: <b>${{capex}}</b></span>
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

      if (solucaoAtiva[1]) {{
        camadasSolucao[1].forEach(poly => poly.bringToFront());
      }}

      Object.values(marcadoresFixos).forEach(mk => {{
        const sols = mk.dados.solucoes || [1, 2, 3];
        const algumAtivo = sols.some(r => solucaoAtiva[r]);
        if (algumAtivo) {{
          if (!map.hasLayer(mk)) mk.addTo(map);
          mk.setTooltipContent(tooltipDoSitio(mk.dados));
        }} else {{
          if (map.hasLayer(mk)) map.removeLayer(mk);
        }}
      }});
    }}

    function alternarSolucao(rk, estado) {{
      solucaoAtiva[rk] = estado;
      atualizarVisibilidadeMapa();
      if (estado && camadasSolucao[rk].length > 0) {{
        const linkDestaque = camadasSolucao[rk].find(p => p.dados.distancia_km > 40) || camadasSolucao[rk][0];
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
    atualizarVisibilidadeMapa();

    // TOOLBAR
    function setModo(modo) {{
      modoAtual = modo;
      document.querySelectorAll('#toolbar .tool-btn').forEach(b => {{
        if (b.id !== 'btn-cob' && b.id !== 'btn-calc-shortcut') b.classList.remove('active');
      }});
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
          altura_torre_m: 30.0,
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
          if (pontoOrigemPtp !== mk) criarNovoEnlacePtP(pontoOrigemPtp, mk);
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
        color: '#00b4ff', weight: 4.5, opacity: 0.95
      }}).addTo(map);

      poly.dados = {{
        id: 'LINK_' + Date.now(),
        origem: stA.nome, destino: stB.nome,
        id_origem: stA.id, id_destino: stB.id,
        origem_obj: stA, destino_obj: stB,
        mk_a: mkA, mk_b: mkB,
        h_torre_origem_m: stA.altura_torre_m || 30.0,
        h_torre_destino_m: stB.altura_torre_m || 30.0,
        frequencia_ghz: 11.0,
        potencia_tx_dbm: 30.0,
        sensibilidade_dbm: -73.0,
        ganho_tx_dbi: 35.0,
        ganho_rx_dbi: 35.0,
        radio_utilizado: 'airFiber 11FX',
        channel_width_mhz: 28,
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
          badge.textContent = 'SOLUÇÃO #2 — SALTOS ≤ 56 KM (11 GHz)';
          badge.className = 'badge-rota rota-sol2';
        }} else {{
          badge.textContent = 'SOLUÇÃO #3 — CONTINGÊNCIA';
          badge.className = 'badge-rota rota-sol3';
        }}
        noteEl.textContent = d.nota_solucao || '';

        const hA = ALTURAS_SOL[rk][d.id_origem] ?? d.h_torre_origem_m;
        const hB = ALTURAS_SOL[rk][d.id_destino] ?? d.h_torre_destino_m;
        const gA = GRAU_SOL[rk][d.id_origem] || 1;
        const gB = GRAU_SOL[rk][d.id_destino] || 1;
        document.getElementById('st1-h-torre').textContent = `${{hA}} m`;
        document.getElementById('st2-h-torre').textContent = `${{hB}} m`;
        document.getElementById('st1-grau-pill').textContent = `Torre fixa • ${{gA}} enlace(s)`;
        document.getElementById('st2-grau-pill').textContent = `Torre fixa • ${{gB}} enlace(s)`;
      }} else {{
        badge.textContent = 'ENLACE CUSTOMIZADO (LIVRE)';
        badge.className = 'badge-rota rota-custom';
        noteEl.textContent = '';
        document.getElementById('st1-h-torre').textContent = `${{d.h_torre_origem_m}} m`;
        document.getElementById('st2-h-torre').textContent = `${{d.h_torre_destino_m}} m`;
        document.getElementById('st1-grau-pill').textContent = `Torre custom`;
        document.getElementById('st2-grau-pill').textContent = `Torre custom`;
      }}

      // Sincroniza Rádio, Antena e Largura de Canal com os dados reais
      const rad = d.radio_utilizado || (d.frequencia_ghz === 5.0 ? 'airFiber 5XHD' : 'airFiber 11FX');
      document.getElementById('st1-radio').value = rad;
      document.getElementById('st2-radio').value = rad;
      document.getElementById('st1-antena').value = Number(d.ganho_tx_dbi || 35.0).toFixed(1);
      document.getElementById('st2-antena').value = Number(d.ganho_rx_dbi || 35.0).toFixed(1);

      if (!d.channel_width_mhz) {{
        d.channel_width_mhz = (d.frequencia_ghz === 5.0) ? (d.distancia_km > 20 ? 40 : 20) : 28;
      }}
      document.getElementById('sel-channel-width').value = String(d.channel_width_mhz);

      document.getElementById('st1-nome').textContent = d.origem_obj.nome;
      document.getElementById('st1-coords').textContent = `${{d.origem_obj.latitude.toFixed(4)}}, ${{d.origem_obj.longitude.toFixed(4)}}`;
      document.getElementById('st2-nome').textContent = d.destino_obj.nome;
      document.getElementById('st2-coords').textContent = `${{d.destino_obj.latitude.toFixed(4)}}, ${{d.destino_obj.longitude.toFixed(4)}}`;

      recalcularPerfilGrafico();
    }}

    function fecharGaveta() {{
      document.getElementById('bottom-drawer').style.display = 'none';
      enlaceSelecionado = null;
    }}

    // ALTERAR ALTURA DA TORRE: ATUALIZA A TORRE ÚNICA EM TODOS OS ENLACES CONECTADOS NA SOLUÇÃO!
    function ajustarTorre(st, delta) {{
      if (!enlaceSelecionado) return;
      const d = enlaceSelecionado.dados;
      const siteId = (st === 'st1') ? d.id_origem : d.id_destino;

      if (d.fixo) {{
        const rk = d.rank_solucao;
        let h = (ALTURAS_SOL[rk][siteId] || 15) + delta;
        h = Math.max(10, Math.min(50, h));
        ALTURAS_SOL[rk][siteId] = h;

        // Propaga a altura única da torre para todos os enlaces ligados a ela nessa solução
        camadasSolucao[rk].forEach(p => {{
          if (p.dados.id_origem === siteId) p.dados.h_torre_origem_m = h;
          if (p.dados.id_destino === siteId) p.dados.h_torre_destino_m = h;
          p.setTooltipContent(tooltipDoEnlace(p));
        }});

        if (marcadoresFixos[siteId]) {{
          marcadoresFixos[siteId].setTooltipContent(tooltipDoSitio(marcadoresFixos[siteId].dados));
        }}
        document.getElementById(st === 'st1' ? 'st1-h-torre' : 'st2-h-torre').textContent = `${{h}} m`;
      }} else {{
        let h = ((st === 'st1' ? d.h_torre_origem_m : d.h_torre_destino_m) || 30) + delta;
        h = Math.max(10, Math.min(100, h));
        if (st === 'st1') {{
          d.h_torre_origem_m = h;
          document.getElementById('st1-h-torre').textContent = `${{h}} m`;
        }} else {{
          d.h_torre_destino_m = h;
          document.getElementById('st2-h-torre').textContent = `${{h}} m`;
        }}
      }}
      recalcularPerfilGrafico();
    }}

    function atualizarHardware(origem='st1-radio') {{
      if (!enlaceSelecionado) return;
      const d = enlaceSelecionado.dados;
      const rad = document.getElementById(origem === 'st2-radio' ? 'st2-radio' : 'st1-radio').value;
      document.getElementById('st1-radio').value = rad;
      document.getElementById('st2-radio').value = rad;
      d.radio_utilizado = rad;
      d.frequencia_ghz = rad.includes('5XHD') ? 5.0 : 11.0;

      // Ao trocar a banda do rádio (11 GHz <-> 5 GHz), ajusta automaticamente antenas e canal compatíveis e recalcula Fresnel
      if (origem === 'st1-radio' || origem === 'st2-radio') {{
        const ant5 = ['23.0', '30.0', '34.0'];
        const ant11 = ['35.0', '38.5'];
        const a1 = document.getElementById('st1-antena');
        const a2 = document.getElementById('st2-antena');
        if (d.frequencia_ghz === 5.0) {{
          const padrao5 = d.distancia_km > 35 ? '34.0' : (d.distancia_km > 10 ? '30.0' : '23.0');
          if (!ant5.includes(a1.value)) a1.value = padrao5;
          if (!ant5.includes(a2.value)) a2.value = padrao5;
          document.getElementById('sel-channel-width').value = d.distancia_km > 20 ? '40' : '20';
        }} else {{
          const padrao11 = d.distancia_km > 40 ? '38.5' : '35.0';
          if (!ant11.includes(a1.value)) a1.value = padrao11;
          if (!ant11.includes(a2.value)) a2.value = padrao11;
          document.getElementById('sel-channel-width').value = '28';
        }}
      }}

      d.ganho_tx_dbi = parseFloat(document.getElementById('st1-antena').value);
      d.ganho_rx_dbi = parseFloat(document.getElementById('st2-antena').value);
      d.potencia_tx_dbm = d.frequencia_ghz === 5.0 ? (d.ganho_tx_dbi >= 34 ? 28.0 : 26.0) : 30.0;
      d.sensibilidade_dbm = d.frequencia_ghz === 5.0 ? (d.ganho_rx_dbi >= 34 ? -76.0 : -74.0) : -73.0;
      d.channel_width_mhz = parseInt(document.getElementById('sel-channel-width').value);
      if (d.fixo) enlaceSelecionado.setTooltipContent(tooltipDoEnlace(enlaceSelecionado));
      recalcularPerfilGrafico();
    }}

    function excluirSelecionado() {{
      if (elementoSelecionado) {{
        if (elementoSelecionado.dados && elementoSelecionado.dados.fixo) {{
          alert("Para ocultar as rotas calculadas, use as caixas de seleção no painel 'Melhores Caminhos Mapeados' à esquerda.");
          return;
        }}
        map.removeLayer(elementoSelecionado);
        if (elementoSelecionado === enlaceSelecionado) fecharGaveta();
        elementoSelecionado = null;
      }}
    }}

    // GEODESIA & CHUVA ITU-R P.838-3
    function haversineDist(lat1, lon1, lat2, lon2) {{
      const R = 6371.0;
      const dLat = (lat2 - lat1) * Math.PI / 180.0;
      const dLon = (lon2 - lon1) * Math.PI / 180.0;
      const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180.0)*Math.cos(lat2*Math.PI/180.0)*Math.sin(dLon/2)**2;
      return R * 2.0 * Math.atan2(Math.sqrt(a), Math.sqrt(1.0 - a));
    }}

    function calcularAzimute(lat1, lon1, lat2, lon2) {{
      const p1 = lat1 * Math.PI / 180, p2 = lat2 * Math.PI / 180, dL = (lon2 - lon1) * Math.PI / 180;
      const y = Math.sin(dL) * Math.cos(p2);
      const x = Math.cos(p1)*Math.sin(p2) - Math.sin(p1)*Math.cos(p2)*Math.cos(dL);
      return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
    }}

    function atenuacaoChuvaITUR(distKm, freqGhz, chuvaMmH=50.0) {{
      const k = freqGhz <= 6.0 ? 0.000216 : 0.01772;
      const alpha = freqGhz <= 6.0 ? 1.44 : 1.214;
      const gammaR = k * Math.pow(chuvaMmH, alpha);
      const d0 = 35.0 * Math.exp(-0.015 * chuvaMmH);
      const lEff = distKm / (1.0 + distKm / d0);
      return gammaR * lEff;
    }}

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

    async function recalcularPerfilGrafico() {{
      if (!enlaceSelecionado) return;
      const d = enlaceSelecionado.dados;
      const st1 = d.origem_obj;
      const st2 = d.destino_obj;

      const distTotal = haversineDist(st1.latitude, st1.longitude, st2.latitude, st2.longitude);
      document.getElementById('txt-dist').textContent = `${{distTotal.toFixed(2)}} km`;

      const az1 = calcularAzimute(st1.latitude, st1.longitude, st2.latitude, st2.longitude);
      document.getElementById('st1-azim-tilt').textContent = `${{az1.toFixed(0)}}° / 0.1°`;

      const h1 = d.fixo ? (ALTURAS_SOL[d.rank_solucao][d.id_origem] ?? d.h_torre_origem_m) : (d.h_torre_origem_m || 30);
      const h2 = d.fixo ? (ALTURAS_SOL[d.rank_solucao][d.id_destino] ?? d.h_torre_destino_m) : (d.h_torre_destino_m || 30);
      const gTx = d.ganho_tx_dbi || 35.0;
      const gRx = d.ganho_rx_dbi || 35.0;
      const freq = d.frequencia_ghz || 11.0;
      const pTx = d.potencia_tx_dbm || (freq === 5.0 ? (gTx >= 34 ? 28.0 : 26.0) : 30.0);
      const sens = d.sensibilidade_dbm || (freq === 5.0 ? (gRx >= 34 ? -76.0 : -74.0) : -73.0);
      const bw = d.channel_width_mhz || (freq === 11.0 ? 28 : 20);

      // Link Budget + Chuva
      const fspl = 92.45 + 20 * Math.log10(Math.max(0.1, distTotal)) + 20 * Math.log10(freq);
      const rsl = pTx + gTx + gRx - fspl - 1.5;
      const fadeMargin = rsl - sens;
      const perdaChuva = atenuacaoChuvaITUR(distTotal, freq, 50.0);
      const fadeChuva = fadeMargin - perdaChuva;

      document.getElementById('st1-rsl').textContent = `${{rsl.toFixed(1)}} dBm`;
      document.getElementById('st2-rsl').textContent = `${{rsl.toFixed(1)}} dBm`;
      const fmEl = document.getElementById('txt-fade-margin');
      fmEl.textContent = `${{fadeMargin.toFixed(1)}} dB / ${{fadeChuva.toFixed(1)}} dB`;
      fmEl.style.color = fadeChuva >= 4.0 ? '#00ff55' : '#ffab00';

      const pctSig = Math.max(15, Math.min(100, (rsl + 85) * 2.2));
      document.getElementById('st1-signal-bar').style.width = `${{pctSig}}%`;
      document.getElementById('st2-signal-bar').style.width = `${{pctSig}}%`;

      const capacityMbps = Math.round(bw * 8.6 * Math.min(1.0, Math.max(0.35, fadeMargin / 26.0)));
      document.getElementById('txt-capacity').textContent = `${{capacityMbps}} Mbps`;

      // Física: Abaulamento k=4/3 e Fresnel F1 / 0.6*F1
      const Re_eff = 6371.0 * (4.0/3.0) * 1000.0;
      const abaulMax = ((distTotal * 1000.0) ** 2) / (8.0 * Re_eff);
      const f1Max = 17.32 * Math.sqrt(distTotal / (4.0 * freq));
      document.getElementById('txt-abaulamento').textContent = `+${{abaulMax.toFixed(1)}} m`;
      document.getElementById('txt-fresnel-r1').textContent = `${{f1Max.toFixed(1)}} m`;
      document.getElementById('txt-fresnel-06').textContent = `${{(0.6 * f1Max).toFixed(1)}} m`;
      document.getElementById('txt-chuva-loss').textContent = `-${{perdaChuva.toFixed(2)}} dB`;

      const elevs = await getPerfilTerreno(st1.latitude, st1.longitude, st2.latitude, st2.longitude);
      if (!elevs) {{
        const b = document.getElementById('badge-obstrucao');
        b.textContent = 'SEM DADOS DE RELEVO';
        b.className = 'status-badge status-obstr';
        return;
      }}

      const N = elevs.length;
      const cota1 = elevs[0] + h1;
      const cota2 = elevs[N - 1] + h2;

      let piorFolga = 9999;
      const dadosPlanos = [];
      const dadosTerreno = [];
      const dadosLos = [];
      const dadosCurv = [];
      const dadosF1 = [];

      for (let i = 0; i < N; i++) {{
        const frac = i / (N - 1);
        const distKm = frac * distTotal;
        const curv = ((distKm * 1000) * ((distTotal - distKm) * 1000)) / (2 * Re_eff);
        const terrComCurv = elevs[i] + curv;
        const los = cota1 + (cota2 - cota1) * frac;

        let rF1 = 0;
        if (i > 0 && i < N - 1) {{
          rF1 = 17.32 * Math.sqrt((distKm * (distTotal - distKm)) / (freq * distTotal));
          const folga = (los - 0.6 * rF1) - terrComCurv;
          if (folga < piorFolga) piorFolga = folga;
        }}

        dadosPlanos.push(elevs[i]);
        dadosTerreno.push(terrComCurv);
        dadosLos.push(los);
        dadosCurv.push(curv);
        dadosF1.push(rF1);
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

      ultimoPerfilCanvas = {{ distTotal, dadosPlanos, dadosTerreno, dadosLos, dadosCurv, dadosF1, cota1, cota2, h1, h2, obstruido }};
      desenharCanvasPerfil(ultimoPerfilCanvas);
    }}

    function desenharCanvasPerfil(p, hoverIdx=null) {{
      const cv = document.getElementById('profileCanvas');
      const container = document.getElementById('canvas-container');
      cv.width = container.clientWidth;
      cv.height = container.clientHeight;
      const ctx = cv.getContext('2d');

      const W = cv.width, H = cv.height;
      const {{ dadosPlanos: plano, dadosTerreno: terr, dadosLos: los, dadosF1: f1, cota1, cota2, obstruido }} = p;
      const N = terr.length;

      const losUp100 = los.map((v, i) => v + f1[i]);
      const losDn100 = los.map((v, i) => v - f1[i]);
      const losDn060 = los.map((v, i) => v - 0.6 * f1[i]);

      const minAlt = Math.min(...plano, ...terr, ...losDn100) - 18;
      const maxAlt = Math.max(...losUp100, ...terr) + 22;
      const range = Math.max(10, maxAlt - minAlt);

      const getY = val => H - ((val - minAlt) / range) * (H - 28) - 14;
      const getX = i => (i / (N - 1)) * (W - 76) + 38;

      ctx.clearRect(0, 0, W, H);

      // 1. LINHA DE TERRENO SEM ABAULAMENTO (referência sutil pontilhada)
      ctx.beginPath();
      ctx.setLineDash([2, 3]);
      for (let i = 0; i < N; i++) {{
        if (i === 0) ctx.moveTo(getX(i), getY(plano[i]));
        else ctx.lineTo(getX(i), getY(plano[i]));
      }}
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.35)';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.setLineDash([]);

      // 2. TERRENO REAL COM ABAULAMENTO DA TERRA (k = 4/3)
      ctx.beginPath();
      ctx.moveTo(getX(0), H);
      for (let i = 0; i < N; i++) ctx.lineTo(getX(i), getY(terr[i]));
      ctx.lineTo(getX(N - 1), H);
      ctx.closePath();
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, '#36415c');
      grad.addColorStop(1, '#161a26');
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.strokeStyle = '#64748b';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      // 3. ELIPSE COMPLETA DA 1ª ZONA DE FRESNEL (100% F1 ao redor da Linha de Visada, igual ao UISP)
      ctx.beginPath();
      for (let i = 0; i < N; i++) {{
        if (i === 0) ctx.moveTo(getX(i), getY(losUp100[i]));
        else ctx.lineTo(getX(i), getY(losUp100[i]));
      }}
      for (let i = N - 1; i >= 0; i--) {{
        ctx.lineTo(getX(i), getY(losDn100[i]));
      }}
      ctx.closePath();
      ctx.fillStyle = obstruido ? 'rgba(255, 56, 56, 0.16)' : 'rgba(56, 189, 248, 0.18)';
      ctx.fill();

      // Contorno superior e inferior da elipse 100% F1
      ctx.beginPath();
      for (let i = 0; i < N; i++) {{
        if (i === 0) ctx.moveTo(getX(i), getY(losUp100[i]));
        else ctx.lineTo(getX(i), getY(losUp100[i]));
      }}
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.65)';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      ctx.beginPath();
      for (let i = 0; i < N; i++) {{
        if (i === 0) ctx.moveTo(getX(i), getY(losDn100[i]));
        else ctx.lineTo(getX(i), getY(losDn100[i]));
      }}
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.65)';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      // 4. BORDA CRÍTICA DE 60% DE FRESNEL (0.6 * F1) ABAIXO DA VISADA
      ctx.beginPath();
      ctx.setLineDash([4, 4]);
      for (let i = 0; i < N; i++) {{
        if (i === 0) ctx.moveTo(getX(i), getY(losDn060[i]));
        else ctx.lineTo(getX(i), getY(losDn060[i]));
      }}
      ctx.strokeStyle = '#ffa94d';
      ctx.lineWidth = 1.4;
      ctx.stroke();
      ctx.setLineDash([]);

      // 5. LINHA DE VISADA DIRETA (LOS)
      ctx.beginPath();
      ctx.moveTo(getX(0), getY(cota1));
      ctx.lineTo(getX(N - 1), getY(cota2));
      ctx.strokeStyle = obstruido ? '#ff3838' : '#00ff55';
      ctx.lineWidth = 2.2;
      ctx.stroke();

      // 6. TORRES TX E RX
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(getX(0), getY(terr[0]));
      ctx.lineTo(getX(0), getY(cota1));
      ctx.moveTo(getX(N - 1), getY(terr[N - 1]));
      ctx.lineTo(getX(N - 1), getY(cota2));
      ctx.stroke();

      // Nós das antenas no topo das torres
      [ [getX(0), getY(cota1)], [getX(N - 1), getY(cota2)] ].forEach(([cx, cy]) => {{
        ctx.beginPath();
        ctx.arc(cx, cy, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#38bdf8';
        ctx.fill();
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }});

      // Cursor interativo
      if (hoverIdx !== null && hoverIdx >= 0 && hoverIdx < N) {{
        const hx = getX(hoverIdx);
        ctx.beginPath();
        ctx.moveTo(hx, 8);
        ctx.lineTo(hx, H - 8);
        ctx.strokeStyle = 'rgba(255,255,255,0.35)';
        ctx.lineWidth = 1;
        ctx.stroke();
      }}

      // Rótulos laterais de Cota
      ctx.fillStyle = '#94a3b8';
      ctx.font = '10px monospace';
      ctx.fillText(`${{Math.round(terr[0])}}m`, 4, getY(terr[0]));
      ctx.fillText(`${{Math.round(terr[N-1])}}m`, W - 34, getY(terr[N-1]));
    }}

    // TOOLTIP INTERATIVO SOBRE O GRÁFICO DE PERFIL
    const canvasEl = document.getElementById('profileCanvas');
    const tooltipEl = document.getElementById('canvas-tooltip');
    canvasEl.addEventListener('mousemove', (e) => {{
      if (!ultimoPerfilCanvas) return;
      const rect = canvasEl.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const W = rect.width;
      const frac = Math.max(0, Math.min(1, (x - 38) / (W - 76)));
      const N = ultimoPerfilCanvas.dadosTerreno.length;
      const idx = Math.round(frac * (N - 1));

      const distPt = frac * ultimoPerfilCanvas.distTotal;
      const terrReal = ultimoPerfilCanvas.dadosPlanos[idx];
      const curvPt = ultimoPerfilCanvas.dadosCurv[idx];
      const terrCurv = ultimoPerfilCanvas.dadosTerreno[idx];
      const losPt = ultimoPerfilCanvas.dadosLos[idx];
      const f1Pt = ultimoPerfilCanvas.dadosF1[idx];
      const fres06 = losPt - 0.6 * f1Pt;
      const folgaPt = fres06 - terrCurv;

      desenharCanvasPerfil(ultimoPerfilCanvas, idx);

      tooltipEl.style.display = 'block';
      const leftPos = (x + 215 > W) ? (x - 208) : (x + 12);
      tooltipEl.style.left = `${{Math.max(4, leftPos)}}px`;
      tooltipEl.style.top = '8px';
      tooltipEl.innerHTML =
        `<b>Distância:</b> ${{distPt.toFixed(2)}} km<br>` +
        `<b>Terreno Real:</b> ${{terrReal.toFixed(1)}} m<br>` +
        `<b>Abaulamento (k=4/3):</b> +${{curvPt.toFixed(1)}} m<br>` +
        `<b>Linha de Visada (LOS):</b> ${{losPt.toFixed(1)}} m<br>` +
        `<b>Borda 0.6·F1:</b> ${{fres06.toFixed(1)}} m<br>` +
        `<b>Folga Livre:</b> <span style="color:${{folgaPt>=0?'#00ff55':'#ff6b6b'}};font-weight:700">${{folgaPt>=0?'+':''}}${{folgaPt.toFixed(1)}} m</span>`;
    }});
    canvasEl.addEventListener('mouseleave', () => {{
      tooltipEl.style.display = 'none';
      if (ultimoPerfilCanvas) desenharCanvasPerfil(ultimoPerfilCanvas, null);
    }});

    // =========================================================================
    // SEGUNDA INTERFACE: CÁLCULOS, CHUVA ITU-R & ORÇAMENTO (APRESENTAÇÃO)
    // =========================================================================
    function renderizarPainelCalculos() {{
      const el = document.getElementById('calc-content');
      const sol1 = SOLUCOES[0] || {{}};
      const sol2 = SOLUCOES[1] || {{}};
      const sol3 = SOLUCOES[2] || {{}};

      const popTotal = DEMANDA_SMP.reduce((a, x) => a + x.populacao_total, 0);
      const assinTotal = DEMANDA_SMP.reduce((a, x) => a + x.assinantes_operadora, 0);
      const erlTotal = DEMANDA_SMP.reduce((a, x) => a + x.trafego_total_erl, 0);
      const erbsTotal = COBERTURA_SMP.reduce((a, x) => a + x.erbs_finais_adotadas, 0);
      const raioCel = COBERTURA_SMP[0] ? COBERTURA_SMP[0].raio_cobertura_km : 1.808;
      const areaCel = COBERTURA_SMP[0] ? COBERTURA_SMP[0].area_erb_km2 : 8.5;

      const capex1 = sol1.orcamento ? sol1.orcamento.custo_total_capex_brl : 0;
      const capex2 = sol2.orcamento ? sol2.orcamento.custo_total_capex_brl : 0;
      const capex3 = sol3.orcamento ? sol3.orcamento.custo_total_capex_brl : 0;

      // Linhas Etapa 1 + 2
      const rowsCidades = DEMANDA_SMP.map((d, i) => {{
        const c = COBERTURA_SMP[i] || {{}};
        return `<tr>
          <td><b>${{d.cidade}}</b></td>
          <td>${{d.populacao_total.toLocaleString('pt-BR')}}</td>
          <td>${{d.assinantes_operadora.toLocaleString('pt-BR')}}</td>
          <td>${{d.trafego_total_erl}} Erl</td>
          <td>${{d.portadoras_rf_por_setor}} RF/setor (${{(d.portadoras_rf_por_setor*0.2).toFixed(1)}} MHz)</td>
          <td>${{c.area_urbana_km2 || '-'}} km²</td>
          <td>${{d.erbs_capacidade}} / ${{c.erbs_por_cobertura || '-'}}</td>
          <td><span class="pill-ok">${{c.erbs_finais_adotadas || d.erbs_capacidade}} ERBs</span></td>
        </tr>`;
      }}).join('');

      // Linhas Etapa 3 (S/I pior caso e Rappaport)
      const rowsSI = (INTERFERENCIA_SMP.resultados_simulacao || [])
        .filter(r => r['Expoente (γ)'] === 3.5 || r['Expoente (γ)'] === 4.0)
        .map(r => `<tr>
          <td>${{r['Cenário']}}</td>
          <td>γ = ${{r['Expoente (γ)']}}</td>
          <td><b>${{r['S/I Calculado (dB)']}} dB</b></td>
          <td>&gt; ${{r['S/I Exigido (dB)']}} dB</td>
          <td>+${{r['Margem (dB)']}} dB</td>
          <td><span class="${{r['Conformidade']==='APROVADO'?'pill-ok':'pill-bad'}}">${{r['Conformidade']}}</span></td>
        </tr>`).join('');

      // Linhas Etapa 6 (Enlaces Solução #1 + Chuva + Orçamento)
      const rowsSol1Links = (sol1.enlaces || []).map(l => `<tr>
        <td><b>${{l.origem}}</b> ➔ ${{l.destino}}</td>
        <td class="nowrap">${{l.distancia_km}} km</td>
        <td><span class="pill-info">${{l.frequencia_ghz}} GHz</span></td>
        <td class="nowrap"><b>${{l.h_torre_origem_m}}m / ${{l.h_torre_destino_m}}m</b></td>
        <td class="nowrap">+${{l.abaulamento_max_m}} m</td>
        <td class="nowrap">+${{l.folga_fresnel_m}} m</td>
        <td class="nowrap">${{l.radio_utilizado}} + ${{l.antena_tx.split(' ')[0]}}</td>
        <td class="nowrap">${{l.fade_margin_db}} dB</td>
        <td class="nowrap">-${{l.atenuacao_chuva_50mmh_db}} dB</td>
        <td><span class="pill-ok">${{l.fade_margin_chuva_db}} dB</span></td>
        <td class="nowrap">${{formatarBRL(l.custo_kits_brl)}}</td>
      </tr>`).join('');

      // Alturas únicas fixas das torres da Solução #1
      const rowsTorresUnicas = Object.entries(sol1.alturas_fixas_torres || {{}}).map(([sid, h]) => {{
        const sitio = SITIOS_FIXOS.find(s => s.id === sid) || {{ nome: sid, altitude_terreno_m: '-' }};
        const g = GRAU_SOL[1][sid] || 1;
        const cotaFmt = Number.isFinite(Number(sitio.altitude_terreno_m)) ? `${{Number(sitio.altitude_terreno_m).toFixed(1)}} m` : '-';
        return `<tr>
          <td><b>${{sitio.nome}}</b></td>
          <td>${{cotaFmt}}</td>
          <td><span class="pill-ok">${{h}} m (única e fixa)</span></td>
          <td>${{g}} enlace(s) atendido(s)</td>
        </tr>`;
      }}).join('');

      // Contagens dinâmicas para Tabela de Referências de Custos (Solução #1)
      const linksSol1 = sol1.enlaces || [];
      const qtd5XHD = linksSol1.filter(l => l.radio_utilizado === 'airFiber 5XHD').length * 2;
      const qtd11FX = linksSol1.filter(l => l.radio_utilizado === 'airFiber 11FX').length * 2;
      const countAnt = (frag) => linksSol1.reduce((acc, l) => acc + (l.antena_tx.includes(frag) ? 1 : 0) + (l.antena_rx.includes(frag) ? 1 : 0), 0);
      const qtd5G23 = countAnt('AF-5G23');
      const qtd5G30 = countAnt('AF-5G30');
      const qtd5G34 = countAnt('AF-5G34');
      const qtd11G35 = countAnt('AF-11G35');
      const qtd11Dish = countAnt('1.2m');
      const somaMetrosTorres1 = Object.values(sol1.alturas_fixas_torres || {{}}).reduce((a, b) => a + b, 0);
      const numEnlaces1 = linksSol1.length;
      const numKits1 = numEnlaces1 * 2;
      const numKits2 = ((sol2.enlaces || []).length) * 2;
      const numKits3 = ((sol3.enlaces || []).length) * 2;
      const numTorres1 = Object.keys(sol1.alturas_fixas_torres || {{}}).length;
      const qtd5GLinks1 = linksSol1.filter(l => Math.round(Number(l.frequencia_ghz)) === 5).length;
      const qtd11GLinks1 = linksSol1.filter(l => Math.round(Number(l.frequencia_ghz)) === 11).length;
      const qtdReps1 = sol1.num_repetidoras || 4;
      const qtdSitiosExist1 = Object.keys(sol1.alturas_fixas_torres || {{}}).length - qtdReps1;
      const ativos1 = sol1.orcamento ? sol1.orcamento.custo_ativos_brl : 0;
      const civilTotal1 = (sol1.orcamento ? (sol1.orcamento.custo_torres_brl + sol1.orcamento.custo_infra_sitios_brl) : 0);
      const ativos2 = sol2.orcamento ? sol2.orcamento.custo_ativos_brl : 0;
      const civilTotal2 = (sol2.orcamento ? (sol2.orcamento.custo_torres_brl + sol2.orcamento.custo_infra_sitios_brl) : 0);
      const ativos3 = sol3.orcamento ? sol3.orcamento.custo_ativos_brl : 0;
      const civilTotal3 = (sol3.orcamento ? (sol3.orcamento.custo_torres_brl + sol3.orcamento.custo_infra_sitios_brl) : 0);

      el.innerHTML = `
        <div class="calc-hero">
          <div>
            <h1>📘 Memorial de Cálculo, Propagação, Chuva & Orçamento — Projeto 07</h1>
            <p>Visão completa e didática para apresentação em sala (Maria Letícia & Matteo | Debatedores: Ian & Gustavo). Todos os números abaixo são gerados automaticamente pelos scripts Python sobre o Censo IBGE 2022 e o relevo real Copernicus DEM 30m.</p>
          </div>
          <button class="nav-tab active" onclick="alternarAba('map')">⬅️ Voltar ao Mapa Interativo</button>
        </div>

        <div class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-label">Sistema Celular SMP</div>
            <div class="kpi-value">1.800 MHz (4×3)</div>
            <div class="kpi-sub">8 slots / RF (200 kHz) • máx 8 RF/setor</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Raio Celular (COST 231)</div>
            <div class="kpi-value">${{raioCel}} km</div>
            <div class="kpi-sub">Área = ${{areaCel}} km²/ERB • Total: ${{erbsTotal}} ERBs</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">Interferência Pior Caso</div>
            <div class="kpi-value">12,56 dB (&gt; 12 dB)</div>
            <div class="kpi-sub">Cluster K=4 (Q=3,464) • 2 interferentes</div>
          </div>
          <div class="kpi-card highlight">
            <div class="kpi-label">Solução #1 — Torres Fixas</div>
            <div class="kpi-value">Máx ${{sol1.altura_max_torre_m || 30}} m (≤ 50 m)</div>
            <div class="kpi-sub">${{sol1.num_repetidoras}} repetidoras (só 1 p/ Natal!)</div>
          </div>
          <div class="kpi-card highlight">
            <div class="kpi-label">Só Ativos Rádio+Antena (#1)</div>
            <div class="kpi-value">${{formatarBRL(ativos1)}}</div>
            <div class="kpi-sub">${{numKits1}} kits (${{numEnlaces1}} enlaces) • +${{formatarBRL(civilTotal1)}} Torres/Civil = ${{formatarBRL(capex1)}}</div>
          </div>
        </div>

        <!-- ETAPA 1 E 2 -->
        <div class="section-card">
          <div class="section-title">1️⃣ Etapas 1 e 2 — Tráfego (Erlang B), Link Budget Celular e Quantidade de ERBs <span class="section-tag">1800 MHz • 0,015 Erl/usuário</span></div>
          <div class="two-col">
            <div class="formula-box">
              <b>Como entrou o Tráfego do Enunciado:</b><br>
              • Concorrência: <b>2 concorrentes</b> (3 operadoras) ⇒ Nossa fatia = <code>1/3</code> da população (${{assinTotal.toLocaleString('pt-BR')}} clientes de ${{popTotal.toLocaleString('pt-BR')}} hab., totalizando <b>${{erlTotal.toFixed(1)}} Erl</b>).<br>
              • Canais por setor: máx <code>8 RF × 8 slots - 1 controle (BCCH) = 63 canais</code>.<br>
              • Pela fórmula de <b>Erlang B (GoS = 2%)</b>, 1 setor suporta <code>52,48 Erl</code> ⇒ 1 ERB (3 setores) suporta <code>157,44 Erl</code>.
            </div>
            <div class="formula-box">
              <b>Como entrou a Cobertura (Gargalo no Uplink):</b><br>
              • <b>Uplink (EM → ERB):</b> <code>0,8 W (29,03 dBm)</code> + <code>0 dBi</code> − <code>1,5 dB</code> (corpo) + <code>18 dBi</code> − <code>2 dB</code> (cabo) − <code>6 dB</code> (sombreamento) − <code>(-105 dBm)</code> = <b>${{BALANCO_SMP.pl_max_uplink_db}} dB</b> (gargalo!).<br>
              • <b>Downlink (ERB → EM):</b> <code>10 W (40 dBm)</code> ⇒ <b>${{BALANCO_SMP.pl_max_downlink_db}} dB</b>.<br>
              • Invertendo o modelo <b>COST 231 Hata (1800 MHz)</b> com <code>h_ERB = 45 m</code>, resulta em <b>R = ${{raioCel}} km</b> (${{areaCel}} km² por hexágono).
            </div>
          </div>
          <table class="eng-table">
            <thead>
              <tr><th>Município</th><th>População</th><th>Clientes (1/3)</th><th>Tráfego</th><th>Portadoras/Setor</th><th>Área Urbana</th><th>ERBs (Cap / Cob)</th><th>Adotadas</th></tr>
            </thead>
            <tbody>${{rowsCidades}}</tbody>
          </table>
        </div>

        <!-- ETAPA 3 -->
        <div class="section-card">
          <div class="section-title">2️⃣ Etapa 3 — Interferência Co-Canal no Cluster 4×3 <span class="section-tag">S/I &gt; 12 dB Aprovado</span></div>
          <div class="formula-box">
            No cluster <b>K = 4</b> com <b>3 setores de 120°</b> (4×3), a razão de reuso é <code>Q = D/R = √(3·K) = √12 = 3,4641</code>, e a setorização reduz os interferentes de 6 para apenas <b>2 células co-canal</b>. Mesmo no <b>Pior Caso Extremo</b> (usuário na borda com interferentes a <code>D−R</code> e <code>D</code>), para <code>γ = 3,5</code> obtemos <code>S/I = 12,56 dB &gt; 12,0 dB</code>.
          </div>
          <table class="eng-table">
            <thead>
              <tr><th>Cenário Geométrico</th><th>Expoente de Perda</th><th>S/I Calculado</th><th>Exigência</th><th>Margem</th><th>Status</th></tr>
            </thead>
            <tbody>${{rowsSI}}</tbody>
          </table>
        </div>

        <!-- ETAPA 4 & 5: POSICIONAMENTO E ALTURAS ÚNICAS -->
        <div class="section-card">
          <div class="section-title">3️⃣ Etapas 4 e 5 — Escolha dos Locais, Abaulamento (k=4/3), Fresnel e Altura Fixa Única das Torres <span class="section-tag">Torres ≤ 50 m • Sem Saltos Redundantes</span></div>
          <div class="two-col">
            <div class="formula-box">
              <b>Como escolhemos os melhores locais (sem "caixa-preta"):</b><br>
              1. <b>Micro-Siting Urbano (±750 m):</b> Dentro da zona de cobertura de cada cidade, varremos o DEM Copernicus 30m e subimos a ERB para a cota urbana firme mais alta (ex.: em Currais Novos subiu de 342 m para <b>435,7 m</b>; em Natal usamos a cota alta urbana da <b>Candelária/BR-101 a 101,2 m</b> com acesso e energia). Em <b>Carnaúba dos Dantas</b>, a ERB urbana fica na encosta do Monte do Galo (<code>-6.55850, -36.59150</code>, 317,3 m) cobrindo 100% da cidade no raio de <b>1,808 km</b> e subindo em visada limpa de 3,55 km até o cume real norte de <b>666,0 m</b> em <b>Rep. Cume 69</b> (<code>-6.52731, -36.59820</code>), concentrando Carnaúba, Jardim do Seridó e Caicó direto até Currais Novos (eliminando repetidora extra).<br>
              2. <b>Varredura de Serras (94.644 pontos) + Hill Climbing:</b> Achamos os melhores cumes reais e proibimos saltos &lt; 12 km entre repetidoras.<br>
              3. <b>Altura Única por Torre:</b> Cada torre tem <b>uma única altura fixa (20 m a 45 m na Sol. #1)</b> que atende todos os enlaces ligados a ela!<br>
            </div>
            <div class="formula-box">
              <b>Física da Visada (Abaulamento + Zona de Fresnel):</b><br>
              • <b>Abaulamento da Terra (k = 4/3):</b> <code>h_curv(d) = (d₁ · d₂) / (2 · k · R_Terra)</code>. No salto de 76,7 km até Natal, a Terra "sobe" <b>+86,6 m</b> no centro (descontando a refração k=4/3)!<br>
              • <b>1ª Zona de Fresnel:</b> <code>R₁ = 17,32 · √((d₁ · d₂) / (f_GHz · D))</code>. Exigimos pelo menos <b>60% de F₁ livre + 16 m de folga de segurança</b> (evitando torres baixas e feixe rente ao solo/vegetação).<br>
              • <b>Chuva Intensa (ITU-R P.838-3 @ 50 mm/h):</b> Em <code>76,7 km</code> (Rep. Cume 46 → Natal), 11 GHz perderia ~28 dB na chuva; por isso adotamos <b>5 GHz (airFiber 5XHD)</b> nesse salto longo, perdendo apenas <b>0,82 dB</b>!
            </div>
          </div>

          <h4 style="color:#cbd5e1; margin-top:4px; font-size:0.9rem;">📏 Tabela de Altura Física Única por Torre — Solução #1 (Torres de 20 m a ${{sol1.altura_max_torre_m || 35}} m • Folga mín +${{sol1.folga_minima_m || 16}} m!)</h4>
          <table class="eng-table">
            <thead>
              <tr><th>Sítio / Torre</th><th>Altitude do Solo (DEM 30m)</th><th>Altura Física Única</th><th>Enlaces Compartilhados</th></tr>
            </thead>
            <tbody>${{rowsTorresUnicas}}</tbody>
          </table>
        </div>

        <!-- ETAPA 6: ORÇAMENTO & CHUVA -->
        <div class="section-card">
          <div class="section-title">4️⃣ Orçamento Separado (Ativos vs. Torres/Civil), Referências & Quadro Síntese <span class="section-tag">Comparativo Solução #1 vs #2 vs #3</span></div>
          <div class="formula-box">
            <b>Por que comparar separando Ativos vs. Obra Civil?</b> Trabalhos focados apenas em enlaces PTP normalmente contabilizam <b>só os rádios e antenas (Ativos)</b>. Na nossa Solução #1 completa, os <b>Ativos de Telecom</b> somam <b>${{formatarBRL(ativos1)}}</b> (${{numKits1}} kits em ${{numEnlaces1}} enlaces, incluindo ${{qtd11GLinks1}} saltos em banda licenciada 11 GHz e ${{qtd5GLinks1}} em 5 GHz), enquanto <b>Torres + Infraestrutura Civil</b> respondem por <b>${{formatarBRL(civilTotal1)}}</b> (torres, fundação, SPDA, bancos de bateria/solar nas serras e racks), totalizando o CAPEX <i>turn-key</i> de <b>${{formatarBRL(capex1)}}</b>.
          </div>
          <div class="budget-grid">
            <div class="budget-card win">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <b style="color:#00ff55;">★ Solução #1 — Ótima Principal</b>
                <span class="pill-ok">MELHOR CUSTO</span>
              </div>
              <div class="budget-total">${{formatarBRL(capex1)}}</div>
              <div class="budget-split">
                <div class="split-pill"><span>📡 Só Ativos (${{numKits1}} kits)</span><b style="color:#38bdf8;">${{formatarBRL(ativos1)}}</b></div>
                <div class="split-pill"><span>🏗️ Torres + Civil</span><b style="color:#cbd5e1;">${{formatarBRL(civilTotal1)}}</b></div>
              </div>
              <div style="font-size:0.78rem; color:#cbd5e1; line-height:1.48;">
                • <b>Torres (20–${{sol1.altura_max_torre_m || 45}} m, ${{somaMetrosTorres1}} m somados):</b> ${{formatarBRL(sol1.orcamento?.custo_torres_brl)}}<br>
                • <b>Civil/Energia (${{qtdReps1}} rep. + ${{qtdSitiosExist1}} ERBs/CCC):</b> ${{formatarBRL(sol1.orcamento?.custo_infra_sitios_brl)}}<br>
                • <b>Destaque:</b> Apenas <b>1 repetidora</b> indo de Santa Cruz até Natal!
              </div>
            </div>
            <div class="budget-card">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <b style="color:#00d4ff;">Solução #2 — Saltos ≤ 56 km (11 GHz)</b>
                <span class="pill-info">+${{formatarBRL(capex2 - capex1)}}</span>
              </div>
              <div class="budget-total">${{formatarBRL(capex2)}}</div>
              <div class="budget-split">
                <div class="split-pill"><span>📡 Só Ativos (${{numKits2}} kits)</span><b style="color:#38bdf8;">${{formatarBRL(ativos2)}}</b></div>
                <div class="split-pill"><span>🏗️ Torres + Civil</span><b style="color:#cbd5e1;">${{formatarBRL(civilTotal2)}}</b></div>
              </div>
              <div style="font-size:0.78rem; color:#9fb0c9; line-height:1.48;">
                • <b>Torres (≤ ${{sol2.altura_max_torre_m || 45}} m):</b> ${{formatarBRL(sol2.orcamento?.custo_torres_brl)}}<br>
                • <b>Civil/Energia (${{sol2.num_repetidoras}} repetidoras):</b> ${{formatarBRL(sol2.orcamento?.custo_infra_sitios_brl)}}<br>
                • Exige 1 repetidora extra antes de Natal para manter todos os saltos em 11 GHz ≤ 56 km.
              </div>
            </div>
            <div class="budget-card">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <b style="color:#ffab00;">Solução #3 — Rota de Contingência</b>
                <span class="pill-bad">+${{formatarBRL(capex3 - capex1)}}</span>
              </div>
              <div class="budget-total">${{formatarBRL(capex3)}}</div>
              <div class="budget-split">
                <div class="split-pill"><span>📡 Só Ativos (${{numKits3}} kits)</span><b style="color:#38bdf8;">${{formatarBRL(ativos3)}}</b></div>
                <div class="split-pill"><span>🏗️ Torres + Civil</span><b style="color:#cbd5e1;">${{formatarBRL(civilTotal3)}}</b></div>
              </div>
              <div style="font-size:0.78rem; color:#9fb0c9; line-height:1.48;">
                • <b>Torres (≤ 50 m):</b> ${{formatarBRL(sol3.orcamento?.custo_torres_brl)}}<br>
                • <b>Civil/Energia (${{sol3.num_repetidoras}} repetidoras):</b> ${{formatarBRL(sol3.orcamento?.custo_infra_sitios_brl)}}<br>
                • Rota reserva usando 100% outros cumes caso haja bloqueio fundiário nos da #1.
              </div>
            </div>
          </div>

          <h4 style="color:#cbd5e1; margin-top:6px; font-size:0.9rem;">🧾 Detalhamento Unitário e Fontes de Referência por Item — Solução #1</h4>
          <div style="overflow-x:auto;">
            <table class="eng-table">
              <thead>
                <tr>
                  <th>Categoria</th><th>Item / Especificação</th><th>Qtd.</th><th>Valor Unitário</th><th>Subtotal (Sol. #1)</th><th>Base Técnica e Link de Referência</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="pill-info">Ativos (5 GHz)</span></td>
                  <td><b>Rádio Ubiquiti airFiber 5XHD</b> (5 GHz, até 1 Gbps)</td>
                  <td class="nowrap">${{qtd5XHD}} un</td>
                  <td class="nowrap">R$ 3.778,20</td>
                  <td class="nowrap"><b>${{formatarBRL(qtd5XHD * 3778.20)}}</b></td>
                  <td>Preço à vista PIX direto na página: <a class="ref-link" href="https://www.kabum.com.br/produto/1041600/radio-ubiquiti-airfiber-af-5xhd-ip-67-5ghz-1gbps-200km" target="_blank" rel="noopener">KaBuM! AF-5XHD (R$ 3.778,20)</a> • <a class="ref-link" href="https://dl.ubnt.com/datasheets/airFiber/airFiber_5XHD_DS.pdf" target="_blank" rel="noopener">Datasheet Oficial</a></td>
                </tr>
                <tr>
                  <td><span class="pill-info">Ativos (5 GHz)</span></td>
                  <td><b>Antena AF-5G23-S45</b> (0,38 m / 23 dBi) — enlaces urbanos</td>
                  <td class="nowrap">${{qtd5G23}} un</td>
                  <td class="nowrap">R$ 933,07</td>
                  <td class="nowrap"><b>${{formatarBRL(qtd5G23 * 933.07)}}</b></td>
                  <td>Preço PIX direto no catálogo BR: <a class="ref-link" href="https://www.tudoemubiquiti.com.br/t/categoria-tudo-em-ubiquiti/airfiber/antenas" target="_blank" rel="noopener">Tudo em Ubiquiti (R$ 933,07)</a> • <a class="ref-link" href="https://dl.ubnt.com/datasheets/airFiber/airFiber_Antennas_DS.pdf" target="_blank" rel="noopener">Datasheet Antenas</a></td>
                </tr>
                <tr>
                  <td><span class="pill-info">Ativos (5 GHz)</span></td>
                  <td><b>Antena AF-5G30-S45</b> (0,65 m / 30 dBi)</td>
                  <td class="nowrap">${{qtd5G30}} un</td>
                  <td class="nowrap">R$ 1.303,55</td>
                  <td class="nowrap"><b>${{formatarBRL(qtd5G30 * 1303.55)}}</b></td>
                  <td>Preço PIX direto no catálogo BR: <a class="ref-link" href="https://www.tudoemubiquiti.com.br/t/categoria-tudo-em-ubiquiti/airfiber/antenas" target="_blank" rel="noopener">Tudo em Ubiquiti (R$ 1.303,55)</a> • <a class="ref-link" href="https://dl.ubnt.com/datasheets/airFiber/airFiber_Antennas_DS.pdf" target="_blank" rel="noopener">Datasheet Antenas</a></td>
                </tr>
                <tr>
                  <td><span class="pill-info">Ativos (5 GHz)</span></td>
                  <td><b>Antena AF-5G34-S45</b> (1,05 m / 34 dBi) — salto 76,7 km Natal</td>
                  <td class="nowrap">${{qtd5G34}} un</td>
                  <td class="nowrap">R$ 7.894,00</td>
                  <td class="nowrap"><b>${{formatarBRL(qtd5G34 * 7894.00)}}</b></td>
                  <td>Preço à vista PIX direto na loja: <a class="ref-link" href="https://netcomputadores.com.br/p/af5g34s45-ubiquiti-antena-airfiberx-5ghz/24725" target="_blank" rel="noopener">NetComputadores AF-5G34-S45 (R$ 7.894,00)</a></td>
                </tr>
                <tr>
                  <td><span class="pill-info">Ativos (11 GHz)</span></td>
                  <td><b>Rádio Ubiquiti airFiber 11FX + Duplexador</b> (11 GHz licenciado)</td>
                  <td class="nowrap">${{qtd11FX}} un</td>
                  <td class="nowrap">R$ 6.042,61</td>
                  <td class="nowrap"><b>${{formatarBRL(qtd11FX * 6042.61)}}</b></td>
                  <td>Soma exata PIX: <a class="ref-link" href="https://netcomputadores.com.br/p/af11fx-ubiquiti-airfiber-sem-duplexador/71689" target="_blank" rel="noopener">AF-11FX (R$ 4.646,00)</a> + <a class="ref-link" href="https://netcomputadores.com.br/p/af11fxdupl-ubiquiti-airfiber-duplexador-banda/71694" target="_blank" rel="noopener">Duplexador (R$ 1.396,61)</a> • <a class="ref-link" href="https://store.ui.com/us/en/products/af-11" target="_blank" rel="noopener">Ubiquiti Store ($999)</a></td>
                </tr>
                <tr>
                  <td><span class="pill-info">Ativos (11 GHz)</span></td>
                  <td><b>Antena AF-11G35</b> (0,9 m / 35 dBi)</td>
                  <td class="nowrap">${{qtd11G35}} un</td>
                  <td class="nowrap">R$ 3.450,00</td>
                  <td class="nowrap"><b>${{formatarBRL(qtd11G35 * 3450.00)}}</b></td>
                  <td>Ref. direta distribuidor ($379,00 FOB EUA ≈ R$ 3.450 nacionalizada c/ frete e impostos): <a class="ref-link" href="https://www.microcom.us/af11g35.html" target="_blank" rel="noopener">Microcom AF-11G35 ($379.00)</a> • <a class="ref-link" href="https://dl.ubnt.com/datasheets/airFiber/airFiber_11FX_DS.pdf" target="_blank" rel="noopener">Datasheet 11FX</a></td>
                </tr>
                <tr>
                  <td><span class="pill-info">Ativos (11 GHz)</span></td>
                  <td><b>Prato High-Gain 1,2 m</b> (38,5 dBi) — Caicó 54,1 km</td>
                  <td class="nowrap">${{qtd11Dish}} un</td>
                  <td class="nowrap">R$ 5.200,00</td>
                  <td class="nowrap"><b>${{formatarBRL(qtd11Dish * 5200.00)}}</b></td>
                  <td>Prato maior 1,2 m (~1,5× preço do AF-11G35 p/ ganho 38,5 dBi no <a class="ref-link" href="https://ispdesign.ui.com/" target="_blank" rel="noopener">UISP Design Center</a>; base: <a class="ref-link" href="https://www.microcom.us/af11g35.html" target="_blank" rel="noopener">Microcom $379.00</a>)</td>
                </tr>
                <tr style="background:rgba(56,189,248,0.08);">
                  <td colspan="4" style="text-align:right;"><b>SUBTOTAL 1 — EQUIPAMENTOS ATIVOS (RÁDIOS + ANTENAS):</b></td>
                  <td class="nowrap"><b style="color:#38bdf8;">${{formatarBRL(ativos1)}}</b></td>
                  <td>Comparável direto aos orçamentos que listam só rádios e antenas</td>
                </tr>
                <tr>
                  <td><span class="pill-ok">Estruturas</span></td>
                  <td><b>Torres Estaiadas (20 m a ${{sol1.altura_max_torre_m || 45}} m) com base e estais</b></td>
                  <td class="nowrap">${{somaMetrosTorres1}} m (${{numTorres1}} torres)</td>
                  <td class="nowrap">R$ 902,50 / m</td>
                  <td class="nowrap"><b>${{formatarBRL(sol1.orcamento?.custo_torres_brl)}}</b></td>
                  <td>Preço por metro direto no anúncio: <a class="ref-link" href="https://www.mfrural.com.br/busca/torre-modulos" target="_blank" rel="noopener">MF Rural (R$ 902,50/m)</a> • Ref. módulo avulso 2m sem estais: <a class="ref-link" href="https://www.supertower.com.br/produto/modulo-torre-estaiada-2m-r-450-00-cada" target="_blank" rel="noopener">Super Tower (R$ 450/2m)</a></td>
                </tr>
                <tr>
                  <td><span class="pill-ok">Energia + Rack</span></td>
                  <td><b>Infraestrutura Autônoma Repetidora (Solar + Rack Outdoor + 2 Baterias)</b></td>
                  <td class="nowrap">${{qtdReps1}} sítios</td>
                  <td class="nowrap">R$ 11.228,83 / sítio</td>
                  <td class="nowrap"><b>${{formatarBRL(qtdReps1 * 11228.83)}}</b></td>
                  <td>Soma exata dos 3 links: <a class="ref-link" href="https://www.minhacasasolar.com.br/kit-solar-hibrido-165kwh-mes-inversor-off-grid-3-6kw-48v-220v-wifi-deye-sun-3-6k-84368" target="_blank" rel="noopener">Kit Solar Off-Grid (R$ 8.177,80)</a> + <a class="ref-link" href="https://www.kabum.com.br/produto/630756/rack-intelbras-outdoor-5u-470mm-4770040" target="_blank" rel="noopener">Rack Intelbras 5U (R$ 1.323,09)</a> + <a class="ref-link" href="https://www.minhacasasolar.com.br/bateria-estacionaria-105ah-freedom-df2000-84553" target="_blank" rel="noopener">2× Bateria 105Ah (R$ 863,97/un)</a></td>
                </tr>
                <tr>
                  <td><span class="pill-ok">Energia + Rack</span></td>
                  <td><b>Adequação Backhaul em ERBs Urbanas e CCCs (Rack + 1 Bateria)</b></td>
                  <td class="nowrap">${{qtdSitiosExist1}} sítios</td>
                  <td class="nowrap">R$ 2.187,06 / sítio</td>
                  <td class="nowrap"><b>${{formatarBRL(qtdSitiosExist1 * 2187.06)}}</b></td>
                  <td>Soma exata em sítio já existente: <a class="ref-link" href="https://www.kabum.com.br/produto/630756/rack-intelbras-outdoor-5u-470mm-4770040" target="_blank" rel="noopener">Rack Intelbras 5U (R$ 1.323,09)</a> + <a class="ref-link" href="https://www.minhacasasolar.com.br/bateria-estacionaria-105ah-freedom-df2000-84553" target="_blank" rel="noopener">1× Bateria 105Ah (R$ 863,97)</a></td>
                </tr>
                <tr style="background:rgba(0,255,85,0.09);">
                  <td colspan="4" style="text-align:right;"><b>SUBTOTAL 2 — TORRES + ENERGIA/RACK:</b></td>
                  <td class="nowrap"><b style="color:#00ff55;">${{formatarBRL(civilTotal1)}}</b></td>
                  <td>Infraestrutura física cotada diretamente com links reais</td>
                </tr>
              </tbody>
            </table>
          </div>

          <h4 style="color:#cbd5e1; margin-top:6px; font-size:0.9rem;">📋 Quadro Síntese dos ${{numEnlaces1}} Enlaces da Solução #1 (Chuva ITU-R P.838-3 + Custo de Equipamentos)</h4>
          <div style="overflow-x:auto;">
            <table class="eng-table">
              <thead>
                <tr>
                  <th>Enlace (Origem ➔ Destino)</th><th>Dist.</th><th>Banda</th><th>Torres Fixas</th><th>Abaul. k=4/3</th><th>Folga 0.6·F1</th><th>Equipamento Ubiquiti</th><th>FM Limpo</th><th>Chuva 50mm/h</th><th>FM Chuva</th><th>Ativos (2 kits)</th>
                </tr>
              </thead>
              <tbody>${{rowsSol1Links}}</tbody>
            </table>
          </div>

          <h4 style="color:#cbd5e1; margin-top:6px; font-size:0.9rem;">🔀 Diagrama Lógico da Rede (Solução #1 — Fluxo do Seridó até Natal)</h4>
          <div class="diagram-box">
            <svg viewBox="0 0 1160 250" width="100%" height="230" style="min-width:940px;">
              <defs>
                <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                  <path d="M 0 1 L 10 5 L 0 9 z" fill="#00ff55" />
                </marker>
              </defs>
              <!-- Linhas lógicas -->
              <line x1="160" y1="45" x2="280" y2="112" stroke="#00ff55" stroke-width="2.5" marker-end="url(#arrow)" />
              <line x1="160" y1="125" x2="280" y2="125" stroke="#00ff55" stroke-width="2.5" marker-end="url(#arrow)" />
              <line x1="160" y1="205" x2="280" y2="138" stroke="#00ff55" stroke-width="2.5" marker-end="url(#arrow)" />
              <line x1="426" y1="125" x2="498" y2="125" stroke="#00ff55" stroke-width="3" marker-end="url(#arrow)" />
              <line x1="650" y1="125" x2="720" y2="125" stroke="#00ff55" stroke-width="3" marker-end="url(#arrow)" />
              <line x1="844" y1="125" x2="895" y2="125" stroke="#00ff55" stroke-width="3" marker-end="url(#arrow)" />
              <!-- Nós -->
              <rect x="12" y="22" width="148" height="46" rx="8" fill="#172033" stroke="#00e5ff" />
              <text x="86" y="42" fill="#fff" font-size="11" font-weight="bold" text-anchor="middle">Caicó (3 ERBs)</text>
              <text x="86" y="57" fill="#7dd3fc" font-size="9.5" text-anchor="middle">54,1 km • 11FX • Torre 25m</text>

              <rect x="12" y="102" width="148" height="46" rx="8" fill="#172033" stroke="#00e5ff" />
              <text x="86" y="122" fill="#fff" font-size="11" font-weight="bold" text-anchor="middle">Jardim do Seridó</text>
              <text x="86" y="137" fill="#7dd3fc" font-size="9.5" text-anchor="middle">20,1 km • 11FX • Torre 20m</text>

              <rect x="12" y="182" width="148" height="46" rx="8" fill="#172033" stroke="#00e5ff" />
              <text x="86" y="202" fill="#fff" font-size="11" font-weight="bold" text-anchor="middle">Carnaúba (Urbana)</text>
              <text x="86" y="217" fill="#7dd3fc" font-size="9.5" text-anchor="middle">3,55 km • 5XHD • Torre 20m</text>

              <rect x="282" y="96" width="144" height="58" rx="8" fill="#122b22" stroke="#00ff55" stroke-width="2" />
              <text x="354" y="117" fill="#00ff55" font-size="11" font-weight="bold" text-anchor="middle">Rep. Cume 69 (Pico)</text>
              <text x="354" y="132" fill="#cbd5e1" font-size="9.5" text-anchor="middle">666 m • Torre 20m</text>
              <text x="354" y="145" fill="#94a3b8" font-size="9" text-anchor="middle">30,6 km • 11FX → CCC</text>

              <rect x="500" y="96" width="150" height="58" rx="8" fill="#331520" stroke="#ff1744" stroke-width="2" />
              <text x="575" y="117" fill="#fff" font-size="11" font-weight="bold" text-anchor="middle">CCC Currais Novos</text>
              <text x="575" y="132" fill="#fda4af" font-size="9.5" text-anchor="middle">2 ERBs • 45m / 25m</text>
              <text x="575" y="145" fill="#cbd5e1" font-size="9" text-anchor="middle">35,3 km → Cume 28</text>

              <rect x="722" y="96" width="122" height="58" rx="8" fill="#122b22" stroke="#00ff55" stroke-width="2" />
              <text x="783" y="117" fill="#00ff55" font-size="11" font-weight="bold" text-anchor="middle">Rep. Cume 28</text>
              <text x="783" y="132" fill="#cbd5e1" font-size="9.5" text-anchor="middle">681 m • Torre 25m</text>
              <text x="783" y="145" fill="#94a3b8" font-size="9" text-anchor="middle">22,9 km → Sta Cruz</text>

              <rect x="897" y="96" width="118" height="58" rx="8" fill="#172033" stroke="#00e5ff" />
              <text x="956" y="117" fill="#fff" font-size="11" font-weight="bold" text-anchor="middle">Santa Cruz</text>
              <text x="956" y="132" fill="#7dd3fc" font-size="9.5" text-anchor="middle">2 ERBs • 20m / 30m</text>
              <text x="956" y="145" fill="#94a3b8" font-size="9" text-anchor="middle">20,9 km → Cume 46</text>

              <rect x="1050" y="34" width="98" height="54" rx="8" fill="#122b22" stroke="#00ff55" stroke-width="2" />
              <text x="1099" y="54" fill="#00ff55" font-size="10.5" font-weight="bold" text-anchor="middle">Rep. Cume 46</text>
              <text x="1099" y="68" fill="#cbd5e1" font-size="9" text-anchor="middle">381 m • 20m</text>
              <text x="1099" y="80" fill="#94a3b8" font-size="8.5" text-anchor="middle">1 salto → NTL</text>

              <rect x="1050" y="166" width="98" height="54" rx="8" fill="#331520" stroke="#ff1744" stroke-width="2" />
              <text x="1099" y="186" fill="#fff" font-size="10.5" font-weight="bold" text-anchor="middle">CCC Natal</text>
              <text x="1099" y="200" fill="#fda4af" font-size="9" text-anchor="middle">76,7 km • 5XHD</text>
              <text x="1099" y="212" fill="#cbd5e1" font-size="8.5" text-anchor="middle">Torre 20m</text>
              <line x1="1099" y1="88" x2="1099" y2="164" stroke="#00ff55" stroke-width="2.5" marker-end="url(#arrow)" />
              <line x1="956" y1="96" x2="1050" y2="61" stroke="#00ff55" stroke-width="2.5" marker-end="url(#arrow)" />
            </svg>
          </div>
        </div>
      `;
    }}

    // =========================================================================
    // TERCEIRA INTERFACE: VISADA 3D LATERAL (THREE.JS + DEM 30m + SATÉLITE)
    // =========================================================================
    let cena3d = null, cam3d = null, rend3d = null, grupo3d = null, anim3dId = null;
    let orbit3d = {{ theta: Math.PI / 2, phi: 1.44, radius: 12, target: null, down: false, pan: false, lx: 0, ly: 0 }};
    let estado3d = {{ exag: 8, satelite: true, fresnel: true, curvatura: true, preset: 'side', polyAtual: null, listaLinks: [] }};

    function redimensionarCena3D() {{
      const host = document.getElementById('canvas-3d-host');
      if (!host || !rend3d || !cam3d) return;
      const w = host.clientWidth || window.innerWidth;
      const h = host.clientHeight || (window.innerHeight - 50);
      cam3d.aspect = w / Math.max(1, h);
      cam3d.updateProjectionMatrix();
      rend3d.setSize(w, h);
    }}
    window.addEventListener('resize', () => {{
      if (document.getElementById('view-3d').style.display === 'block') redimensionarCena3D();
    }});

    function inicializarCena3D() {{
      if (rend3d) return true;
      const host = document.getElementById('canvas-3d-host');
      if (typeof THREE === 'undefined') {{
        host.innerHTML = '<div style="display:flex;height:100%;align-items:center;justify-content:center;color:#fda4af;font-size:1rem;padding:24px;text-align:center;">Não foi possível carregar o motor 3D (Three.js CDN). Verifique sua conexão com a internet para visualizar a cena 3D.</div>';
        return false;
      }}
      const w = host.clientWidth || window.innerWidth;
      const h = host.clientHeight || (window.innerHeight - 50);
      cena3d = new THREE.Scene();
      cena3d.fog = new THREE.FogExp2(0x0b1120, 0.0022);

      cam3d = new THREE.PerspectiveCamera(44, w / Math.max(1, h), 0.05, 600);
      rend3d = new THREE.WebGLRenderer({{ antialias: true, alpha: true }});
      rend3d.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
      rend3d.setSize(w, h);
      host.innerHTML = '';
      host.appendChild(rend3d.domElement);

      cena3d.add(new THREE.AmbientLight(0xdbeafe, 0.72));
      const solDir = new THREE.DirectionalLight(0xffffff, 0.92);
      solDir.position.set(25, 45, 20);
      cena3d.add(solDir);
      const contraDir = new THREE.DirectionalLight(0x93c5fd, 0.35);
      contraDir.position.set(-20, 18, -25);
      cena3d.add(contraDir);

      grupo3d = new THREE.Group();
      cena3d.add(grupo3d);
      orbit3d.target = new THREE.Vector3(0, 0.5, 0);

      // Controles manuais de órbita / pan / zoom (compatível com file:// sem script adicional)
      const dom = rend3d.domElement;
      dom.addEventListener('contextmenu', e => e.preventDefault());
      dom.addEventListener('pointerdown', e => {{
        orbit3d.down = true;
        orbit3d.pan = (e.button === 2 || e.shiftKey);
        orbit3d.lx = e.clientX;
        orbit3d.ly = e.clientY;
      }});
      window.addEventListener('pointerup', () => {{ orbit3d.down = false; }});
      window.addEventListener('pointermove', e => {{
        if (!orbit3d.down || document.getElementById('view-3d').style.display !== 'block') return;
        const dx = e.clientX - orbit3d.lx;
        const dy = e.clientY - orbit3d.ly;
        orbit3d.lx = e.clientX;
        orbit3d.ly = e.clientY;
        if (orbit3d.pan) {{
          const fwd = new THREE.Vector3().subVectors(orbit3d.target, cam3d.position).normalize();
          const right = new THREE.Vector3().crossVectors(fwd, new THREE.Vector3(0, 1, 0)).normalize();
          const up = new THREE.Vector3().crossVectors(right, fwd).normalize();
          const scale = orbit3d.radius * 0.0014;
          orbit3d.target.addScaledVector(right, -dx * scale);
          orbit3d.target.addScaledVector(up, dy * scale);
        }} else {{
          orbit3d.theta -= dx * 0.0075;
          orbit3d.phi = Math.max(0.12, Math.min(Math.PI * 0.495, orbit3d.phi - dy * 0.0065));
        }}
        atualizarPosicaoCamera3D();
      }});
      dom.addEventListener('wheel', e => {{
        e.preventDefault();
        const factor = e.deltaY > 0 ? 1.12 : 0.89;
        orbit3d.radius = Math.max(0.8, Math.min(240, orbit3d.radius * factor));
        atualizarPosicaoCamera3D();
      }}, {{ passive: false }});

      const loop = () => {{
        anim3dId = requestAnimationFrame(loop);
        if (document.getElementById('view-3d').style.display === 'block') {{
          rend3d.render(cena3d, cam3d);
        }}
      }};
      loop();
      return true;
    }}

    function atualizarPosicaoCamera3D() {{
      if (!cam3d || !orbit3d.target) return;
      const {{ theta, phi, radius, target }} = orbit3d;
      cam3d.position.set(
        target.x + radius * Math.sin(phi) * Math.cos(theta),
        target.y + radius * Math.cos(phi),
        target.z + radius * Math.sin(phi) * Math.sin(theta)
      );
      cam3d.lookAt(target);
    }}

    function abrirVisada3D() {{
      alternarAba('3d');
      if (!inicializarCena3D()) return;

      // Preenche seletor com os enlaces disponíveis (Sol #1 + ativos + custom)
      const todos = [];
      [1, 2, 3].forEach(rk => (camadasSolucao[rk] || []).forEach(p => todos.push(p)));
      linksCustom.forEach(p => todos.push(p));
      estado3d.listaLinks = todos;

      const sel = document.getElementById('sel-link-3d');
      sel.innerHTML = todos.map((p, idx) => {{
        const d = p.dados;
        const tag = d.fixo ? `[Sol #${{d.rank_solucao}}]` : '[Custom]';
        const dist = d.distancia_km || haversineKm(d.origem_obj.latitude, d.origem_obj.longitude, d.destino_obj.latitude, d.destino_obj.longitude).toFixed(2);
        return `<option value="${{idx}}">${{tag}} ${{d.origem_obj.nome}} ➔ ${{d.destino_obj.nome}} (${{dist}} km)</option>`;
      }}).join('');

      let idxAlvo = 0;
      if (enlaceSelecionado) {{
        const achado = todos.indexOf(enlaceSelecionado);
        if (achado >= 0) idxAlvo = achado;
      }} else {{
        const car = todos.findIndex(p => p.dados.rank_solucao === 1 && p.dados.origem_obj.nome.includes('Carnaúba'));
        if (car >= 0) idxAlvo = car;
      }}
      sel.value = String(idxAlvo);
      selecionarLink3D(idxAlvo, true);
    }}

    async function selecionarLink3D(idx, resetCam = true) {{
      const poly = estado3d.listaLinks[Number(idx)];
      if (!poly) return;
      estado3d.polyAtual = poly;
      const d = poly.dados;
      const st1 = d.origem_obj, st2 = d.destino_obj;
      const distKm = haversineKm(st1.latitude, st1.longitude, st2.latitude, st2.longitude);

      if (resetCam) {{
        // Sugere exagero vertical didático conforme a distância do salto
        const autoExag = distKm < 8 ? 4 : (distKm < 25 ? 6 : 10);
        estado3d.exag = autoExag;
        document.getElementById('rng-exag-3d').value = String(autoExag);
        document.getElementById('lbl-exag-3d').textContent = `${{autoExag}}×`;
      }}
      await construirCenaLink3D(poly, resetCam);
    }}

    function atualizarExagero3D(val) {{
      estado3d.exag = Number(val) || 8;
      document.getElementById('lbl-exag-3d').textContent = `${{estado3d.exag}}×`;
      if (estado3d.polyAtual) construirCenaLink3D(estado3d.polyAtual, false);
    }}

    function alternarCamadaSatelite3D() {{
      estado3d.satelite = !estado3d.satelite;
      const b = document.getElementById('btn-3d-sat');
      b.textContent = estado3d.satelite ? '🛰️ Satélite: ON' : '⛰️ Relevo: Hipsométrico';
      b.classList.toggle('sky', estado3d.satelite);
      if (estado3d.polyAtual) construirCenaLink3D(estado3d.polyAtual, false);
    }}

    function alternarFresnel3D() {{
      estado3d.fresnel = !estado3d.fresnel;
      const b = document.getElementById('btn-3d-fresnel');
      b.textContent = estado3d.fresnel ? '🔵 Fresnel: ON' : '🔵 Fresnel: OFF';
      b.classList.toggle('active', estado3d.fresnel);
      if (estado3d.polyAtual) construirCenaLink3D(estado3d.polyAtual, false);
    }}

    function alternarCurvatura3D() {{
      estado3d.curvatura = !estado3d.curvatura;
      const b = document.getElementById('btn-3d-bulge');
      b.textContent = estado3d.curvatura ? '🌍 Terra k=4/3: ON' : '🌍 Terra k=4/3: Plana';
      b.classList.toggle('active', estado3d.curvatura);
      if (estado3d.polyAtual) construirCenaLink3D(estado3d.polyAtual, false);
    }}

    function definirCamera3D(preset) {{
      estado3d.preset = preset;
      ['side', 'aerial', 'tx'].forEach(k => {{
        const el = document.getElementById('cam-btn-' + k);
        if (el) el.classList.toggle('active', k === preset);
      }});
      if (!estado3d.polyAtual || !grupo3d || !grupo3d.userData.distKm) return;
      const {{ distKm, midY, halfWKm }} = grupo3d.userData;
      orbit3d.target.set(0, midY, 0);
      if (preset === 'side') {{
        orbit3d.theta = Math.PI / 2;
        orbit3d.phi = 1.46;
        orbit3d.radius = Math.max(distKm * 1.18, halfWKm * 2.2);
      }} else if (preset === 'aerial') {{
        orbit3d.theta = Math.PI * 0.34;
        orbit3d.phi = 1.02;
        orbit3d.radius = Math.max(distKm * 1.15, halfWKm * 2.4);
      }} else if (preset === 'tx') {{
        orbit3d.target.set(distKm * 0.18, midY, 0);
        orbit3d.theta = Math.PI + 0.08;
        orbit3d.phi = 1.44;
        orbit3d.radius = Math.max(distKm * 0.82, 4.0);
      }}
      atualizarPosicaoCamera3D();
    }}

    function obterCorredor3D(st1, st2, distKm) {{
      const tol = 0.003;
      const hit = CORREDORES_3D.find(c =>
        (Math.abs(c.a[0] - st1.latitude) < tol && Math.abs(c.a[1] - st1.longitude) < tol &&
         Math.abs(c.b[0] - st2.latitude) < tol && Math.abs(c.b[1] - st2.longitude) < tol) ||
        (Math.abs(c.a[0] - st2.latitude) < tol && Math.abs(c.a[1] - st2.longitude) < tol &&
         Math.abs(c.b[0] - st1.latitude) < tol && Math.abs(c.b[1] - st1.longitude) < tol)
      );
      if (!hit) return null;
      const invertido = !(Math.abs(hit.a[0] - st1.latitude) < tol && Math.abs(hit.a[1] - st1.longitude) < tol);
      return {{ grid: hit, invertido }};
    }}

    function criarSpriteRotulo3D(titulo, subtitulo, corBorda) {{
      const cv = document.createElement('canvas');
      cv.width = 512; cv.height = 128;
      const ctx = cv.getContext('2d');
      ctx.fillStyle = 'rgba(11, 16, 28, 0.90)';
      ctx.strokeStyle = corBorda;
      ctx.lineWidth = 5;
      ctx.beginPath();
      if (typeof ctx.roundRect === 'function') ctx.roundRect(8, 8, 496, 112, 18);
      else ctx.rect(8, 8, 496, 112);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = '#ffffff';
      ctx.font = 'bold 28px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(titulo.slice(0, 34), 256, 54);
      ctx.fillStyle = corBorda;
      ctx.font = 'bold 24px monospace';
      ctx.fillText(subtitulo, 256, 94);
      const tex = new THREE.CanvasTexture(cv);
      const mat = new THREE.SpriteMaterial({{ map: tex, transparent: true, depthTest: false }});
      return new THREE.Sprite(mat);
    }}

    function corHipsometrica(alt, minAlt, maxAlt) {{
      const t = Math.max(0, Math.min(1, (alt - minAlt) / Math.max(20, maxAlt - minAlt)));
      // Gradiente topográfico: vale verde-oliva -> planalto ocre -> crista granito/clara
      const c = new THREE.Color();
      if (t < 0.45) c.setRGB(0.14 + t * 0.55, 0.32 + t * 0.40, 0.20 + t * 0.12);
      else if (t < 0.78) c.setRGB(0.39 + (t - 0.45) * 0.65, 0.50 - (t - 0.45) * 0.12, 0.25 + (t - 0.45) * 0.20);
      else c.setRGB(0.60 + (t - 0.78) * 1.2, 0.50 + (t - 0.78) * 1.2, 0.42 + (t - 0.78) * 1.3);
      return c;
    }}

    function carregarTexturaSateliteCorredor(lats, lons, uvs, onReady) {{
      let minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
      for (let k = 0; k < lats.length; k++) {{
        if (lats[k] < minLat) minLat = lats[k];
        if (lats[k] > maxLat) maxLat = lats[k];
        if (lons[k] < minLon) minLon = lons[k];
        if (lons[k] > maxLon) maxLon = lons[k];
      }}
      const lon2tileX = (lo, z) => ((lo + 180) / 360) * Math.pow(2, z);
      const lat2tileY = (la, z) => {{
        const r = la * Math.PI / 180;
        return ((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2) * Math.pow(2, z);
      }};

      let zEscolhido = 10;
      for (let z = 14; z >= 8; z--) {{
        const x0 = Math.floor(lon2tileX(minLon, z)), x1 = Math.floor(lon2tileX(maxLon, z));
        const y0 = Math.floor(lat2tileY(maxLat, z)), y1 = Math.floor(lat2tileY(minLat, z));
        if ((x1 - x0 + 1) * (y1 - y0 + 1) <= 20) {{
          zEscolhido = z;
          break;
        }}
      }}
      const tx0 = Math.floor(lon2tileX(minLon, zEscolhido));
      const tx1 = Math.floor(lon2tileX(maxLon, zEscolhido));
      const ty0 = Math.floor(lat2tileY(maxLat, zEscolhido));
      const ty1 = Math.floor(lat2tileY(minLat, zEscolhido));
      const nx = tx1 - tx0 + 1, ny = ty1 - ty0 + 1;

      const tileCanvas = document.createElement('canvas');
      tileCanvas.width = nx * 256;
      tileCanvas.height = ny * 256;
      const ctx = tileCanvas.getContext('2d');

      for (let k = 0; k < lats.length; k++) {{
        const px = (lon2tileX(lons[k], zEscolhido) - tx0) * 256;
        const py = (lat2tileY(lats[k], zEscolhido) - ty0) * 256;
        uvs[k * 2] = px / tileCanvas.width;
        uvs[k * 2 + 1] = 1.0 - (py / tileCanvas.height);
      }}

      const promessas = [];
      for (let gx = tx0; gx <= tx1; gx++) {{
        for (let gy = ty0; gy <= ty1; gy++) {{
          promessas.push(new Promise(res => {{
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => {{
              ctx.drawImage(img, (gx - tx0) * 256, (gy - ty0) * 256, 256, 256);
              res(true);
            }};
            img.onerror = () => res(false);
            img.src = `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/${{zEscolhido}}/${{gy}}/${{gx}}`;
          }}));
        }}
      }}
      Promise.all(promessas).then(oks => {{
        if (oks.some(Boolean)) {{
          const tex = new THREE.CanvasTexture(tileCanvas);
          tex.anisotropy = 4;
          onReady(tex);
        }}
      }});
    }}

    let renderGen3d = 0;
    async function construirCenaLink3D(poly, resetCam) {{
      if (!grupo3d) return;
      const myGen = ++renderGen3d;
      while (grupo3d.children.length > 0) grupo3d.remove(grupo3d.children[0]);

      const d = poly.dados;
      const st1 = d.origem_obj, st2 = d.destino_obj;
      const rk = d.fixo ? (d.rank_solucao || 1) : null;
      const h1 = (rk && ALTURAS_SOL[rk] && ALTURAS_SOL[rk][d.id_origem] != null) ? ALTURAS_SOL[rk][d.id_origem] : (d.h_torre_origem_m || 15);
      const h2 = (rk && ALTURAS_SOL[rk] && ALTURAS_SOL[rk][d.id_destino] != null) ? ALTURAS_SOL[rk][d.id_destino] : (d.h_torre_destino_m || 15);
      const freq = Number(d.frequencia_ghz) || 11.0;

      const midLat = 0.5 * (st1.latitude + st2.latitude);
      const midLon = 0.5 * (st1.longitude + st2.longitude);
      const mPerLat = 111139.0;
      const mPerLon = 111139.0 * Math.cos(midLat * Math.PI / 180.0);
      const dxM = (st2.longitude - st1.longitude) * mPerLon;
      const dyM = (st2.latitude - st1.latitude) * mPerLat;
      const distM = Math.max(100, Math.hypot(dxM, dyM));
      const distKm = distM / 1000.0;
      const ux = dxM / distM, uy = dyM / distM;
      const rx = uy, ry = -ux;

      const encontrado = obterCorredor3D(st1, st2, distKm);
      let nu = 65, nv = 33, padKm = Math.max(0.6, distKm * 0.08), halfWKm = Math.max(2.2, Math.min(8.0, distKm * 0.22)), zArr = null;
      if (encontrado) {{
        const g = encontrado.grid;
        nu = g.nu; nv = g.nv;
        padKm = g.pad_m / 1000.0;
        halfWKm = g.w_m / 1000.0;
        zArr = new Float32Array(nu * nv);
        for (let j = 0; j < nv; j++) {{
          for (let i = 0; i < nu; i++) {{
            const sj = encontrado.invertido ? (nv - 1 - j) : j;
            const si = encontrado.invertido ? (nu - 1 - i) : i;
            zArr[j * nu + i] = g.z[sj * nu + si];
          }}
        }}
      }} else {{
        const prof = await getPerfilTerreno(st1.latitude, st1.longitude, st2.latitude, st2.longitude);
        const centro = prof || Array.from({{ length: 65 }}, () => 250);
        zArr = new Float32Array(nu * nv);
        for (let j = 0; j < nv; j++) {{
          const offFrac = Math.abs((j / (nv - 1)) * 2 - 1);
          for (let i = 0; i < nu; i++) {{
            const uIdx = Math.min(centro.length - 1, Math.max(0, Math.round((i / (nu - 1)) * (centro.length - 1))));
            zArr[j * nu + i] = centro[uIdx] - offFrac * 18.0;
          }}
        }}
      }}

      const ReEffM = 6371000.0 * (4.0 / 3.0);
      const exag = estado3d.exag;
      let minZ = 1e9, maxZ = -1e9;
      for (let k = 0; k < zArr.length; k++) {{
        if (zArr[k] < minZ) minZ = zArr[k];
        if (zArr[k] > maxZ) maxZ = zArr[k];
      }}
      const baseKm = (minZ - 30.0) / 1000.0;

      // Construção da malha 3D do terreno (1 unidade Three.js = 1 km)
      const nVerts = nu * nv;
      const positions = new Float32Array(nVerts * 3);
      const colors = new Float32Array(nVerts * 3);
      const uvs = new Float32Array(nVerts * 2);
      const lats = new Float32Array(nVerts);
      const lons = new Float32Array(nVerts);

      const xMinKm = -distKm / 2 - padKm, xMaxKm = distKm / 2 + padKm;
      const centerRow = Math.floor(nv / 2);
      const centerLinePts = [];

      for (let j = 0; j < nv; j++) {{
        const zKm = -halfWKm + (j / (nv - 1)) * (2 * halfWKm);
        for (let i = 0; i < nu; i++) {{
          const xKm = xMinKm + (i / (nu - 1)) * (xMaxKm - xMinKm);
          const idx = j * nu + i;
          const d1M = (xKm + distKm / 2) * 1000.0;
          const d2M = (distKm / 2 - xKm) * 1000.0;
          const curvM = (estado3d.curvatura && d1M >= 0 && d2M >= 0) ? (d1M * d2M) / (2 * ReEffM) : 0.0;
          const altM = zArr[idx] + curvM;
          const yKm = ((altM / 1000.0) - baseKm) * exag;

          positions[idx * 3] = xKm;
          positions[idx * 3 + 1] = yKm;
          positions[idx * 3 + 2] = zKm;

          const c = corHipsometrica(zArr[idx], minZ, maxZ);
          colors[idx * 3] = c.r;
          colors[idx * 3 + 1] = c.g;
          colors[idx * 3 + 2] = c.b;

          const ptsXM = xKm * 1000.0 * ux + zKm * 1000.0 * rx;
          const ptsYM = xKm * 1000.0 * uy + zKm * 1000.0 * ry;
          lats[idx] = midLat + ptsYM / mPerLat;
          lons[idx] = midLon + ptsXM / mPerLon;

          if (j === centerRow) centerLinePts.push(new THREE.Vector3(xKm, yKm + 0.008 * exag, 0));
        }}
      }}

      const indices = [];
      for (let j = 0; j < nv - 1; j++) {{
        for (let i = 0; i < nu - 1; i++) {{
          const a = j * nu + i, b = a + 1, c = (j + 1) * nu + i, dIdx = c + 1;
          indices.push(a, c, b, b, c, dIdx);
        }}
      }}
      const geoTerr = new THREE.BufferGeometry();
      geoTerr.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geoTerr.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      geoTerr.setAttribute('uv', new THREE.BufferAttribute(uvs, 2));
      geoTerr.setIndex(indices);
      geoTerr.computeVertexNormals();

      const matTerr = new THREE.MeshLambertMaterial({{
        vertexColors: true,
        side: THREE.DoubleSide
      }});
      const meshTerr = new THREE.Mesh(geoTerr, matTerr);
      grupo3d.add(meshTerr);

      // Fio sutil de grade topográfica no modo hipsométrico
      if (!estado3d.satelite) {{
        const wireMat = new THREE.MeshBasicMaterial({{ color: 0x38bdf8, wireframe: true, transparent: true, opacity: 0.14 }});
        grupo3d.add(new THREE.Mesh(geoTerr, wireMat));
      }} else {{
        carregarTexturaSateliteCorredor(lats, lons, uvs, (tex) => {{
          if (!estado3d.satelite) return;
          geoTerr.attributes.uv.needsUpdate = true;
          matTerr.map = tex;
          matTerr.vertexColors = false;
          matTerr.color.setHex(0xffffff);
          matTerr.needsUpdate = true;
        }});
      }}

      // Linha de corte do terreno exatamente sob o enlace (z = 0)
      const geoCorte = new THREE.BufferGeometry().setFromPoints(centerLinePts);
      grupo3d.add(new THREE.Line(geoCorte, new THREE.LineBasicMaterial({{ color: 0xfacc15 }})));

      // Elevações exatas do terreno sob TX e RX (do perfil real se disponível)
      const profCentro = await getPerfilTerreno(st1.latitude, st1.longitude, st2.latitude, st2.longitude);
      if (myGen !== renderGen3d) return;
      const altTxM = profCentro ? profCentro[0] : (st1.altitude_terreno_m || zArr[centerRow * nu + 4]);
      const altRxM = profCentro ? profCentro[profCentro.length - 1] : (st2.altitude_terreno_m || zArr[centerRow * nu + nu - 5]);

      const ySolo1 = ((altTxM / 1000.0) - baseKm) * exag;
      const ySolo2 = ((altRxM / 1000.0) - baseKm) * exag;
      const yAnt1 = ySolo1 + (h1 / 1000.0) * exag;
      const yAnt2 = ySolo2 + (h2 / 1000.0) * exag;

      // Calcula folga real sobre o perfil para colorir o feixe e Fresnel
      let piorFolga = 9999;
      const arrRef = profCentro || zArr.slice(centerRow * nu, (centerRow + 1) * nu);
      for (let i = 1; i < arrRef.length - 1; i++) {{
        const frac = i / (arrRef.length - 1);
        const d1 = frac * distKm;
        const d2 = distKm - d1;
        const curv = estado3d.curvatura ? ((d1 * 1000) * (d2 * 1000)) / (2 * ReEffM) : 0;
        const losM = (altTxM + h1) + ((altRxM + h2) - (altTxM + h1)) * frac;
        const r1 = 17.32 * Math.sqrt((d1 * d2) / (freq * distKm));
        const flg = (losM - 0.6 * r1) - (arrRef[i] + curv);
        if (flg < piorFolga) piorFolga = flg;
      }}
      const limpo = piorFolga >= 0;
      const corFeixe = limpo ? 0x00ff55 : 0xff3b3b;

      // Torres 3D (mastro + base + prato apontado para o outro lado)
      const x1 = -distKm / 2, x2 = distKm / 2;
      const rTorre = Math.max(0.035, distKm * 0.0045);
      const addTorre = (xPos, ySolo, yAnt, corHex, nome, altTorre) => {{
        const altMastro = Math.max(0.04, yAnt - ySolo);
        const mast = new THREE.Mesh(
          new THREE.CylinderGeometry(rTorre * 0.55, rTorre * 1.3, altMastro, 10),
          new THREE.MeshLambertMaterial({{ color: 0xe2e8f0 }})
        );
        mast.position.set(xPos, ySolo + altMastro / 2, 0);
        grupo3d.add(mast);

        const prato = new THREE.Mesh(
          new THREE.SphereGeometry(rTorre * 2.1, 14, 14),
          new THREE.MeshBasicMaterial({{ color: corHex }})
        );
        prato.position.set(xPos, yAnt, 0);
        grupo3d.add(prato);

        const lbl = criarSpriteRotulo3D(nome, `Torre ${{altTorre}} m • Solo ${{Math.round(xPos < 0 ? altTxM : altRxM)}} m`, xPos < 0 ? '#38bdf8' : '#00ff55');
        const escSpr = Math.max(1.2, distKm * 0.17);
        lbl.scale.set(escSpr, escSpr * 0.25, 1);
        lbl.position.set(xPos, yAnt + escSpr * 0.22, 0);
        grupo3d.add(lbl);
      }};
      addTorre(x1, ySolo1, yAnt1, 0x38bdf8, st1.nome, h1);
      addTorre(x2, ySolo2, yAnt2, 0x00ff55, st2.nome, h2);

      // Feixe central (Linha de Visada)
      const geoLos = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(x1, yAnt1, 0),
        new THREE.Vector3(x2, yAnt2, 0)
      ]);
      grupo3d.add(new THREE.Line(geoLos, new THREE.LineBasicMaterial({{ color: corFeixe }})));

      // Elipsoides 3D da 1ª Zona de Fresnel (100% F1 externo + 60% F1 interno)
      if (estado3d.fresnel) {{
        const segsU = 56, segsR = 16;
        const buildFresnelTube = (fator, hexCor, opacidade, wire) => {{
          const vPos = [], vIdx = [];
          for (let i = 0; i <= segsU; i++) {{
            const t = i / segsU;
            const d1 = t * distKm, d2 = (1 - t) * distKm;
            const x = x1 + t * distKm;
            const yCentro = yAnt1 + (yAnt2 - yAnt1) * t;
            const r1Km = (i === 0 || i === segsU) ? 0.001 : ((17.32 * Math.sqrt((d1 * d2) / (freq * distKm)) * fator) / 1000.0);
            const rY = r1Km * exag;
            const rZ = r1Km * Math.max(exag, 3.0);
            for (let k = 0; k <= segsR; k++) {{
              const ang = (k / segsR) * Math.PI * 2;
              vPos.push(x, yCentro + rY * Math.sin(ang), rZ * Math.cos(ang));
            }}
          }}
          for (let i = 0; i < segsU; i++) {{
            for (let k = 0; k < segsR; k++) {{
              const a = i * (segsR + 1) + k, b = a + segsR + 1;
              vIdx.push(a, b, a + 1, b, b + 1, a + 1);
            }}
          }}
          const fg = new THREE.BufferGeometry();
          fg.setAttribute('position', new THREE.Float32BufferAttribute(vPos, 3));
          fg.setIndex(vIdx);
          fg.computeVertexNormals();
          return new THREE.Mesh(fg, new THREE.MeshBasicMaterial({{
            color: hexCor, transparent: true, opacity: opacidade, wireframe: wire, side: THREE.DoubleSide, depthWrite: false
          }}));
        }};
        grupo3d.add(buildFresnelTube(1.0, 0x38bdf8, 0.16, true));
        grupo3d.add(buildFresnelTube(0.6, corFeixe, 0.28, false));
      }}

      let yCenterMin = Infinity;
      centerLinePts.forEach(pt => {{ if (pt.y < yCenterMin) yCenterMin = pt.y; }});
      const yMaxTopo = Math.max(yAnt1, yAnt2);
      const midY = 0.5 * (yMaxTopo + (Number.isFinite(yCenterMin) ? yCenterMin : 0));
      grupo3d.userData = {{ distKm, midY, halfWKm }};

      // Atualiza telemetria lateral
      const f1Max = 17.32 * Math.sqrt(distKm / (4.0 * freq));
      const curvMax = ((distKm * 1000) ** 2) / (8 * ReEffM);
      document.getElementById('telemetry-3d').innerHTML =
        `<div><b>${{st1.nome}}</b> ➔ <b>${{st2.nome}}</b></div>` +
        `<div>Distância: <b>${{distKm.toFixed(2)}} km</b> | Banda: <b>${{freq}} GHz</b> | Torres: <b>${{h1}}m / ${{h2}}m</b></div>` +
        `<div>Abaulamento k=4/3: <b>+${{curvMax.toFixed(1)}} m</b> | Raio 0.6·F1: <b>${{(0.6 * f1Max).toFixed(1)}} m</b></div>` +
        `<div>Status 3D: <b style="color:${{limpo ? '#00ff55' : '#ff6b6b'}};">${{limpo ? 'VISADA LIMPA (+' + piorFolga.toFixed(1) + ' m)' : 'OBSTRUÍDO (' + piorFolga.toFixed(1) + ' m)'}}</b></div>`;

      if (resetCam) definirCamera3D(estado3d.preset || 'side');
    }}

    // SELECIONA O ENLACE DE LONGA DISTÂNCIA PARA NATAL OU CAICÓ AO ABRIR
    setTimeout(() => {{
      if (camadasSolucao[1] && camadasSolucao[1].length > 0) {{
        const linkDestaque = camadasSolucao[1].find(p => p.dados.distancia_km > 45) || camadasSolucao[1][0];
        selecionarEnlace(linkDestaque);
      }}
    }}, 350);
  </script>
</body>
</html>
"""

caminho_saida = os.path.abspath("outputs/mapa_interativo.html")
with open(caminho_saida, "w", encoding="utf-8") as f:
    f.write(html_code)

caminho_index = os.path.abspath("index.html")
with open(caminho_index, "w", encoding="utf-8") as f:
    f.write(html_code)

print("=" * 80)
print(" UISP DESIGN CENTER + INTERFACE DE CÁLCULOS & ORÇAMENTO GERADOS!")
print(f" Arquivo: file://{caminho_saida}")
print("=" * 80)

webbrowser.open(f"file://{caminho_saida}")
