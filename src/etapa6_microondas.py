"""src/etapa6_microondas.py - Otimização de Antenas e Rádios com Catálogo Oficial Ubiquiti UISP."""

import json
import math
import os
import pandas as pd

# Catálogo oficial Ubiquiti presente no ISP Design Center (UISP)
CATALOGO_UBIQUITI = {
    11.0: [  # airFiber 11FX (11 GHz Licenciado)
        {
            "modelo_radio": "airFiber 11FX",
            "modelo_antena": "AF-11G35 (0.9m / 35 dBi)",
            "diametro_m": 0.9,
            "ganho_dbi": 35.0,
            "potencia_tx_dbm": 30.0,
            "sensibilidade_dbm": -73.0,
            "peso_kg": 18.0,
            "area_vento_m2": 0.75,
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
            "custo_relativo": 4.8,
        },
    ],
    5.0: [  # airFiber 5XHD (5 GHz)
        {
            "modelo_radio": "airFiber 5XHD",
            "modelo_antena": "AF-5G23-S45 (0.38m / 23 dBi)",
            "diametro_m": 0.38,
            "ganho_dbi": 23.0,
            "potencia_tx_dbm": 26.0,
            "sensibilidade_dbm": -74.0,
            "peso_kg": 3.2,
            "area_vento_m2": 0.14,
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
            "custo_relativo": 1.6,
        },
        {
            "modelo_radio": "airFiber 5XHD",
            "modelo_antena": "AF-5G34-S45 (1.05m / 34 dBi)",
            "diametro_m": 1.05,
            "ganho_dbi": 34.0,
            "potencia_tx_dbm": 26.0,
            "sensibilidade_dbm": -74.0,
            "peso_kg": 13.5,
            "area_vento_m2": 0.95,
            "custo_relativo": 2.5,
        },
    ],
}

MARGEM_FADING_MIN_DB = 30.0


def fspl_db(dist_km: float, freq_ghz: float) -> float:
    return 92.45 + 20.0 * math.log10(dist_km) + 20.0 * math.log10(freq_ghz)


def otimizar_hardware_ubiquiti(dist_km: float, freq_ghz: float) -> dict:
    opcoes = CATALOGO_UBIQUITI[freq_ghz]
    candidatos = []

    perda_espaco = fspl_db(dist_km, freq_ghz)

    for tx in opcoes:
        for rx in opcoes:
            # RSL = P_tx + G_tx + G_rx - FSPL - Perdas de jumper/conectores (1.5 dB total)
            rsl = (
                tx["potencia_tx_dbm"]
                + tx["ganho_dbi"]
                + rx["ganho_dbi"]
                - perda_espaco
                - 1.5
            )
            fm = rsl - rx["sensibilidade_dbm"]

            custo_par = tx["custo_relativo"] + rx["custo_relativo"]
            viavel = fm >= MARGEM_FADING_MIN_DB

            candidatos.append(
                {
                    "radio_utilizado": tx["modelo_radio"],
                    "antena_tx": tx["modelo_antena"],
                    "antena_rx": rx["modelo_antena"],
                    "diametro_tx_m": tx["diametro_m"],
                    "diametro_rx_m": rx["diametro_m"],
                    "rsl_dbm": round(rsl, 2),
                    "fade_margin_db": round(fm, 2),
                    "peso_antenas_kg": tx["peso_kg"] + rx["peso_kg"],
                    "area_vento_m2": round(
                        tx["area_vento_m2"] + rx["area_vento_m2"], 2
                    ),
                    "custo_relativo": custo_par,
                    "viavel": viavel,
                }
            )

    viaveis = [c for c in candidatos if c["viavel"]]
    if viaveis:
        # Menor custo e menor diâmetro (prioriza a menor antena viável)
        return min(
            viaveis,
            key=lambda x: (
                x["custo_relativo"],
                max(x["diametro_tx_m"], x["diametro_rx_m"]),
                x["fade_margin_db"],
            ),
        )

    return max(candidatos, key=lambda x: x["fade_margin_db"])


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
            "antena_rx",
            "fade_margin_db",
            "custo_relativo",
        ]
    ]

    print("=" * 120)
    print("ETAPA 6: OTIMIZAÇÃO DE HARDWARE UBIQUITI (airFiber 11FX / airFiber 5XHD)")
    print("=" * 120)
    print(df.to_string(index=False))
    print("=" * 120)

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/enlaces_com_antenas.json", "w", encoding="utf-8") as f:
        json.dump(enlaces_ubiquiti, f, indent=4, ensure_ascii=False)

    # Enriquece também as 3 soluções (solucoes_topologia.json) com os rádios e antenas Ubiquiti
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
        with open(arq_sol, "w", encoding="utf-8") as f:
            json.dump(solucoes, f, indent=4, ensure_ascii=False)

    print("Ficheiro 'outputs/enlaces_com_antenas.json' gravado com sucesso.")
    return enlaces_ubiquiti


if __name__ == "__main__":
    executar_etapa6()