"""Dados de entrada com a fonte de cada valor.

[1] Abdel-Rahman, Stueckler, Siu, Infineon AN rev. 1.1, 2016 (via manuscrito base e busca)
[2] Jiang et al., IEEE TPEL 35(10), 2020 (valores extraidos no manuscrito base)
[3] Magnetics, 2025 Powder Cores Catalog (valores citados no manuscrito base)
[7] Magnetics, datasheet 0077083A7, rev. 2021 (dimensoes e parametros)
"""
import numpy as np
from pfcmodel import *

mm = 1e-3
# Conversor [1]
SPEC = PFCSpec(Vo=400.0, Po_rated=1200.0, fs=100e3, fL=60.0, eta=1.0, source="[1]")
L_REQ, I_REQ, I_MAX = 168.5e-6, 19.97, 22.5           # [1, Eq. 1 e 2]

# Nucleo unitario 0077083A7 [7]
def core_77083(n_stack):
    return Toroid("0077083A7", OD=40.77 * mm, ID=23.32 * mm, HT=15.37 * mm,
                  Ae=107e-6, le=98.4 * mm, Ve=10.6e-6, n_stack=n_stack, source="[7]")

# Kool Mu 60u [3]: %mu = 1/(0.01 + 2.142e-6 H^1.855), H em Oe; PL = 44.30 B^1.988 f^1.541
H0_KM, n_KM = magnetics_to_H0n(0.01, 2.142e-6, 1.855)
k_KM, a_KM, b_KM = steinmetz_magnetics(44.30, 1.988, 1.541)
KM = Material("Kool Mu 60u", 60, rolloff_H0n(H0_KM, n_KM), k_KM, a_KM, b_KM, source="[3]")

# Po nanocristalino [2]: (1) com H0 = 93.0 A/cm, n = 1.71; P = 89.38 f^1.193 dB^2.01 (kW/m3, kHz, T p-p)
H0_NC, n_NC = 93.0e2, 1.71
k_NC, a_NC, b_NC = steinmetz_dB_kWm3(89.38, 1.193, 2.01)
NC = Material("Po nanocristalino 60u", 60, rolloff_H0n(H0_NC, n_NC), k_NC, a_NC, b_NC, source="[2]")
# leitura de pico (so para referencia): k sem o fator 2^beta
NC_pk = Material("NC leitura de pico", 60, rolloff_H0n(H0_NC, n_NC),
                 k_NC / 2.0 ** b_NC, a_NC, b_NC, source="[2]")

# Fio [1]: 1.15 mm; esmaltado 1.22 mm (premissa do manuscrito base)
D_CU, D_O = 1.15 * mm, 1.22 * mm
N_REF = 64
L0_REF, RDC_REF = 680e-6, 70e-3                         # [1]
