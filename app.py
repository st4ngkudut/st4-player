from flask import Flask, render_template, request, jsonify
import subprocess
import json
import os
import threading
import time
import socket
import re
import hashlib
import random
import requests
from threading import Lock
from ytmusicapi import YTMusic
# Pastikan library.py sudah ada dan benar
from library import lib_mgr 

app = Flask(__name__)

# ==========================================
# KONFIGURASI PATH (TERMUX FRIENDLY)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IS_ANDROID = "ANDROID_ROOT" in os.environ or os.path.exists("/system/bin/app_process")

# Socket MPV (Penting untuk komunikasi)
if IS_ANDROID:
    MPV_SOCKET = "/data/data/com.termux/files/usr/tmp/mpv_socket"
else:
    MPV_SOCKET = "/tmp/mpv_socket"

# File System
PLAYLIST_FILE = os.path.join(BASE_DIR, "playlist.json")
COVER_DIR = os.path.join(BASE_DIR, "static", "covers")
PLAY_SCRIPT = os.path.join(BASE_DIR, "play.sh")
DEFAULT_PATH_FILE = os.path.join(BASE_DIR, "default_path.txt")
BP_MODE_FILE = os.path.join(BASE_DIR, "state_bp_mode")

# Format Audio
AUDIO_EXTS = ('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.wma', '.aac')

# Globals
state_lock = Lock()
yt_music = YTMusic()
needs_restore = False

# ==========================================
# STATE GLOBAL (STATUS PLAYER)
# ==========================================
st4_state = {
    "title": "Ready", 
    "artist": "Waiting...", 
    "album": "",
    "genre": "", 
    "year": "", 
    "tech_info": "",
    "current_time": 0, 
    "total_time": 0, 
    "status": "stopped",
    "volume": 50, 
    "active_preset": "Normal",
    "thumb": "",
    "queue": [],
    "current_index": -1,
    "sleep_target": 0,
    "current_eq_cmd": "",
    "last_play_time": 0,
    "error_count": 0
}

# State Filter Audio (DSP)
af_state = {
    "eq": "",        # FireEqualizer
    "balance": "",   # Pan Filter
    "crossfeed": ""  # BS2B Filter
}

# ==========================================
# FUNGSI FILTER & DSP
# ==========================================
def is_bp_active():
    """Cek status Bit Perfect"""
    if os.path.exists(BP_MODE_FILE):
        try:
            with open(BP_MODE_FILE, 'r') as f: return f.read().strip() == "1"
        except: pass
    return False

def update_mpv_filters():
    """Update filter audio di MPV"""
    # Jika Bit Perfect aktif, matikan semua filter
    if is_bp_active():
        mpv_send(["set_property", "af", ""]) 
        mpv_send(["set_property", "volume", 100])
        with state_lock: st4_state["volume"] = 100
        return

    # Jika Normal, gabungkan filter
    filters = []
    if af_state["balance"]: filters.append(af_state["balance"])
    if af_state["eq"]: filters.append(af_state["eq"])
    if af_state["crossfeed"]: filters.append(af_state["crossfeed"])
    
    cmd_str = ",".join(filters) if filters else ""
    mpv_send(["set_property", "af", cmd_str])

