"""Jembatan ke API Aladhan (https://aladhan.com) — gratis, tanpa API key."""

import requests

API = "https://api.aladhan.com/v1/timingsByCity"
METODE_KEMENAG = 20   # 20 = metode Kementerian Agama RI

NAMA_WAKTU = ["Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"]
KUNCI_API = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]


def ambil_jadwal(kota):
    """Ambil jadwal sholat HARI INI untuk satu kota di Indonesia.

    Return: [("Subuh", "04:35"), ("Dzuhur", "11:50"), ...]
    Memicu Exception kalau gagal (tanpa internet, kota tidak dikenal, dll).
    """
    r = requests.get(
        API,
        params={"city": kota, "country": "Indonesia", "method": METODE_KEMENAG},
        timeout=10,
    )
    r.raise_for_status()          # error otomatis kalau server menolak
    data = r.json()["data"]["timings"]

    jadwal = []
    for nama, kunci in zip(NAMA_WAKTU, KUNCI_API):
        jam = data[kunci][:5]     # "04:35 (WIB)" → "04:35"
        j, m = jam.split(":")
        jadwal.append((nama, f"{int(j):02d}:{int(m):02d}"))
    return jadwal