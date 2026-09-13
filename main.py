import datetime
import re
import threading

from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import ListProperty, StringProperty
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


class Tema:
    """Pusat semua warna IbadahKu. Ubah di sini, seluruh app ikut."""

    terang = {
        "latar":      (0.95, 0.96, 0.95, 1),
        "kartu":      (1, 1, 1, 1),
        "utama":      (0.13, 0.45, 0.36, 1),
        "utama_muda": (0.85, 0.93, 0.87, 1),
        "netral":     (0.93, 0.93, 0.95, 1),
        "nav":        (0.88, 0.92, 0.89, 1),
        "teks":       (0.13, 0.15, 0.14, 1),
        "teks_pudar": (0.45, 0.48, 0.46, 1),
        "aksen":      (1, 0.95, 0.8, 1),
        "putih":      (1, 1, 1, 1),
    }
    gelap = {
        "latar":      (0.09, 0.11, 0.10, 1),
        "kartu":      (0.16, 0.19, 0.18, 1),
        "utama":      (0.16, 0.40, 0.33, 1),
        "utama_muda": (0.22, 0.35, 0.29, 1),
        "netral":     (0.20, 0.22, 0.21, 1),
        "nav":        (0.20, 0.24, 0.22, 1),
        "teks":       (0.92, 0.95, 0.93, 1),
        "teks_pudar": (0.60, 0.65, 0.62, 1),
        "aksen":      (0.95, 0.87, 0.6, 1),
        "putih":      (1, 1, 1, 1),
    }
    warna = terang

    @classmethod
    def muat(cls):
        gelap = db.ambil_pengaturan("mode_gelap", "0") == "1"
        cls.warna = cls.gelap if gelap else cls.terang


class Tombol(Button):
    """Button rata (flat) yang warnanya diambil dari Tema."""

    gaya = StringProperty("utama")          # kunci warna latar
    gaya_teks = StringProperty("putih")     # kunci warna tulisan

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.perbarui_warna()

    def on_gaya(self, *args):
        self.perbarui_warna()

    def on_gaya_teks(self, *args):
        self.perbarui_warna()

    def perbarui_warna(self):
        self.background_color = Tema.warna[self.gaya]
        self.color = Tema.warna[self.gaya_teks]


