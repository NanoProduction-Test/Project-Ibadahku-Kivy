import sqlite3

DB = "ibadahku.db"

NAMA_WAKTU = ["Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"]


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


# ---------------- kegiatan (sama seperti Minggu 1) ----------------

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


# ---------------- pengaturan (BARU) ----------------

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


# ---------------- cache jadwal sholat (BARU) ----------------

def simpan_jadwal(kota, tanggal, jadwal):
    """jadwal = [("Subuh", "04:35"), ...] disimpan per kota & tanggal."""
    jam = [waktu for _, waktu in jadwal]
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT OR REPLACE INTO jadwal_cache VALUES (?,?,?,?,?,?,?)",
            (kota, tanggal, *jam),
        )


def ambil_jadwal(kota, tanggal):
    """Return list (nama, jam), atau None kalau belum ada di cache."""
    with sqlite3.connect(DB) as con:
        baris = con.execute(
            "SELECT subuh, dzuhur, ashar, maghrib, isya FROM jadwal_cache"
            " WHERE kota = ? AND tanggal = ?",
            (kota, tanggal),
        ).fetchone()
    if baris is None:
        return None
    return list(zip(NAMA_WAKTU, baris))