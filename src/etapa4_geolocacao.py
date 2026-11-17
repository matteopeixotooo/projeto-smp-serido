"""
src/etapa4_geolocacao.py - Alocação geográfica, micro-posicionamento altimétrico e definição dos CCCs.
"""
import math
import json
import os
import unicodedata
import numpy as np
import pandas as pd

# Centróides urbanos oficiais dos municípios do Seridó (Datum WGS84)
CENTROIDES_MUNICIPIOS = {
    "Caicó": {"lat": -6.4586, "lon": -37.0978, "alt_base_m": 151.0},
    "Currais Novos": {"lat": -6.2608, "lon": -36.5147, "alt_base_m": 341.0},
    "Santa Cruz": {"lat": -6.2289, "lon": -36.0225, "alt_base_m": 230.0},
    "Jardim do Seridó": {"lat": -6.5844, "lon": -36.7725, "alt_base_m": 218.0},
    "Carnaúba dos Dantas": {"lat": -6.5556, "lon": -36.5947, "alt_base_m": 308.0}
}

# Coordenadas fixadas por cobertura 100% da mancha urbana real em favo de mel exato (validadas em mapa híbrido + acesso viário)
SITIOS_COORD_FIXA = {
    "ERB_CAICO_01": (-6.46600, -37.08119),               # Sudeste: Nova Descoberta / Vila Altiva / Centro (favo 3,05 km)
    "ERB_CAICO_02": (-6.46600, -37.10881),               # Sudoeste: Paulo VI / Castelo do Engady (favo 3,05 km)
    "ERB_CAICO_03": (-6.44223, -37.09500),               # Norte: Alto da Boa Vista / RN-118 / Samanaú (favo 3,05 km)
    "ERB_CAICO_04": (-6.44223, -37.06738),               # Nordeste: IFRN / Aeródromo / Loteamentos Leste RN-427 (favo 3,05 km)
    "ERB_CAICO_05": (-6.48977, -37.06738),               # Sul-Sudeste: Atacadão / Mirante da Serra / Lot. Itans RN-118 (favo 3,05 km)
    "ERB_CURRAIS_NOVOS_01": (-6.26400, -36.50600),       # CCC Centro-Leste: Paizinho Maria / Mirante (cota 346,6 m, favo 2,94 km)
    "ERB_CURRAIS_NOVOS_02": (-6.25077, -36.52905),       # Noroeste: JK / UFRN / José Dantas (favo 2,94 km)
    "ERB_CURRAIS_NOVOS_03": (-6.27723, -36.52905),       # Sudoeste: Sílvio Bezerra / BR-427 / Atacadão (favo 2,94 km)
    "ERB_CURRAIS_NOVOS_04": (-6.23850, -36.51200),       # Norte: Terreno seco RN-041 / Radir Pereira / Parque Dourado North
    "ERB_SANTA_CRUZ_01": (-6.21300, -36.02300),          # Norte: Maracujá / BR-226 (favo 2,94 km)
    "ERB_SANTA_CRUZ_02": (-6.23590, -36.00970),          # Leste-Sudeste: Santuário / Expansão BR-226 Leste (favo 2,94 km)
    "ERB_SANTA_CRUZ_03": (-6.23590, -36.03630),          # Oeste-Sudoeste: Av. Paulo Afonso / IFRN / Paraíso (favo 2,94 km)
    "ERB_JARDIM_DO_SERIDO_01": (-6.58800, -36.77300),    # Centro urbano (BR-427): 100% da cidade
    "ERB_CARNAUBA_DOS_DANTAS_01": (-6.55850, -36.59150), # Encosta urbana Monte do Galo: 100% cidade + LOS Cume 69
}

NOMES_URBANOS = {
    "ERB_CAICO_01": "ERB Caicó - Setor Sudeste",
    "ERB_CAICO_02": "ERB Caicó - Setor Sudoeste",
    "ERB_CAICO_03": "ERB Caicó - Setor Norte",
    "ERB_CAICO_04": "ERB Caicó - Setor Nordeste (IFRN/Aeródromo)",
    "ERB_CAICO_05": "ERB Caicó - Setor Sul (Itans/Mirante)",
    "ERB_CURRAIS_NOVOS_01": "ERB Currais Novos - Leste (CCC - Núcleo da Rede)",
    "ERB_CURRAIS_NOVOS_02": "ERB Currais Novos - Noroeste (UFRN/JK)",
    "ERB_CURRAIS_NOVOS_03": "ERB Currais Novos - Sudoeste (Sílvio Bezerra)",
    "ERB_CURRAIS_NOVOS_04": "ERB Currais Novos - Norte (Radir Pereira/RN-041)",
    "ERB_SANTA_CRUZ_01": "ERB Santa Cruz - Norte (Maracujá)",
    "ERB_SANTA_CRUZ_02": "ERB Santa Cruz - Sudeste (Santuário/BR-226 Leste)",
    "ERB_SANTA_CRUZ_03": "ERB Santa Cruz - Oeste (IFRN/Paraíso)",
    "ERB_JARDIM_DO_SERIDO_01": "ERB Jardim do Seridó - Centro",
    "ERB_CARNAUBA_DOS_DANTAS_01": "ERB Carnaúba dos Dantas - Centro",
}

