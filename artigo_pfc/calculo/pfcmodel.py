"""
Modelo analitico do indutor boost PFC ao longo do semiciclo de rede.

Unidades SI em todo o modulo (A/m, T, m, Hz, W/m^3), salvo indicacao.
Nenhum dado de material ou de componente fica embutido aqui: tudo entra
por parametros, com a fonte registrada em quem chama (dados.py).

Hipoteses do modelo
- Controle por corrente media: corrente media de periodo senoidal retificada.
- Modo de conducao decidido ponto a ponto (CCM ou DCM) em cada angulo de rede.
- Indutancia incremental L(theta) avaliada no campo da corrente media local.
- Excursao de inducao pela lei de Faraday: dB = v_in t_on / (N Ae), independente de L.
- Perda no nucleo pela iGSE com coeficientes de Steinmetz senoidais (B de amplitude).
- Perda no cobre: componente de rede em Rcc; harmonicas de chaveamento em
  Rcc*FR(n fs), FR de Dowell para condutor redondo.
"""
import numpy as np
from scipy.integrate import quad, cumulative_trapezoid

MU0 = 4e-7 * np.pi
OE = 1000.0 / (4.0 * np.pi)          # 1 Oe em A/m
RHO_CU_20 = 1.724e-8                 # ohm.m a 20 C (IACS)
ALPHA_CU = 0.00393                   # 1/K
DENS_CU = 8.96e3                     # kg/m^3


# ---------------------------------------------------------------- material
class Material:
    """Material de nucleo em po.

    rolloff(H): fracao da permeabilidade inicial (0..1), incremental, H em A/m.
    k, alpha, beta: Steinmetz SI, Pv[W/m^3] = k f^alpha Bpk^beta, Bpk = dB/2.
    """

    def __init__(self, name, mu_i, rolloff, k, alpha, beta, source=""):
        self.name = name
        self.mu_i = mu_i
        self.rolloff = rolloff
        self.k, self.alpha, self.beta = k, alpha, beta
        self.source = source
        self._ki = None
        self._bh = None

    @property
    def ki(self):
        if self._ki is None:
            a, b = self.alpha, self.beta
            integ, _ = quad(lambda t: abs(np.cos(t)) ** a, 0.0, 2.0 * np.pi, limit=200)
            self._ki = self.k / ((2.0 * np.pi) ** (a - 1.0) * integ * 2.0 ** (b - a))
        return self._ki

    def pv_sine(self, f, Bpk):
        return self.k * np.asarray(f) ** self.alpha * np.asarray(Bpk) ** self.beta

    def B_of_H(self, H):
        """Curva integrada: B(H) = mu0 mu_i * integral_0^H rolloff(h) dh."""
        if self._bh is None:
            Hg = np.concatenate(([0.0], np.logspace(-1, 6.5, 6000)))
            Bg = MU0 * self.mu_i * cumulative_trapezoid(self.rolloff(Hg), Hg, initial=0.0)
            self._bh = (Hg, Bg)
        Hg, Bg = self._bh
        return np.interp(np.abs(H), Hg, Bg) * np.sign(H)


def rolloff_H0n(H0, n):
    """mu_inc/mu_i = 1/(1 + (H/H0)^n), H e H0 em A/m."""
    return lambda H: 1.0 / (1.0 + (np.abs(H) / H0) ** n)


def magnetics_to_H0n(a, b, c):
    """Ajuste de catalogo %mu = 1/(a + b H^c), H em Oe -> (H0 em A/m, n)."""
    H0_oe = (a / b) ** (1.0 / c)
    return H0_oe * OE, c


def steinmetz_magnetics(a, b, c):
    """PL[mW/cm^3] = a Bpk[T]^b f[kHz]^c  ->  SI (W/m^3, Hz, T de amplitude)."""
    return a * 10.0 ** (3.0 - 3.0 * c), c, b


def steinmetz_dB_kWm3(a, alpha, beta):
    """P[kW/m^3] = a f[kHz]^alpha dB[T]^beta, dB pico a pico -> SI com B de amplitude."""
    k = a * 1e3 * 10.0 ** (-3.0 * alpha) * 2.0 ** beta
    return k, alpha, beta


