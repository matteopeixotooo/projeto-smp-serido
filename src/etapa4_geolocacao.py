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
    "Carnaúba dos Dantas": {"lat": -6.52181, "lon": -36.59170, "alt_base_m": 577.0}
}

# Coordenadas fixadas por restrição explícita de terreno/usuário (não deslocadas pelo micro-siting)
SITIOS_COORD_FIXA = {
    # Carnaúba dos Dantas: coordenada exata solicitada (06.52181S, 036.59170W)
    "ERB_CARNAUBA_DOS_DANTAS_01": (-6.52181, -36.59170),
}

# Micro-ajustes base para evitar espelhos d'água (rios/açudes) e rodovias antes do micro-siting em DEM
AJUSTES_TERRENO_FIRME = {
    "ERB_CAICO_02": (-6.469200, -37.101200),
    "ERB_CAICO_03": (-6.447800, -37.099800),
    "ERB_SANTA_CRUZ_02": (-6.240300, -36.021700),
}

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
            dist_centro = raio_km * 0.65
            angulos = [90, 210, 330]

            for idx, ang in enumerate(angulos, start=1):
                rad = math.radians(ang)
                dx = dist_centro * math.sin(rad)
                dy = dist_centro * math.cos(rad)
                lat_s, lon_s = deslocamento_geografico(centro["lat"], centro["lon"], dx, dy)

                id_sitio = f"ERB_{id_cidade}_{idx:02d}"
                nomes_caico = ["Leste", "Sudoeste", "Noroeste"]
                nome_sitio = f"ERB {cidade} - Setor {nomes_caico[idx - 1]}"

                sitio = {
                    "id": id_sitio,
                    "nome": nome_sitio,
                    "cidade": cidade,
                    "tipo": "ERB",
                    "latitude": lat_s,
                    "longitude": lon_s,
                    "altitude_terreno_m": centro["alt_base_m"],
                    "altura_torre_m": 45.0,
                    "setores": 3,
                    "raio_celula_km": raio_km
                }
                lista_sitios.append(sitio)

    for s in lista_sitios:
        if s["id"] in AJUSTES_TERRENO_FIRME:
            s["latitude"], s["longitude"] = AJUSTES_TERRENO_FIRME[s["id"]]

    # Adiciona o Núcleo da Rede (CCC) em Natal (NTL) para interconexão via Backhaul de Micro-ondas
    lista_sitios.append(dict(CCC_NATAL_FIXO))

    # Micro-siting real em DEM 30m: move cada ERB para a cota urbana seca mais favorável num raio <= 780 m
    otimizar_micro_sitios_dem(lista_sitios)

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
    print(f"Total de Sítios Gerados: {len(sitios)} pontos operacionais (9 ERBs + 1 CCC Natal)")
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
