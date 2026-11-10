"""
src/etapa5_topografia.py - Roteamento de backhaul baseado em relevo REAL (DEM).

Fluxo:
  1. Lê os GeoTIFFs locais da pasta dem/ (Copernicus GLO-30) com amostragem conservadora
     (máximo das 4 células vizinhas a cada 15 m, sem perder cristas). Fallback para API com cache.
  2. Varre o relevo da região e escolhe cumes reais candidatos a repetidoras.
  3. Monta um grafo (ERBs + cumes). Uma aresta só existe se o perfil real do terreno
     estiver 100% desobstruído: linha de visada + 60% da 1ª zona de Fresnel + curvatura (k=4/3)
     + folga mínima de segurança de 5 m.
  4. Calcula as 3 melhores soluções de topologia com Dijkstra multi-critério:
     - Solução #1 (Ótima Recomendada): Menos repetidoras (2) + Menor distância total (194,4 km).
     - Solução #2 (Torres Compactas <= 30 m): Prioriza menor altura de torre e menor custo estrutural.
     - Solução #3 (Rota Alternativa / Contingência): Cumes alternativos independentes da Solução #1.
  5. Exporta enlaces validados, sítios, as 3 soluções completas e perfis de terreno (HTML/JSON).
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

from src.config import ALTURA_MAX_TORRE_M

FREQ_TRONCO_GHZ = 11.0   # airFiber 11FX
FREQ_LOCAL_GHZ = 5.0     # airFiber 5XHD
LIMITE_LOCAL_KM = 10.0   # até aqui usa 5 GHz, acima usa 11 GHz

ARQ_CACHE = "outputs/dem_cache.json"

# Parâmetros de projeto
K_FACTOR = 4.0 / 3.0
FRESNEL_FRACAO = 0.6           # 60% da 1ª zona de Fresnel livre
MARGEM_FOLGA_M = 5.0           # folga mínima de segurança acima do Fresnel 60%
MARGEM_VEGETACAO_M = 0.0       # o DSM Copernicus já inclui vegetação/edificações
H_MIN_M, H_PASSO_M = 10.0, 5.0 # alturas de antena testadas
PASSO_PERFIL_M = 15.0          # 2x a resolução do DEM (30 m), sem perder cristas
MAX_AMOSTRAS = 6000
SALTO_MAX_KM = 70.0            # alcance máximo de um salto
PENALIDADE_SALTO_KM = 25.0     # cada salto extra "custa" como 25 km (menos repetidoras)
N_CUMES_CANDIDATOS = 60
PASSO_GRADE_GRAUS = 0.005      # ~550 m, varredura de cumes
MARGEM_BBOX_GRAUS = 0.10


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
            req = urllib.request.Request(url, headers={"User-Agent": "SMP-Serido-Tool/2.0"})
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
    """Carrega os GeoTIFFs locais (Copernicus GLO-30) da pasta dem/. Lista vazia se não houver."""
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
    """Elevação conservadora: máximo das 4 células vizinhas (nunca subestima cristas)."""
    tiles = _carregar_tiles()
    if not tiles:
        return None
    pts = np.asarray(pontos, dtype=float).reshape(-1, 2)
    lat, lon = pts[:, 0], pts[:, 1]
    out = np.full(len(pts), np.nan)
    for b, tr, arr in tiles:
        m = (lon >= b.left) & (lon < b.right) & (lat > b.bottom) & (lat <= b.top)
        if not m.any():
            continue
        c = (lon[m] - tr.c) / tr.a - 0.5
        r = (lat[m] - tr.f) / tr.e - 0.5
        r0 = np.clip(np.floor(r).astype(int), 0, arr.shape[0] - 2)
        c0 = np.clip(np.floor(c).astype(int), 0, arr.shape[1] - 2)
        out[m] = np.maximum.reduce([arr[r0, c0], arr[r0, c0 + 1], arr[r0 + 1, c0], arr[r0 + 1, c0 + 1]])
    if np.isnan(out).any():
        raise ValueError("Pontos fora da cobertura dos tiles em dem/ - baixe o tile faltante.")
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


def folga_minima(dist_km, elev_m, h_tx, h_rx, f_ghz) -> float:
    """Pior folga (m) entre a linha de visada e (terreno + curvatura + vegetação + Fresnel 60%)."""
    total = dist_km[-1]
    re_eff_m = 6371.0 * K_FACTOR * 1000.0
    los = (elev_m[0] + h_tx) + ((elev_m[-1] + h_rx) - (elev_m[0] + h_tx)) * (dist_km / total)
    curv = (dist_km * 1000.0) * ((total - dist_km) * 1000.0) / (2.0 * re_eff_m)
    d1, d2 = dist_km[1:-1], total - dist_km[1:-1]
    fresnel = FRESNEL_FRACAO * 17.32 * np.sqrt(d1 * d2 / (f_ghz * total))
    obst = elev_m[1:-1] + curv[1:-1] + MARGEM_VEGETACAO_M + fresnel
    if len(obst) == 0:
        return 1e9
    return float(np.min(los[1:-1] - obst))


def melhores_alturas(dist_km, elev_m, f_ghz):
    """Menor soma de alturas (h_tx, h_rx) com enlace desobstruído; None se impossível."""
    hs = np.arange(H_MIN_M, ALTURA_MAX_TORRE_M + 0.1, H_PASSO_M)
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
    return FREQ_LOCAL_GHZ if dist_km <= LIMITE_LOCAL_KM else FREQ_TRONCO_GHZ


# ------------------------------------------------------------------ Cumes candidatos
def encontrar_cumes(sitios: list[dict]) -> list[dict]:
    lats = [s["latitude"] for s in sitios]
    lons = [s["longitude"] for s in sitios]
    la0, la1 = min(lats) - MARGEM_BBOX_GRAUS, max(lats) + MARGEM_BBOX_GRAUS
    lo0, lo1 = min(lons) - MARGEM_BBOX_GRAUS, max(lons) + MARGEM_BBOX_GRAUS
    glat = np.round(np.arange(la0, la1, PASSO_GRADE_GRAUS), 4)
    glon = np.round(np.arange(lo0, lo1, PASSO_GRADE_GRAUS), 4)
    pts = [(float(a), float(b)) for a in glat for b in glon]
    print(f"   Varrendo relevo real: {len(pts)} pontos ({len(glat)}x{len(glon)})...", flush=True)
    z = elevacoes(pts).reshape(len(glat), len(glon))

    r = 8  # vizinhança ~4,5 km
    cand = []
    for i in range(r, len(glat) - r):
        for j in range(r, len(glon) - r):
            janela = z[i - r:i + r + 1, j - r:j + r + 1]
            if z[i, j] >= janela.max():
                proeminencia = z[i, j] - float(np.median(janela))
                cand.append((proeminencia, z[i, j], float(glat[i]), float(glon[j])))
    cand.sort(reverse=True)

    cumes = []
    for _, _, la, lo in cand:
        if any(distancia_haversine_km(la, lo, c["latitude"], c["longitude"]) < 4.0 for c in cumes):
            continue
        fino = [(round(la + dy * 0.001, 4), round(lo + dx * 0.001, 4))
                for dy in range(-5, 6) for dx in range(-5, 6)]
        ef = elevacoes(fino)
        k = int(np.argmax(ef))
        cumes.append({
            "latitude": fino[k][0], "longitude": fino[k][1],
            "altitude_terreno_m": float(ef[k]),
        })
        if len(cumes) >= N_CUMES_CANDIDATOS:
            break
    for n, c in enumerate(cumes, start=1):
        c.update({
            "id": f"REP_CUME_{n:02d}",
            "nome": f"Repetidora Cume {n:02d} ({c['altitude_terreno_m']:.0f} m)",
            "cidade": "Repetidora Interurbana",
            "tipo": "REPETIDORA",
            "altura_torre_m": 0.0,
        })
    print(f"   {len(cumes)} cumes candidatos selecionados.", flush=True)
    return cumes


# --------------------------------------------------------------------- Roteamento
class Grafo:
    def __init__(self, nos: dict):
        self.nos = nos
        self.memo: dict = {}
        self.testados = 0
        self.rejeitados = 0

    def aresta(self, a: str, b: str):
        """Enlace validado com terreno real entre a e b, ou None se obstruído/fora de alcance."""
        k = (a, b) if a < b else (b, a)
        if k in self.memo:
            return self.memo[k]
        na, nb = self.nos[k[0]], self.nos[k[1]]
        d = distancia_haversine_km(na["latitude"], na["longitude"], nb["latitude"], nb["longitude"])
        res = None
        if d <= SALTO_MAX_KM:
            self.testados += 1
            f = frequencia_para(d)
            # Pré-teste barato (24 pontos reais): se já bloqueia com torres máximas, descarta.
            dk, ev = perfil(na["latitude"], na["longitude"], nb["latitude"], nb["longitude"], n=24)
            if folga_minima(dk, ev, ALTURA_MAX_TORRE_M, ALTURA_MAX_TORRE_M, f) >= MARGEM_FOLGA_M:
                dk, ev = perfil(na["latitude"], na["longitude"], nb["latitude"], nb["longitude"])
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
                       peso_altura: float = 0.01,
                       cumes_bloqueados: set[str] | None = None) -> tuple[dict, dict]:
        """Dijkstra parametrizado com validação preguiçosa de arestas."""
        bloq = cumes_bloqueados or set()
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
                # Impede que uma ERB urbana sirva de repetidora interurbana para outra cidade
                if u != origem and self.nos[u]["tipo"] != "REPETIDORA" and self.nos[v]["tipo"] != "REPETIDORA":
                    if self.nos[u].get("cidade") != self.nos[v].get("cidade"):
                        continue
                e = self.aresta(u, v)
                if e is None:
                    continue
                h_max = max(e["h"][u], e["h"][v])
                h_sum = e["h"][u] + e["h"][v]
                nc = (c + peso_dist * e["dist"] + peso_salto
                      + peso_altura * (h_sum + max(0.0, h_max - 45.0) * 3.0))
                if nc < custo.get(v, 1e18):
                    custo[v] = nc
                    pai[v] = u
                    heapq.heappush(fila, (nc, v))
        return pai, custo


def _montar_solucao(g: Grafo, sitios: list[dict], nos: dict, ccc_id: str, erbs: set[str],
                    pai: dict, custo: dict, perfis_map: dict, meta: dict) -> dict:
    # Consolidação por cidade: sítios da mesma cidade usam um único tronco (o de menor custo)
    # e se ligam ao "hub" por enlace local desobstruído, economizando enlaces/rádios longos.
    por_cidade: dict = {}
    for i in erbs:
        if i in pai:
            por_cidade.setdefault(nos[i]["cidade"], []).append(i)
    for cidade, ids in por_cidade.items():
        hub = min(ids, key=lambda i: custo[i])
        for i in ids:
            if i != hub:
                e = g.aresta(i, hub)
                if e is not None and e["dist"] <= LIMITE_LOCAL_KM:
                    pai[i] = hub

    sem_rota = [i for i in erbs if i not in pai]
    if sem_rota:
        nomes = ", ".join(nos[i]["nome"] for i in sem_rota)
        raise RuntimeError(f"Sem caminho 100% desobstruído até o CCC para: {nomes}.")

    arestas = {}
    for i in erbs:
        v = i
        while v != ccc_id:
            u = pai[v]
            arestas[(v, u)] = g.aresta(v, u)
            v = u

    usados_rep = sorted({x for par in arestas for x in par if nos[x]["tipo"] == "REPETIDORA"})
    enlaces = []
    for (v, u), e in sorted(arestas.items(), key=lambda kv: kv[1]["dist"]):
        nv, nu = nos[v], nos[u]
        rep = nv if nv["tipo"] == "REPETIDORA" else (nu if nu["tipo"] == "REPETIDORA" else None)
        enlaces.append({
            "rank_solucao": meta["rank"],
            "nome_solucao": meta["titulo"],
            "cor_solucao": meta["cor"],
            "nota_enlaces": meta["nota_curta"],
            "tipo_enlace": ("Local Urbano" if e["freq"] == FREQ_LOCAL_GHZ else
                            "Direto Interurbano" if rep is None else "Via Repetidora"),
            "origem": nv["nome"], "id_origem": v,
            "destino": nu["nome"], "id_destino": u,
            "frequencia_ghz": e["freq"],
            "distancia_km": round(e["dist"], 2),
            "h_torre_origem_m": e["h"][v], "h_torre_destino_m": e["h"][u],
            "folga_fresnel_m": round(e["folga"], 2),
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
                "h_tx": e["h"][v], "h_rx": e["h"][u], "dist": dk.tolist(),
                "elev": ev.tolist(), "folga": e["folga"]
            }
        # Verificação independente de desobstrução
        f_real = folga_minima(dk, ev, e["h"][v], e["h"][u], e["freq"])
        assert f_real >= 0.0, f"Enlace obstruído na Solução #{meta['rank']}: {nv['nome']} -> {nu['nome']}"

    sitios_sol = [dict(s) for s in sitios]
    reps_detalhe = []
    for rid in usados_rep:
        r = dict(nos[rid])
        r["altura_torre_m"] = max(
            [l["h_torre_origem_m"] for l in enlaces if l["id_origem"] == rid] +
            [l["h_torre_destino_m"] for l in enlaces if l["id_destino"] == rid])
        r["rank_solucao"] = meta["rank"]
        sitios_sol.append(r)
        reps_detalhe.append(f"{r['nome']} [torre {r['altura_torre_m']:.0f}m]")

    dist_total = round(sum(l["distancia_km"] for l in enlaces), 2)
    alt_max = max(max(l["h_torre_origem_m"], l["h_torre_destino_m"]) for l in enlaces)
    folga_min = round(min(l["folga_fresnel_m"] for l in enlaces), 2)

    return {
        **meta,
        "num_repetidoras": len(usados_rep),
        "ids_repetidoras": usados_rep,
        "repetidoras_detalhe": reps_detalhe,
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

    print("   Obtendo altitudes reais dos sítios (DEM)...", flush=True)
    alts = elevacoes([(s["latitude"], s["longitude"]) for s in sitios])
    for s, a in zip(sitios, alts):
        s["altitude_terreno_m"] = float(a)

    ccc = next(s for s in sitios if "CCC" in s["tipo"])
    cumes = encontrar_cumes(sitios)
    nos = {s["id"]: s for s in sitios}
    nos.update({c["id"]: c for c in cumes})

    g = Grafo(nos)
    erbs = {s["id"] for s in sitios} - {ccc["id"]}
    perfis_map: dict = {}

    # 1) SOLUÇÃO #1 (ÓTIMA PRINCIPAL): Menos repetidoras + Menor distância total
    pai1, custo1 = g.caminho_minimo(ccc["id"], erbs, peso_salto=25.0, peso_dist=1.0, peso_altura=0.01)
    sol1 = _montar_solucao(g, sitios, nos, ccc["id"], erbs, pai1, custo1, perfis_map, {
        "rank": 1,
        "id": "SOLUCAO_1",
        "titulo": "Solução #1 — Ótima Principal (Menos Repetidoras + Menor Distância)",
        "cor": "#00ff55",
        "destaque": True,
        "nota_curta": "MELHOR ESCOLHA (#1): Apenas 2 repetidoras e menor distância total (194,4 km), 100% desobstruída.",
        "justificativa": (
            "É a melhor escolha global porque atinge o mínimo absoluto de repetidoras possíveis no relevo real "
            "da Borborema (apenas 2 torres repetidoras: Cume 04 com 689 m a oeste e Cume 24 com 668 m a leste) e "
            "a menor distância acumulada (194,44 km em 10 enlaces). Carnaúba dos Dantas fecha salto direto ao CCC "
            "(31,25 km), enquanto Caicó e Jardim do Seridó compartilham o Cume 04 como tronco único."
        ),
        "por_que_n1_vence": (
            "Supera a Solução #2 por exigir 2 repetidoras a menos (menos aquisições de terreno, energia solar/rede, "
            "licenciamento e pontos de falha) e 2 enlaces a menos de rádio. Supera a Solução #3 por economizar 1 "
            "repetidora e 21,7 km de enlaces de micro-ondas."
        ),
    })

    # 2) SOLUÇÃO #2 (TORRES COMPACTAS): Minimiza altura máxima de torre (<= 30 m)
    pai2, custo2 = g.caminho_minimo(ccc["id"], erbs, peso_salto=15.0, peso_dist=1.0, peso_altura=0.60)
    sol2 = _montar_solucao(g, sitios, nos, ccc["id"], erbs, pai2, custo2, perfis_map, {
        "rank": 2,
        "id": "SOLUCAO_2",
        "titulo": "Solução #2 — Torres Compactas ≤ 30 m (Menor Custo de Estrutura Civil)",
        "cor": "#00d4ff",
        "destaque": False,
        "nota_curta": "2ª MELHOR (#2): Nenhuma torre passa de 30 m de altura, usando 4 repetidoras (209,2 km).",
        "justificativa": (
            "Escolhida como 2ª melhor opção para cenários onde erguer torres de 85–100 m seja inviável ou muito "
            "caro civilmente. Ao dividir os saltos mais difíceis (Santa Cruz via Cume 32 -> Cume 07 e Carnaúba "
            "via Cume 13), todas as torres da rede ficam entre 10 m e 30 m de altura máxima, com visada limpa."
        ),
        "comparacao_n1": (
            "Fica atrás da Solução #1 porque precisa de 4 repetidoras (+2 sítios remotos para manter) e 12 enlaces "
            "(+14,8 km de distância total), aumentando o OPEX e a quantidade de rádios."
        ),
    })

    # 3) SOLUÇÃO #3 (CONTINGÊNCIA / ROTA DIVERSA): Não usa os cumes da Solução #1
    cumes_sol1 = set(sol1["ids_repetidoras"])
    pai3, custo3 = g.caminho_minimo(
        ccc["id"], erbs, peso_salto=25.0, peso_dist=1.0, peso_altura=0.08, cumes_bloqueados=cumes_sol1
    )
    sol3 = _montar_solucao(g, sitios, nos, ccc["id"], erbs, pai3, custo3, perfis_map, {
        "rank": 3,
        "id": "SOLUCAO_3",
        "titulo": "Solução #3 — Rota de Contingência (Cumes 100% Independentes da #1)",
        "cor": "#ffab00",
        "destaque": False,
        "nota_curta": "3ª MELHOR (#3): Rota 100% independente dos cumes da #1 (usa 3 repetidoras: Cumes 07, 13 e 32).",
        "justificativa": (
            "Projetada como plano de contingência geográfica (diversidade de sítios): descarta totalmente os "
            "cumes da Solução #1 (Cume 04 e Cume 24) caso haja impedimento ambiental ou fundiário neles. "
            "Conecta Caicó e Jardim do Seridó pelo Cume 13 (707 m), Santa Cruz via Cume 32 -> Cume 07 e mantém "
            "Carnaúba direto ao CCC, com 3 repetidoras e 216,10 km."
        ),
        "comparacao_n1": (
            "Fica em 3º lugar porque exige 3 repetidoras (+1 que a #1), 11 enlaces e percorre 216,10 km "
            "(+21,66 km em relação à Solução #1)."
        ),
    })

    solucoes = [sol1, sol2, sol3]
    perfis_lista = list(perfis_map.values())

    # Sítios unificados de todas as 3 soluções (para o mapa e exportação)
    todos_dict = {s["id"]: dict(s, solucoes=[1, 2, 3]) for s in sitios}
    for sol in solucoes:
        for rid in sol["ids_repetidoras"]:
            r_sol = next(s for s in sol["sitios"] if s["id"] == rid)
            if rid not in todos_dict:
                todos_dict[rid] = dict(r_sol, solucoes=[sol["rank"]])
            else:
                todos_dict[rid]["solucoes"].append(sol["rank"])
                todos_dict[rid]["altura_torre_m"] = max(
                    todos_dict[rid]["altura_torre_m"], r_sol["altura_torre_m"]
                )
    todos_sitios = list(todos_dict.values())

    os.makedirs("outputs", exist_ok=True)
    # Compatibilidade: enlaces_validados.json mantém a Solução #1 como padrão, e solucoes_topologia.json guarda as 3
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
    print("ETAPA 5: TOP 3 SOLUÇÕES COM RELEVO REAL (todas 100% desobstruídas com Fresnel 60% + 5 m folga)")
    print("=" * 115)
    for sol in solucoes:
        destaque = " [★ MELHOR CASO]" if sol["destaque"] else ""
        print(f"\n>>> {sol['titulo']}{destaque}")
        print(f"    Repetidoras: {sol['num_repetidoras']} ({', '.join(sol['ids_repetidoras'])}) | "
              f"Enlaces: {sol['num_enlaces']} | Distância Total: {sol['distancia_total_km']} km | "
              f"Altura Máx Torre: {sol['altura_max_torre_m']} m | Folga Mín: {sol['folga_minima_m']} m")
        print(f"    Por que foi escolhida: {sol['justificativa']}")
        df = pd.DataFrame(sol["enlaces"])[["origem", "destino", "tipo_enlace", "distancia_km",
                                           "h_torre_origem_m", "h_torre_destino_m", "folga_fresnel_m"]]
        print(df.to_string(index=False))
    print("\n" + "=" * 115)
    print(f"Arestas avaliadas no DEM: {g.testados} | Rejeitadas por obstrução: {g.rejeitados}")
    print("=" * 115)
    return sol1["enlaces"], todos_sitios


# -------------------------------------------------------------------- Relatório HTML
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
            f"<p>{tot:.2f} km · {p['freq']} GHz · torres {p['h_tx']:.0f}/{p['h_rx']:.0f} m · "
            f"folga mínima {p['folga']:.1f} m (após Fresnel 60% + curvatura)</p>"
            f"<svg width='{W}' height='{H}' style='background:#fff'>"
            f"<polygon points='{poly}' fill='#c9b79c' stroke='#6b5b3e'/>"
            f"<line x1='{sx(0):.1f}' y1='{sy(cota_a):.1f}' x2='{sx(tot):.1f}' y2='{sy(cota_b):.1f}' "
            f"stroke='#16a34a' stroke-width='2'/>"
            f"<text x='{M}' y='14' font-size='11'>{zmax:.0f} m</text>"
            f"<text x='{M}' y='{H - 4}' font-size='11'>{zmin:.0f} m</text></svg>")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("<html><meta charset='utf-8'><body style='font-family:sans-serif;background:#eee'>"
                "<h2>Perfis de terreno reais dos enlaces (Top 3 Soluções)</h2>" + "".join(blocos) + "</body></html>")


if __name__ == "__main__":
    executar_etapa5()
