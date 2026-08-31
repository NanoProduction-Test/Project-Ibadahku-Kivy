🕌 IbadahKu
Aplikasi pencatat jadwal ibadah & kegiatan harian, dibuat dengan Python dan Kivy.Menampilkan timeline harian yang menggabungkan waktu sholat dengan kegiatan pribadi — supaya ibadah dan aktivitas terlihat dalam satu pandangan.

Python
Kivy
SQLite

✨ Fitur
📅 Timeline harian: waktu sholat & kegiatan pribadi terurut otomatis
➕ Tambah kegiatan: nama, jam, hari, kategori — lengkap dengan validasi input
💾 Data tersimpan permanen (SQLite) — tidak hilang saat aplikasi ditutup
🗑️ Hapus kegiatan
🕌 Jadwal sholat otomatis per kota (minggu 2)
⏱️ Timer sesi ibadah & checklist harian (minggu 3)
📊 Statistik & build APK (minggu 4)
🖼️ Tampilan
Beranda	Tambah Kegiatan
(screenshot menyusul)	(screenshot menyusul)
🚀 Cara Menjalankan
# 1. Install librarypip install kivy# 2. Jalankan aplikasipython main.py
🛠️ Teknologi
Teknologi
Peran
Python 3.13	Bahasa utama
Kivy 2.3	Framework GUI multi-platform
SQLite	Penyimpanan data kegiatan
Aladhan API	Sumber jadwal sholat (minggu 2)
📁 Struktur Project
ibadahku/
├── main.py          # Otak aplikasi: layar & logika
├── ibadahku.kv      # Layout antarmuka (Kivy language)
├── database.py      # Query SQLite
└── prayertimes.py   # Jadwal sholat dari API (minggu 2)
📈 Progres Pengembangan
Project ini dikerjakan bertahap selama 4 minggu:

 Minggu 1 — Kerangka aplikasi, CRUD kegiatan, timeline harian
 Minggu 2 — Jadwal sholat otomatis (API Aladhan) + pilih kota
 Minggu 3 — Timer sesi ibadah, checklist harian, streak
 Minggu 4 — Statistik, mode gelap, build APK