import sqlite3

DB = "ibadahku.db"


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


def tambah(nama, jam, hari, kategori):
    with sqlite3.connect(DB) as con:
        con.execute(
            "INSERT INTO kegiatan (nama, jam, hari, kategori) VALUES (?, ?, ?, ?)",
            (nama, jam, hari, kategori),
        )


def semua():
    """Semua kegiatan, urut berdasarkan jam."""
    with sqlite3.connect(DB) as con:
        con.row_factory = sqlite3.Row
        return con.execute("SELECT * FROM kegiatan ORDER BY jam").fetchall()


def kegiatan_hari_ini(nama_hari):
    """Kegiatan hari ini: yang 'Setiap hari' + yang cocok dengan hari ini."""
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