EQ_PRESETS = {
    "Normal": {"f1":0,"f2":0,"f3":0,"f4":0,"f5":0,"f6":0,"f7":0,"f8":0,"f9":0,"f10":0},
    "Bass":   {"f1":7,"f2":6,"f3":5,"f4":3,"f5":0,"f6":0,"f7":0,"f8":-1,"f9":-2,"f10":-3},
    "Rock":   {"f1":5,"f2":3,"f3":1,"f4":-1,"f5":-2,"f6":0,"f7":2,"f8":4,"f9":5,"f10":5},
    "Pop":    {"f1":-1,"f2":1,"f3":3,"f4":4,"f5":4,"f6":2,"f7":0,"f8":1,"f9":2,"f10":2},
    "Jazz":   {"f1":2,"f2":2,"f3":3,"f4":2,"f5":2,"f6":4,"f7":2,"f8":2,"f9":3,"f10":3},
    "Vocal":  {"f1":-3,"f2":-3,"f3":-2,"f4":0,"f5":4,"f6":6,"f7":5,"f8":3,"f9":1,"f10":-1},
    "Dance":  {"f1":8,"f2":7,"f3":4,"f4":0,"f5":0,"f6":2,"f7":4,"f8":5,"f9":6,"f10":5},
    "Acoust": {"f1":1,"f2":2,"f3":2,"f4":3,"f5":4,"f6":4,"f7":3,"f8":2,"f9":3,"f10":2},
    "Party":  {"f1":7,"f2":6,"f3":4,"f4":1,"f5":2,"f6":4,"f7":5,"f8":5,"f9":6,"f10":5},
    "Soft":   {"f1":0,"f2":-1,"f3":-1,"f4":1,"f5":2,"f6":1,"f7":0,"f8":-1,"f9":-2,"f10":-4},
    "Metal":  {"f1":6,"f2":5,"f3":0,"f4":-2,"f5":-3,"f6":0,"f7":3,"f8":6,"f9":7,"f10":7},
    "Classic":{"f1":4,"f2":3,"f3":2,"f4":2,"f5":-1,"f6":-1,"f7":0,"f8":2,"f9":3,"f10":4},
    "RnB":    {"f1":6,"f2":5,"f3":3,"f4":0,"f5":-1,"f6":2,"f7":3,"f8":2,"f9":3,"f10":4},
    "Live":   {"f1":-2,"f2":0,"f3":2,"f4":3,"f5":4,"f6":4,"f7":4,"f8":3,"f9":2,"f10":1},
    "Techno": {"f1":8,"f2":7,"f3":0,"f4":-2,"f5":-2,"f6":0,"f7":2,"f8":4,"f9":6,"f10":6},
    "KZEDCPro": {"f1":6,"f2":5,"f3":3,"f4":1,"f5":0,"f6":0,"f7":-1,"f8":-1,"f9":0,"f10":0}
}

# ==========================================
# FUNGSI HELPER
# ==========================================

def mpv_send(cmd):
    """Kirim perintah JSON ke socket MPV"""
    if not os.path.exists(MPV_SOCKET): return None
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.2)
        s.connect(MPV_SOCKET)
        s.send((json.dumps({"command": cmd}) + "\n").encode())
        res = s.recv(8192).decode()
        s.close()
        return json.loads(res).get("data")
    except: return None

def get_yt_thumb(url):
    match = re.search(r"([a-zA-Z0-9_-]{11})", url or "")
    if match: return f"https://img.youtube.com/vi/{match.group(1)}/0.jpg"
    return ""

