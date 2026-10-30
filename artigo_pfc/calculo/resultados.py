"""Gera todos os numeros do artigo em resultados.json."""
import json
from projeto import *

H_NPC = 21.4e-3
S_NPC = H_NPC / 15.37e-3
npc = npc_inductor(N_REF, S_NPC)
OUT = {}

def desc(ind):
    g, c = ind.geom, ind.core
    return dict(OD=c.OD*1e3, ID=c.ID*1e3, HT=c.HT*1e3, Ae=c.Ae*1e6, le=c.le*1e3, Ve=c.Ve*1e6,
                Vgeom=c.V_geom*1e6, N=ind.wdg.N, layers=g["layers"], Ku=100*g["Ku"],
                MLT=g["MLT"]*1e3, Rdc=ind.Rdc*1e3, L0=ind.L0*1e6,
                L_req=ind.L_inc(I_REQ)*1e6, L_max=ind.L_inc(I_MAX)*1e6,
                H_req=ind.wdg.N*I_REQ/c.le/100, OD_w=g["OD_w"]*1e3, HT_w=g["HT_w"]*1e3,
                V_box=g["V_box"]*1e6, m_cu=g["m_cu"]*1e3,
                B_req=float(ind.mat.B_of_H(ind.wdg.N*I_REQ/c.le)),
                J=1200/85/ind.wdg.A_cu/1e6)
OUT["ref"] = desc(ref); OUT["npc"] = desc(npc)
OUT["param"] = dict(H0_KM=H0_KM/100, H0_REF=H0_REF/100, n_KM=n_KM, H0_NC=H0_NC/100, n_NC=n_NC,
                    kcore=ref.kcore, s_npc=S_NPC, s_min64=s_min(64),
                    k_KM=k_KM, k_NC=k_NC, ki_KM=KM.ki, ki_NC=NC.ki)

# propriedades: perda a 100 kHz e dB = 100 mT; B integrada no campo da crista
OUT["prop"] = dict(Pv_KM=KM.pv_sine(1e5, 0.05)/1e3, Pv_NC=NC.pv_sine(1e5, 0.05)/1e3,
                   B130_KM=float(KM.B_of_H(12990)), B130_NC=float(NC.B_of_H(12990)),
                   B146_KM=float(KM.B_of_H(14630)), B146_NC=float(NC.B_of_H(14630)))

# pontos de operacao
pts = []
for V in (85, 115, 230, 265):
    for ld in (0.2, 0.5, 1.0):
        rr = line_cycle(SPEC, V, ld, ref); rn = line_cycle(SPEC, V, ld, npc)
        pts.append(dict(V=V, load=ld,
            core_ref=rr["P_core"], core_npc=rn["P_core"],
            culf_ref=rr["P_cu_lf"], culf_npc=rn["P_cu_lf"],
            cuhf_ref=rr["P_cu_hf"], cuhf_npc=rn["P_cu_hf"],
            cu_ref=rr["P_cu"], cu_npc=rn["P_cu"], tot_ref=rr["P_tot"], tot_npc=rn["P_tot"],
            dcm_ref=100*(~rr["ccm"]).mean(), dcm_npc=100*(~rn["ccm"]).mean(),
            dBmax_ref=1e3*rr["dB"].max(), dBmax_npc=1e3*rn["dB"].max(),
            Bmax_ref=rr["B_max"].max(), Bmax_npc=rn["B_max"].max(),
            ipk_ref=rr["i_pk"].max(), ipk_npc=rn["i_pk"].max(),
            rip_ref=rr["Delta"][np.argmax(rr["i_avg"])], rip_npc=rn["Delta"][np.argmax(rn["i_avg"])],
            Pin=rr["P_in"]))
OUT["pts"] = pts

# varredura de tensao
Vs = np.arange(85, 266, 1.0)
sweep = {}
for ld in (0.2, 0.5, 1.0):
    a = []
    for V in Vs:
        rr = line_cycle(SPEC, V, ld, ref, ntheta=200); rn = line_cycle(SPEC, V, ld, npc, ntheta=200)
        a.append([V, rr["P_core"], rn["P_core"], rr["P_cu"], rn["P_cu"], rr["P_tot"], rn["P_tot"]])
    sweep[str(ld)] = a
OUT["sweep"] = sweep

# espaco de projeto
ds = []
for N in range(40, 97, 2):
    s = s_min(N); ind = npc_inductor(N, s)
    r85 = line_cycle(SPEC, 85.0, 1.0, ind); r230 = line_cycle(SPEC, 230.0, 1.0, ind)
    ds.append([N, s, ind.core.Ve*1e6, r85["P_tot"], r230["P_tot"], r85["P_core"], r230["P_core"],
               r85["P_cu"], r230["P_cu"], ind.geom["V_box"]*1e6, 100*ind.geom["Ku"]])
OUT["design_space"] = ds
r85 = line_cycle(SPEC, 85.0, 1.0, ref); r230 = line_cycle(SPEC, 230.0, 1.0, ref)
OUT["ref_85_230"] = [r85["P_tot"], r230["P_tot"]]

# ciclo de rede a plena carga
cyc = {}
for V in (85, 230):
    rr = line_cycle(SPEC, V, 1.0, ref); rn = line_cycle(SPEC, V, 1.0, npc)
    cyc[str(V)] = dict(theta=list(np.degrees(rr["theta"])),
                       core_ref=list(rr["p_core"]), core_npc=list(rn["p_core"]),
                       cu_ref=list(rr["p_cu_lf"]+rr["p_cu_hf"]), cu_npc=list(rn["p_cu_lf"]+rn["p_cu_hf"]),
                       dB=list(rr["dB"]), L_ref=list(rr["L"]), L_npc=list(rn["L"]))
OUT["cycle"] = cyc
json.dump(OUT, open("resultados.json", "w"), indent=1, default=float)

# impressao
for k in ("ref", "npc"):
    print(k, {kk: (round(v, 3) if isinstance(v, float) else v) for kk, v in OUT[k].items()})
print(OUT["param"]); print(OUT["prop"])
print("\n V  carga | nucleo ref  npc | cobre ref  npc (AF ref npc) | total ref  npc  dif% | DCM% ref npc | dBmax ref npc | Bmax")
for p in pts:
    print(f"{p['V']:3d} {p['load']:4.1f} | {p['core_ref']:6.3f} {p['core_npc']:6.3f} | {p['cu_ref']:6.3f} {p['cu_npc']:6.3f} ({p['cuhf_ref']:.3f} {p['cuhf_npc']:.3f}) |"
          f" {p['tot_ref']:6.3f} {p['tot_npc']:6.3f} {100*(p['tot_npc']/p['tot_ref']-1):+6.1f} | {p['dcm_ref']:5.1f} {p['dcm_npc']:5.1f} |"
          f" {p['dBmax_ref']:5.1f} {p['dBmax_npc']:5.1f} | {p['Bmax_ref']:.2f} {p['Bmax_npc']:.2f} | rip {p['rip_ref']:.2f} {p['rip_npc']:.2f} ipk {p['ipk_ref']:.2f} {p['ipk_npc']:.2f} Pin {p['Pin']:.1f}")
