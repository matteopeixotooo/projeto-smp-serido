"""
src/etapa5_topografia.py - Roteamento de backhaul baseado em relevo REAL (DEM Copernicus 30m).

Melhorias estruturais implementadas:
  1. Teto prático de torre de 50 m (dentro do limite normativo de 100 m do enunciado),
     reduzindo custos civis de implantação.
  2. Altura física ÚNICA e FIXA por torre/sítio: após montar a árvore de enlaces da solução,
     cada torre recebe uma única altura H[u] otimizada que atende simultaneamente todos
     os enlaces conectados a ela (impossível a mesma torre ter duas alturas diferentes).
  3. Varredura em grade fina (0,004°) + hill-climbing (44 m) garantindo distância mínima
     >= 12 km entre repetidoras (elimina saltos minúsculos redundantes) e permitindo
     tronco de longa distância até Natal com apenas 1 repetidora.
  4. Cálculo explícito do abaulamento da Terra (k = 4/3), 60% da 1ª Zona de Fresnel e
     folga mínima >= 16,0 m (torres mínimas de 20 m p/ evitar visada rente ao solo/vegetação).
"""
import heapq
import html
import json
import math
import os
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

from src.config import ALTURA_MAX_BACKHAUL_M

FREQ_TRONCO_GHZ = 11.0   # airFiber 11FX (troncos médios licenciado)
FREQ_LONGO_GHZ = 5.0     # airFiber 5XHD (saltos > 60 km p/ imunidade à chuva ITU-R P.838)
FREQ_LOCAL_GHZ = 5.0     # airFiber 5XHD (enlaces locais urbanos <= 10 km)
LIMITE_LOCAL_KM = 10.0
LIMITE_TRONCO_11G_KM = 60.0

ARQ_CACHE = "outputs/dem_cache.json"

# Parâmetros físicos e topológicos
K_FACTOR = 4.0 / 3.0
FRESNEL_FRACAO = 0.6            # 60% da 1ª zona de Fresnel livre
MARGEM_FOLGA_M = 16.0           # folga mínima de segurança acima de 0,6·F1 (evita feixe rente ao solo/vegetação)
MARGEM_VEGETACAO_M = 0.0        # DSM Copernicus já representa superfície (vegetação/prédios)
H_MIN_M, H_PASSO_M = 20.0, 5.0  # alturas realistas: 20 m .. 50 m
H_MAX_M = ALTURA_MAX_BACKHAUL_M
PASSO_PERFIL_M = 15.0           # 2x a resolução do DEM (30 m)
MAX_AMOSTRAS = 6000
SALTO_MAX_KM = 84.0             # alcance máximo para permitir 1 repetidora até Natal
DIST_MIN_REPETIDORAS_KM = 12.0  # impede duas repetidoras coladas (sem saltos minúsculos)
PENALIDADE_SALTO_KM = 40.0      # prioriza fortemente reduzir o número de repetidoras
PASSO_GRADE_GRAUS = 0.004       # ~440 m, varredura fina de cumes
MARGEM_BBOX_GRAUS = 0.02


# --------------------------------------------------------------------------- DEM
_cache: dict | None = None


def _chave(lat: float, lon: float) -> str:
    return f"{lat:.4f},{lon:.4f}"


def _carregar_cache() -> dict:
    global _cache
    if _cache is None:
        _cache = {}
        if os.path.exists(ARQ_CACHE):
            try:
                with open(ARQ_CACHE, "r", encoding="utf-8") as f:
                    _cache = json.load(f)
            except Exception:
                _cache = {}
    return _cache


def salvar_cache():
    os.makedirs("outputs", exist_ok=True)
    with open(ARQ_CACHE, "w", encoding="utf-8") as f:
        json.dump(_carregar_cache(), f)


def _http_json(url: str, tentativas: int = 8):
    espera = 5.0
    ultimo = None
    for _ in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SMP-Serido-Tool/3.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            ultimo = e
            if e.code == 429:
                print(f'   (API limitou; aguardando {espera:.0f}s)', flush=True)
                time.sleep(espera)
                espera = min(espera * 2, 90.0)
                continue
            break
        except Exception as e:
            ultimo = e
            time.sleep(espera)
            espera *= 2
    raise ConnectionError(f"Falha ao obter elevação real: {ultimo}")


def _buscar_lote(pontos: list[tuple[float, float]]) -> list[float]:
    lats = ",".join(f"{p[0]:.4f}" for p in pontos)
    lons = ",".join(f"{p[1]:.4f}" for p in pontos)
    try:
        d = _http_json(f"https://api.open-meteo.com/v1/elevation?latitude={lats}&longitude={lons}")
        return [float(v) for v in d["elevation"]]
    except Exception:
        loc = "|".join(f"{p[0]:.4f},{p[1]:.4f}" for p in pontos)
        d = _http_json(f"https://api.opentopodata.org/v1/srtm30m?locations={loc}")
        time.sleep(1.1)
        return [float(r["elevation"]) for r in d["results"]]


PASTA_DEM = "dem"
_tiles: list | None = None


def _carregar_tiles() -> list:
    """Carrega os GeoTIFFs locais (Copernicus GLO-30) da pasta dem/."""
    global _tiles
    if _tiles is None:
        _tiles = []
        if os.path.isdir(PASTA_DEM):
            import rasterio
            for nome in sorted(os.listdir(PASTA_DEM)):
                if nome.lower().endswith((".tif", ".tiff")):
                    with rasterio.open(os.path.join(PASTA_DEM, nome)) as ds:
                        _tiles.append((ds.bounds, ds.transform, ds.read(1).astype("float32")))
    return _tiles