def extract_local_cover(filepath):
    if not filepath or not os.path.exists(filepath): return ""
    try:
        hash_name = hashlib.md5(filepath.encode('utf-8')).hexdigest()
        cover_filename = f"{hash_name}.jpg"
        save_path = os.path.join(COVER_DIR, cover_filename)
        if os.path.exists(save_path): return f"/static/covers/{cover_filename}"
        
        # Jangan ekstrak jika file terlalu kecil (bukan lagu)
        if os.path.getsize(filepath) < 102400: return ""
        
        cmd = ["ffmpeg", "-i", filepath, "-an", "-vcodec", "mjpeg", "-q:v", "2", "-frames:v", "1", "-y", save_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        
        if os.path.exists(save_path): return f"/static/covers/{cover_filename}"
    except: pass
    return ""

def trigger_play(url):
    global needs_restore
    if os.path.exists(PLAY_SCRIPT):
        # Beri izin execute
        os.chmod(PLAY_SCRIPT, 0o755)
        
        with state_lock: 
            st4_state["last_play_time"] = time.time()
            if "http" in url: st4_state["thumb"] = get_yt_thumb(url)
            else: st4_state["thumb"] = ""
            st4_state["status"] = "loading"
        
        needs_restore = True
        subprocess.Popen(["/bin/bash", PLAY_SCRIPT, url])

def play_next_in_queue():
    with state_lock:
        if not st4_state["queue"]: return
        
        time_diff = time.time() - st4_state.get("last_play_time", 0)
        # Proteksi loop error (jika lagu skip terlalu cepat)
        if time_diff < 2.0:
            st4_state["error_count"] += 1
        else:
            st4_state["error_count"] = 0
            
        if st4_state["error_count"] > 5:
            st4_state["status"] = "stopped"
            st4_state["error_count"] = 0
            return

        next_idx = st4_state["current_index"] + 1
        if next_idx < len(st4_state["queue"]):
            st4_state["current_index"] = next_idx
            next_song = st4_state["queue"][next_idx]
            threading.Thread(target=trigger_play, args=(next_song['link'],)).start()
        else:
            st4_state["status"] = "stopped"

def find_key_insensitive(data, search_keys):
    if not data or not isinstance(data, dict): return ""
    for k in search_keys:
        for data_k, data_v in data.items():
            if data_k.lower() == k.lower():
                return data_v
    return ""

# ==========================================
# WORKER UTAMA (METADATA & AUTO PLAY)
# ==========================================
def metadata_worker():
    global st4_state, needs_restore
    last_path = ""
    idle_counter = 0
    
    if not os.path.exists(COVER_DIR): os.makedirs(COVER_DIR, exist_ok=True)
    
    while True:
        try:
            # 1. Sleep Timer Logic
            with state_lock:
                target = st4_state["sleep_target"]
                if target > 0 and time.time() >= target:
                    st4_state["sleep_target"] = 0
                    st4_state["queue"] = []
                    st4_state["current_index"] = -1
                    threading.Thread(target=mpv_send, args=(["stop"],)).start()
            
            # 2. Cek Koneksi MPV
            mpv_ready = False
            try:
                if mpv_send(["get_property", "idle-active"]) is not None:
                    mpv_ready = True
            except: pass

            if mpv_ready:
                idle_counter = 0 
                
                # Restore Settings (Vol & EQ) saat ganti lagu
                path = mpv_send(["get_property", "path"])
                if path and (path != last_path or needs_restore):
                    last_path = path
                    needs_restore = False
                    time.sleep(0.5)
                    with state_lock: saved_vol = st4_state["volume"]
                    mpv_send(["set_property", "volume", saved_vol])
                    update_mpv_filters()

                # Logic Auto Play Next
                is_eof = mpv_send(["get_property", "eof-reached"])
                is_idle = mpv_send(["get_property", "idle-active"])
                
                if is_eof is True or (is_idle is True and st4_state["status"] == "playing"):
                    play_next_in_queue()
                    time.sleep(1)
                    continue

                # Ambil Metadata Thumbnail
                final_thumb = ""
                with state_lock:
                    if st4_state["queue"] and st4_state["current_index"] < len(st4_state["queue"]):
                        final_thumb = st4_state["queue"][st4_state["current_index"]].get('thumb', '')
                
                if not final_thumb:
                    if path and "http" in path: 
                        if "googlevideo" not in path: final_thumb = get_yt_thumb(path)
                    else:
                        loc = extract_local_cover(path)
                        if loc: final_thumb = loc
                with state_lock: st4_state["thumb"] = final_thumb

                # Ambil Metadata Audio Tags
                meta_all = mpv_send(["get_property", "metadata"]) or {}
                mpv_title = mpv_send(["get_property", "media-title"])
                
                queue_title = "Unknown Title"
                with state_lock:
                    if st4_state["queue"] and st4_state["current_index"] < len(st4_state["queue"]):
                        queue_title = st4_state["queue"][st4_state["current_index"]]['title']
                
                final_title = queue_title 
                if mpv_title:
                    is_junk = any(x in mpv_title.lower() for x in ["http", "www.", ".com", "webm&", "googlevideo", "?source"])
                    if not is_junk: final_title = mpv_title
                
                temp_artist = find_key_insensitive(meta_all, ["artist", "performer", "composer"]) or "Unknown Artist"
                temp_album = find_key_insensitive(meta_all, ["album"]) or ""
                temp_genre = find_key_insensitive(meta_all, ["genre"])
                temp_year = find_key_insensitive(meta_all, ["date", "year", "original_date"])

                # --- TECH SPECS (CODEC INFO) ---
                tech_display = []
                raw_codec = mpv_send(["get_property", "audio-codec-name"])
                raw_fmt = mpv_send(["get_property", "audio-params/format"])
                raw_rate = mpv_send(["get_property", "audio-params/samplerate"])
                raw_br = mpv_send(["get_property", "audio-bitrate"])
                
                codec_str = raw_codec.upper() if raw_codec else "UNK"
                tech_display.append(codec_str)

                # Bitrate
                if raw_br and int(raw_br) > 0:
                    tech_display.append(f"{int(int(raw_br)/1000)}kbps")
                
                # Sample Rate
                sample_rate_val = 0
                if raw_rate:
                    try:
                        sample_rate_val = float(raw_rate)
                        tech_display.append(f"{sample_rate_val/1000:g}kHz")
                    except: pass

                # Bit Depth
                bit_depth = ""
                if raw_fmt:
                    if 's16' in raw_fmt: bit_depth = "16bit"
                    elif 's24' in raw_fmt: bit_depth = "24bit"
                    elif 's32' in raw_fmt or 'float' in raw_fmt: bit_depth = "32bit"
                    elif 'dsd' in raw_fmt: bit_depth = "1bit(DSD)"
                
                lossy_list = ['MP3', 'AAC', 'VORBIS', 'OPUS', 'WEBM', 'M4A']
                is_lossy = any(x in codec_str for x in lossy_list)
                if not is_lossy and bit_depth:
                    tech_display.append(bit_depth)

                # Badge
                badge = "Lossless"
                if is_lossy: badge = "Lossy"
                elif (bit_depth in ["24bit", "32bit"]) or (sample_rate_val > 48000):
                    badge = "Hi-Res"
                
                tech_display.append(badge)
                temp_info = " • ".join(tech_display)
                
                is_paused = mpv_send(["get_property", "pause"])
                temp_status = "paused" if is_paused else "playing"

                with state_lock:
                    st4_state.update({
                        "title": final_title,
                        "artist": temp_artist, "album": temp_album,
                        "genre": temp_genre, "year": temp_year,
                        "status": temp_status,
                        "tech_info": temp_info,
                        "current_time": mpv_send(["get_property", "time-pos"]) or 0,
                        "total_time": mpv_send(["get_property", "duration"]) or 0
                    })
                    val_vol = mpv_send(["get_property", "volume"])
                    if val_vol is not None: st4_state["volume"] = val_vol
            else:
                idle_counter += 1
                if idle_counter == 5:
                    with state_lock: st4_state["status"] = "stopped"
                if idle_counter == 15 and st4_state["status"] != "stopped":
                    play_next_in_queue()
                    
        except Exception as e: pass
        time.sleep(1)
        
threading.Thread(target=metadata_worker, daemon=True).start()

# ==========================================
# FLASK ROUTES
# ==========================================

@app.route('/')
def index(): return render_template('index.html')

@app.route('/status')
def status():
    with state_lock:
        resp = st4_state.copy()
        # Format Timer Display
        target = resp.get("sleep_target", 0)
        if target > 0:
            remaining = int(target - time.time())
            if remaining > 0:
                resp["timer_display"] = f"{int(remaining/60)+1}m"
                resp["timer_active"] = True
            else:
                resp["timer_display"] = "OFF"
                resp["timer_active"] = False
        else:
            resp["timer_display"] = "OFF"
            resp["timer_active"] = False
        return jsonify(resp)

# --- ROUTES PLAYBACK CONTROL ---
@app.route('/play', methods=['GET', 'POST'])
def play():
    url = request.args.get('url') or request.form.get('link')
    mode = request.args.get('mode', 'play_now')
    title = request.args.get('title', 'Unknown Title')
    if not url: return jsonify({"error": "no url"})
    song_obj = {'link': url, 'title': title}
    
    with state_lock:
        if mode == 'play_now':
            # Jika play folder/file lokal
            if os.path.exists(url) and os.path.isfile(url):
                try:
                    folder_path = os.path.dirname(url)
                    folder_files = [f for f in os.listdir(folder_path) if f.lower().endswith(AUDIO_EXTS)]
                    folder_files.sort(key=lambda x: x.lower())
                    new_queue = []
                    target_index = 0
                    for idx, fname in enumerate(folder_files):
                        full_path = os.path.join(folder_path, fname)
                        new_queue.append({'link': full_path, 'title': fname})
                        if full_path == url: target_index = idx
                    st4_state["queue"] = new_queue
                    st4_state["current_index"] = target_index
                except:
                    st4_state["queue"] = [song_obj]; st4_state["current_index"] = 0
            
            # Jika play YouTube
            elif "youtube.com" in url or "youtu.be" in url:
                st4_state["queue"] = [song_obj]; st4_state["current_index"] = 0
                try:
                    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
                    video_id = match.group(1) if match else None
                    if video_id:
                        data = yt_music.get_watch_playlist(videoId=video_id, limit=20)
                        if 'tracks' in data:
                            new_queue = []
                            for t in data['tracks']:
                                vid = t.get('videoId')
                                if vid:
                                    t_artist = t['artists'][0]['name'] if 'artists' in t and t['artists'] else ""
                                    full_title = f"{t_artist} - {t['title']}" if t_artist else t['title']
                                    new_queue.append({'link': f"https://music.youtube.com/watch?v={vid}", 'title': full_title})
                            if new_queue: st4_state["queue"] = new_queue; st4_state["current_index"] = 0
                except: pass
            else:
                st4_state["queue"] = [song_obj]; st4_state["current_index"] = 0
            
            st4_state["error_count"] = 0
            threading.Thread(target=trigger_play, args=(url,)).start()
        elif mode == 'enqueue':
            st4_state["queue"].append(song_obj)
            if st4_state["status"] == "stopped" and len(st4_state["queue"]) == 1:
                st4_state["current_index"] = 0
                threading.Thread(target=trigger_play, args=(url,)).start()
    return jsonify({"status": "ok", "mode": mode, "queue_len": len(st4_state["queue"])})

@app.route('/control/<action>')
def control(action):
    if action == "pause": mpv_send(["cycle", "pause"])
    elif action == "stop":
        mpv_send(["stop"])
        with state_lock: st4_state["status"] = "stopped"
    elif action == "next": play_next_in_queue()
    elif action == "prev":
        with state_lock:
            if st4_state["current_index"] > 0:
                st4_state["current_index"] -= 1
                prev_song = st4_state["queue"][st4_state["current_index"]]
                trigger_play(prev_song['link'])
            else: mpv_send(["seek", 0, "absolute"])
    elif action == "shuffle":
        with state_lock:
            if len(st4_state["queue"]) > 1:
                current_song = st4_state["queue"][st4_state["current_index"]]
                random.shuffle(st4_state["queue"])
                for idx, song in enumerate(st4_state["queue"]):
                    if song['link'] == current_song['link']:
                        st4_state["current_index"] = idx; break
        return jsonify({"status": "shuffled"})
    elif action == "volume":
        try: 
            v = int(request.args.get('val', 50))
            mpv_send(["set_property", "volume", v])
            with state_lock: st4_state["volume"] = v
        except: pass
    elif action == "seek":
        try: mpv_send(["seek", float(request.args.get('val', 0)), "absolute-percent"])
        except: pass
    return jsonify({"status": "ok"})

@app.route('/control/jump')
def jump_to_index():
    try:
        idx = int(request.args.get('index', -1))
        with state_lock:
            if 0 <= idx < len(st4_state["queue"]):
                st4_state["current_index"] = idx
                song = st4_state["queue"][idx]
                st4_state["error_count"] = 0 
                threading.Thread(target=trigger_play, args=(song['link'],)).start()
                return jsonify({"status": "ok", "title": song['title']})
    except: pass
    return jsonify({"error": "invalid index"})

# --- EQ & SOUND CONTROL ---
def generate_fireq_cmd(gains_dict):
    freqs = [32, 64, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    entries = []
    for i in range(1, 11):
        try: val = float(gains_dict.get(f'f{i}', 0))
        except: val = 0.0
        entries.append(f"entry({freqs[i-1]},{val})")
    
    entry_str = ";".join(entries)
    return f"firequalizer=gain_entry='{entry_str}'"

@app.route('/control/eq')
def set_eq():
    p = request.args
    gains = {}
    for i in range(1, 11):
        gains[f'f{i}'] = p.get(f'f{i}', 0)
    cmd_str = generate_fireq_cmd(gains)
    af_state["eq"] = f"lavfi=[{cmd_str}]"
    update_mpv_filters()
    with state_lock: st4_state["current_eq_cmd"] = af_state["eq"]
    return jsonify({"status": "ok"})

@app.route('/control/preset')
def set_preset():
    n = request.args.get('name')
    if n in EQ_PRESETS:
        preset = EQ_PRESETS[n]
        cmd_str = generate_fireq_cmd(preset)
        af_state["eq"] = f"lavfi=[{cmd_str}]"
        update_mpv_filters()
        with state_lock: 
            st4_state["active_preset"] = n
            st4_state["current_eq_cmd"] = af_state["eq"]
        return jsonify(preset)
    return jsonify({"error": "not found"}), 404

@app.route('/control/bitperfect')
def toggle_bitperfect():
    current = "0"
    if os.path.exists(BP_MODE_FILE):
        with open(BP_MODE_FILE, 'r') as f: current = f.read().strip()
    
    new_state = "1" if current == "0" else "0"
    with open(BP_MODE_FILE, 'w') as f: f.write(new_state)
    
    update_mpv_filters()
    
    if new_state == "0":
        mpv_send(["set_property", "volume", 50])
        with state_lock: st4_state["volume"] = 50

    return jsonify({"status": "ok", "bitperfect": new_state == "1"})

@app.route('/get_bitperfect')
def get_bitperfect():
    active = False
    if os.path.exists(BP_MODE_FILE):
        with open(BP_MODE_FILE, 'r') as f: active = f.read().strip() == "1"
    return jsonify({"active": active})

@app.route('/control/crossfeed')
def toggle_crossfeed():
    state = request.args.get('state', 'on')
    af_state["crossfeed"] = "lavfi=[bs2b=profile=cmoy]" if state == 'on' else ""
    update_mpv_filters()
    return jsonify({"status": "ok", "crossfeed": state == 'on'})

@app.route('/get_crossfeed')
def get_crossfeed():
    return jsonify({"active": len(af_state["crossfeed"]) > 0})

@app.route('/control/balance')
def set_balance():
    try:
        l_vol = float(request.args.get('l', 1.0))
        r_vol = float(request.args.get('r', 1.0))
    except:
        l_vol = 1.0; r_vol = 1.0

    pan_cmd = f"pan=stereo|c0={l_vol:.2f}*c0|c1={r_vol:.2f}*c1"
    
    if l_vol >= 0.99 and r_vol >= 0.99:
        af_state["balance"] = ""
    else:
        af_state["balance"] = f"lavfi=[{pan_cmd}]"
    
    update_mpv_filters()
    return jsonify({"status": "ok", "L": l_vol, "R": r_vol})

# --- SYSTEM UTILS ---
@app.route('/system/default_path', methods=['GET', 'POST'])
def handle_default_path():
    if request.method == 'POST':
        try:
            data = request.json; new_path = data.get('path', '/root')
            if os.path.exists(new_path):
                with open(DEFAULT_PATH_FILE, 'w') as f: f.write(new_path)
                return jsonify({"status": "ok", "path": new_path})
            else: return jsonify({"error": "Path not found"}), 404
        except Exception as e: return jsonify({"error": str(e)}), 500
    else:
        path = "/root/music"
        if os.path.exists(DEFAULT_PATH_FILE):
            try:
                with open(DEFAULT_PATH_FILE, 'r') as f: path = f.read().strip()
            except: pass
        return jsonify({"path": path})

@app.route('/system/timer')
def set_timer():
    try: minutes = int(request.args.get('min', 0))
    except: minutes = 0
    with state_lock: st4_state["sleep_target"] = (time.time() + minutes*60) if minutes > 0 else 0
    return jsonify({"status": "ok", "timer": minutes})

# --- QUEUE & PLAYLIST ---
@app.route('/queue/list')
def get_queue():
    with state_lock: return jsonify({"queue": st4_state["queue"], "current_index": st4_state["current_index"]})

@app.route('/queue/clear')
def clear_queue():
    with state_lock: st4_state["queue"] = []; st4_state["current_index"] = -1
    return jsonify({"status": "cleared"})

@app.route('/get_playlist')
def get_playlist():
    if os.path.exists(PLAYLIST_FILE):
        try:
            with open(PLAYLIST_FILE, 'r') as f: return jsonify(json.load(f))
        except: pass
    return jsonify([])

@app.route('/save_playlist', methods=['POST'])
def save_playlist():
    try:
        with open(PLAYLIST_FILE, 'w') as f: json.dump(request.json, f)
        return jsonify({"status": "ok"})
    except: return jsonify({"error": "failed"}), 500

# --- LIBRARY & FILES ---
@app.route('/get_files')
def get_files():
    target = request.args.get('path', '/')
    items = []
    try:
        if not os.path.exists(target): target = '/'
        abs_path = os.path.abspath(target)
        if abs_path != '/' and abs_path != os.path.dirname(abs_path):
            items.append({'name': '..', 'path': os.path.dirname(abs_path), 'type': 'dir'})
        with os.scandir(abs_path) as entries:
            for entry in entries:
                if entry.name.startswith('.'): continue
                if entry.is_dir(): items.append({'name': entry.name, 'path': entry.path, 'type': 'dir'})
                elif entry.is_file() and entry.name.lower().endswith(AUDIO_EXTS):
                    items.append({'name': entry.name, 'path': entry.path, 'type': 'file'})
    except: return jsonify([])
    items.sort(key=lambda x: (x['type'] != 'dir', x['name'].lower()))
    return jsonify(items)

@app.route('/library/scan')
def scan_library():
    scan_path = "/storage/emulated/0/"
    if os.path.exists(DEFAULT_PATH_FILE):
        try:
            with open(DEFAULT_PATH_FILE, 'r') as f: scan_path = f.read().strip()
        except: pass
    
    lib_mgr.scan_directory(scan_path)
    return jsonify({"status": "started", "path": scan_path})

@app.route('/library/status')
def library_status():
    return jsonify(lib_mgr.get_scan_status())

@app.route('/library/tracks')
def library_tracks():
    sort_mode = request.args.get('sort', 'title')
    tracks = lib_mgr.get_all_tracks(sort_mode)
    
    formatted = []
    for t in tracks:
        formatted.append({
            'name': t['title'], 
            'path': t['path'], 
            'type': 'file',
            'artist': t['artist'],
            'album': t['album'],
            'meta': f"{t['artist']} - {t['album']}"
        })
    return jsonify(formatted)

@app.route('/search')
def search_yt():
    query = request.args.get('q', '')
    if not query: return jsonify([])
    try:
        results = yt_music.search(query, filter="songs", limit=15)
        data = []
        for r in results:
            thumb = r['thumbnails'][-1]['url'] if 'thumbnails' in r else ""
            artists = ", ".join([a['name'] for a in r.get('artists', [])])
            data.append({'title': r.get('title'), 'artist': artists, 'duration': r.get('duration',''), 'thumb': thumb, 'link': f"https://music.youtube.com/watch?v={r['videoId']}", 'videoId': r['videoId']})
        return jsonify(data)
    except: return jsonify([])

@app.route('/get_lyrics')
def get_lyrics():
    with state_lock:
        artist = st4_state.get("artist", "")
        title = st4_state.get("title", "")
    
    if not artist or not title or artist == "Unknown Artist":
        return jsonify({"error": "No track info"})

    # Bersihkan nama agar pencarian lebih akurat
    clean_title = re.sub(r"\(.*?\)|\[.*?\]", "", title).strip()
    
    try:
        url = "https://lrclib.net/api/get"
        params = { "artist_name": artist, "track_name": clean_title }
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        
        if 'syncedLyrics' in data and data['syncedLyrics']:
            return jsonify({"type": "synced", "lyrics": data['syncedLyrics']})
        elif 'plainLyrics' in data and data['plainLyrics']:
            return jsonify({"type": "plain", "lyrics": data['plainLyrics']})
        else:
            return jsonify({"error": "Not found"})
    except Exception as e:
        return jsonify({"error": str(e)})

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

if __name__ == '__main__':
    local_ip = get_ip()
    print("\n" + "="*40)
    print(f"  ST4 PLAYER IS RUNNING! 🚀")
    print(f"  Access from this device: http://127.0.0.1:5000")
    print(f"  Access from PC/Laptop:   http://{local_ip}:5000")
    print("="*40 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)