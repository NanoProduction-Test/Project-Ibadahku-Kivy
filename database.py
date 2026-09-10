import sqlite3
from datetime import date, timedelta

DB = "ibadahku.db"

NAMA_WAKTU = ["Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"]

CEKLIS_DEFAULT = [
    "Sholat Subuh", "Sholat Dzuhur", "Sholat Ashar",
    "Sholat Maghrib", "Sholat Isya",
    "Tilawah Qur'an", "Dzikir pagi", "Dzikir petang",
]


def buat_tabel():
    with sqlite3.connect(DB) as con:
        con.execute(
            """CREATE TABLE IF NOT EXISTS kegiatan (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                nama     TEXT NOT NULL,
                jam      TEXT NOT NULL,
                hari     TEXT NOT NULL DEFAULT 'Setiap hari',
                kategori TEXT NOT NULL DEFAULT 'Ibadah',
                aktif    INTEGER NOT NULL DEFAULT 1
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS pengaturan (
                kunci TEXT PRIMARY KEY,
                nilai TEXT NOT NULL
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS jadwal_cache (
                kota    TEXT NOT NULL,
                tanggal TEXT NOT NULL,
                subuh TEXT, dzuhur TEXT, ashar TEXT,
                maghrib TEXT, isya TEXT,
                PRIMARY KEY (kota, tanggal)
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS ceklis (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT NOT NULL,
                aktif INTEGER NOT NULL DEFAULT 1
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS ceklis_log (
                tanggal TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                selesai INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (tanggal, item_id)
            )"""
        )
        con.execute(
            """CREATE TABLE IF NOT EXISTS timer_log (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal TEXT NOT NULL,
                menit   INTEGER NOT NULL
            )"""
        )
        # isi item ceklis bawaan — hanya saat tabel masih kosong
        if con.execute("SELECT COUNT(*) FROM ceklis").fetchone()[0] == 0:
            for nama in CEKLIS_DEFAULT:
                con.execute("INSERT INTO ceklis (nama) VALUES (?)", (nama,))


# ---------------- kegiatan (sama seperti sebelumnya) ----------------

def tambah(nama, jam, hari, kategori):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO kegiatan (nama, jam, hari, kategori) VALUES (?, ?, ?, ?)",
            (nama, jam, hari, kategori),
        )


def semua():
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute("SELECT * FROM kegiatan ORDER BY jam").fetchall()


def kegiatan_hari_ini(nama_hari):
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(
            """SELECT * FROM kegiatan
               WHERE aktif = 1 AND (hari = ? OR hari = 'Setiap hari')
               ORDER BY jam""",
            (nama_hari,),
        ).fetchall()


def hapus(id_kegiatan):
    with sqlite3.connect(DB) as con:
        con.execute("DELETE FROM kegiatan WHERE id = ?", (id_kegiatan,))


# ---------------- pengaturan (sama seperti sebelumnya) ----------------

def simpan_pengaturan(kunci, nilai):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT OR REPLACE INTO pengaturan (kunci, nilai) VALUES (?, ?)",
            (kunci, nilai),
        )


def ambil_pengaturan(kunci, default=None):
    with sqlite3.connect(DB) as con:
        baris = con.execute(
            "SELECT nilai FROM pengaturan WHERE kunci = ?", (kunci,)
        ).fetchone()
        return baris[0] if baris else default


# ---------------- cache jadwal sholat (sama seperti sebelumnya) ----------------

def simpan_jadwal(kota, tanggal, jadwal):
    jam = [waktu for _, waktu in jadwal]
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT OR REPLACE INTO jadwal_cache VALUES (?,?,?,?,?,?,?)",
            (kota, tanggal, *jam),
        )


def ambil_jadwal(kota, tanggal):
    with sqlite3.connect(DB) as con:
        baris = con.execute(
            "SELECT subuh, dzuhur, ashar, maghrib, isya FROM jadwal_cache"
            " WHERE kota = ? AND tanggal = ?",
            (kota, tanggal),
        ).fetchone()
    if baris is None:
        return None
    return list(zip(NAMA_WAKTU, baris))


# ---------------- ceklis harian (BARU) ----------------

def semua_ceklis():
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute(
            "SELECT * FROM ceklis WHERE aktif = 1 ORDER BY id").fetchall()


def status_ceklis(tanggal):
    """Return dict {item_id: True/False} untuk satu tanggal."""
    with sqlite3.connect(DB) as con:
        baris = con.execute(
            "SELECT item_id, selesai FROM ceklis_log WHERE tanggal = ?",
            (tanggal,),
        ).fetchall()
    return {b[0]: bool(b[1]) for b in baris}


def toggle_ceklis(item_id, tanggal):
    """Balik status satu item (selesai <-> belum) pada satu tanggal."""
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT OR IGNORE INTO ceklis_log (tanggal, item_id, selesai)"
            " VALUES (?, ?, 0)", (tanggal, item_id))
        con.execute(
            "UPDATE ceklis_log SET selesai = 1 - selesai"
            " WHERE tanggal = ? AND item_id = ?", (tanggal, item_id))


def tambah_item_ceklis(nama):
    with sqlite3.connect(DB) as con:
        con.execute("INSERT INTO ceklis (nama) VALUES (?)", (nama,))


def hapus_item_ceklis(item_id):
    """Item disembunyikan (aktif = 0), riwayat log tetap utuh."""
    with sqlite3.connect(DB) as con:
        con.execute("UPDATE ceklis SET aktif = 0 WHERE id = ?", (item_id,))


def hitung_streak():
    """Berapa hari berturut-turut (minimal 1 item selesai) sampai hari ini."""
    with sqlite3.connect(DB) as con:
        baris = con.execute(
            "SELECT DISTINCT tanggal FROM ceklis_log WHERE selesai = 1"
            " ORDER BY tanggal DESC").fetchall()
    tanggal_ada = {b[0] for b in baris}
    hari = date.today()
    if hari.isoformat() not in tanggal_ada:
        hari -= timedelta(days=1)   # hari ini belum ada -> mulai cek dari kemarin
    streak = 0
    while hari.isoformat() in tanggal_ada:
        streak += 1
        hari -= timedelta(days=1)
    return streak


# ---------------- timer sesi ibadah (BARU) ----------------

def catat_timer(menit):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO timer_log (tanggal, menit) VALUES (?, ?)",
            (date.today().isoformat(), menit))


def total_timer_hari_ini():
    with sqlite3.connect(DB) as con:
        baris = con.execute(
            "SELECT COALESCE(SUM(menit), 0) FROM timer_log WHERE tanggal = ?",
            (date.today().isoformat(),)).fetchone()
    return baris[0]