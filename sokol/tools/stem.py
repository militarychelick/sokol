# -*- coding: utf-8 -*-
"""
SOKOL v8.0 — STEM (Science, Technology, Engineering, Math)
Chemical data, molar masses, physical constants.
"""

STEM_DATA = {
    "molar_mass": {
        "h2o": 18.015,
        "h2so4": 98.079,
        "nacl": 58.44,
        "co2": 44.01,
        "nh3": 17.031,
        "ch4": 16.04,
        "c6h12o6": 180.16,
        "h": 1.008,
        "he": 4.0026,
        "c": 12.011,
        "n": 14.007,
        "o": 15.999,
        "na": 22.99,
        "cl": 35.45,
        "fe": 55.845,
        "cu": 63.546,
        "au": 196.97,
    },
    "constants": {
        "c": "299,792,458 m/s (speed of light)",
        "g": "6.67430e-11 m^3 kg^-1 s^-2 (gravitational constant)",
        "g_earth": "9.80665 m/s^2 (standard gravity)",
        "h": "6.62607015e-34 J s (Planck constant)",
        "k": "1.380649e-23 J/K (Boltzmann constant)",
        "na": "6.02214076e23 mol^-1 (Avogadro constant)",
        "r": "8.314462618 J/(mol K) (gas constant)",
    }
}

class STEMCore:
    @classmethod
    def get_molar_mass(cls, formula):
        f = formula.lower().strip()
        val = STEM_DATA["molar_mass"].get(f)
        if val:
            return f"Molar mass of {formula}: {val} g/mol"
        return f"Molar mass for '{formula}' not found in local STEM_DATA."

    @classmethod
    def get_constant(cls, name):
        n = name.lower().strip()
        val = STEM_DATA["constants"].get(n)
        if val:
            return f"Constant {name}: {val}"
        return f"Constant '{name}' not found in local STEM_DATA."
