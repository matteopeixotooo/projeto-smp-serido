# Verificação independente: lê os GeoTIFFs direto (rasterio.sample, vizinho mais próximo, passo 15 m)
import json, glob, math, numpy as np, rasterio
from rasterio.merge import merge
srcs=[rasterio.open(f) for f in sorted(glob.glob('dem/*.tif'))]
arr,tr=merge(srcs); arr=arr[0]
def z(lat,lon):
    c,r=(lon-tr.c)/tr.a,(lat-tr.f)/tr.e
    return arr[int(r),int(c)]
def hav(a,b,c,d):
    p1,p2=math.radians(a),math.radians(c);dl=math.radians(d-b)
    x=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 12742*math.asin(math.sqrt(x))
for p in json.load(open('outputs/perfis_enlaces.json')):
    D=hav(p['lat_a'],p['lon_a'],p['lat_b'],p['lon_b']); n=int(D*1000/15)
    t=np.linspace(0,1,n); la=p['lat_a']+t*(p['lat_b']-p['lat_a']); lo=p['lon_a']+t*(p['lon_b']-p['lon_a'])
    e=np.array([z(a,b) for a,b in zip(la,lo)]); d=t*D
    los=(e[0]+p['h_tx'])+((e[-1]+p['h_rx'])-(e[0]+p['h_tx']))*t
    curv=(d*1000)*((D-d)*1000)/(2*6371000*4/3)
    fr=0.6*17.32*np.sqrt(np.clip(d*(D-d),0,None)/(p['freq']*D))
    f=(los-(e+curv+fr))[1:-1].min()
    print(f"{p['origem'][:34]:34} -> {p['destino'][:30]:30} {D:6.2f} km  folga mín {f:6.1f} m  {'OK' if f>=0 else 'OBSTRUÍDO'}")