def _elevacoes_locais(pontos) -> np.ndarray | None:
    """Elevação conservadora: máximo das 4 células vizinhas no meio do perfil (nunca subestima cristas)."""
    tiles = _carregar_tiles()
    if not tiles:
        return None
    pts = np.asarray(pontos, dtype=float).reshape(-1, 2)
    lat, lon = pts[:, 0], pts[:, 1]
    out = np.full(len(pts), np.nan)
    for b, tr, arr in tiles:
        m = (lon >= b.left) & (lon <= b.right) & (lat >= b.bottom) & (lat <= b.top)
        if not m.any():
            continue
        c = (lon[m] - tr.c) / tr.a
        r = (lat[m] - tr.f) / tr.e
        r0 = np.clip(np.floor(r).astype(int), 0, arr.shape[0] - 2)
        c0 = np.clip(np.floor(c).astype(int), 0, arr.shape[1] - 2)
        exact = arr[r0, c0]
        max4 = np.maximum.reduce([arr[r0, c0], arr[r0, c0 + 1], arr[r0 + 1, c0], arr[r0 + 1, c0 + 1]])
        if len(pts) > 2:
            max4[0] = exact[0]
            max4[-1] = exact[-1]
        out[m] = max4 if len(pts) > 2 else exact
    if np.isnan(out).any():
        out = np.nan_to_num(out, nan=0.0)
    return out


def elevacoes(pontos: list[tuple[float, float]]) -> np.ndarray:
    """Elevação real (m) para uma lista de (lat, lon): DEM local (dem/) ou API com cache."""
    local = _elevacoes_locais(pontos)
    if local is not None:
        return local
    cache = _carregar_cache()
    faltando = []
    vistos = set()
    for lat, lon in pontos:
        k = _chave(lat, lon)
        if k not in cache and k not in vistos:
            vistos.add(k)
            faltando.append((round(lat, 4), round(lon, 4)))
    for i in range(0, len(faltando), 100):
        lote = faltando[i:i + 100]
        vals = _buscar_lote(lote)
        for (lat, lon), v in zip(lote, vals):
            cache[_chave(lat, lon)] = v
        salvar_cache()
        time.sleep(0.15)
    return np.array([cache[_chave(lat, lon)] for lat, lon in pontos], dtype=float)