class Kartu(BoxLayout):
    """Panel dengan latar warna dan sudut membulat."""

    def __init__(self, warna=None, radius=12, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self.instr_warna = Color(rgba=warna or Tema.warna["kartu"])
            self.bg = RoundedRectangle(pos=self.pos, size=self.size,
                                       radius=[radius])
        self.bind(pos=self.perbarui_bg, size=self.perbarui_bg)

    def perbarui_bg(self, *args):
        self.bg.pos = self.pos
        self.bg.size = self.size


class Navigasi(BoxLayout):
    """Bar navigasi bawah, dipakai di semua layar."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = 58
        self.padding = [4, 4]
        self.spacing = 4
        menu = [("Beranda", "home"), ("Kegiatan", "kegiatan"),
                ("Timer", "timer"), ("Tasbih", "tasbih"),
                ("Lainnya", "pengaturan")]
        for judul, nama_screen in menu:
            btn = Tombol(text=judul, font_size=12, gaya="nav",
                         gaya_teks="teks")
            btn.bind(on_release=lambda b, s=nama_screen: self.pindah(s))
            self.add_widget(btn)

    def pindah(self, nama):
        sm = App.get_running_app().root
        if sm.current != nama:
            sm.current = nama


class BarisTimeline(Kartu):
    """Satu baris timeline di Beranda: jam + nama kegiatan."""

    def __init__(self, jam, nama, warna, **kwargs):
        super().__init__(warna=warna, **kwargs)
        self.size_hint_y = None
        self.height = 46
        self.padding = [14, 0]
        self.add_widget(Label(text=jam, size_hint_x=0.25, bold=True,
                              color=Tema.warna["teks"]))
        self.add_widget(Label(text=nama, size_hint_x=0.75,
                              color=Tema.warna["teks"]))


class BarisCeklis(Kartu):
    """Satu baris ceklis: tombol centang + nama + tombol hapus."""

    def __init__(self, data, selesai, layar, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = 48
        self.padding = [10, 4]
        self.item_id = data["id"]
        self.layar = layar
        self.selesai = selesai
        self.instr_warna.rgba = self.warna_baris()

        self.tombol = Tombol(text="[x]" if selesai else "[ ]",
                             gaya="utama" if selesai else "netral",
                             gaya_teks="putih" if selesai else "teks",
                             size_hint_x=0.14, font_size=15)
        self.tombol.bind(on_release=self.tekan)
        self.add_widget(self.tombol)

        self.add_widget(Label(text=data["nama"], size_hint_x=0.68,
                              font_size=16, color=Tema.warna["teks"]))

        hapus = Tombol(text="Hapus", gaya="netral", gaya_teks="teks_pudar",
                       size_hint_x=0.18, font_size=12)
        hapus.bind(on_release=lambda b: self.hapus())
        self.add_widget(hapus)

    def warna_baris(self):
        return (Tema.warna["utama_muda"] if self.selesai
                else Tema.warna["netral"])

    def tekan(self, *_):
        db.toggle_ceklis(self.item_id, datetime.date.today().isoformat())
        self.layar.muat_ceklis()

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
        tombol = Tombol(text="Simpan", size_hint_y=None, height=48)
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
        self.kegiatan_hari_ini = []
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
            item = [(jam, nama, Tema.warna["utama_muda"])
                    for nama, jam in self.jadwal]
        for k in db.kegiatan_hari_ini(HARI[datetime.date.today().weekday()]):
            item.append((k["jam"], k["nama"], Tema.warna["netral"]))
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


class BarisKegiatan(Kartu):
    """Satu baris kegiatan di layar Kegiatan + tombol hapus."""

    def __init__(self, data, layar, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = 64
        self.padding = [14, 8]

        info = BoxLayout(orientation="vertical")
        info.add_widget(Label(text=data["nama"], bold=True, font_size=17,
                              color=Tema.warna["teks"]))
        info.add_widget(Label(
            text=f"{data['jam']}  •  {data['hari']}  •  {data['kategori']}",
            font_size=13, color=Tema.warna["teks_pudar"]))
        self.add_widget(info)

        btn = Tombol(text="Hapus", gaya="netral", gaya_teks="teks_pudar",
                     size_hint_x=0.22, font_size=12)
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
        self.sisa = 0
        self.total = 1
        self.event = None

    def on_enter(self):
        self.perbarui_total()

    def perbarui_total(self):
        menit = db.total_timer_hari_ini()
        self.total_hari_ini = f"Total sesi hari ini: {menit} menit"

    def mulai(self):
        if self.event:
            return
        if self.sisa <= 0:
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


class TasbihScreen(Screen):
    hitungan_label = StringProperty("0")
    progres_label = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hitungan = 0
        self.tercatat = 0

    def on_enter(self):
        hari = datetime.date.today().isoformat()
        self.hitungan = db.ambil_tasbih(hari)
        self.tercatat = self.hitungan
        self.perbarui()

    def on_leave(self):
        self.simpan()

    def simpan(self):
        delta = self.hitungan - self.tercatat
        if delta > 0:
            db.simpan_tasbih(datetime.date.today().isoformat(), delta)
            self.tercatat = self.hitungan

    def tap(self):
        self.hitungan += 1
        teks_target = self.ids.spin_target.text
        if teks_target != "Bebas":
            target = int(teks_target)
            if self.hitungan == target:
                dzikir = self.ids.spin_dzikir.text
                kirim_notif("IbadahKu",
                            f"MasyaAllah, {target}x {dzikir} selesai!")
        self.perbarui()

    def ulang(self):
        self.hitungan = 0
        self.tercatat = 0
        db.reset_tasbih(datetime.date.today().isoformat())
        self.perbarui()

    def perbarui(self, *args):
        try:
            teks_target = self.ids.spin_target.text
        except AttributeError:
            return                       # ids belum siap saat layout dibangun
        self.hitungan_label = str(self.hitungan)
        if teks_target == "Bebas":
            self.progres_label = "Mode bebas (tanpa target)"
        else:
            self.progres_label = f"{self.hitungan} / {teks_target}"


class StatistikScreen(Screen):
    def on_enter(self):
        self.muat_statistik()

    def muat_statistik(self):
        grid = self.ids.grid_stat
        grid.clear_widgets()

        hari = datetime.date.today().isoformat()
        awal = (datetime.date.today()
                - datetime.timedelta(days=6)).isoformat()

        streak = db.hitung_streak()
        status = db.status_ceklis(hari)
        selesai = sum(1 for v in status.values() if v)
        aktif = len(db.semua_ceklis())
        menit_hari = db.total_timer_hari_ini()
        tasbih_hari = db.ambil_tasbih(hari)
        menit_minggu, tasbih_minggu, hari_aktif = db.ringkasan_minggu(awal)
        total_menit, total_tasbih = db.total_keseluruhan()

        self.baris(grid, "Streak ceklis", f"{streak} hari beruntun")
        self.baris(grid, "Ceklis hari ini",
                   f"{selesai} dari {aktif} item selesai")
        self.baris(grid, "Timer hari ini", f"{menit_hari} menit")
        self.baris(grid, "Tasbih hari ini", f"{tasbih_hari} kali")
        self.baris(grid, "7 hari terakhir",
                   f"{menit_minggu} menit  •  {tasbih_minggu}x dzikir  •  "
                   f"aktif {hari_aktif} hari")
        self.baris(grid, "Total keseluruhan",
                   f"{total_menit} menit  •  {total_tasbih}x dzikir")

    def baris(self, grid, judul, isi):
        kartu = Kartu(size_hint_y=None, height=72, padding=[16, 8])
        kotak = BoxLayout(orientation="vertical")
        kotak.add_widget(Label(text=judul, font_size=13,
                               color=Tema.warna["teks_pudar"],
                               size_hint_y=None, height=22))
        kotak.add_widget(Label(text=isi, font_size=16, bold=True,
                               color=Tema.warna["teks"]))
        kartu.add_widget(kotak)
        grid.add_widget(kartu)


class PengaturanScreen(Screen):
    def on_enter(self):
        self._sedang_muat = True          # cegah switch "menyala sendiri"
        spin = self.ids.spin_kota
        if not spin.values:
            spin.values = DAFTAR_KOTA
        spin.text = db.ambil_pengaturan("kota", KOTA_DEFAULT)
        self.ids.sw_gelap.active = db.ambil_pengaturan("mode_gelap", "0") == "1"
        self._sedang_muat = False

    def simpan_kota(self):
        kota = self.ids.spin_kota.text
        db.simpan_pengaturan("kota", kota)
        self.ids.lbl_status.text = f"Kota tersimpan: {kota}"

    def ubah_mode(self, switch, aktif):
        if getattr(self, "_sedang_muat", False):
            return
        db.simpan_pengaturan("mode_gelap", "1" if aktif else "0")
        self.ids.lbl_status.text = ("Tersimpan! Buka ulang aplikasi "
                                    "untuk melihat temanya")


class IbadahKuApp(App):
    title = "IbadahKu"

    # warna yang bisa dibaca oleh file .kv
    warna_utama = ListProperty((0.13, 0.45, 0.36, 1))
    warna_teks = ListProperty((0.13, 0.15, 0.14, 1))
    warna_pudar = ListProperty((0.45, 0.48, 0.46, 1))

    def build(self):
        db.buat_tabel()
        Tema.muat()
        Window.clearcolor = Tema.warna["latar"]   # latar jendela ikut tema
        self.warna_utama = Tema.warna["utama"]
        self.warna_teks = Tema.warna["teks"]
        self.warna_pudar = Tema.warna["teks_pudar"]

        sm = ScreenManager()
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(KegiatanScreen(name="kegiatan"))
        sm.add_widget(TambahScreen(name="tambah"))
        sm.add_widget(TimerScreen(name="timer"))
        sm.add_widget(TasbihScreen(name="tasbih"))
        sm.add_widget(StatistikScreen(name="statistik"))
        sm.add_widget(PengaturanScreen(name="pengaturan"))
        return sm


if __name__ == "__main__":
    IbadahKuApp().run()