# ---------------------------------------------------------------- geometria
class Toroid:
    """Toroide; dimensoes externas (com acabamento) em m e parametros magneticos.

    n_stack: numero (real) de alturas do nucleo unitario; Ae e Ve escalam com ele.
    """

    def __init__(self, name, OD, ID, HT, Ae, le, Ve, n_stack=1.0, source=""):
        self.name = name
        self.OD, self.ID = OD, ID
        self.HT1, self.Ae1, self.Ve1 = HT, Ae, Ve
        self.le = le
        self.n_stack = n_stack
        self.source = source

    @property
    def HT(self):
        return self.HT1 * self.n_stack

    @property
    def Ae(self):
        return self.Ae1 * self.n_stack

    @property
    def Ve(self):
        return self.Ve1 * self.n_stack

    @property
    def Wa(self):
        return np.pi * (self.ID / 2.0) ** 2

    @property
    def V_geom(self):
        return np.pi / 4.0 * (self.OD ** 2 - self.ID ** 2) * self.HT

    def AL_nominal(self, mu_i):
        return MU0 * mu_i * self.Ae / self.le


# ---------------------------------------------------------------- enrolamento
class Winding:
    """Fio redondo esmaltado: d_cu (cobre) e d_o (externo)."""

    def __init__(self, N, d_cu, d_o, T_w=20.0):
        self.N = int(N)
        self.d_cu, self.d_o = d_cu, d_o
        self.T_w = T_w

    @property
    def rho(self):
        return RHO_CU_20 * (1.0 + ALPHA_CU * (self.T_w - 20.0))

    @property
    def A_cu(self):
        return np.pi * self.d_cu ** 2 / 4.0

    def geometry(self, core):
        """Camadas na face interna, espira media, ocupacao e envoltoria."""
        total, r, lay, k = self.N, core.ID / 2.0, [], 0
        while total > 0:
            rc = r - (k + 0.5) * self.d_o
            if rc <= self.d_o:
                return None
            cap = int(np.floor(2.0 * np.pi * rc / self.d_o))
            lay.append(min(cap, total))
            total -= lay[-1]
            k += 1
        t_in = len(lay) * self.d_o
        cap_out = np.floor(2.0 * np.pi * (core.OD / 2.0 + self.d_o / 2.0) / self.d_o)
        t_out = int(np.ceil(self.N / cap_out)) * self.d_o
        w = (core.OD - core.ID) / 2.0
        mlt = 2.0 * (w + core.HT) + np.pi * (t_in + t_out) / 2.0
        OD_w = core.OD + 2.0 * t_out
        HT_w = core.HT + 2.0 * t_in
        r1 = r - 0.5 * self.d_o
        pitch = max(2.0 * np.pi * r1 / lay[0], self.d_o)
        return dict(layers=lay, t_in=t_in, t_out=t_out, MLT=mlt,
                    Ku=self.N * np.pi * self.d_o ** 2 / 4.0 / core.Wa,
                    OD_w=OD_w, HT_w=HT_w, V_box=np.pi / 4.0 * OD_w ** 2 * HT_w,
                    pitch=pitch, m_cu=DENS_CU * self.N * mlt * self.A_cu)

    def Fr(self, f, pitch, m=1):
        """Dowell para condutor redondo (camada equivalente de lado sqrt(pi) d/2)."""
        f = np.atleast_1d(f).astype(float)
        delta = np.sqrt(self.rho / (np.pi * f * MU0))
        D = (np.pi / 4.0) ** 0.75 * (self.d_cu / delta) * np.sqrt(self.d_cu / pitch)
        D = np.minimum(D, 300.0)
        t1 = (np.sinh(2 * D) + np.sin(2 * D)) / (np.cosh(2 * D) - np.cos(2 * D))
        t2 = (np.sinh(D) - np.sin(D)) / (np.cosh(D) + np.cos(D))
        return D * (t1 + 2.0 * (m ** 2 - 1.0) / 3.0 * t2)


class Inductor:
    """Nucleo + material + enrolamento; L0 e Rcc podem vir declarados (fonte externa)."""

    def __init__(self, name, mat, core, wdg, L0=None, Rdc=None, m_dowell=1,
                 kcore=1.0):
        self.name, self.mat, self.core, self.wdg = name, mat, core, wdg
        self.geom = wdg.geometry(core)
        self.L0 = L0 if L0 is not None else wdg.N ** 2 * core.AL_nominal(mat.mu_i)
        self.Rdc = Rdc if Rdc is not None else wdg.rho * wdg.N * self.geom["MLT"] / wdg.A_cu
        self.m_dowell = m_dowell
        self.kcore = kcore              # fator de ancoragem da lei de perda (1 = sem)

    def L_inc(self, i):
        H = self.wdg.N * np.abs(i) / self.core.le
        return self.L0 * self.mat.rolloff(H)


