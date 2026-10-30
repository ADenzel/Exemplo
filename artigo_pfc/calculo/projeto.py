"""Indutor de referencia (ancorado em [1]) e reprojeto com po nanocristalino."""
from dados import *
from scipy.optimize import brentq

ANCORAR = True
H_REQ = N_REF * I_REQ / 0.0984                     # campo na crista de 85 V, A/m

# --- referencia: curva do catalogo com H0 ajustado para L0 = 680 uH e L(19,97 A) = 165 uH [1]
L_CRISTA_REF = 165e-6
if ANCORAR:
    x = (1.0 / (L_CRISTA_REF / L0_REF) - 1.0) ** (1.0 / n_KM)
    H0_REF = H_REQ / x
else:
    H0_REF = H0_KM
KM_ref = Material("Kool Mu 60u (indutor de [1])", 60, rolloff_H0n(H0_REF, n_KM), k_KM, a_KM, b_KM, "[1],[3]")
core_ref = core_77083(2.0)
w_ref = Winding(N_REF, D_CU, D_O, T_w=20.0)
ref = Inductor("Referencia (Kool Mu)", KM_ref, core_ref, w_ref, L0=L0_REF, Rdc=RDC_REF)
if ANCORAR:
    p_mod = line_cycle(SPEC, 85.0, 1.0, ref)["P_core"]
    ref.kcore = 0.62 / p_mod
MLT_REF = ref.geom["MLT"]

def npc_inductor(N, s):
    core = core_77083(s)
    w = Winding(N, D_CU, D_O, T_w=20.0)
    ind = Inductor("Po nanocristalino", NC, core, w, L0=None, Rdc=1.0)
    ind.Rdc = RDC_REF * (N * ind.geom["MLT"]) / (N_REF * MLT_REF)   # razao de comprimentos
    return ind

def s_min(N):
    f = lambda s: npc_inductor(N, s).L_inc(I_REQ) - L_REQ
    return brentq(f, 0.2, 6.0)

if __name__ == "__main__":
    print(f"H0 catalogo = {H0_KM/100:.2f} A/cm; H0 do indutor de [1] = {H0_REF/100:.2f} A/cm; kcore = {ref.kcore:.4f}")
    print(f"Ref: L0 = {ref.L0*1e6:.1f} uH, L(19,97 A) = {ref.L_inc(I_REQ)*1e6:.1f} uH, L(22,5 A) = {ref.L_inc(I_MAX)*1e6:.1f} uH, MLT = {MLT_REF*1e3:.2f} mm")
    print("\nEspaco de projeto do po nanocristalino (L >= 168,5 uH a 19,97 A, fio de 1,15 mm, mesma matriz):")
    print(" N   s_min  h(mm)  H_crista(A/cm)  Ve(cm3)  Ku(%)  Rdc(mOhm)  P85(W)  P230(W)")
    for N in range(44, 92, 4):
        s = s_min(N)
        ind = npc_inductor(N, s)
        r85 = line_cycle(SPEC, 85.0, 1.0, ind); r230 = line_cycle(SPEC, 230.0, 1.0, ind)
        print(f"{N:3d}  {s:5.3f}  {ind.core.HT*1e3:5.2f}  {N*I_REQ/0.0984/100:6.1f}        {ind.core.Ve*1e6:6.2f}  {100*ind.geom['Ku']:5.1f}  {ind.Rdc*1e3:6.1f}     {r85['P_tot']:6.2f}  {r230['P_tot']:6.2f}")
    r85 = line_cycle(SPEC, 85.0, 1.0, ref); r230 = line_cycle(SPEC, 230.0, 1.0, ref)
    print(f"Ref: Ve = {ref.core.Ve*1e6:.2f} cm3, Ku = {100*ref.geom['Ku']:.1f}%, P85 = {r85['P_tot']:.2f} W, P230 = {r230['P_tot']:.2f} W")