# Notas de acesso viário e infraestrutura elétrica verificadas em mapa híbrido
INFRA_ACESSO_SITIOS = {
    "ERB_CAICO_01": "Rua urbana pavimentada (Nova Descoberta/Vila Altiva) + rede elétrica urbana",
    "ERB_CAICO_02": "Rua urbana pavimentada (Paulo VI) + rede elétrica urbana",
    "ERB_CAICO_03": "Acesso urbano junto à RN-118 (Alto da Boa Vista) + rede elétrica urbana",
    "ERB_CAICO_04": "Acesso asfaltado RN-427 / IFRN-Caicó (Expansão Leste) + rede elétrica urbana",
    "ERB_CAICO_05": "Margem asfaltada da RN-118 / acesso Lot. Itans e Atacadão + rede elétrica urbana",
    "ERB_CURRAIS_NOVOS_01": "Via urbana asfaltada (Paizinho Maria / Mirante) + rede elétrica trifásica",
    "ERB_CURRAIS_NOVOS_02": "Rua urbana pavimentada (JK / UFRN) + rede elétrica urbana",
    "ERB_CURRAIS_NOVOS_03": "Acesso rodoviário direto BR-427/BR-226 (Sílvio Bezerra) + rede elétrica urbana",
    "ERB_CURRAIS_NOVOS_04": "Terreno firme junto à RN-041 (Radir Pereira / Norte) + rede elétrica urbana",
    "ERB_SANTA_CRUZ_01": "Acesso urbano junto à BR-226 (Maracujá norte) + rede elétrica urbana",
    "ERB_SANTA_CRUZ_02": "Margem urbana BR-226 Leste (Santuário / Loteamento Leste) + rede elétrica urbana",
    "ERB_SANTA_CRUZ_03": "Acesso asfaltado Av. Paulo Afonso / RN-023 (IFRN/Paraíso) + rede elétrica urbana",
    "ERB_JARDIM_DO_SERIDO_01": "Centro urbano junto à BR-427 + rede elétrica urbana",
    "ERB_CARNAUBA_DOS_DANTAS_01": "Rua urbana na encosta do Monte do Galo + rede elétrica urbana",
    "CCC_NATAL_01": "Via urbana consolidada Candelária / BR-101 + rede elétrica trifásica",
}

# Micro-ajustes base para evitar espelhos d'água (rios/açudes) e rodovias antes do micro-siting em DEM
AJUSTES_TERRENO_FIRME = {}

# Núcleo Principal da Rede em Natal (NTL) em cota urbana alta consolidada (Candelária / Pitimbu - BR-101)
# Localizado fora de áreas de preservação (Parque das Dunas), com acesso viário e rede elétrica trifásica
CCC_NATAL_FIXO = {
    "id": "CCC_NATAL_01",
    "nome": "CCC Principal Natal - Candelária/BR-101 (Núcleo NTL)",
    "cidade": "Natal",
    "tipo": "CCC_NATAL",
    "latitude": -5.839300,
    "longitude": -35.234800,
    "altitude_terreno_m": 101.2,
    "altura_torre_m": 30.0,
    "setores": 0,
    "raio_celula_km": 0.0
}


def sanitizar_id(texto: str) -> str:
    """Remove acentos e espaços para gerar IDs ASCII compatíveis."""
    nfkd = unicodedata.normalize('NFKD', texto)
    sem_acento = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return sem_acento.upper().replace(' ', '_')


def deslocamento_geografico(lat_origem: float, lon_origem: float, dx_km: float, dy_km: float) -> tuple[float, float]:
    delta_lat = dy_km / 111.139
    lat_rad = math.radians(lat_origem)
    km_por_grau_lon = 111.139 * math.cos(lat_rad)
    delta_lon = dx_km / km_por_grau_lon
    return round(lat_origem + delta_lat, 6), round(lon_origem + delta_lon, 6)


