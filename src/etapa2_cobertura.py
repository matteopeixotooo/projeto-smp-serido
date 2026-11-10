"""src/etapa2_cobertura.py - Balanço de Potência de RF e Raio de Cobertura (COST 231 Hata)."""

import json
import math
import os
import pandas as pd
from src.config import (
    FREQ_SMP_MHZ,
    POT_TX_ERB_W,
    POT_TX_EM_W,
    GANHO_ANTENA_ERB_DBI,
    GANHO_ANTENA_EM_DBI,
    LIMIAR_RX_ERB_DBM,
    LIMIAR_RX_EM_DBM,
    ALTURA_PADRAO_ERB_M,
    ALTURA_EM_M,
    PERDAS_CABO_ERB_DB,
    PERDAS_CORPO_EM_DB,
    MARGEM_SOMBREAMENTO_DB,
)


def w_para_dbm(potencia_w: float) -> float:
    """Converte potência de Watts para dBm."""
    return 10.0 * math.log10(potencia_w * 1000.0)


def calcular_balanco_potencia():
    """Calcula a perda máxima de percurso permitida (PL_max) nos sentidos Uplink e Downlink."""
    p_tx_erb_dbm = w_para_dbm(POT_TX_ERB_W)  # 10 W = 40 dBm[cite: 1]
    p_tx_em_dbm = w_para_dbm(POT_TX_EM_W)  # 0.8 W = 29.03 dBm[cite: 1]

    # Enlace Reverso (Uplink: EM -> ERB) - Canal Restritivo
    # EIRP_em = P_tx_em + G_em - L_corpo
    eirp_em = p_tx_em_dbm + GANHO_ANTENA_EM_DBI - PERDAS_CORPO_EM_DB
    # P_rx_erb = EIRP_em - PL + G_erb - L_cabo >= LIMIAR_RX_ERB_DBM
    pl_max_uplink = (
        eirp_em
        + GANHO_ANTENA_ERB_DBI
        - PERDAS_CABO_ERB_DB
        - MARGEM_SOMBREAMENTO_DB
        - LIMIAR_RX_ERB_DBM
    )

    # Enlace Direto (Downlink: ERB -> EM)
    eirp_erb = (
        p_tx_erb_dbm + GANHO_ANTENA_ERB_DBI - PERDAS_CABO_ERB_DB
    )
    pl_max_downlink = (
        eirp_erb
        + GANHO_ANTENA_EM_DBI
        - PERDAS_CORPO_EM_DB
        - MARGEM_SOMBREAMENTO_DB
        - LIMIAR_RX_EM_DBM
    )

    # O sistema é limitado pelo enlace mais desfavorável
    pl_max_adotado = min(pl_max_uplink, pl_max_downlink)

    return {
        "p_tx_em_dbm": round(p_tx_em_dbm, 2),
        "p_tx_erb_dbm": round(p_tx_erb_dbm, 2),
        "pl_max_uplink_db": round(pl_max_uplink, 2),
        "pl_max_downlink_db": round(pl_max_downlink, 2),
        "pl_max_adotado_db": round(pl_max_adotado, 2),
        "gargalo": "Uplink (Reverso)"
        if pl_max_uplink < pl_max_downlink
        else "Downlink (Direto)",
    }


def calcular_raio_cost231_hata(
    pl_max_db: float,
    f_mhz: float = FREQ_SMP_MHZ,
    h_erb: float = ALTURA_PADRAO_ERB_M,
    h_em: float = ALTURA_EM_M,
    tipo_ambiente: str = "medio_pequeno",
) -> float:
    """Inverte a equação de perda de propagação do modelo COST 231 Hata para encontrar o raio R (km)."""
    # Fator de correção de altura da antena móvel a(h_m) para cidades médias/pequenas
    a_hm = (1.1 * math.log10(f_mhz) - 0.7) * h_em - (
        1.56 * math.log10(f_mhz) - 0.8
    )

    # Parâmetro de ambiente (C_m): 0 dB para médias/pequenas cidades, 3 dB para centros metropolitanos densos
    c_m = 0.0 if tipo_ambiente == "medio_pequeno" else 3.0

    # L_cost231 = A + B * log10(R)
    a = (
        46.3
        + 33.9 * math.log10(f_mhz)
        - 13.82 * math.log10(h_erb)
        - a_hm
        + c_m
    )
    b = 44.9 - 6.55 * math.log10(h_erb)

    # Isolando R: log10(R) = (L - A) / B
    log_r = (pl_max_db - a) / b
    raio_km = 10.0**log_r
    return raio_km


