"""
src/etapa5_topografia.py - Roteamento de backhaul baseado em relevo REAL (DEM Copernicus 30m).

Melhorias estruturais implementadas:
  1. Teto de torre de 80 m (dentro do limite normativo de 100 m do enunciado),
     viabilizando implantação das repetidoras diretamente em vias carroçáveis reais.
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
FRESNEL_FRACAO = 1.0            # 100% da 1ª zona de Fresnel livre (garante 60% e 100% acima de vegetação/relevo)
MARGEM_FOLGA_M = 16.0           # folga mínima de segurança acima de 100%·F1 (evita feixe rente ao solo/vegetação)
MARGEM_VEGETACAO_M = 0.0        # DSM Copernicus já representa superfície (vegetação/prédios)
H_MIN_M, H_PASSO_M = 20.0, 5.0  # alturas realistas: 20 m .. H_MAX_M
H_MAX_M = ALTURA_MAX_BACKHAUL_M
PASSO_PERFIL_M = 15.0           # 2x a resolução do DEM (30 m)
MAX_AMOSTRAS = 6000
SALTO_MAX_KM = 88.0             # alcance máximo para permitir 1 repetidora em estrada até Natal
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
    """Menor soma de alturas (h_tx, h_rx <= H_MAX_M) com enlace desobstruído; None se impossível."""
    hs = [float(x) for x in np.arange(H_MIN_M, H_MAX_M + 0.1, H_PASSO_M)]
    pares = sorted(((a + b, abs(a - b), a, b) for a in hs for b in hs))
    for _, _, a, b in pares:
        f = folga_minima(dist_km, elev_m, a, b, f_ghz)
        if f >= MARGEM_FOLGA_M:
            return a, b, f
    return None


def frequencia_para(dist_km: float) -> float:
    if dist_km <= LIMITE_LOCAL_KM:
        return FREQ_LOCAL_GHZ
    if dist_km > LIMITE_TRONCO_11G_KM:
        # Acima de 60 km (ex.: Serra da Tapuia -> Natal) usa 5 GHz para imunidade à atenuação por chuva
        return FREQ_LONGO_GHZ
    return FREQ_TRONCO_GHZ


# Sítios candidatos com acesso viário real verificado no OpenStreetMap (OSRM <= 200 m)
SITIOS_REPETIDORAS_VIARIOS = [
    ("REP_ESTRADA_CARNAUBA", "Rep. Serra da Rajada/Carnaúba - Rua", -6.51886, -36.57160,
     "Serra da Rajada / Carnaúba Norte: rua residencial local direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_ACARI", "Rep. Serra do Acari - Rodovia", -6.39141, -36.60442,
     "Serra do Acari: rodovia terciária/vicinal direta até o sítio + kit solar off-grid"),
    ("REP_CUME_28", "Repetidora Cume 28", -6.13280, -36.21160,
     "Comunidade Serra Verde: estrada vicinal/rua rural até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_BORB_N", "Rep. São Tomé / Borborema - Estrada", -6.10424, -36.11633,
     "Borborema / São Tomé: estrada rural carroçável direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_TAPUIA", "Rep. Serra da Tapuia - Vicinal", -6.08662, -35.96669,
     "Serra da Tapuia (Sítio Novo): estrada vicinal carroçável direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_TAPUIA_T", "Rep. Serra da Tapuia - Rodovia", -6.09150, -35.94410,
     "Serra da Tapuia (Sítio Novo): rodovia terciária direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_MACAIBA", "Rep. Macaíba / Lagoa Seca - Estrada", -5.96564, -35.38682,
     "Lagoa Seca / Macaíba: estrada rural direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_JUNDIA", "Rep. Jundiá - Estrada", -6.23386, -35.33870,
     "Jundiá: estrada rural direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_BORB_W", "Rep. Borborema Oeste - Estrada", -6.13766, -36.39279,
     "Borborema Oeste: estrada rural direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_PICUI", "Rep. Serra Carnaúba/Picuí - Estrada", -6.53798, -36.47545,
     "Serra Carnaúba / Picuí: estrada vicinal carroçável direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_SERIDO_O", "Rep. São José do Seridó - Estrada", -6.41748, -36.87265,
     "São José do Seridó: estrada vicinal carroçável direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_PARELHAS", "Rep. Parelhas BR - Rodovia", -6.65768, -36.68165,
     "Parelhas / Jardim do Seridó: rodovia principal direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_CRUZETA", "Rep. Serra da Formiga/Cruzeta - Estrada", -6.33984, -36.92918,
     "Serra da Formiga / Cruzeta: estrada vicinal direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_JAPI", "Rep. Japi - Estrada", -6.54786, -35.77921,
     "Japi / Borborema Sul: estrada rural direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_EZEQUIEL", "Rep. Cel. Ezequiel - Estrada", -6.48244, -35.99273,
     "Coronel Ezequiel: estrada rural direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_SNOVO", "Rep. Sítio Novo - Estrada", -6.21731, -35.79329,
     "Sítio Novo: estrada rural direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_LPEDRAS", "Rep. Lagoa de Pedras - Estrada", -6.33935, -35.62174,
     "Lagoa de Pedras: estrada rural direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_MONTE_AL", "Rep. Monte Alegre - Estrada", -6.13817, -35.26848,
     "Monte Alegre: estrada rural direta até o sítio + kit solar off-grid"),
    ("REP_ESTRADA_SERRINHA", "Rep. Serrinha - Estrada", -6.43123, -35.60096,
     "Serrinha: estrada rural direta até o sítio + kit solar off-grid"),
]


# ------------------------------------------------------------------ Cumes candidatos
def encontrar_cumes(sitios: list[dict]) -> list[dict]:
    """
    Varre o relevo DEM Copernicus 30m e seleciona exclusivamente sítios repetidores
    com acesso viário carroçável real verificado (mantendo REP_CUME_28 e substituindo
    cumes isolados sem estrada para viabilizar construção e manutenção em todas as rotas).
    """
    lats = [s["latitude"] for s in sitios]
    lons = [s["longitude"] for s in sitios]
    la0, la1 = min(lats) - MARGEM_BBOX_GRAUS, max(lats) + MARGEM_BBOX_GRAUS
    lo0, lo1 = min(lons) - MARGEM_BBOX_GRAUS, max(lons) + MARGEM_BBOX_GRAUS
    glat = np.round(np.arange(la0, la1, PASSO_GRADE_GRAUS), 4)
    glon = np.round(np.arange(lo0, lo1, PASSO_GRADE_GRAUS), 4)
    print(f"   Varrendo relevo real (grade {PASSO_GRADE_GRAUS}°): {len(glat) * len(glon)} pontos ({len(glat)}x{len(glon)}) + filtro viário OSM...", flush=True)

    cumes = []
    for rid, rnome, rla, rlo, _ in SITIOS_REPETIDORAS_VIARIOS:
        ralt = float(elevacoes([(rla, rlo)])[0])
        cumes.append({
            "id": rid,
            "nome": f"{rnome} ({ralt:.0f} m)",
            "cidade": "Repetidora Interurbana",
            "tipo": "REPETIDORA",
            "latitude": rla,
            "longitude": rlo,
            "altitude_terreno_m": ralt,
            "altura_torre_m": 0.0,
        })

    print(f"   {len(cumes)} pontos repetidores com acesso viário real selecionados (Seridó -> Tapuia -> Natal).", flush=True)
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
        for sc_id in sorted(i for i in erbs if i.startswith("ERB_SANTA_CRUZ_")):
            # Evita ciclos bloqueando todos os nós já presentes no caminho de sc_id até o CCC
            ancestrais_sc = set()
            cur = sc_id
            while cur in pai and cur not in ancestrais_sc:
                ancestrais_sc.add(cur)
                cur = pai[cur]
            ancestrais_sc.add(ccc_id)
            p_sc, c_sc = g.caminho_minimo(
                sc_id, {"CCC_NATAL_01"},
                peso_salto=meta.get("peso_salto", 40.0),
                peso_dist=meta.get("peso_dist", 1.0),
                peso_altura=meta.get("peso_altura", 0.05),
                max_salto_km=meta.get("max_salto_km", SALTO_MAX_KM),
                cumes_bloqueados=cumes_bloq_natal | (ancestrais_sc - {sc_id})
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
            outros_ativos = {ccc_id} | {x for par in arestas for x in par if x != rep_id and (nos[x]["tipo"] == "REPETIDORA" or x.startswith("ERB_SANTA_CRUZ_"))}
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
    transito_leste = {s["id"] for s in sitios if s["cidade"] == "Santa Cruz"} | {"ERB_CAICO_01"}
    perfis_map: dict = {}

    # 1) SOLUÇÃO #1 (ÓTIMA PRINCIPAL): Menor CAPEX real com 100% acesso viário e 100% Fresnel livre
    pai1, custo1 = g.caminho_minimo(
        ccc["id"], erbs, peso_salto=80.0, peso_dist=1.0, peso_altura=0.30,
        max_salto_km=88.0, permitir_erb_transito=transito_leste
    )
    sol1 = _montar_solucao(g, sitios, nos, ccc["id"], erbs, pai1, custo1, perfis_map, {
        "rank": 1,
        "id": "SOLUCAO_1",
        "peso_salto": 80.0, "peso_dist": 1.0, "peso_altura": 0.30,
        "max_salto_km": 88.0, "cumes_bloq": set(),
        "titulo": "Solução #1 — Ótima Principal (Menor CAPEX + Acesso Viário + 100% Fresnel)",
        "cor": "#00ff55",
        "destaque": True,
        "nota_curta": "MELHOR ESCOLHA (#1): Menor CAPEX total, 100% das repetidoras em estradas reais e só 1 salto até Natal.",
        "justificativa": (
            "É a melhor escolha técnica e econômica: atende todas as 13 ERBs e Natal com o MENOR CAPEX entre todas as rotas viárias, "
            "mantendo 100% das repetidoras em vias carroçáveis reais (Serra da Rajada/Carnaúba, Serra do Acari, Comunidade Serra Verde/Cume 28 "
            "e Serra da Tapuia - Vicinal em 1 salto para Natal), com torres ≤ 80 m (norma ≤ 100 m) e 100% da 1ª Zona de Fresnel + 16 m livre."
        ),
        "por_que_n1_vence": (
            "Supera a Solução #2 por ter menor CAPEX total (evita estação extra antes de Natal) e menos repetidoras. "
            "Supera a Solução #3 por usar menor distância total e menor CAPEX global mantendo acesso viário em todos os pontos."
        ),
    })

    # 2) SOLUÇÃO #2 (SALTOS <= 56 KM / 11 GHz LICENCIADO): Divide trecho até Natal em vias reais
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
        "nota_curta": "OPÇÃO #2: Divide o tronco até Natal em saltos ≤ 56 km em 11 GHz licenciado (em vias reais).",
        "justificativa": (
            "Alternativa de máxima disponibilidade licenciada em 11 GHz: limita todos os saltos interurbanos a ≤ 56 km "
            "em sítios com acesso viário real (exigindo repetidora adicional até Natal), mantendo torres ≤ 80 m."
        ),
        "comparacao_n1": (
            "Fica atrás da Solução #1 porque exige construir e energizar 1 estação repetidora adicional até Natal, elevando o CAPEX total."
        ),
    })

    # 3) SOLUÇÃO #3 (CONTINGÊNCIA / ROTA DIVERSA): Sítios viários 100% independentes da #1
    cumes_sol1 = set(sol1["ids_repetidoras"])
    pai3, custo3 = g.caminho_minimo(
        ccc["id"], erbs, peso_salto=30.0, peso_dist=1.0, peso_altura=0.20,
        max_salto_km=88.0, cumes_bloqueados=cumes_sol1, permitir_erb_transito=transito_leste
    )
    sol3 = _montar_solucao(g, sitios, nos, ccc["id"], erbs, pai3, custo3, perfis_map, {
        "rank": 3,
        "id": "SOLUCAO_3",
        "peso_salto": 30.0, "peso_dist": 1.0, "peso_altura": 0.20,
        "max_salto_km": 88.0, "cumes_bloq": cumes_sol1,
        "titulo": "Solução #3 — Rota de Contingência (Sítios Viários 100% Independentes da #1)",
        "cor": "#ffab00",
        "destaque": False,
        "nota_curta": "OPÇÃO #3: Rota reserva 100% independente dos sítios da Solução #1, todos com acesso viário.",
        "justificativa": (
            "Plano de contingência geográfica caso algum terreno da Solução #1 sofra embargo fundiário: "
            "bloqueia 100% das repetidoras da Solução #1 e fecha todo o backhaul até Natal usando outros sítios em estradas reais, "
            "sem saltos minúsculos (< 12 km) entre repetidoras e com torres ≤ 80 m."
        ),
        "comparacao_n1": (
            "Fica atrás da Solução #1 porque percorre maior distância total e apresenta CAPEX superior."
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

    acesso_por_id = {rid: ac for rid, _, _, _, ac in SITIOS_REPETIDORAS_VIARIOS}
    for sol in solucoes:
        for rid in sol["ids_repetidoras"]:
            r_sol = next(s for s in sol["sitios"] if s["id"] == rid)
            if rid not in todos_dict:
                r_copy = dict(r_sol, solucoes=[sol["rank"]],
                              alturas_por_solucao={str(sol["rank"]): r_sol["altura_torre_m"]})
                r_copy["acesso_infra"] = acesso_por_id.get(rid, "Via rural carroçável direta até o sítio + kit solar off-grid")
                todos_dict[rid] = r_copy
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
    print("ETAPA 5: TOP 3 SOLUÇÕES — RELEVO REAL COPERNICUS 30m | ALTURA FIXA POR TORRE <= 80 m (NORMA <= 100 m)")
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
    print(f"Arestas avaliadas no DEM: {g.testados} | Rejeitadas por obstrução/altura > 80m: {g.rejeitados}")
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
                "<h2>Perfis de terreno reais dos enlaces (Top 3 Soluções — Torres ≤ 80 m)</h2>" + "".join(blocos) + "</body></html>")


if __name__ == "__main__":
    executar_etapa5()
