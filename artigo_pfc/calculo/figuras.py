"""Figuras em escala de cinza, largura de uma coluna IEEE (88,9 mm), 600 dpi."""
import json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
from PIL import Image
from dados import KM, NC, H0_KM, n_KM
from projeto import ref, H0_REF

R = json.load(open("resultados.json"))

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Liberation Serif"], "mathtext.fontset": "stix",
    "font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 6.5, "axes.linewidth": 0.6, "xtick.major.width": 0.6,
    "ytick.major.width": 0.6, "xtick.minor.width": 0.4, "ytick.minor.width": 0.4,
    "xtick.direction": "in", "ytick.direction": "in", "xtick.top": True, "ytick.right": True,
    "lines.linewidth": 1.0, "legend.frameon": False, "legend.handlelength": 2.6,
    "savefig.dpi": 600, "axes.grid": True, "grid.color": "0.88", "grid.linewidth": 0.35,
    "grid.linestyle": "-"})
K, G = "0.0", "0.55"                       # preto: Kool Mu; cinza: po nanocristalino
DASH, DOT = (0, (4.0, 1.8)), (0, (1.0, 1.4))
W = 3.5

def br(x, pos=None, nd=None):
    s = (f"{x:.{nd}f}" if nd is not None else f"{x:g}")
    return s.replace(".", ",")
fmt = FuncFormatter(lambda x, p: br(x))
def num(x, nd): return br(x, nd=nd)

def save(fig, name):
    fig.savefig(f"fig/{name}.pdf")
    fig.savefig(f"fig/{name}.png")
    Image.open(f"fig/{name}.png").convert("L").save(f"fig/{name}.png", dpi=(600, 600))
    plt.close(fig)

def tagr(ax, t):
    ax.text(0.985, 0.97, t, transform=ax.transAxes, va="top", ha="right", fontsize=8,
            bbox=dict(fc="white", ec="none", pad=0.6))

def tagb(ax, t):
    ax.text(0.015, 0.03, t, transform=ax.transAxes, va="bottom", ha="left", fontsize=8,
            bbox=dict(fc="white", ec="none", pad=0.6))

def tag(ax, t):
    ax.text(0.015, 0.97, t, transform=ax.transAxes, va="top", ha="left", fontsize=8,
            bbox=dict(fc="white", ec="none", pad=0.6))

# ---------------- Fig. 1: propriedades
fig, (a1, a2) = plt.subplots(2, 1, figsize=(W, 3.75))
H = np.linspace(0, 16000, 800)
a1.plot(H/100, 100*KM.rolloff(H), color=K, label="Kool Mµ, catálogo [10]")
a1.plot(H/100, 100*ref.mat.rolloff(H), color=K, ls=DOT, label="Kool Mµ, indutor de [7]")
a1.plot(H/100, 100*NC.rolloff(H), color=G, ls=DASH, lw=1.2, label="Pó nanocristalino [8]")
a1.axvline(129.9, color="0.6", lw=0.5)
a1.text(131.5, 72, "crista em 85 V\n129,9 A/cm", fontsize=6.5, va="top")
a1.set_xlim(0, 160); a1.set_ylim(0, 105)
a1.set_xlabel("Campo de polarização $H$ (A/cm)"); a1.set_ylabel("$\\mu_{inc}/\\mu_i$ (%)")
a1.legend(loc="lower left", bbox_to_anchor=(0.0, 0.0)); tagr(a1, "(a)")
a1.xaxis.set_major_formatter(fmt)