def calcular_area_cobertura_erb(raio_km: float) -> float:
    """Calcula a área de cobertura (km²) atendida por uma ERB tri-setorizada

    modelada pela geometria de célula hexagonal circunscrita de raio R.
    """
    return (3.0 * math.sqrt(3) / 2.0) * (raio_km**2)


def executar_etapa2(arquivo_etapa1: str = "outputs/demanda_capacidade.json"):
    # Carregar resultados da Etapa 1
    if not os.path.exists(arquivo_etapa1):
        # Fallback de diretório relativo se executado dentro de src/
        arquivo_etapa1 = "demanda_capacidade.json"

    with open(arquivo_etapa1, "r", encoding="utf-8") as f:
        dados_capacidade = json.load(f)

    # 1. Balanço de Potência de RF
    balanco = calcular_balanco_potencia()

    # 2. Raio Máximo de Cobertura
    raio_max_km = calcular_raio_cost231_hata(balanco["pl_max_adotado_db"])
    area_por_erb_km2 = calcular_area_cobertura_erb(raio_max_km)

    # Áreas estimadas de manchas urbanas consolidada (IBGE / Malhas Territoriais) em km²
    areas_urbanas_km2 = {
        "Caicó": 22.5,
        "Currais Novos": 14.8,
        "Santa Cruz": 12.0,
        "Jardim do Seridó": 5.2,
        "Carnaúba dos Dantas": 3.8,
    }

    resultados_finais = []
    for reg in dados_capacidade:
        cidade = reg["cidade"]
        area_urb = areas_urbanas_km2.get(cidade, 10.0)

        # Quantidade de ERBs exigidas pela mancha geográfica
        erbs_cobertura = math.ceil(area_urb / area_por_erb_km2)
        if erbs_cobertura == 0:
            erbs_cobertura = 1

        # O dimensionamento final do sítio é o maior valor entre a restrição de tráfego e a de área
        erbs_finais = max(reg["erbs_capacidade"], erbs_cobertura)

        criterio_dominante = (
            "Capacidade (Tráfego)"
            if reg["erbs_capacidade"] >= erbs_cobertura
            else "Cobertura (Área Urbana)"
        )

        resultados_finais.append(
            {
                "cidade": cidade,
                "populacao_total": reg["populacao_total"],
                "area_urbana_km2": area_urb,
                "erbs_por_capacidade": reg["erbs_capacidade"],
                "erbs_por_cobertura": erbs_cobertura,
                "erbs_finais_adotadas": erbs_finais,
                "criterio_dominante": criterio_dominante,
                "raio_cobertura_km": round(raio_max_km, 3),
                "area_erb_km2": round(area_por_erb_km2, 2),
            }
        )

    df = pd.DataFrame(resultados_finais)

    print("=" * 95)
    print("ETAPA 2: BALANÇO DE POTÊNCIA E DIMENSIONAMENTO DE COBERTURA")
    print("=" * 95)
    print(f"Potência Tx EM: {POT_TX_EM_W} W ({balanco['p_tx_em_dbm']} dBm)[cite: 1]")
    print(f"Potência Tx ERB: {POT_TX_ERB_W} W ({balanco['p_tx_erb_dbm']} dBm)[cite: 1]")
    print(
        f"Perda Máxima Permitida (Uplink):   {balanco['pl_max_uplink_db']} dB"
    )
    print(
        f"Perda Máxima Permitida (Downlink): {balanco['pl_max_downlink_db']} dB"
    )
    print(
        f"Gargalo do Sistema: {balanco['gargalo']} -> PL_max = {balanco['pl_max_adotado_db']} dB"
    )
    print(
        f"Raio Máximo de Célula (COST 231 Hata): R = {round(raio_max_km, 3)} km (Área = {round(area_por_erb_km2, 2)} km²)"
    )
    print("-" * 95)
    print(
        df[
            [
                "cidade",
                "area_urbana_km2",
                "erbs_por_capacidade",
                "erbs_por_cobertura",
                "erbs_finais_adotadas",
                "criterio_dominante",
            ]
        ].to_string(index=False)
    )
    print("=" * 95)

    os.makedirs("outputs", exist_ok=True)
    with open(
        "outputs/dimensionamento_cobertura.json", "w", encoding="utf-8"
    ) as f:
        json.dump(resultados_finais, f, indent=4, ensure_ascii=False)
    print("Ficheiro 'outputs/dimensionamento_cobertura.json' gerado com sucesso.")

    return resultados_finais


if __name__ == "__main__":
    executar_etapa2()