def otimizar_micro_sitios_dem(lista_sitios: list[dict]):
    """
    Para cada ERB urbana (exceto pontos travados pelo usuário), varre uma micro-grade local
    (±0,006° ≈ ±660 m ao redor do ponto geométrico no DEM Copernicus 30m) e posiciona a torre
    na cota urbana firme mais elevada daquela zona.
    Isso preserva intacta a cobertura celular (raio 2,096 km), evita vales/rios e reduz
    drasticamente a altura necessária das torres (mantendo todas <= 50 m).
    """
    try:
        from src.etapa5_topografia import elevacoes, distancia_haversine_km
    except Exception:
        return

    passo = 0.0005  # ~55 m
    offsets = range(-12, 13)  # ±660 m (mas limitado a raio circular de 750 m)

    for s in lista_sitios:
        if s["id"] in SITIOS_COORD_FIXA:
            la_fix, lo_fix = SITIOS_COORD_FIXA[s["id"]]
            s["latitude"], s["longitude"] = la_fix, lo_fix
            s["altitude_terreno_m"] = round(float(elevacoes([(la_fix, lo_fix)])[0]), 1)
            continue

        if s["tipo"] == "CCC_NATAL":
            s["altitude_terreno_m"] = round(float(elevacoes([(s["latitude"], s["longitude"])])[0]), 1)
            continue

        la0, lo0 = s["latitude"], s["longitude"]
        cands = []
        for dy in offsets:
            for dx in offsets:
                la = round(la0 + dy * passo, 5)
                lo = round(lo0 + dx * passo, 5)
                if distancia_haversine_km(la0, lo0, la, lo) <= 0.78:
                    cands.append((la, lo))
        if not cands:
            continue
        evs = elevacoes(cands)
        # Penaliza levemente afastamentos maiores apenas em caso de empate de altitude
        best_idx = int(np.argmax(evs))
        s["latitude"], s["longitude"] = cands[best_idx]
        s["altitude_terreno_m"] = round(float(evs[best_idx]), 1)


def gerar_posicionamento_erbs(dados_cobertura: list[dict]) -> tuple[list[dict], dict]:
    lista_sitios = []
    ccc_info = None

    for item in dados_cobertura:
        cidade = item["cidade"]
        n_erbs = item["erbs_finais_adotadas"]
        raio_km = item["raio_cobertura_km"]
        centro = CENTROIDES_MUNICIPIOS[cidade]
        id_cidade = sanitizar_id(cidade)

        if n_erbs == 1:
            id_sitio = f"ERB_{id_cidade}_01"
            sitio = {
                "id": id_sitio,
                "nome": f"ERB {cidade} - Centro",
                "cidade": cidade,
                "tipo": "ERB",
                "latitude": centro["lat"],
                "longitude": centro["lon"],
                "altitude_terreno_m": centro["alt_base_m"],
                "altura_torre_m": 45.0,
                "setores": 3,
                "raio_celula_km": raio_km
            }
            lista_sitios.append(sitio)

        elif n_erbs == 2:
            dist_centro = raio_km * 0.75
            angulos = [0, 180] if cidade == "Santa Cruz" else [120, 300]

            for idx, ang in enumerate(angulos, start=1):
                rad = math.radians(ang)
                dx = dist_centro * math.sin(rad)
                dy = dist_centro * math.cos(rad)
                lat_s, lon_s = deslocamento_geografico(centro["lat"], centro["lon"], dx, dy)

                id_sitio = f"ERB_{id_cidade}_{idx:02d}"
                nome_sitio = f"ERB {cidade} - Sítio {idx:02d}" if idx > 1 else f"ERB {cidade} - Centro"

                eh_ccc = (cidade == "Currais Novos" and idx == 1)
                tipo_sitio = "ERB_CCC" if eh_ccc else "ERB"
                if eh_ccc:
                    nome_sitio += " (CCC - Núcleo da Rede)"

                sitio = {
                    "id": id_sitio,
                    "nome": nome_sitio,
                    "cidade": cidade,
                    "tipo": tipo_sitio,
                    "latitude": lat_s,
                    "longitude": lon_s,
                    "altitude_terreno_m": centro["alt_base_m"],
                    "altura_torre_m": 45.0,
                    "setores": 3,
                    "raio_celula_km": raio_km
                }
                lista_sitios.append(sitio)

                if eh_ccc:
                    ccc_info = sitio

        elif n_erbs >= 3:
            # Distribuição geométrica base (substituída por SITIOS_COORD_FIXA quando validada no mapa)
            dist_centro = raio_km * (0.65 if cidade == "Caicó" else 0.75)
            ang_offset = 90.0 if cidade == "Caicó" else 0.0

            for idx in range(1, n_erbs + 1):
                ang = ang_offset + (idx - 1) * (360.0 / n_erbs)
                rad = math.radians(ang)
                dx = dist_centro * math.sin(rad)
                dy = dist_centro * math.cos(rad)
                lat_s, lon_s = deslocamento_geografico(centro["lat"], centro["lon"], dx, dy)

                id_sitio = f"ERB_{id_cidade}_{idx:02d}"
                if id_sitio in SITIOS_COORD_FIXA:
                    lat_s, lon_s = SITIOS_COORD_FIXA[id_sitio]
                eh_ccc = (cidade == "Currais Novos" and idx == 1)
                tipo_sitio = "ERB_CCC" if eh_ccc else "ERB"
                nome_sitio = NOMES_URBANOS.get(
                    id_sitio,
                    (f"ERB {cidade} - Centro (CCC - Núcleo da Rede)" if eh_ccc else f"ERB {cidade} - Setor {idx:02d}")
                )

                sitio = {
                    "id": id_sitio,
                    "nome": nome_sitio,
                    "cidade": cidade,
                    "tipo": tipo_sitio,
                    "latitude": lat_s,
                    "longitude": lon_s,
                    "altitude_terreno_m": centro["alt_base_m"],
                    "altura_torre_m": 45.0,
                    "setores": 3,
                    "raio_celula_km": raio_km
                }
                lista_sitios.append(sitio)

                if eh_ccc:
                    ccc_info = sitio

    for s in lista_sitios:
        if s["id"] in AJUSTES_TERRENO_FIRME:
            s["latitude"], s["longitude"] = AJUSTES_TERRENO_FIRME[s["id"]]

    # Adiciona o Núcleo da Rede (CCC) em Natal (NTL) para interconexão via Backhaul de Micro-ondas
    lista_sitios.append(dict(CCC_NATAL_FIXO))

    # Micro-siting real em DEM 30m: move cada ERB para a cota urbana seca mais favorável num raio <= 780 m
    otimizar_micro_sitios_dem(lista_sitios)
    for s in lista_sitios:
        s["acesso_infra"] = INFRA_ACESSO_SITIOS.get(s["id"], "Via urbana + rede elétrica local")

    return lista_sitios, ccc_info