dB = np.logspace(np.log10(0.02), np.log10(0.4), 200)
a2.loglog(1e3*dB, KM.pv_sine(1e5, dB/2)/1e3, color=K, label="Kool Mµ, catálogo [10]")
a2.loglog(1e3*dB, NC.pv_sine(1e5, dB/2)/1e3, color=G, ls=DASH, lw=1.2, label="Pó nanocristalino [8]")
a2.plot([248], [25.4/28.6e-6/1e3], "o", ms=4.5, mfc=K, mec=K, label="Kool Mµ, medido em [8]")
a2.plot([248], [38.2/28.6e-6/1e3], "s", ms=4.5, mfc="white", mec=G, mew=1.0, label="Pó nano, medido em [8]")
a2.set_xlim(20, 400); a2.set_ylim(5, 5000)
a2.set_xlabel("Excursão de indução pico a pico $\\Delta B$ (mT)")
a2.set_ylabel("$P_v$ a 100 kHz (kW/m³)")
a2.xaxis.set_major_formatter(FuncFormatter(lambda x, p: br(x)))
a2.yaxis.set_major_formatter(FuncFormatter(lambda x, p: br(x)))
a2.xaxis.set_minor_formatter(NullFormatter()); a2.set_xticks([20, 50, 100, 200, 400])
a2.legend(loc="lower right"); tag(a2, "(b)")
fig.tight_layout(pad=0.3, h_pad=0.6); save(fig, "fig1")

# ---------------- Fig. 2: projeto
fig, (b1, b2) = plt.subplots(2, 1, figsize=(W, 3.75))
i = np.linspace(0, 25, 500)
from projeto import npc_inductor
nd = npc_inductor(64, 21.4/15.37)
b1.plot(i, 1e6*ref.L_inc(i), color=K, label="Referência, Kool Mµ")
b1.plot(i, 1e6*nd.L_inc(i), color=G, ls=DASH, lw=1.2, label="Pó nanocristalino, 21,4 mm")
b1.plot([0, 19.97], [680, 165], "o", ms=4, mfc="white", mec=K, mew=0.9, label="Valores de [7]", clip_on=False, zorder=5)
b1.plot([19.97], [168.5], "x", ms=6, color=K, mew=1.0, label="Requisito de [7]")
b1.set_xlim(0, 25); b1.set_ylim(0, 720)
b1.set_xlabel("Corrente de polarização (A)"); b1.set_ylabel("Indutância incremental (µH)")
b1.legend(loc="upper right"); tagb(b1, "(a)")
b1.xaxis.set_major_formatter(fmt)

ds = np.array(R["design_space"]); r85, r230 = R["ref_85_230"]; Vref = 21.2
x = 100*ds[:, 2]/Vref
b2.axhline(100, color="0.6", lw=0.5); b2.axvline(100, color="0.6", lw=0.5)
b2.plot(x, 100*ds[:, 3]/r85, color=K, marker="o", ms=2.2, lw=0.9, label="85 V, plena carga")
b2.plot(x, 100*ds[:, 4]/r230, color=G, ls=DASH, marker="s", ms=2.2, lw=1.1, label="230 V, plena carga")
j = int(np.where(ds[:, 0] == 64)[0][0])
b2.plot([x[j]], [100*ds[j, 3]/r85], "o", ms=5.5, mfc=K, mec=K)
b2.plot([x[j]], [100*ds[j, 4]/r230], "s", ms=5.5, mfc=G, mec=G)
b2.plot([100], [100], "*", ms=7, color=K, label="Referência")
for n_, o230, o85 in ((40, (-28, 6), (-28, -11)), (64, (-6, 7), (-6, -12)), (96, (-4, 7), (-4, -12))):
    k = int(np.where(ds[:, 0] == n_)[0][0])
    b2.annotate(f"N = {n_}", (x[k], 100*ds[k, 4]/r230), xytext=o230, textcoords="offset points", fontsize=6.5)
    b2.annotate(f"N = {n_}", (x[k], 100*ds[k, 3]/r85), xytext=o85, textcoords="offset points", fontsize=6.5)
b2.set_xlim(45, 120); b2.set_ylim(70, 175)
b2.set_xlabel("Volume efetivo do núcleo, relativo à referência (%)")
b2.set_ylabel("Perda total, relativa à referência (%)")
b2.legend(loc="upper left", bbox_to_anchor=(0.06, 1.0)); tag(b2, "(b)")
fig.tight_layout(pad=0.3, h_pad=0.6); save(fig, "fig2")

