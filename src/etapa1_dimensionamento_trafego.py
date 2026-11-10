import json
import math
import pandas as pd


def erlang_b(canais: int, trafego: float) -> float:
    """Calcula a probabilidade de bloqueio pelo modelo de Erlang B via recursividade estável."""
    if canais == 0:
        return 1.0
    b = 1.0
    for k in range(1, canais + 1):
        b = (trafego * b) / (k + trafego * b)
    return b


def erlang_b_capacidade(canais: int, gos_alvo: float = 0.02) -> float:
    """Calcula a capacidade máxima em Erlangs suportada por um número fixo de canais

    para um GoS (Grade of Service) específico através de busca binária.
    """
    if canais <= 0:
        return 0.0
    a_min, a_max = 0.001, float(canais)
    while erlang_b(canais, a_max) < gos_alvo:
        a_max *= 1.5

    for _ in range(50):
        a_mid = (a_min + a_max) / 2.0
        pb = erlang_b(canais, a_mid)
        if pb < gos_alvo:
            a_min = a_mid
        else:
            a_max = a_mid
    return a_mid


def dimensionar_cidade(
    nome: str,
    populacao: int,
    trafego_usuario: float = 0.015,
    fracao_mercado: float = 1 / 3,
    setores_por_erb: int = 3,
    max_canais_rf_setor: int = 8,
    slots_por_rf: int = 8,
    gos: float = 0.02,
) -> dict:
    """Calcula o tráfego oferecido, canais e número de ERBs por capacidade para um município."""
    # Base de assinantes da operadora (considerando 2 concorrentes)
    assinantes = populacao * fracao_mercado
    trafego_total_erl = assinantes * trafego_usuario

    # Cada portadora de RF possui 8 time slots; 1 slot do setor pode ser reservado para controlo/sinalização (BCCH)
    canais_voz_max_setor = (max_canais_rf_setor * slots_por_rf) - 1
    erlang_max_setor = erlang_b_capacidade(canais_voz_max_setor, gos)
    erlang_max_erb = erlang_max_setor * setores_por_erb

    # Quantidade mínima de ERBs para escoar o tráfego gerado
    erbs_capacidade = math.ceil(trafego_total_erl / erlang_max_erb)
    if erbs_capacidade == 0:
        erbs_capacidade = 1

    # Distribuição de tráfego por setor nas ERBs alocadas
    trafego_por_setor = trafego_total_erl / (erbs_capacidade * setores_por_erb)

    # Identificação do número ótimo de portadoras de RF por setor
    canais_rf_necessarios = 1
    for n_rf in range(1, max_canais_rf_setor + 1):
        canais_disponiveis = (n_rf * slots_por_rf) - 1
        if (
            erlang_b_capacidade(canais_disponiveis, gos)
            >= trafego_por_setor
        ):
            canais_rf_necessarios = n_rf
            break
    else:
        canais_rf_necessarios = max_canais_rf_setor

    return {
        "cidade": nome,
        "populacao_total": populacao,
        "assinantes_operadora": round(assinantes),
        "trafego_total_erl": round(trafego_total_erl, 2),
        "erbs_capacidade": erbs_capacidade,
        "setores_totais": erbs_capacidade * setores_por_erb,
        "trafego_por_setor_erl": round(trafego_por_setor, 2),
        "portadoras_rf_por_setor": canais_rf_necessarios,
        "capacidade_max_setor_erl": round(erlang_max_setor, 2),
    }


def executar_etapa1():
    # População dos municípios do escopo (Censo IBGE 2022)
    municipios = [
        {"nome": "Caicó", "pop": 61146},
        {"nome": "Currais Novos", "pop": 41311},
        {"nome": "Santa Cruz", "pop": 37313},
        {"nome": "Jardim do Seridó", "pop": 11655},
        {"nome": "Carnaúba dos Dantas", "pop": 7992},
    ]

    # Parâmetros definidos no projeto
    TRAFEGO_POR_USUARIO = 0.015  # 0,015 Erlang por assinante
    DIVISAO_MERCADO = 1 / 3  # Nossa empresa + 2 concorrentes no mercado
    SETORES_ERB = 3  # 3 células setorizadas por ERB
    MAX_CANAIS_RF = (
        8  # Máximo de 8 canais de RF para tráfego por setor
    )
    SLOTS_POR_CANAL = 8  # 8 time slots por canal de RF
    GOS_BLOQUEIO = 0.02  # Grau de serviço típico de 2% de bloqueio

    resultados = [
        dimensionar_cidade(
            cidade["nome"],
            cidade["pop"],
            trafego_usuario=TRAFEGO_POR_USUARIO,
            fracao_mercado=DIVISAO_MERCADO,
            setores_por_erb=SETORES_ERB,
            max_canais_rf_setor=MAX_CANAIS_RF,
            slots_por_rf=SLOTS_POR_CANAL,
            gos=GOS_BLOQUEIO,
        )
        for cidade in municipios
    ]

    df = pd.DataFrame(resultados)

    print("=" * 85)
    print("ETAPA 1: DIMENSIONAMENTO DE TRÁFEGO E CAPACIDADE (ERLANG B)")
    print("=" * 85)
    print(
        df[
            [
                "cidade",
                "populacao_total",
                "assinantes_operadora",
                "trafego_total_erl",
                "erbs_capacidade",
                "portadoras_rf_por_setor",
            ]
        ].to_string(index=False)
    )
    print("=" * 85)

    # Exportação para alimentar diretamente a Etapa 2
    with open("demanda_capacidade.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, indent=4, ensure_ascii=False)
    print("Ficheiro 'demanda_capacidade.json' gerado com sucesso.")


if __name__ == "__main__":
    executar_etapa1()