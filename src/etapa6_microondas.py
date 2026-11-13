"""src/etapa6_microondas.py - Otimização de Antenas/Rádios Ubiquiti, Atenuação por Chuva (ITU-R P.838-3) e Orçamento CAPEX."""

import json
import math
import os
import pandas as pd

# Catálogo oficial Ubiquiti (UISP Design Center) com cotações de mercado (referência Brasil / Mercado Livre)
CATALOGO_UBIQUITI = {
    11.0: [  # airFiber 11FX (11 GHz Licenciado)
        {
            "modelo_radio": "airFiber 11FX",
            "modelo_antena": "AF-11G35 (0.9m / 35 dBi)",
            "diametro_m": 0.9,
            "ganho_dbi": 35.0,
            "potencia_tx_dbm": 30.0,
            "sensibilidade_dbm": -73.0,  # 64QAM / 256QAM operacional
            "peso_kg": 18.0,
            "area_vento_m2": 0.75,
            "preco_radio_brl": 6850.00,
            "preco_antena_brl": 3450.00,
            "custo_relativo": 3.0,
        },
        {
            "modelo_radio": "airFiber 11FX",
            "modelo_antena": "High-Gain Dish 1.2m (38.5 dBi)",
            "diametro_m": 1.2,
            "ganho_dbi": 38.5,
            "potencia_tx_dbm": 30.0,
            "sensibilidade_dbm": -73.0,
            "peso_kg": 38.0,
            "area_vento_m2": 1.30,
            "preco_radio_brl": 6850.00,
            "preco_antena_brl": 5200.00,
            "custo_relativo": 4.8,
        },
    ],
    5.0: [  # airFiber 5XHD (5 GHz - Cotações Mercado Livre / Brasil)
        {
            "modelo_radio": "airFiber 5XHD",
            "modelo_antena": "AF-5G23-S45 (0.38m / 23 dBi)",
            "diametro_m": 0.38,
            "ganho_dbi": 23.0,
            "potencia_tx_dbm": 26.0,
            "sensibilidade_dbm": -74.0,
            "peso_kg": 3.2,
            "area_vento_m2": 0.14,
            "preco_radio_brl": 3608.10,
            "preco_antena_brl": 950.00,
            "custo_relativo": 1.0,
        },
        {
            "modelo_radio": "airFiber 5XHD",
            "modelo_antena": "AF-5G30-S45 (0.65m / 30 dBi)",
            "diametro_m": 0.65,
            "ganho_dbi": 30.0,
            "potencia_tx_dbm": 26.0,
            "sensibilidade_dbm": -74.0,
            "peso_kg": 7.4,
            "area_vento_m2": 0.38,
            "preco_radio_brl": 3608.10,
            "preco_antena_brl": 1499.00,
            "custo_relativo": 1.6,
        },
        {
            "modelo_radio": "airFiber 5XHD",
            "modelo_antena": "AF-5G34-S45 (1.05m / 34 dBi)",
            "diametro_m": 1.05,
            "ganho_dbi": 34.0,
            "potencia_tx_dbm": 28.0,
            "sensibilidade_dbm": -76.0,  # 64QAM (>250 Mbps em 40 MHz)
            "peso_kg": 13.5,
            "area_vento_m2": 0.95,
            "preco_radio_brl": 3608.10,
            "preco_antena_brl": 2890.00,
            "custo_relativo": 2.5,
        },
    ],
}

MARGEM_FADING_MIN_DB = 24.0

# Custos referenciais de Infraestrutura Civil e Implantação (Torre <= 50 m)
CUSTO_TORRE_POR_METRO_BRL = 2100.00     # Torre autoportante/estaiada leve + fundação + SPDA
CUSTO_BASE_REPETIDORA_BRL = 38000.00    # Gabinete outdoor, banco de baterias/solar, cercado e acesso
CUSTO_BASE_ERB_BACKHAUL_BRL = 8500.00   # Adequação elétrica/rack no sítio SMP já existente


def fspl_db(dist_km: float, freq_ghz: float) -> float:
    return 92.45 + 20.0 * math.log10(dist_km) + 20.0 * math.log10(freq_ghz)


