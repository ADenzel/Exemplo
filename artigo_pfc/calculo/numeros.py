import json, numpy as np
from scipy.optimize import brentq
from projeto import *
R = json.load(open("resultados.json"))
npc = npc_inductor(64, 21.4/15.37)
f = lambda i: npc.L_inc(i) - ref.L_inc(i)
print("cruzamento de L (A):", round(brentq(f, 5, 22.5), 2))
H = 64*19.97/0.0984
print("mu%% a 129,9 A/cm: KM cat %.1f, ref %.1f, NC %.1f" % (100*KM.rolloff(H), 100*ref.mat.rolloff(H), 100*NC.rolloff(H)))
print("B integrada a 129,9 A/cm: KM cat %.3f ref %.3f NC %.3f" % (KM.B_of_H(H), ref.mat.B_of_H(H), NC.B_of_H(H)))
r1 = line_cycle(SPEC, 85, 1.0, ref); r2 = line_cycle(SPEC, 85, 1.0, npc)
print("Bmax 85 V: ref %.3f npc %.3f ; dBmax 230: " % (r1["B_max"].max(), r2["B_max"].max()))
for ld in ("0.2", "0.5", "1.0"):
    a = np.array(R["sweep"][ld]); V = a[:, 0]
    print(ld, "Vin do maximo de nucleo: ref %.0f npc %.0f" % (V[a[:,1].argmax()], V[a[:,2].argmax()]),
          "max nucleo ref %.3f npc %.3f" % (a[:,1].max(), a[:,2].max()), "Vin do maximo da dif total %.0f" % V[(a[:,6]/a[:,5]).argmax()])
# inicio do DCM em 20 % de carga
for ind, nm in ((ref, "ref"), (npc, "npc")):
    for V in np.arange(85, 266, 1.0):
        r = line_cycle(SPEC, V, 0.2, ind, ntheta=400)
        if (~r["ccm"]).any():
            print("DCM a 20 %:", nm, "a partir de", V, "V"); break
    for V in np.arange(85, 266, 1.0):
        r = line_cycle(SPEC, V, 0.5, ind, ntheta=400)
        if (~r["ccm"]).any():
            print("DCM a 50 %:", nm, "a partir de", V, "V"); break
# 230 V, theta = 38 graus
r = line_cycle(SPEC, 230, 1.0, npc); rr = line_cycle(SPEC, 230, 1.0, ref)
j = np.argmax(r["p_core"])
print("230 V em theta=%.1f: npc nucleo %.2f cobre %.2f razao %.2f ; ref nucleo %.2f cobre %.2f" %
      (np.degrees(r["theta"][j]), r["p_core"][j], (r["p_cu_lf"]+r["p_cu_hf"])[j], r["p_core"][j]/(r["p_cu_lf"]+r["p_cu_hf"])[j],
       rr["p_core"][j], (rr["p_cu_lf"]+rr["p_cu_hf"])[j]))
# leitura de pico
for V in (85, 230):
    for ld in (1.0, 0.2):
        a = line_cycle(SPEC, V, ld, ref); b = line_cycle(SPEC, V, ld, npc)
        tot_pk = b["P_cu"] + b["P_core"]/2**2.01
        print(f"leitura de pico {V} V {ld}: nucleo npc {b['P_core']/2**2.01:.3f} vs ref {a['P_core']:.3f}; total npc {tot_pk:.3f} vs ref {a['P_tot']:.3f} -> {100*(tot_pk/a['P_tot']-1):+.1f}%")
# fatores de perda no nucleo
npc2 = npc_inductor(64, 2.0)
for V in (85, 230):
    a = line_cycle(SPEC, V, 1.0, ref)["P_core"]; b = line_cycle(SPEC, V, 1.0, npc)["P_core"]; c = line_cycle(SPEC, V, 1.0, npc2)["P_core"]
    print(f"{V} V: razao total {b/a:.3f} = geometria {b/c:.3f} x material {c/a:.3f}")
print("Ipico/fase:", 64*22.5/0.0984/100, "A/cm em 22,5 A")