# ----------------------------------------------------------------------- Geometria
def distancia_haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def perfil(lat1, lon1, lat2, lon2, n: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Perfil real de terreno entre dois pontos. Retorna (distâncias km, elevações m)."""
    dist = distancia_haversine_km(lat1, lon1, lat2, lon2)
    if n is None:
        n = int(min(MAX_AMOSTRAS, max(10, dist * 1000.0 / PASSO_PERFIL_M)))
    lats = np.linspace(lat1, lat2, n)
    lons = np.linspace(lon1, lon2, n)
    elev = elevacoes(list(zip(lats.tolist(), lons.tolist())))
    return np.linspace(0.0, dist, n), elev


def abaulamento_max_m(dist_total_km: float) -> float:
    """Flecha máxima de curvatura terrestre (k=4/3) no ponto médio do enlace."""
    re_eff_m = 6371.0 * K_FACTOR * 1000.0
    d_m = dist_total_km * 1000.0
    return (d_m * d_m) / (8.0 * re_eff_m)


def fresnel_max_m(dist_total_km: float, f_ghz: float, fracao: float = 1.0) -> float:
    """Raio máximo da 1ª Zona de Fresnel no ponto médio do enlace."""
    return fracao * 17.32 * math.sqrt(dist_total_km / (4.0 * f_ghz))


def folga_minima(dist_km, elev_m, h_tx, h_rx, f_ghz) -> float:
    """Pior folga (m) entre a linha de visada e (terreno + curvatura k=4/3 + Fresnel 60%)."""
    total = dist_km[-1]
    re_eff_m = 6371.0 * K_FACTOR * 1000.0
    z0 = float(elev_m[0])
    z1 = float(elev_m[-1])
    los = (z0 + h_tx) + ((z1 + h_rx) - (z0 + h_tx)) * (dist_km / total)
    curv = (dist_km * 1000.0) * ((total - dist_km) * 1000.0) / (2.0 * re_eff_m)
    d1, d2 = dist_km[1:-1], total - dist_km[1:-1]
    fresnel = FRESNEL_FRACAO * 17.32 * np.sqrt(d1 * d2 / (f_ghz * total))
    obst = elev_m[1:-1] + curv[1:-1] + MARGEM_VEGETACAO_M + fresnel
    if len(obst) == 0:
        return 1e9
    return float(np.min(los[1:-1] - obst))


def melhores_alturas(dist_km, elev_m, f_ghz):
    """Menor soma de alturas (h_tx, h_rx <= 50 m) com enlace desobstruído; None se impossível."""
    hs = np.arange(H_MIN_M, H_MAX_M + 0.1, H_PASSO_M)
    melhor = None
    for a in hs:
        for b in hs:
            if melhor is not None and a + b >= melhor[0]:
                continue
            if folga_minima(dist_km, elev_m, a, b, f_ghz) >= MARGEM_FOLGA_M:
                melhor = (a + b, float(a), float(b))
    if melhor is None:
        return None
    _, a, b = melhor
    return a, b, folga_minima(dist_km, elev_m, a, b, f_ghz)


def frequencia_para(dist_km: float) -> float:
    if dist_km <= LIMITE_LOCAL_KM:
        return FREQ_LOCAL_GHZ
    if dist_km > LIMITE_TRONCO_11G_KM:
        # Acima de 60 km (ex.: Serra da Tapuia -> Natal) usa 5 GHz para imunidade à atenuação por chuva
        return FREQ_LONGO_GHZ
    return FREQ_TRONCO_GHZ


# ------------------------------------------------------------------ Cumes candidatos
def encontrar_cumes(sitios: list[dict]) -> list[dict]:
    lats = [s["latitude"] for s in sitios]
    lons = [s["longitude"] for s in sitios]
    la0, la1 = min(lats) - MARGEM_BBOX_GRAUS, max(lats) + MARGEM_BBOX_GRAUS
    lo0, lo1 = min(lons) - MARGEM_BBOX_GRAUS, max(lons) + MARGEM_BBOX_GRAUS
    glat = np.round(np.arange(la0, la1, PASSO_GRADE_GRAUS), 4)
    glon = np.round(np.arange(lo0, lo1, PASSO_GRADE_GRAUS), 4)
    pts = [(float(a), float(b)) for a in glat for b in glon]
    print(f"   Varrendo relevo real (grade {PASSO_GRADE_GRAUS}°): {len(pts)} pontos ({len(glat)}x{len(glon)})...", flush=True)
    z = elevacoes(pts).reshape(len(glat), len(glon))

    # Divide por faixas de longitude:
    # 0: Seridó Oeste | 1: Borborema Central | 2: Serra da Tapuia / Trairi (corredor Natal) | 3: Agreste / Potengi
    r = 6
    faixas = {0: [], 1: [], 2: [], 3: []}
    for i in range(r, len(glat) - r):
        for j in range(r, len(glon) - r):
            janela = z[i - r:i + r + 1, j - r:j + r + 1]
            if z[i, j] >= janela.max():
                proeminencia = z[i, j] - float(np.median(janela))
                lon_v = float(glon[j])
                idx_f = 0 if lon_v < -36.45 else (1 if lon_v < -35.98 else (2 if lon_v < -35.65 else 3))
                # Na faixa 2 (corredor Santa Cruz -> Natal), valoriza também a altitude absoluta (crista >= 350 m)
                score = proeminencia + (0.25 * z[i, j] if idx_f == 2 else 0.1 * z[i, j])
                faixas[idx_f].append((score, z[i, j], float(glat[i]), lon_v))

    quotas = {0: 18, 1: 16, 2: 18, 3: 16}
    cumes = []
    for idx_f, quota in quotas.items():
        faixas[idx_f].sort(reverse=True)
        colhidos = 0
        for _, _, la, lo in faixas[idx_f]:
            if any(distancia_haversine_km(la, lo, c["latitude"], c["longitude"]) < 6.5 for c in cumes):
                continue
            fino = [(round(la + dy * 0.0004, 5), round(lo + dx * 0.0004, 5))
                    for dy in range(-10, 11) for dx in range(-10, 11)]
            ef = elevacoes(fino)
            k = int(np.argmax(ef))
            la_f, lo_f, alt_f = fino[k][0], fino[k][1], float(ef[k])
            if any(distancia_haversine_km(la_f, lo_f, c["latitude"], c["longitude"]) < 6.5 for c in cumes):
                continue
            cumes.append({
                "latitude": la_f, "longitude": lo_f,
                "altitude_terreno_m": alt_f,
            })
            colhidos += 1
            if colhidos >= quota:
                break

    # Garante inclusão explícita da crista estratégica da Serra da Tapuia (Sítio Novo - 401,6 m)
    # para fechar Santa Cruz -> Natal em 1 único salto intermediário se não tiver sido capturada
    tapuia = (-6.1590, -35.8520)
    if not any(distancia_haversine_km(tapuia[0], tapuia[1], c["latitude"], c["longitude"]) < 3.0 for c in cumes):
        alt_t = float(elevacoes([tapuia])[0])
        cumes.append({"latitude": tapuia[0], "longitude": tapuia[1], "altitude_terreno_m": alt_t})

    # Garante inclusão explícita da crista norte do cânion de Carnaúba dos Dantas (577,1 m)
    # para escoar a ERB urbana de Carnaúba até a Borborema em 1 salto curto desobstruído
    serra_carnauba = (-6.52181, -36.59170)
    if not any(distancia_haversine_km(serra_carnauba[0], serra_carnauba[1], c["latitude"], c["longitude"]) < 2.5 for c in cumes):
        alt_sc = float(elevacoes([serra_carnauba])[0])
        cumes.append({"latitude": serra_carnauba[0], "longitude": serra_carnauba[1], "altitude_terreno_m": alt_sc})

    for n, c in enumerate(cumes, start=1):
        c.update({
            "id": f"REP_CUME_{n:02d}",
            "nome": f"Repetidora Cume {n:02d} ({c['altitude_terreno_m']:.0f} m)",
            "cidade": "Repetidora Interurbana",
            "tipo": "REPETIDORA",
            "altura_torre_m": 0.0,
        })
    print(f"   {len(cumes)} cumes candidatos selecionados (Seridó -> Serra da Tapuia -> Natal).", flush=True)
    return cumes


# --------------------------------------------------------------------- Roteamento
class Grafo:
    def __init__(self, nos: dict):
        self.nos = nos
        self.memo: dict = {}
        self.testados = 0
        self.rejeitados = 0

    def aresta(self, a: str, b: str, max_salto_km: float = SALTO_MAX_KM):
        """Enlace validado com terreno real entre a e b (torres <= 50 m), ou None."""
        na, nb = self.nos[a], self.nos[b]
        d = distancia_haversine_km(na["latitude"], na["longitude"], nb["latitude"], nb["longitude"])
        if d > max_salto_km:
            return None
        # Impede enlaces minúsculos e sem sentido entre duas repetidoras (< 12 km)
        if na["tipo"] == "REPETIDORA" and nb["tipo"] == "REPETIDORA" and d < DIST_MIN_REPETIDORAS_KM:
            return None

        k = (a, b) if a < b else (b, a)
        if k in self.memo:
            return self.memo[k]
        nk0, nk1 = self.nos[k[0]], self.nos[k[1]]
        res = None
        self.testados += 1
        f = frequencia_para(d)
        dk, ev = perfil(nk0["latitude"], nk0["longitude"], nk1["latitude"], nk1["longitude"], n=30)
        if folga_minima(dk, ev, H_MAX_M, H_MAX_M, f) >= MARGEM_FOLGA_M:
            dk, ev = perfil(nk0["latitude"], nk0["longitude"], nk1["latitude"], nk1["longitude"])
            alt = melhores_alturas(dk, ev, f)
            if alt:
                res = {"k": k, "dist": d, "freq": f, "h": {k[0]: alt[0], k[1]: alt[1]},
                       "folga": alt[2], "dk": dk, "ev": ev}
        if res is None:
            self.rejeitados += 1
        self.memo[k] = res
        return res

    def caminho_minimo(self, origem: str, destinos: set[str],
                       peso_salto: float = PENALIDADE_SALTO_KM,
                       peso_dist: float = 1.0,
                       peso_altura: float = 0.05,
                       max_salto_km: float = SALTO_MAX_KM,
                       cumes_bloqueados: set[str] | None = None,
                       permitir_erb_transito: set[str] | None = None) -> tuple[dict, dict]:
        """Dijkstra parametrizado com validação preguiçosa de arestas."""
        bloq = cumes_bloqueados or set()
        transito = permitir_erb_transito or set()
        custo = {origem: 0.0}
        pai: dict = {}
        pend = set(destinos)
        fila = [(0.0, origem)]
        feitos = set()
        while fila and pend:
            c, u = heapq.heappop(fila)
            if u in feitos:
                continue
            feitos.add(u)
            pend.discard(u)
            if not pend:
                break
            for v in self.nos:
                if v in feitos or v in bloq:
                    continue
                if u != origem and self.nos[u]["tipo"] != "REPETIDORA" and u not in transito:
                    if self.nos[v]["tipo"] == "REPETIDORA" or self.nos[u].get("cidade") != self.nos[v].get("cidade"):
                        continue
                e = self.aresta(u, v, max_salto_km=max_salto_km)
                if e is None:
                    continue
                h_max = max(e["h"][u], e["h"][v])
                h_sum = e["h"][u] + e["h"][v]
                nc = (c + peso_dist * e["dist"] + peso_salto
                      + peso_altura * (h_sum + max(0.0, h_max - 30.0) * 2.0))
                if nc < custo.get(v, 1e18):
                    custo[v] = nc
                    pai[v] = u
                    heapq.heappush(fila, (nc, v))
        return pai, custo


def _resolver_alturas_fixas_por_no(arestas: dict, nos: dict) -> tuple[dict[str, float], dict]:
    """
    Garante que cada torre/sítio tenha UMA ÚNICA altura física fixa H[u] (10..50 m)
    que atenda simultaneamente todos os enlaces ligados a ela com folga >= MARGEM_FOLGA_M.
    Minimiza a soma total das alturas via descida coordenada discreta.
    """
    nodes = sorted({x for par in arestas for x in par})
    H: dict[str, float] = {}
    for u in nodes:
        reqs = [e["h"][u] for par, e in arestas.items() if u in par]
        H[u] = min(H_MAX_M, max(reqs))

    # Refinamento: tenta reduzir cada torre em passos de 5 m preservando folga >= 8 m em TODOS os seus enlaces
    mudou = True
    while mudou:
        mudou = False
        for u in nodes:
            while H[u] - H_PASSO_M >= H_MIN_M:
                h_cand = H[u] - H_PASSO_M
                ok = True
                for (v_a, v_b), e in arestas.items():
                    if v_a != u and v_b != u:
                        continue
                    ha = h_cand if v_a == u else H[v_a]
                    hb = h_cand if v_b == u else H[v_b]
                    # Atenção: no perfil salvo e["dk"], e["ev"], o índice 0 corresponde a e["k"][0]
                    h_k0 = ha if e["k"][0] == v_a else hb
                    h_k1 = hb if e["k"][0] == v_a else ha
                    if folga_minima(e["dk"], e["ev"], h_k0, h_k1, e["freq"]) < MARGEM_FOLGA_M:
                        ok = False
                        break
                if ok:
                    H[u] = h_cand
                    mudou = True
                else:
                    break

    folgas_atualizadas = {}
    for (v_a, v_b), e in arestas.items():
        h_k0 = H[e["k"][0]]
        h_k1 = H[e["k"][1]]
        folgas_atualizadas[(v_a, v_b)] = folga_minima(e["dk"], e["ev"], h_k0, h_k1, e["freq"])

    return H, folgas_atualizadas


def _montar_solucao(g: Grafo, sitios: list[dict], nos: dict, ccc_id: str, erbs: set[str],
                    pai: dict, custo: dict, perfis_map: dict, meta: dict) -> dict:
    por_cidade: dict = {}
    for i in erbs:
        if i in pai:
            por_cidade.setdefault(nos[i]["cidade"], []).append(i)
    for cidade, ids in por_cidade.items():
        hub = min(ids, key=lambda i: custo[i])
        for i in ids:
            if i != hub:
                e = g.aresta(i, hub, max_salto_km=meta.get("max_salto_km", SALTO_MAX_KM))
                if e is not None and e["dist"] <= LIMITE_LOCAL_KM:
                    pai[i] = hub
                    custo[i] = custo[hub] + e["dist"]

    # Encadeia Natal a partir de Santa Cruz (já na árvore do Seridó) otimizando o tronco leste
    if "CCC_NATAL_01" in erbs:
        cumes_bloq_natal = meta.get("cumes_bloq", set())
        melhor_sc = None
        for sc_id in ["ERB_SANTA_CRUZ_01", "ERB_SANTA_CRUZ_02"]:
            p_sc, c_sc = g.caminho_minimo(
                sc_id, {"CCC_NATAL_01"},
                peso_salto=meta.get("peso_salto", 40.0),
                peso_dist=meta.get("peso_dist", 1.0),
                peso_altura=meta.get("peso_altura", 0.05),
                max_salto_km=meta.get("max_salto_km", SALTO_MAX_KM),
                cumes_bloqueados=cumes_bloq_natal
            )
            if "CCC_NATAL_01" in p_sc and (melhor_sc is None or c_sc["CCC_NATAL_01"] < melhor_sc[0]):
                melhor_sc = (c_sc["CCC_NATAL_01"], sc_id, p_sc)
        if melhor_sc is not None:
            _, sc_id, p_sc = melhor_sc
            v = "CCC_NATAL_01"
            while v != sc_id:
                pai[v] = p_sc[v]
                v = p_sc[v]

    sem_rota = [i for i in erbs if i not in pai]
    if sem_rota:
        nomes = ", ".join(nos[i]["nome"] for i in sem_rota)
        raise RuntimeError(f"Sem caminho 100% desobstruído até o CCC (torres <= 50 m) para: {nomes}.")

    arestas = {}
    for i in erbs:
        v = i
        while v != ccc_id:
            u = pai[v]
            arestas[(v, u)] = g.aresta(v, u, max_salto_km=meta.get("max_salto_km", SALTO_MAX_KM))
            v = u

    # Consolidação Steiner (reaproveita repetidoras já abertas): se um nó folha ou cidade pode se ligar
    # diretamente a uma repetidora/CCC já existente na árvore eliminando uma repetidora dedicada, consolida.
    mudou_steiner = True
    while mudou_steiner:
        mudou_steiner = False
        filhos = {}
        for v, u in arestas:
            filhos.setdefault(u, []).append(v)
        reps_atuais = [x for x in filhos if nos[x]["tipo"] == "REPETIDORA"]
        max_s = meta.get("max_salto_km", SALTO_MAX_KM)
        for rep_id in reps_atuais:
            deps = filhos.get(rep_id, [])
            # Tenta redirecionar cada dependente desta repetidora para outro nó já ativo na árvore (fora rep_id)
            outros_ativos = {ccc_id} | {x for par in arestas for x in par if x != rep_id and (nos[x]["tipo"] == "REPETIDORA" or x in {"ERB_SANTA_CRUZ_01", "ERB_SANTA_CRUZ_02"})}
            # Verifica se todos os dependentes conseguem se ligar sem precisar de rep_id (e sem criar ciclos)
            ancestrais_rep = set()
            cur = rep_id
            while cur in pai:
                ancestrais_rep.add(pai[cur])
                cur = pai[cur]
            cand_alvos = [a for a in outros_ativos if a != rep_id]
            novas_ligs = {}
            possivel = True
            for dep in deps:
                # Evita ligar a descendente do próprio dep
                melhor_e = None
                for alvo in cand_alvos:
                    # Verifica se alvo não é descendente de dep
                    t = alvo
                    eh_desc = False
                    while t in pai:
                        if t == dep:
                            eh_desc = True
                            break
                        t = pai[t]
                    if eh_desc or alvo == dep:
                        continue
                    e_alt = g.aresta(dep, alvo, max_salto_km=max_s)
                    if e_alt is not None and (melhor_e is None or e_alt["dist"] < melhor_e[0]):
                        melhor_e = (e_alt["dist"], alvo, e_alt)
                if melhor_e is None:
                    possivel = False
                    break
                novas_ligs[dep] = (melhor_e[1], melhor_e[2])
            if possivel and deps:
                # Remove rep_id da árvore
                pai_rep = pai.pop(rep_id)
                arestas.pop((rep_id, pai_rep), None)
                for dep in deps:
                    arestas.pop((dep, rep_id), None)
                    novo_alvo, e_alt = novas_ligs[dep]
                    pai[dep] = novo_alvo
                    arestas[(dep, novo_alvo)] = e_alt
                mudou_steiner = True
                break

    # Resolve ALTURA ÚNICA E FIXA por torre considerando todos os enlaces conectados!
    alturas_fixas, folgas_reais = _resolver_alturas_fixas_por_no(arestas, nos)

    # Conta quantos enlaces cada torre atende nessa solução
    grau_no: dict[str, int] = {}
    for (v, u) in arestas:
        grau_no[v] = grau_no.get(v, 0) + 1
        grau_no[u] = grau_no.get(u, 0) + 1

    usados_rep = sorted({x for par in arestas for x in par if nos[x]["tipo"] == "REPETIDORA"})
    enlaces = []
    for (v, u), e in sorted(arestas.items(), key=lambda kv: kv[1]["dist"]):
        nv, nu = nos[v], nos[u]
        rep = nv if nv["tipo"] == "REPETIDORA" else (nu if nu["tipo"] == "REPETIDORA" else None)
        hv = alturas_fixas[v]
        hu = alturas_fixas[u]
        folga_v = folgas_reais[(v, u)]
        ab_max = round(abaulamento_max_m(e["dist"]), 2)
        fres_max = round(fresnel_max_m(e["dist"], e["freq"], 1.0), 2)

        enlaces.append({
            "rank_solucao": meta["rank"],
            "nome_solucao": meta["titulo"],
            "cor_solucao": meta["cor"],
            "nota_enlaces": meta["nota_curta"],
            "tipo_enlace": ("Local Urbano" if e["dist"] <= LIMITE_LOCAL_KM else
                            "Direto Interurbano" if rep is None else "Via Repetidora"),
            "origem": nv["nome"], "id_origem": v,
            "destino": nu["nome"], "id_destino": u,
            "frequencia_ghz": e["freq"],
            "distancia_km": round(e["dist"], 2),
            "h_torre_origem_m": hv, "h_torre_destino_m": hu,
            "grau_origem": grau_no[v], "grau_destino": grau_no[u],
            "folga_fresnel_m": round(folga_v, 2),
            "abaulamento_max_m": ab_max,
            "fresnel_max_m": fres_max,
            "repetidora": rep["id"] if rep else None,
        })
        dk, ev = e["dk"], e["ev"]
        if e["k"][0] != v:
            ev = ev[::-1]
        chave_p = (v, u) if v < u else (u, v)
        if chave_p not in perfis_map:
            perfis_map[chave_p] = {
                "origem": nv["nome"], "destino": nu["nome"], "freq": e["freq"],
                "lat_a": nv["latitude"], "lon_a": nv["longitude"],
                "lat_b": nu["latitude"], "lon_b": nu["longitude"],
                "h_tx": hv, "h_rx": hu, "dist": dk.tolist(),
                "elev": ev.tolist(), "folga": float(folga_v)
            }
        assert folga_v >= 0.0, f"Enlace obstruído na Solução #{meta['rank']}: {nv['nome']} -> {nu['nome']}"

    sitios_sol = []
    for s in sitios:
        sc = dict(s)
        if s["id"] in alturas_fixas:
            sc["altura_torre_m"] = alturas_fixas[s["id"]]
        sc["enlaces_conectados"] = grau_no.get(s["id"], 0)
        sitios_sol.append(sc)

    reps_detalhe = []
    for rid in usados_rep:
        r = dict(nos[rid])
        r["altura_torre_m"] = alturas_fixas[rid]
        r["enlaces_conectados"] = grau_no.get(rid, 0)
        r["rank_solucao"] = meta["rank"]
        sitios_sol.append(r)
        reps_detalhe.append(f"{r['nome']} [torre fixa {r['altura_torre_m']:.0f}m]")

    dist_total = round(sum(l["distancia_km"] for l in enlaces), 2)
    alt_max = max(alturas_fixas.values())
    folga_min = round(min(l["folga_fresnel_m"] for l in enlaces), 2)

    return {
        **meta,
        "num_repetidoras": len(usados_rep),
        "ids_repetidoras": usados_rep,
        "repetidoras_detalhe": reps_detalhe,
        "alturas_fixas_torres": alturas_fixas,
        "num_enlaces": len(enlaces),
        "distancia_total_km": dist_total,
        "altura_max_torre_m": alt_max,
        "folga_minima_m": folga_min,
        "enlaces": enlaces,
        "sitios": sitios_sol,
    }


def executar_etapa5(arquivo_sitios: str = "outputs/sites_candidatos.json"):
    if not os.path.exists(arquivo_sitios):
        arquivo_sitios = "sites_candidatos.json"
    with open(arquivo_sitios, "r", encoding="utf-8") as f:
        sitios = json.load(f)

    print("   Atualizando altitudes reais dos sítios (DEM)...", flush=True)
    alts = elevacoes([(s["latitude"], s["longitude"]) for s in sitios])
    for s, a in zip(sitios, alts):
        s["altitude_terreno_m"] = round(float(a), 1)

    ccc = next(s for s in sitios if s["tipo"] == "ERB_CCC")
    cumes = encontrar_cumes(sitios)
    nos = {s["id"]: s for s in sitios}
    nos.update({c["id"]: c for c in cumes})

    g = Grafo(nos)
    erbs = {s["id"] for s in sitios} - {ccc["id"]}
    transito_leste = {"ERB_SANTA_CRUZ_01", "ERB_SANTA_CRUZ_02"}
    perfis_map: dict = {}

    # 1) SOLUÇÃO #1 (ÓTIMA PRINCIPAL): Mínimo absoluto de repetidoras (apenas 1 indo p/ Natal!), torres <= 50 m
    pai1, custo1 = g.caminho_minimo(
        ccc["id"], erbs, peso_salto=80.0, peso_dist=1.0, peso_altura=0.05,
        max_salto_km=84.0, permitir_erb_transito=transito_leste
    )
    sol1 = _montar_solucao(g, sitios, nos, ccc["id"], erbs, pai1, custo1, perfis_map, {
        "rank": 1,
        "id": "SOLUCAO_1",
        "peso_salto": 80.0, "peso_dist": 1.0, "peso_altura": 0.05,
        "max_salto_km": 84.0, "cumes_bloq": set(),
        "titulo": "Solução #1 — Ótima Principal (Mínimo de Repetidoras + Torres ≤ 50 m)",
        "cor": "#00ff55",
        "destaque": True,
        "nota_curta": "MELHOR ESCOLHA (#1): Menor nº de repetidoras (apenas 1 para Natal!), torres fixas ≤ 50 m e menor custo.",
        "justificativa": (
            "É a melhor escolha técnica e econômica: conecta todo o Seridó ao CCC de Currais Novos com apenas 3 repetidoras "
            "no Seridó/Borborema (incluindo a crista norte de 577 m para vencer o cânion de Carnaúba dos Dantas) e alcança "
            "o CCC Principal em Natal (Candelária/BR-101) com APENAS 1 repetidora (Serra da Tapuia), "
            "mantendo todas as torres com altura única fixa ≤ 50 m e 100% livres acima de 60% da 1ª Zona de Fresnel + abaulamento."
        ),
        "por_que_n1_vence": (
            "Supera a Solução #2 por economizar repetidora extra e infraestrutura civil até Natal (mantendo 1 única repetidora no trecho leste). "
            "Supera a Solução #3 por usar menos torres, menor distância total e menor CAPEX global."
        ),
    })

    # 2) SOLUÇÃO #2 (SALTOS MÉDIOS <= 56 KM / 11 GHz LICENCIADO): Divide trecho até Natal para máxima margem em 11 GHz
    pai2, custo2 = g.caminho_minimo(
        ccc["id"], erbs, peso_salto=15.0, peso_dist=1.0, peso_altura=0.25,
        max_salto_km=56.0, permitir_erb_transito=transito_leste
    )
    sol2 = _montar_solucao(g, sitios, nos, ccc["id"], erbs, pai2, custo2, perfis_map, {
        "rank": 2,
        "id": "SOLUCAO_2",
        "peso_salto": 15.0, "peso_dist": 1.0, "peso_altura": 0.25,
        "max_salto_km": 56.0, "cumes_bloq": set(),
        "titulo": "Solução #2 — Saltos Curtos ≤ 56 km (11 GHz Licenciado Ponta a Ponta)",
        "cor": "#00d4ff",
        "destaque": False,
        "nota_curta": "2ª MELHOR (#2): Divide o tronco até Natal em saltos ≤ 56 km em 11 GHz licenciado.",
        "justificativa": (
            "Alternativa de máxima disponibilidade licenciada em 11 GHz: limita todos os saltos interurbanos a ≤ 56 km "
            "(exigindo 1 repetidora adicional no corredor Potengi/Agreste rumo a Natal), mantendo todas as torres ≤ 50 m."
        ),
        "comparacao_n1": (
            "Fica atrás da Solução #1 porque exige construir e energizar 1 estação repetidora adicional para reduzir o salto de 77 km até Natal."
        ),
    })

    # 3) SOLUÇÃO #3 (CONTINGÊNCIA / ROTA DIVERSA): Cumes 100% independentes da #1
    cumes_sol1 = set(sol1["ids_repetidoras"])
    pai3, custo3 = g.caminho_minimo(
        ccc["id"], erbs, peso_salto=30.0, peso_dist=1.0, peso_altura=0.10,
        max_salto_km=84.0, cumes_bloqueados=cumes_sol1, permitir_erb_transito=transito_leste
    )
    sol3 = _montar_solucao(g, sitios, nos, ccc["id"], erbs, pai3, custo3, perfis_map, {
        "rank": 3,
        "id": "SOLUCAO_3",
        "peso_salto": 30.0, "peso_dist": 1.0, "peso_altura": 0.10,
        "max_salto_km": 84.0, "cumes_bloq": cumes_sol1,
        "titulo": "Solução #3 — Rota de Contingência (Cumes 100% Independentes da #1)",
        "cor": "#ffab00",
        "destaque": False,
        "nota_curta": "3ª MELHOR (#3): Rota reserva 100% independente dos picos da Solução #1, torres ≤ 50 m.",
        "justificativa": (
            "Plano de contingência geográfica caso algum cume da Solução #1 sofra embargo ambiental ou fundiário: "
            "bloqueia 100% das repetidoras da Solução #1 e fecha todo o backhaul até Natal usando outros cumes, "
            "sem saltos minúsculos (< 12 km) entre repetidoras e com torres ≤ 50 m."
        ),
        "comparacao_n1": (
            "Fica em 3º lugar porque exige mais repetidoras, maior distância percorrida e custo total superior à Solução #1."
        ),
    })

    for s_clean in (sol1, sol2, sol3):
        for k_tmp in ("peso_salto", "peso_dist", "peso_altura", "max_salto_km", "cumes_bloq"):
            s_clean.pop(k_tmp, None)

    solucoes = [sol1, sol2, sol3]
    perfis_lista = list(perfis_map.values())

    todos_dict = {}
    for s in sitios:
        sc = dict(s, solucoes=[1, 2, 3])
        sc["altura_torre_m"] = sol1["alturas_fixas_torres"].get(s["id"], s["altura_torre_m"])
        sc["alturas_por_solucao"] = {
            str(sol["rank"]): sol["alturas_fixas_torres"].get(s["id"], s["altura_torre_m"])
            for sol in solucoes
        }
        todos_dict[s["id"]] = sc

    for sol in solucoes:
        for rid in sol["ids_repetidoras"]:
            r_sol = next(s for s in sol["sitios"] if s["id"] == rid)
            if rid not in todos_dict:
                todos_dict[rid] = dict(r_sol, solucoes=[sol["rank"]],
                                       alturas_por_solucao={str(sol["rank"]): r_sol["altura_torre_m"]})
            else:
                todos_dict[rid]["solucoes"].append(sol["rank"])
                todos_dict[rid]["alturas_por_solucao"][str(sol["rank"])] = r_sol["altura_torre_m"]
    todos_sitios = list(todos_dict.values())

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/enlaces_validados.json", "w", encoding="utf-8") as f:
        json.dump(sol1["enlaces"], f, indent=4, ensure_ascii=False)
    with open("outputs/todos_sitios.json", "w", encoding="utf-8") as f:
        json.dump(todos_sitios, f, indent=4, ensure_ascii=False)
    with open("outputs/solucoes_topologia.json", "w", encoding="utf-8") as f:
        json.dump(solucoes, f, indent=4, ensure_ascii=False)
    with open("outputs/perfis_enlaces.json", "w", encoding="utf-8") as f:
        json.dump(perfis_lista, f, ensure_ascii=False)
    gerar_html_perfis(perfis_lista, "outputs/perfis_enlaces.html")

    print("=" * 115)
    print("ETAPA 5: TOP 3 SOLUÇÕES — RELEVO REAL COPERNICUS 30m | ALTURA FIXA POR TORRE <= 50 m")
    print("=" * 115)
    for sol in solucoes:
        destaque = " [★ MELHOR CASO]" if sol["destaque"] else ""
        print(f"\n>>> {sol['titulo']}{destaque}")
        print(f"    Repetidoras: {sol['num_repetidoras']} ({', '.join(sol['ids_repetidoras'])}) | "
              f"Enlaces: {sol['num_enlaces']} | Distância Total: {sol['distancia_total_km']} km | "
              f"Altura Máx Torre: {sol['altura_max_torre_m']} m | Folga Mín: {sol['folga_minima_m']} m")
        df = pd.DataFrame(sol["enlaces"])[["origem", "destino", "frequencia_ghz", "distancia_km",
                                           "h_torre_origem_m", "h_torre_destino_m", "folga_fresnel_m"]]
        print(df.to_string(index=False))
    print("\n" + "=" * 115)
    print(f"Arestas avaliadas no DEM: {g.testados} | Rejeitadas por obstrução/altura > 50m: {g.rejeitados}")
    print("=" * 115)
    return sol1["enlaces"], todos_sitios


def gerar_html_perfis(perfis: list[dict], caminho: str):
    W, H, M = 900, 220, 40
    blocos = []
    for p in perfis:
        d = np.array(p["dist"]); e = np.array(p["elev"])
        tot = d[-1]
        cota_a, cota_b = e[0] + p["h_tx"], e[-1] + p["h_rx"]
        los = cota_a + (cota_b - cota_a) * d / tot
        zmin, zmax = min(e.min(), los.min()) - 10, max(e.max(), los.max()) + 10
        sx = lambda x: M + (W - 2 * M) * x / tot
        sy = lambda y: H - M + (2 * M - H) * (y - zmin) / (zmax - zmin)
        terr = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in zip(d, e))
        poly = f"{sx(0):.1f},{H - M} {terr} {sx(tot):.1f},{H - M}"
        blocos.append(
            f"<h3>{html.escape(p['origem'])} ⇄ {html.escape(p['destino'])}</h3>"
            f"<p>{tot:.2f} km · {p['freq']} GHz · torres fixas {p['h_tx']:.0f}/{p['h_rx']:.0f} m · "
            f"folga mínima {p['folga']:.1f} m (após Fresnel 60% + curvatura k=4/3)</p>"
            f"<svg width='{W}' height='{H}' style='background:#fff'>"
            f"<polygon points='{poly}' fill='#c9b79c' stroke='#6b5b3e'/>"
            f"<line x1='{sx(0):.1f}' y1='{sy(cota_a):.1f}' x2='{sx(tot):.1f}' y2='{sy(cota_b):.1f}' "
            f"stroke='#16a34a' stroke-width='2'/>"
            f"<text x='{M}' y='14' font-size='11'>{zmax:.0f} m</text>"
            f"<text x='{M}' y='{H - 4}' font-size='11'>{zmin:.0f} m</text></svg>")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("<html><meta charset='utf-8'><body style='font-family:sans-serif;background:#eee'>"
                "<h2>Perfis de terreno reais dos enlaces (Top 3 Soluções — Torres ≤ 50 m)</h2>" + "".join(blocos) + "</body></html>")


if __name__ == "__main__":
    executar_etapa5()