def atenuacao_chuva_itur_db(dist_km: float, freq_ghz: float, taxa_chuva_mmh: float = 50.0) -> float:
    """
    Calcula a atenuação por chuva intensa (R = 50 mm/h) conforme ITU-R P.838-3 + fator de redução P.530:
      gamma_R = k * R^alpha  [dB/km]
      L_eff = dist_km / (1 + dist_km / d0), com d0 = 35 * exp(-0.015 * R)
    """
    if freq_ghz <= 6.0:
        # Coeficientes médios ITU-R P.838-3 em ~5 GHz (quase imune à chuva)
        k_r, alpha_r = 0.000216, 1.44
    else:
        # Coeficientes médios ITU-R P.838-3 em ~11 GHz
        k_r, alpha_r = 0.01772, 1.214

    gamma_r = k_r * (taxa_chuva_mmh ** alpha_r)
    d0 = 35.0 * math.exp(-0.015 * taxa_chuva_mmh)
    r_fator = 1.0 / (1.0 + dist_km / d0)
    l_eff = dist_km * r_fator
    return round(gamma_r * l_eff, 2)


def otimizar_hardware_ubiquiti(dist_km: float, freq_ghz: float) -> dict:
    opcoes = CATALOGO_UBIQUITI[freq_ghz]
    candidatos = []
    perda_espaco = fspl_db(dist_km, freq_ghz)
    perda_chuva = atenuacao_chuva_itur_db(dist_km, freq_ghz, 50.0)

    for tx in opcoes:
        for rx in opcoes:
            rsl = (
                tx["potencia_tx_dbm"]
                + tx["ganho_dbi"]
                + rx["ganho_dbi"]
                - perda_espaco
                - 1.5
            )
            fm = rsl - rx["sensibilidade_dbm"]
            fm_chuva = fm - perda_chuva
            custo_brl = (
                tx["preco_radio_brl"] + tx["preco_antena_brl"]
                + rx["preco_radio_brl"] + rx["preco_antena_brl"]
            )
            custo_par = tx["custo_relativo"] + rx["custo_relativo"]
            # Exige >= 24 dB de margem limpa e margem positiva mesmo sob temporal de 50 mm/h
            viavel = (fm >= MARGEM_FADING_MIN_DB) and (fm_chuva >= 4.0)

            candidatos.append(
                {
                    "radio_utilizado": tx["modelo_radio"],
                    "antena_tx": tx["modelo_antena"],
                    "antena_rx": rx["modelo_antena"],
                    "ganho_tx_dbi": tx["ganho_dbi"],
                    "ganho_rx_dbi": rx["ganho_dbi"],
                    "potencia_tx_dbm": tx["potencia_tx_dbm"],
                    "sensibilidade_dbm": rx["sensibilidade_dbm"],
                    "diametro_tx_m": tx["diametro_m"],
                    "diametro_rx_m": rx["diametro_m"],
                    "fspl_db": round(perda_espaco, 2),
                    "atenuacao_chuva_50mmh_db": perda_chuva,
                    "rsl_dbm": round(rsl, 2),
                    "fade_margin_db": round(fm, 2),
                    "fade_margin_chuva_db": round(fm_chuva, 2),
                    "peso_antenas_kg": tx["peso_kg"] + rx["peso_kg"],
                    "area_vento_m2": round(tx["area_vento_m2"] + rx["area_vento_m2"], 2),
                    "custo_kits_brl": round(custo_brl, 2),
                    "custo_relativo": custo_par,
                    "viavel": viavel,
                }
            )

    viaveis = [c for c in candidatos if c["viavel"]]
    if viaveis:
        return min(
            viaveis,
            key=lambda x: (
                x["custo_kits_brl"],
                max(x["diametro_tx_m"], x["diametro_rx_m"]),
                -x["fade_margin_chuva_db"],
            ),
        )

    return max(candidatos, key=lambda x: x["fade_margin_chuva_db"])


