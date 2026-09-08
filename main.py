import datetime
import re
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
from kivy.graphics import Color, Rectangle
from kivy.properties import StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen

import database as db
import prayertimes

# jendela ukuran layar HP
Config.set("graphics", "width", "400")
Config.set("graphics", "height", "700")

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Ahad"]
BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
         "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

KOTA_DEFAULT = "Jakarta"
DAFTAR_KOTA = [
    "Jakarta", "Bandung", "Bekasi", "Bogor", "Tangerang", "Depok",
    "Semarang", "Yogyakarta", "Surabaya", "Malang",
    "Medan", "Palembang", "Makassar", "Denpasar",
]


class Navigasi(BoxLayout):
    """Bar navigasi bawah, dipakai di semua layar."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = 58
        menu = [("Beranda", "home"), ("Kegiatan", "kegiatan"),
                ("Timer", "timer"), ("Pengaturan", "pengaturan")]
        for judul, nama_screen in menu:
            btn = Button(text=judul, font_size=13)
            btn.bind(on_release=lambda b, s=nama_screen: self.pindah(s))
            self.add_widget(btn)

    def pindah(self, nama):
        sm = App.get_running_app().root
        if sm.current != nama:
            sm.current = nama


class BarisTimeline(BoxLayout):
    """Satu baris timeline di Beranda: jam + nama kegiatan."""

    def __init__(self, jam, nama, warna, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = 46
        with self.canvas.before:
            Color(*warna)
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.perbarui_bg, size=self.perbarui_bg)
        self.add_widget(Label(text=jam, size_hint_x=0.25, bold=True))
        self.add_widget(Label(text=nama, size_hint_x=0.75))

    def perbarui_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size


class HomeScreen(Screen):
    tanggal = StringProperty("")
    countdown = StringProperty("Memuat jadwal...")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.jadwal = None            # [("Subuh","04:35"), ...]
        self.jam_event = None         # timer countdown
        self.sedang_memuat = False    # thread API sedang jalan?

    def on_enter(self):
        hari = datetime.date.today()
        self.tanggal = (f"{HARI[hari.weekday()]}, {hari.day} "
                        f"{BULAN[hari.month - 1]} {hari.year}")

        # 1) coba cache dulu (offline-friendly)
        kota = db.ambil_pengaturan("kota", KOTA_DEFAULT)
        cache = db.ambil_jadwal(kota, hari.isoformat())
        if cache:
            self.jadwal = cache
        elif not self.sedang_memuat:
            # 2) tidak ada cache → ambil dari API di THREAD TERPISAH
            self.sedang_memuat = True
            self.countdown = "Memuat jadwal..."
            threading.Thread(
                target=self.ambil_dari_api, args=(kota,), daemon=True
            ).start()

        self.muat_timeline()
        self.mulai_countdown()

    def on_leave(self):
        # matikan timer biar tidak dobel saat kembali ke layar ini
        if self.jam_event:
            self.jam_event.cancel()
            self.jam_event = None

    # ---------- jadwal sholat ----------

    def ambil_dari_api(self, kota):
        """Berjalan di thread KEDUA. Jaringan di sini, bukan di thread utama."""
        try:
            jadwal = prayertimes.ambil_jadwal(kota)
        except Exception:
            jadwal = None
        # kirim hasil balik ke thread utama untuk mengubah tampilan
        Clock.schedule_once(lambda dt: self.jadwal_tiba(jadwal))

    def jadwal_tiba(self, jadwal):
        self.sedang_memuat = False
        if jadwal:
            kota = db.ambil_pengaturan("kota", KOTA_DEFAULT)
            db.simpan_jadwal(kota, datetime.date.today().isoformat(), jadwal)
            self.jadwal = jadwal
            self.muat_timeline()
            self.perbarui_countdown()
        else:
            self.countdown = "Jadwal gagal dimuat (cek internet / kota)"

    # ---------- countdown ----------

    def mulai_countdown(self):
        if self.jam_event:            # sudah jalan? jangan dobel
            return
        self.perbarui_countdown()
        self.jam_event = Clock.schedule_interval(self.perbarui_countdown, 30)

    def perbarui_countdown(self, *args):
        if not self.jadwal:
            return                    # masih memuat / gagal
        nama, target, besok = self.waktu_berikutnya()
        selisih = int((target - datetime.datetime.now()).total_seconds())
        if selisih < 0:
            selisih = 0
        j = selisih // 3600
        m = (selisih % 3600) // 60
        keterangan = " (besok)" if besok else ""
        self.countdown = f"Menuju {nama}{keterangan} - {j}j {m:02d}m"

    def waktu_berikutnya(self):
        """Cari waktu sholat berikutnya dari sekarang."""
        sekarang = datetime.datetime.now()
        for nama, jam in self.jadwal:
            j, m = map(int, jam.split(":"))
            target = sekarang.replace(hour=j, minute=m, second=0, microsecond=0)
            if target > sekarang:
                return nama, target, False
        # sudah lewat Isya → targetnya Subuh besok
        nama, jam = self.jadwal[0]
        j, m = map(int, jam.split(":"))
        target = sekarang.replace(hour=j, minute=m, second=0, microsecond=0)
        return nama, target + datetime.timedelta(days=1), True

    # ---------- timeline ----------

    def muat_timeline(self):
        daftar = self.ids.timeline
        daftar.clear_widgets()

        item = []
        if self.jadwal:
            item = [(jam, nama, (0.85, 0.93, 0.87, 1))
                    for nama, jam in self.jadwal]
        for k in db.kegiatan_hari_ini(HARI[datetime.date.today().weekday()]):
            item.append((k["jam"], k["nama"], (0.93, 0.93, 0.95, 1)))
        item.sort(key=lambda x: x[0])

        for jam, nama, warna in item:
            daftar.add_widget(BarisTimeline(jam, nama, warna))


class BarisKegiatan(BoxLayout):
    """Satu baris kegiatan di layar Kegiatan + tombol hapus."""

    def __init__(self, data, layar, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = 62
        self.padding = [10, 6]

        info = BoxLayout(orientation="vertical")
        info.add_widget(Label(text=data["nama"], bold=True, font_size=17))
        info.add_widget(Label(
            text=f"{data['jam']}  •  {data['hari']}  •  {data['kategori']}",
            font_size=13))
        self.add_widget(info)

        btn = Button(text="Hapus", size_hint_x=0.25)
        btn.bind(on_release=lambda b: self.hapus(data["id"], layar))
        self.add_widget(btn)

    def hapus(self, id_kegiatan, layar):
        db.hapus(id_kegiatan)
        layar.muat_daftar()


class KegiatanScreen(Screen):
    def on_enter(self):
        self.muat_daftar()

    def muat_daftar(self):
        daftar = self.ids.daftar_kegiatan
        daftar.clear_widgets()
        for k in db.semua():
            daftar.add_widget(BarisKegiatan(k, self))


class TambahScreen(Screen):
    def simpan(self):
        nama = self.ids.inp_nama.text.strip()
        jam = self.ids.inp_jam.text.strip()

        if not nama:
            self.ids.lbl_pesan.text = "Nama kegiatan belum diisi"
            return
        cocok = re.fullmatch(r"(\d{1,2}):(\d{2})", jam)
        if not cocok:
            self.ids.lbl_pesan.text = "Format jam: HH:MM (contoh: 06:30)"
            return
        j, m = int(cocok.group(1)), int(cocok.group(2))
        if j > 23 or m > 59:
            self.ids.lbl_pesan.text = "Jam tidak valid (00:00 - 23:59)"
            return

        jam = f"{j:02d}:{m:02d}"
        db.tambah(nama, jam, self.ids.spin_hari.text, self.ids.spin_kategori.text)

        self.ids.inp_nama.text = ""
        self.ids.inp_jam.text = ""
        self.ids.lbl_pesan.text = ""
        self.manager.current = "kegiatan"


class TimerScreen(Screen):
    pass    # diisi di Minggu 3


class PengaturanScreen(Screen):
    def on_enter(self):
        spin = self.ids.spin_kota
        if not spin.values:
            spin.values = DAFTAR_KOTA
        spin.text = db.ambil_pengaturan("kota", KOTA_DEFAULT)

    def simpan_kota(self):
        kota = self.ids.spin_kota.text
        db.simpan_pengaturan("kota", kota)
        self.ids.lbl_status.text = (f"Kota tersimpan: {kota}\n"
                                    "Jadwal baru dimuat di Beranda")


class IbadahKuApp(App):
    title = "IbadahKu"

    def build(self):
        db.buat_tabel()
        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(KegiatanScreen(name="kegiatan"))
        sm.add_widget(TambahScreen(name="tambah"))
        sm.add_widget(TimerScreen(name="timer"))
        sm.add_widget(PengaturanScreen(name="pengaturan"))
        return sm


if __name__ == "__main__":
    IbadahKuApp().run()