"""src/etapa3_interferencia.py - Modelação da Relação Sinal-Interferência (S/I)

no pior caso geométrico para o cluster 4x3.
"""

import json
import math
import os
import pandas as pd
from src.config import CLUSTER_K, EXIGENCIA_SI_MIN_DB, SETORES_POR_ERB


def calcular_razao_reuso(k: int = CLUSTER_K) -> float:
    """Calcula o fator de redução de co-canal (razão de reuso Q = D / R)."""
    return math.sqrt(3.0 * k)


def calcular_si_pior_caso_downlink(
    q: float,
    expoente_perda: float = 3.5,
    modelo_interferentes: str = "rappaport_geometrico",
) -> tuple[float, float, list[float]]:
    """Calcula a relação Sinal-Interferência (S/I) no pior caso de Downlink (borda da célula).

    No cluster 4x3 com antenas setoriais de 120°, a setorização reduz o número
    de interferentes de primeira camada de 6 para 2 células co-canal que
    iluminam o setor.
    """
    # R normalizado = 1.0; D = Q * R = Q
    r = 1.0
    d = q * r

    if modelo_interferentes == "rappaport_geometrico":
        # Abordagem clássica de Theodore Rappaport:
        # Na ponta extrema do setor de 120°, as distâncias efetivas aos dois interferentes co-canal dominantes
        # são d1 ≈ D e d2 ≈ D + 0.7 * R (ou no pior caso angular estrito d1 ≈ D - R e d2 ≈ D)
        # Consideramos aqui o pior caso severo: d1 = D - R e d2 = D
        d1 = max(d - r, 0.1)
        d2 = d
        distancias_interf = [d1, d2]
    elif modelo_interferentes == "nominal_equidistante":
        # 2 interferentes co-canal à distância média D
        distancias_interf = [d, d]
    else:
        # 2 interferentes com d1 = D e d2 = D + 0.7*R
        distancias_interf = [d, d + 0.7 * r]

    # Potência do sinal desejado na borda da célula (d = R = 1.0): S = R^(-gamma)
    potencia_sinal_util = r ** (-expoente_perda)

    # Soma das potências das fontes interferentes: I = sum(Di^(-gamma))
    potencia_interferencia_total = sum(
        dist ** (-expoente_perda) for dist in distancias_interf
    )

    si_linear = potencia_sinal_util / potencia_interferencia_total
    si_db = 10.0 * math.log10(si_linear)

    return si_linear, si_db, distancias_interf


def executar_etapa3():
    q = calcular_razao_reuso(CLUSTER_K)  # Q = sqrt(12) ≈ 3.464

    # Varrimento por diferentes expoentes de atenuação do meio (gamma de 3.0 a 4.0)
    expoentes = [3.0, 3.3, 3.5, 3.8, 4.0]
    cenarios = [
        ("Nominal (2 interferentes a D)", "nominal_equidistante"),
        ("Rappaport Padrão (D e D+0.7R)", "rappaport_padrao"),
        ("Pior Caso Extremo (D-R e D)", "rappaport_geometrico"),
    ]

    tabela_resultados = []

    for nome_cenario, modo in cenarios:
        for gamma in expoentes:
            _, si_db, dists = calcular_si_pior_caso_downlink(
                q, expoente_perda=gamma, modelo_interferentes=modo
            )
            atende = si_db >= EXIGENCIA_SI_MIN_DB
            tabela_resultados.append(
                {
                    "Cenário": nome_cenario,
                    "Expoente (γ)": gamma,
                    "S/I Calculado (dB)": round(si_db, 2),
                    "S/I Exigido (dB)": EXIGENCIA_SI_MIN_DB,
                    "Margem (dB)": round(si_db - EXIGENCIA_SI_MIN_DB, 2),
                    "Conformidade": "APROVADO" if atende else "REPROVADO",
                }
            )

    df = pd.DataFrame(tabela_resultados)

    print("=" * 95)
    print("ETAPA 3: VALIDAÇÃO ANALÍTICA DA RELAÇÃO SINAL-INTERFERÊNCIA (S/I)")
    print("=" * 95)
    print(f"Topologia: Cluster K = {CLUSTER_K} ERBs | {SETORES_POR_ERB} setores por ERB (Configuração 4x3)")
    print(f"Fator de Redução Co-canal: Q = D/R = √(3·K) = √(12) ≈ {round(q, 4)}")
    print(f"Exigência Normativa de Projeto: S/I > {EXIGENCIA_SI_MIN_DB} dB")
    print("-" * 95)

    # Exibe resumo do pior caso extremo
    df_pior = df[df["Cenário"] == "Pior Caso Extremo (D-R e D)"]
    print(df_pior.to_string(index=False))
    print("=" * 95)

    # Exportação dos resultados
    os.makedirs("outputs", exist_ok=True)
    resumo_json = {
        "cluster_k": CLUSTER_K,
        "setorizacao": SETORES_POR_ERB,
        "razao_reuso_q": round(q, 4),
        "exigencia_min_db": EXIGENCIA_SI_MIN_DB,
        "resultados_simulacao": tabela_resultados,
    }

    with open(
        "outputs/relatorio_interferencia.json", "w", encoding="utf-8"
    ) as f:
        json.dump(resumo_json, f, indent=4, ensure_ascii=False)
    print("Ficheiro 'outputs/relatorio_interferencia.json' gravado com sucesso.")

    return resumo_json


if __name__ == "__main__":
    executar_etapa3()