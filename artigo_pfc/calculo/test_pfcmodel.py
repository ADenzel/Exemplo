# Testes numericos de consistencia do modelo (parametros sinteticos, nao sao dados do artigo)
import numpy as np
from pfcmodel import *

# 1) iGSE reduz a Steinmetz para senoide
m = Material("teste", 60, magnetics_rolloff(0.01, 1e-6, 2.5), k=5.0, alpha=1.4, beta=2.1)
f, Bpk = 1e5, 0.05
t = np.linspace(0, 1/f, 200001)
B = Bpk*np.sin(2*np.pi*f*t)
dBdt = np.gradient(B, t)
p_igse = np.trapezoid(m.ki*np.abs(dBdt)**m.alpha*(2*Bpk)**(m.beta-m.alpha), t)*f
print("iGSE senoide / Steinmetz =", p_igse/m.pv_sine(f, Bpk))

# 2) Parseval das harmonicas: CCM e DCM
for (D1, D2, Dl) in [(0.3, 0.7, 1.0), (0.2, 0.15, 2.0)]:
    An = harmonic_amplitudes(Dl, D1, D2, 4000)[:, 0]
    tt = np.linspace(0, 1, 400001)
    w = np.where(tt < D1, Dl*tt/D1, np.where(tt < D1+D2, Dl*(1-(tt-D1)/D2), 0.0))
    print("Parseval", D1, D2, (An**2/2).sum(), w.var())

# 3) Toroide fino: le -> pi*(OD+ID)/2, Ae -> h*(OD-ID)/2
c = Toroid("fino", 0.101, 0.099, 0.01)
print("le", c.le, np.pi*0.1, "Ae", c.Ae, 0.01*0.001)

# 4) Dowell: F_R -> 1 em baixa frequencia
w = Winding(50, 1.0e-3, 1.07e-3)
c2 = Toroid("t", 0.047, 0.024, 0.018)
print("Fr(50 Hz)", w.Fr(c2, 50.0), "Fr(100k, 300k)", w.Fr(c2, [1e5, 3e5]), "camadas", w.geometry(c2)["layers"])

# 5) Continuidade CCM/DCM e B(H) integrada monotona
spec = PFCSpec(Vo=400, Po_rated=1000, fs=1e5, fL=60, eta=0.95)
r = line_cycle(spec, 230, 0.2, m, c2, w, ntheta=2000)
idx = np.where(np.diff(r["ccm"].astype(int)) != 0)[0]
for i in idx[:2]:
    print("fronteira: Delta", r["Delta"][i], r["Delta"][i+1], " d1", r["d1"][i], r["d1"][i+1])
H = np.logspace(0, 5, 50); Bh = m.B_of_H(H)
print("B(H) monotona:", np.all(np.diff(Bh) > 0), " B(1e5 A/m) =", Bh[-1])
