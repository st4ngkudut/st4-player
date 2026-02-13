# ST4 Player Pro 🎧

**ST4 Player Pro** adalah Web-based Audio Player High-Fidelity yang dirancang khusus untuk berjalan di **Android (via Termux)**.

Aplikasi ini mengubah HP Android lama (atau baru) menjadi **Headless Music Streamer** berkualitas Audiophile yang bisa dikontrol lewat browser dari perangkat apa saja di jaringan WiFi yang sama.

---

## 🔥 Fitur Utama

### 🧠 Core System
- **Lightweight Backend:** Dibangun dengan **Flask** (Python) dan **SQLite**.
- **MPV Audio Engine:** Menggunakan **MPV** via Socket IPC untuk decoding audio bit-perfect.
- **Support Format Luas:** FLAC, WAV, MP3, OGG, AAC, M4A, OPUS.
- **Smart Library:** Scanning ribuan lagu dalam detik menggunakan `mutagen` (Metadata Reader).

### 🎨 User Experience
- **Progressive Web App (PWA):** Bisa diinstall ke Home Screen Android (Fullscreen, Native-like experience).
- **Smooth UI:** Progress bar 60fps dengan interpolasi waktu (anti patah-patah).
- **Physics Knobs:** Kontrol Volume & EQ dengan gaya putar (rotary) yang natural.
- **Lazy Loading:** Optimasi rendering untuk library dengan ribuan lagu.

### 🎛️ Audio Processing (DSP)
- **10-Band Equalizer:** Parametric EQ menggunakan FFmpeg filter (`firequalizer`).
- **Bit-Perfect Mode:** Mode khusus untuk mematikan semua DSP agar output audio 100% murni.
- **Crossfeed (BS2B):** Simulasi binaural untuk mengurangi kelelahan telinga saat memakai headphone.

---

## 🛠️ Instalasi (Termux)

Pastikan kamu sudah menginstall **Termux** dari F-Droid atau GitHub (Jangan dari Play Store karena versinya usang).

### 1. Update System & Install Dependencies
Jalankan perintah ini di terminal Termux:

```bash
pkg update && pkg upgrade -y
pkg install python3 python3-pip ffmpeg mpv git yt-dlp -y
```

### 2. Clone Repository
```bash
git clone https://github.com/st4ngkudut/st4-player.git
cd st4-player
chmod +x play.sh
chmod +x st4player.sh
```

### 3. Install Python Libraries
```bash
pip install -r requirements.txt
```

## 🚀 Cara Menjalankan
### Start Server
Cukup jalankan satu perintah ini:
```bash
bash st4player.sh
```
atau
```bash
python3 app.py
```

---

## 📱 Cara Install (Full Screen App / PWA)

Agar tampilannya full screen tanpa address bar browser:

1. Buka **Chrome** di HP Android  
2. Akses: http://127.0.0.1:5000 di browser
3. Tunggu loading selesai sempurna  
4. Buka **Menu Chrome** (titik tiga di pojok kanan atas)  
5. Pilih **"Add to Home screen"** atau **"Install App"**  
6. Klik **Install**  
7. Cek Home Screen → icon **ST4 Player** siap digunakan 🎉


---

Happy Listening! 🎧  
Built with Python & Love ❤️  


# st4-player-docker