# ---------------------------------------------------------------- conversor
class PFCSpec:
    def __init__(self, Vo, Po_rated, fs, fL=60.0, eta=1.0, source=""):
        self.Vo, self.Po_rated, self.fs, self.fL, self.eta = Vo, Po_rated, fs, fL, eta
        self.source = source


def harmonic_amplitudes(Delta, d1, d2, nmax):
    """Amplitudes das harmonicas de uma triangular por periodo de chaveamento.

    Sobe Delta em d1*Ts, desce Delta em d2*Ts, nula no restante (DCM se d1+d2<1).
    """
    n = np.arange(1, nmax + 1)[:, None]
    Delta = np.atleast_1d(Delta)[None, :]
    d1 = np.maximum(np.atleast_1d(d1)[None, :], 1e-12)
    d2 = np.maximum(np.atleast_1d(d2)[None, :], 1e-12)
    p1 = 2.0 * np.pi * n * d1
    p2 = 2.0 * np.pi * n * (d1 + d2)
    z = (1.0 - np.exp(-1j * p1)) / d1 - (np.exp(-1j * p1) - np.exp(-1j * p2)) / d2
    return Delta / (2.0 * np.pi ** 2 * n ** 2) * np.abs(z)


def line_cycle(spec, Vrms, load, ind, ntheta=400, nharm=60):
    """Grandezas ao longo de meio ciclo de rede, theta em (0, pi)."""
    mat, core, wdg = ind.mat, ind.core, ind.wdg
    th = (np.arange(ntheta) + 0.5) * np.pi / ntheta
    Po = load * spec.Po_rated
    Irms = Po / (spec.eta * Vrms)
    v = np.sqrt(2.0) * Vrms * np.sin(th)
    i_avg = np.sqrt(2.0) * Irms * np.sin(th)
    Ts = 1.0 / spec.fs
    N = wdg.N
    H_dc = N * i_avg / core.le
    L = ind.L_inc(i_avg)

    D_ccm = 1.0 - v / spec.Vo
    di_ccm = v * D_ccm * Ts / L
    ccm = i_avg >= di_ccm / 2.0
    dd = np.sqrt(2.0 * L * i_avg * (spec.Vo - v) / (v * Ts * spec.Vo))
    ipk_dcm = v * dd * Ts / L
    d2_dcm = v * dd / (spec.Vo - v)
    d1 = np.where(ccm, D_ccm, dd)
    d2 = np.where(ccm, 1.0 - D_ccm, d2_dcm)
    Delta = np.where(ccm, di_ccm, ipk_dcm)
    i_pk = np.where(ccm, i_avg + di_ccm / 2.0, ipk_dcm)
    i_min = np.where(ccm, i_avg - di_ccm / 2.0, 0.0)

    dB = v * d1 * Ts / (N * core.Ae)                        # pico a pico (Faraday)
    # niveis de B por periodo (fluxo concatenado linear no tempo; media de i = i_avg)
    B_dc = mat.B_of_H(H_dc)
    B_max = mat.B_of_H(N * i_pk / core.le)

    a, b = mat.alpha, mat.beta
    shape = d1 ** (1.0 - a) + d2 ** (1.0 - a)
    pv = ind.kcore * mat.ki * dB ** b * spec.fs ** a * shape
    p_core = core.Ve * pv

    An = harmonic_amplitudes(Delta, d1, d2, nharm)
    Fr = wdg.Fr(spec.fs * np.arange(1, nharm + 1), ind.geom["pitch"], ind.m_dowell)[:, None]
    p_cu_hf = ind.Rdc * (Fr * An ** 2 / 2.0).sum(axis=0)
    p_cu_lf = ind.Rdc * i_avg ** 2

    return dict(theta=th, v=v, i_avg=i_avg, L=L, ccm=ccm, d1=d1, d2=d2,
                Delta=Delta, i_pk=i_pk, i_min=i_min, H_dc=H_dc,
                H_pk=N * i_pk / core.le, dB=dB, B_dc=B_dc, B_max=B_max,
                pv=pv, p_core=p_core, p_cu_lf=p_cu_lf, p_cu_hf=p_cu_hf,
                P_core=p_core.mean(), P_cu_lf=p_cu_lf.mean(),
                P_cu_hf=p_cu_hf.mean(),
                P_cu=p_cu_lf.mean() + p_cu_hf.mean(),
                P_tot=p_core.mean() + p_cu_lf.mean() + p_cu_hf.mean(),
                Irms=Irms, Po=Po, P_in=np.mean(v * i_avg))
