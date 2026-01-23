import os
import time
from library import lib_mgr

# ==========================================
# KONFIGURASI MANUAL
# ==========================================
# Ganti path ini sesuai tempat lagumu di Android
# Path umum di Android: "/storage/emulated/0/Music"
# Path di Termux (jika sudah setup-storage): "/data/data/com.termux/files/home/storage/music"

TARGET_PATH = "/storage/emulated/0/Music" 

# ==========================================
# DIAGNOSTIC TOOL
# ==========================================

def cek_manual():
    print(f"\n--- 1. CEK PATH: {TARGET_PATH} ---")
    
    if not os.path.exists(TARGET_PATH):
        print(f"[X] GAGAL: Folder tidak ditemukan!")
        print("    Pastikan path benar dan izin storage sudah aktif.")
        print("    Coba jalankan: termux-setup-storage")
        return

    print("[OK] Folder ditemukan.")
    
    print("\n--- 2. CEK ISI FOLDER (OS LISTDIR) ---")
    try:
        files = os.listdir(TARGET_PATH)
        print(f"Total file/folder di root: {len(files)}")
        audio_files = [f for f in files if f.endswith(('.mp3', '.flac', '.m4a'))]
        print(f"File audio di root folder: {len(audio_files)}")
        if len(audio_files) > 0:
            print(f"Contoh file: {audio_files[0]}")
        else:
            print("Warning: Tidak ada file musik langsung di folder ini (mungkin ada di subfolder?)")
    except Exception as e:
        print(f"[X] ERROR BACA FOLDER: {e}")
        return

    print("\n--- 3. TEST SCANNING LIBRARY ---")
    print("Memulai proses scan database...")
    
    # Reset DB biar bersih
    lib_mgr.init_db() 
    
    # Jalankan Scan
    lib_mgr.scan_directory(TARGET_PATH)
    
    # Monitoring Loop (Biar kelihatan progressnya)
    while lib_mgr.scanning:
        status = lib_mgr.get_scan_status()
        print(f"Status: {status['message']} ({status['progress']}%)", end='\r')
        time.sleep(0.5)
    
    print("\n\n--- 4. HASIL AKHIR ---")
    tracks = lib_mgr.get_all_tracks()
    print(f"Total Lagu di Database: {len(tracks)}")
    
    if len(tracks) > 0:
        print("\n5 Lagu Teratas:")
        for i, t in enumerate(tracks[:5]):
            print(f"{i+1}. {t['title']} - {t['artist']} ({t['path']})")
    else:
        print("[X] HASIL KOSONG! Cek apakah file audio benar-benar ada dan ekstensinya didukung.")

if __name__ == "__main__":
    try:
        # Input path manual biar fleksibel
        print("Masukkan path folder musik (Tekan Enter untuk default: /storage/emulated/0/Music)")
        user_path = input("Path: ").strip()
        if user_path:
            TARGET_PATH = user_path
            
        cek_manual()
    except KeyboardInterrupt:
        print("\nDibatalkan.")