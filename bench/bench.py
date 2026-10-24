"""Banco de pruebas: motores de decision sobre datos sinteticos con verdad oculta.
Mide arrepentimiento (regret) = costo esperado REAL del elegido - costo del oraculo, y latencia."""
import numpy as np, time, json
rng=np.random.default_rng(7)
NP,NC=12,8
DELAY={'Flexible':300_000,'Estandar':2_500_000,'Urgente':6_000_000}; CI=8_000_000
base=rng.uniform(3.2e6,4.8e6,NC)
plate=np.clip(rng.beta(2,9,(NP,NC))+np.where(rng.random((NP,NC))<.15,.25,0),0.02,.7)   # P(tarde) real
price=base[None,:]*rng.uniform(.85,1.2,(NP,1))*rng.uniform(.95,1.05,(NP,NC))
inc=rng.uniform(.002,.03,(NP,NC))
vol=rng.choice([3,8,25,80,200],size=(NP,NC),p=[.15,.2,.25,.25,.15])   # historial desigual
late=rng.binomial(vol,plate)
def true_cost(p,c,lvl): return price[p,c]+plate[p,c]*DELAY[lvl]+inc[p,c]*CI
def eng_random(c,l,r): return r.integers(NP)
def eng_cheap(c,l,r): return int(np.argmin(price[:,c]))
def eng_raw(c,l,r):   # historial crudo, sin suavizar
    pl=np.where(vol[:,c]>0,late[:,c]/np.maximum(vol[:,c],1),0.2)
    return int(np.argmin(price[:,c]+pl*DELAY[l]+inc[:,c]*CI))
A0,B0=17,3
def eng_ours(c,l,r):
    a=late[:,c]+B0; n=vol[:,c]+A0+B0; pl=a/n
    var=pl*(1-pl)/(n+1); w=3.29*np.sqrt(var)           # ancho IC 90%
    cost=price[:,c]+pl*DELAY[l]+inc[:,c]*CI+1.0*w*DELAY[l]
    return int(np.argmin(cost))
engines={'Aleatorio':eng_random,'Mas barato':eng_cheap,'Historial crudo':eng_raw,'Nuestro (bayesiano+costo)':eng_ours}
N=6000; reqs=[(rng.integers(NC),list(DELAY)[rng.integers(3)]) for _ in range(N)]
res={}
for name,f in engines.items():
    rg=[];t0=time.perf_counter(); r=np.random.default_rng(1)
    for c,l in reqs:
        p=f(c,l,r); rg.append(true_cost(p,c,l)-min(true_cost(q,c,l) for q in range(NP)))
    dt=(time.perf_counter()-t0)/N*1000
    res[name]={'regret_medio':float(np.mean(rg)),'pct_optimo':float(np.mean(np.array(rg)<1)*100),'ms':dt}
for l in DELAY:
    pass
print(json.dumps(res,indent=1,ensure_ascii=False))
# deriva: un proveedor se deteriora; dias hasta que deja de ser Top-1 con y sin decaimiento
def drift(decay):
    A,Bn=40.,10.;  # proveedor excelente: 40 a tiempo, 10?? -> usar conteos efectivos
    ok,late_=95.,5.   # historia: 95 a tiempo 5 tarde
    rival_p=0.18
    for day in range(1,200):
        ok*= decay; late_*=decay
        late_+=0.6; ok+=0.4      # ahora falla 60% (3 servicios/dia)
        p=(late_+B0)/(ok+late_+A0+B0)
        if p>rival_p: return day
    return None
print('dias hasta bajar del rival: sin decaimiento',drift(1.0),'| con vida media 90d',drift(0.5**(1/90)),'| vida media 30d',drift(0.5**(1/30)))
json.dump(res,open('/root/cosco/bench/res.json','w'))