def calcular_orcamento_solucao(sol: dict) -> dict:
    """Calcula o orçamento completo (Equipamentos Ativos + Torres + Infraestrutura) de uma solução."""
    custo_ativos = sum(l["custo_kits_brl"] for l in sol["enlaces"])
    alturas = sol.get("alturas_fixas_torres", {})
    custo_torres = 0.0
    custo_infra_sitios = 0.0
    for sid, h_m in alturas.items():
        custo_torres += h_m * CUSTO_TORRE_POR_METRO_BRL
        if sid.startswith("REP_"):
            custo_infra_sitios += CUSTO_BASE_REPETIDORA_BRL
        else:
            custo_infra_sitios += CUSTO_BASE_ERB_BACKHAUL_BRL

    total_capex = custo_ativos + custo_torres + custo_infra_sitios
    return {
        "custo_ativos_brl": round(custo_ativos, 2),
        "custo_torres_brl": round(custo_torres, 2),
        "custo_infra_sitios_brl": round(custo_infra_sitios, 2),
        "custo_total_capex_brl": round(total_capex, 2),
        "num_kits_radio_antena": len(sol["enlaces"]) * 2,
    }


def executar_etapa6(arquivo_enlaces: str = "outputs/enlaces_validados.json"):
    if not os.path.exists(arquivo_enlaces):
        arquivo_enlaces = "enlaces_validados.json"

    with open(arquivo_enlaces, "r", encoding="utf-8") as f:
        enlaces = json.load(f)

    enlaces_ubiquiti = []
    for link in enlaces:
        dist = link["distancia_km"]
        freq = link["frequencia_ghz"]
        hw = otimizar_hardware_ubiquiti(dist, freq)
        enlaces_ubiquiti.append({**link, **hw})

    df = pd.DataFrame(enlaces_ubiquiti)[
        [
            "origem",
            "destino",
            "frequencia_ghz",
            "distancia_km",
            "radio_utilizado",
            "antena_tx",
            "fade_margin_db",
            "atenuacao_chuva_50mmh_db",
            "fade_margin_chuva_db",
            "custo_kits_brl",
        ]
    ]

    print("=" * 130)
    print("ETAPA 6: HARDWARE UBIQUITI, ATENUAÇÃO POR CHUVA (ITU-R P.838-3 @ 50 mm/h) E ORÇAMENTO")
    print("=" * 130)
    print(df.to_string(index=False))
    print("=" * 130)

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/enlaces_com_antenas.json", "w", encoding="utf-8") as f:
        json.dump(enlaces_ubiquiti, f, indent=4, ensure_ascii=False)

    arq_sol = "outputs/solucoes_topologia.json"
    if os.path.exists(arq_sol):
        with open(arq_sol, "r", encoding="utf-8") as f:
            solucoes = json.load(f)
        for sol in solucoes:
            enlaces_sol_hw = []
            custo_hw_total = 0.0
            for link in sol["enlaces"]:
                hw = otimizar_hardware_ubiquiti(link["distancia_km"], link["frequencia_ghz"])
                custo_hw_total += hw["custo_relativo"]
                enlaces_sol_hw.append({**link, **hw})
            sol["enlaces"] = enlaces_sol_hw
            sol["custo_hardware_relativo"] = round(custo_hw_total, 1)
            sol["orcamento"] = calcular_orcamento_solucao(sol)
            print(f"Orçamento Solução #{sol['rank']}: Ativos R$ {sol['orcamento']['custo_ativos_brl']:,.2f} | "
                  f"Torres R$ {sol['orcamento']['custo_torres_brl']:,.2f} | "
                  f"Infra R$ {sol['orcamento']['custo_infra_sitios_brl']:,.2f} | "
                  f"TOTAL CAPEX: R$ {sol['orcamento']['custo_total_capex_brl']:,.2f}")
        with open(arq_sol, "w", encoding="utf-8") as f:
            json.dump(solucoes, f, indent=4, ensure_ascii=False)

    print("Ficheiro 'outputs/enlaces_com_antenas.json' gravado com sucesso.")
    return enlaces_ubiquiti


if __name__ == "__main__":
    executar_etapa6()