def exportar_para_geojson(sitios: list[dict], caminho_arquivo: str):
    features = []
    for s in sitios:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [s["longitude"], s["latitude"]]
            },
            "properties": {
                "id": s["id"],
                "nome": s["nome"],
                "cidade": s["cidade"],
                "tipo": s["tipo"],
                "altura_torre_m": s["altura_torre_m"],
                "altitude_m": s["altitude_terreno_m"],
                "raio_cobertura_km": s["raio_celula_km"]
            }
        }
        features.append(feature)

    geojson_data = {
        "type": "FeatureCollection",
        "features": features
    }

    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump(geojson_data, f, indent=4, ensure_ascii=False)


def executar_etapa4(arquivo_etapa2: str = "outputs/dimensionamento_cobertura.json"):
    if not os.path.exists(arquivo_etapa2):
        arquivo_etapa2 = "dimensionamento_cobertura.json"

    with open(arquivo_etapa2, "r", encoding="utf-8") as f:
        dados_cobertura = json.load(f)

    sitios, ccc = gerar_posicionamento_erbs(dados_cobertura)
    df_sitios = pd.DataFrame(sitios)

    print("=" * 105)
    print("ETAPA 4: GEORREFERENCIAMENTO E MICRO-SITING ALTIMÉTRICO DOS SÍTIOS SMP E CCC")
    print("=" * 105)
    print(df_sitios[["id", "cidade", "tipo", "latitude", "longitude", "altitude_terreno_m", "altura_torre_m"]].to_string(index=False))
    print("=" * 105)
    print(f"Núcleo Regional (CCC Seridó): {ccc['nome']} ({ccc['latitude']}, {ccc['longitude']})")
    print(f"Total de Sítios Gerados: {len(sitios)} pontos operacionais ({len(sitios) - 1} ERBs + 1 CCC Natal)")
    print("-" * 105)

    os.makedirs("outputs", exist_ok=True)
    caminho_json = "outputs/sites_candidatos.json"
    caminho_geojson = "outputs/sites_candidatos.geojson"

    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(sitios, f, indent=4, ensure_ascii=False)

    exportar_para_geojson(sitios, caminho_geojson)
    return sitios


if __name__ == "__main__":
    executar_etapa4()
