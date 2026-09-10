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
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.textinput import TextInput

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

# notifikasi bersifat opsional: gagal/absen tidak boleh membuat app crash
try:
    from plyer import notification
except ImportError:
    notification = None


def kirim_notif(judul, pesan):
    if notification is None:
        return
    try:
        notification.notify(title=judul, message=pesan,
                            app_name="IbadahKu", timeout=10)
    except Exception:
        pass


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


class BarisCeklis(BoxLayout):
    """Satu baris ceklis: tombol centang + nama + tombol hapus."""

    def __init__(self, data, selesai, layar, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = 48
        self.padding = [10, 4]
        self.item_id = data["id"]
        self.layar = layar
        self.selesai = selesai

        with self.canvas.before:
            self.instr_warna = Color(rgba=self.warna_baris())
            self.bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self.perbarui_bg, size=self.perbarui_bg)

        self.tombol = Button(text="[x]" if selesai else "[ ]",
                             size_hint_x=0.14, font_size=16)
        self.tombol.bind(on_release=self.tekan)
        self.add_widget(self.tombol)

        self.add_widget(Label(text=data["nama"], size_hint_x=0.68, font_size=16))

        hapus = Button(text="Hapus", size_hint_x=0.18, font_size=12)
        hapus.bind(on_release=lambda b: self.hapus())
        self.add_widget(hapus)

    def warna_baris(self):
        return (0.78, 0.9, 0.8, 1) if self.selesai else (0.93, 0.93, 0.95, 1)

    def perbarui_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size

    def tekan(self, *_):
        db.toggle_ceklis(self.item_id, datetime.date.today().isoformat())
        self.layar.muat_ceklis()          # refresh baris + streak + hitungan

    def hapus(self):
        db.hapus_item_ceklis(self.item_id)
        self.layar.muat_ceklis()


class PopupCeklis(Popup):
    """Form kecil melayang untuk menambah item ceklis."""

    def __init__(self, layar, **kwargs):
        super().__init__(**kwargs)
        self.layar = layar
        self.title = "Tambah Item Ceklis"
        self.size_hint = (0.9, None)
        self.height = 210

        kotak = BoxLayout(orientation="vertical", padding=15, spacing=10)
        kotak.add_widget(Label(text="Nama item ceklis:",
                               size_hint_y=None, height=26))
        self.input = TextInput(hint_text="contoh: Sholat dhuha",
                               multiline=False, size_hint_y=None, height=44)
        kotak.add_widget(self.input)
        tombol = Button(text="Simpan", size_hint_y=None, height=48)
        tombol.bind(on_release=self.simpan)
        kotak.add_widget(tombol)
        self.content = kotak

    def simpan(self, *_):
        nama = self.input.text.strip()
        if nama:
            db.tambah_item_ceklis(nama)
        self.dismiss()
        self.layar.muat_ceklis()