# ---------------- Fig. 3: semiciclo a plena carga
fig, axs = plt.subplots(2, 1, figsize=(W, 3.75), sharex=True)
for ax, V, t in zip(axs, ("85", "230"), ("(a) 85 V", "(b) 230 V")):
    c = R["cycle"][V]; th = np.array(c["theta"])
    m = {k: np.mean(c[k]) for k in ("cu_ref", "cu_npc", "core_ref", "core_npc")}
    ax.plot(th, c["cu_ref"], color=K, label=f"Cobre, Kool Mµ ({num(m['cu_ref'], 2)} W)")
    ax.plot(th, c["cu_npc"], color=K, ls=DASH, label=f"Cobre, pó nano ({num(m['cu_npc'], 2)} W)")
    ax.plot(th, c["core_ref"], color=G, lw=1.2, label=f"Núcleo, Kool Mµ ({num(m['core_ref'], 2)} W)")
    ax.plot(th, c["core_npc"], color=G, ls=DASH, lw=1.2, label=f"Núcleo, pó nano ({num(m['core_npc'], 2)} W)")
    ax.set_ylabel("Perda no período (W)"); tag(ax, t)
    ax.legend(loc="upper right", bbox_to_anchor=(1.0, 1.0))
    ax.yaxis.set_major_formatter(fmt)
axs[0].set_ylim(0, 42); axs[1].set_ylim(0, 6.0)
axs[1].set_xlim(0, 180); axs[1].set_xticks(range(0, 181, 30))
axs[1].set_xlabel("Ângulo da rede θ (°)")
fig.tight_layout(pad=0.3, h_pad=0.5); save(fig, "fig3")

# ---------------- Fig. 4: 85 a 265 V, tres cargas
fig, (c1, c2, c3) = plt.subplots(3, 1, figsize=(W, 4.45), sharex=True)
LS = {"1.0": "-", "0.5": DASH, "0.2": DOT}
LBL = {"1.0": "100 %", "0.5": "50 %", "0.2": "20 %"}
for ld in ("1.0", "0.5", "0.2"):
    a = np.array(R["sweep"][ld]); V = a[:, 0]
    c1.plot(V, a[:, 1], color=K, ls=LS[ld]); c1.plot(V, a[:, 2], color=G, ls=LS[ld], lw=1.2)
    c2.semilogy(V, a[:, 3], color=K, ls=LS[ld]); c2.semilogy(V, a[:, 4], color=G, ls=LS[ld], lw=1.2)
    c3.plot(V, 100*(a[:, 6]/a[:, 5]-1), color=K, ls=LS[ld], label=f"{LBL[ld]} de carga")
from matplotlib.lines import Line2D
h_mat = [Line2D([], [], color=K, label="Kool Mµ (referência)"),
         Line2D([], [], color=G, lw=1.2, label="Pó nanocristalino")]
h_ld = [Line2D([], [], color="0.3", ls=LS[k], label=f"{LBL[k]} de carga") for k in ("1.0", "0.5", "0.2")]
c1.legend(handles=h_mat, loc="upper left", bbox_to_anchor=(0.07, 1.0), ncol=2, columnspacing=1.2)
c1.set_ylim(0, 3.2); c1.set_ylabel("Perda no núcleo (W)"); tag(c1, "(a)")
c1.yaxis.set_major_formatter(fmt)
c2.set_ylim(0.05, 30); c2.set_ylabel("Perda no cobre (W)"); tag(c2, "(b)")
c2.yaxis.set_major_formatter(FuncFormatter(lambda x, p: br(x)))
c3.axhline(0, color="0.6", lw=0.5)
c3.set_ylim(-30, 140); c3.set_ylabel("Variação da perda total (%)"); tag(c3, "(c)")
c3.legend(loc="lower right")
c3.set_xlim(85, 265); c3.set_xticks([85, 115, 145, 175, 205, 235, 265])
c3.set_xlabel("Tensão eficaz de entrada (V)")
fig.tight_layout(pad=0.3, h_pad=0.5); save(fig, "fig4")
print("ok")