class HomeScreen(Screen):
    tanggal = StringProperty("")
    countdown = StringProperty("Memuat jadwal...")
    teks_streak = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.jadwal = None
        self.jam_event = None
        self.sedang_memuat = False
        self.kegiatan_hari_ini = []   # untuk notifikasi "waktunya..."
        self.notif_terkirim = set()

    def on_enter(self):
        hari = datetime.date.today()
        self.tanggal = (f"{HARI[hari.weekday()]}, {hari.day} "
                        f"{BULAN[hari.month - 1]} {hari.year}")

        kota = db.ambil_pengaturan("kota", KOTA_DEFAULT)
        cache = db.ambil_jadwal(kota, hari.isoformat())
        if cache:
            self.jadwal = cache
        elif not self.sedang_memuat:
            self.sedang_memuat = True
            self.countdown = "Memuat jadwal..."
            threading.Thread(
                target=self.ambil_dari_api, args=(kota,), daemon=True
            ).start()

        self.muat_timeline()
        self.muat_ceklis()
        self.mulai_countdown()

    def on_leave(self):
        if self.jam_event:
            self.jam_event.cancel()
            self.jam_event = None

    # ---------- jadwal sholat ----------

    def ambil_dari_api(self, kota):
        jadwal, pesan_error = None, ""
        try:
            jadwal = prayertimes.ambil_jadwal(kota)
        except Exception as e:
            pesan_error = f"{type(e).__name__}: {e}"
        Clock.schedule_once(lambda dt: self.jadwal_tiba(jadwal, pesan_error))

    def jadwal_tiba(self, jadwal, pesan_error=""):
        self.sedang_memuat = False
        if jadwal:
            kota = db.ambil_pengaturan("kota", KOTA_DEFAULT)
            db.simpan_jadwal(kota, datetime.date.today().isoformat(), jadwal)
            self.jadwal = jadwal
            self.muat_timeline()
            self.perbarui_countdown()
        else:
            self.countdown = f"Gagal: {pesan_error}"

    # ---------- countdown + notifikasi kegiatan ----------

    def mulai_countdown(self):
        if self.jam_event:
            return
        self.perbarui_countdown()
        self.jam_event = Clock.schedule_interval(self.perbarui_countdown, 30)

    def perbarui_countdown(self, *args):
        self.cek_notif_kegiatan()
        if not self.jadwal:
            return
        nama, target, besok = self.waktu_berikutnya()
        selisih = int((target - datetime.datetime.now()).total_seconds())
        if selisih < 0:
            selisih = 0
        j = selisih // 3600
        m = (selisih % 3600) // 60
        keterangan = " (besok)" if besok else ""
        self.countdown = f"Menuju {nama}{keterangan} - {j}j {m:02d}m"

    def waktu_berikutnya(self):
        sekarang = datetime.datetime.now()
        for nama, jam in self.jadwal:
            j, m = map(int, jam.split(":"))
            target = sekarang.replace(hour=j, minute=m, second=0, microsecond=0)
            if target > sekarang:
                return nama, target, False
        nama, jam = self.jadwal[0]
        j, m = map(int, jam.split(":"))
        target = sekarang.replace(hour=j, minute=m, second=0, microsecond=0)
        return nama, target + datetime.timedelta(days=1), True

    def cek_notif_kegiatan(self):
        """Dipanggil tiap 30 detik: kegiatan yang jamnya tiba -> notifikasi."""
        sekarang = datetime.datetime.now().strftime("%H:%M")
        for id_k, nama, jam in self.kegiatan_hari_ini:
            if jam == sekarang and id_k not in self.notif_terkirim:
                self.notif_terkirim.add(id_k)
                kirim_notif("IbadahKu", f"Waktunya: {nama}")

    # ---------- timeline & ceklis ----------

    def muat_timeline(self):
        daftar = self.ids.timeline
        daftar.clear_widgets()

        item = []
        self.kegiatan_hari_ini = []
        if self.jadwal:
            item = [(jam, nama, (0.85, 0.93, 0.87, 1))
                    for nama, jam in self.jadwal]
        for k in db.kegiatan_hari_ini(HARI[datetime.date.today().weekday()]):
            item.append((k["jam"], k["nama"], (0.93, 0.93, 0.95, 1)))
            self.kegiatan_hari_ini.append((k["id"], k["nama"], k["jam"]))
        item.sort(key=lambda x: x[0])

        for jam, nama, warna in item:
            daftar.add_widget(BarisTimeline(jam, nama, warna))

    def muat_ceklis(self):
        grid = self.ids.grid_ceklis
        grid.clear_widgets()
        hari = datetime.date.today().isoformat()
        status = db.status_ceklis(hari)

        selesai = total = 0
        for c in db.semua_ceklis():
            total += 1
            done = status.get(c["id"], False)
            if done:
                selesai += 1
            grid.add_widget(BarisCeklis(c, done, self))

        streak = db.hitung_streak()
        self.teks_streak = (f"Streak: {streak} hari  "
                            f" Selesai hari ini: {selesai}/{total}")

    def buka_popup_ceklis(self):
        PopupCeklis(self).open()


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
    waktu = StringProperty("15:00")
    status = StringProperty("Pilih durasi lalu tekan Mulai")
    total_hari_ini = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sisa = 0        # detik tersisa
        self.total = 1       # total detik sesi (diisi saat mulai)
        self.event = None    # penunjuk Clock yang berjalan

    def on_enter(self):
        self.perbarui_total()

    def perbarui_total(self):
        menit = db.total_timer_hari_ini()
        self.total_hari_ini = f"Total sesi hari ini: {menit} menit"

    def mulai(self):
        if self.event:                       # sedang berjalan -> abaikan
            return
        if self.sisa <= 0:                   # sesi baru: baca durasi
            menit = int(self.ids.spin_durasi.text)
            self.total = menit * 60
            self.sisa = self.total
        self.status = "Sesi berjalan..."
        self.tampilkan()
        self.event = Clock.schedule_interval(self.detik, 1)

    def jeda(self):
        if self.event:
            self.event.cancel()
            self.event = None
            self.status = "Jeda - tekan Mulai untuk lanjut"

    def ulang(self):
        self.jeda()
        self.sisa = 0
        self.waktu = "00:00"
        self.status = "Direset. Pilih durasi lalu Mulai"
        self.ids.progres.value = 0

    def detik(self, dt):
        self.sisa -= 1
        if self.sisa <= 0:
            self.selesai_sesi()
            return
        self.tampilkan()

    def tampilkan(self):
        m = self.sisa // 60
        s = self.sisa % 60
        self.waktu = f"{m:02d}:{s:02d}"
        self.ids.progres.value = 1 - self.sisa / self.total

    def selesai_sesi(self):
        self.jeda()
        self.sisa = 0
        self.waktu = "00:00"
        self.ids.progres.value = 1
        self.status = "Alhamdulillah, sesi selesai!"
        db.catat_timer(self.total // 60)
        self.perbarui_total()
        kirim_notif("IbadahKu", "Sesi ibadah selesai. Alhamdulillah!")


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