import sqlite3
import os
import threading
import time
import traceback

try:
    from mutagen import File as MutagenFile
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False
    print("WARNING: 'mutagen' not installed.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "music.db")
AUDIO_EXTS = ('.mp3', '.flac', '.wav', '.m4a', '.ogg', '.opus', '.wma', '.aac')

class LibraryManager:
    def __init__(self):
        self.scanning = False
        self.total_files = 0
        self.scanned_files = 0
        self.status_msg = "Idle"
        self.scan_thread = None
        self.init_db()

    def get_db_connection(self):
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        try:
            conn = self.get_db_connection()
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS tracks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        path TEXT UNIQUE,
                        filename TEXT,
                        title TEXT,
                        artist TEXT,
                        album TEXT,
                        genre TEXT,
                        year TEXT,
                        duration INTEGER,
                        added_at REAL
                    )''')
            c.execute('CREATE INDEX IF NOT EXISTS idx_artist ON tracks(artist)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_title ON tracks(title)')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"DB INIT ERROR: {e}")

    def get_metadata(self, filepath):
        filename = os.path.basename(filepath)
        meta = {'title': filename, 'artist': 'Unknown Artist', 'album': 'Unknown Album',
                'genre': 'Unknown', 'year': '', 'duration': 0}

        if not HAS_MUTAGEN: return meta

        try:
            audio = MutagenFile(filepath, easy=True)
            if audio:
                meta['title'] = audio.get('title', [filename])[0]
                meta['artist'] = audio.get('artist', ['Unknown Artist'])[0]
                meta['album'] = audio.get('album', ['Unknown Album'])[0]
                meta['genre'] = audio.get('genre', ['Unknown'])[0]
                date = audio.get('date', [''])[0] or audio.get('year', [''])[0]
                meta['year'] = str(date).split('-')[0] if date else ''
                if hasattr(audio, 'info') and audio.info:
                    meta['duration'] = int(audio.info.length)
        except: pass
        return meta

    def scan_directory(self, root_path):
        if self.scanning: return
        self.scanning = True
        self.status_msg = "Starting..."
        self.scan_thread = threading.Thread(target=self._worker, args=(root_path,))
        self.scan_thread.daemon = True
        self.scan_thread.start()

    def _worker(self, root_path):
        print(f"[Library] Scanning: {root_path}")
        start_time = time.time()
        
        try:
            conn = self.get_db_connection()
            c = conn.cursor()
            
            self.status_msg = "Listing files..."
            audio_files = []
            for root, dirs, files in os.walk(root_path):
                for f in files:
                    if f.lower().endswith(AUDIO_EXTS):
                        audio_files.append(os.path.join(root, f))
            
            self.total_files = len(audio_files)
            self.scanned_files = 0
            
            c.execute('BEGIN TRANSACTION')
            
            for filepath in audio_files:
                try:
                    m = self.get_metadata(filepath)
                    c.execute('''INSERT OR REPLACE INTO tracks 
                        (path, filename, title, artist, album, genre, year, duration, added_at) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                        (filepath, os.path.basename(filepath), 
                         m['title'], m['artist'], m['album'], m['genre'], m['year'], m['duration'], 
                         time.time()))
                    
                    self.scanned_files += 1
                    if self.scanned_files % 50 == 0:
                        self.status_msg = f"Processing {self.scanned_files}/{self.total_files}"
                except Exception as e:
                    print(f"[Skip] Error on {filepath}: {e}")
            
            self.status_msg = "Cleaning up..."
            c.execute("SELECT path FROM tracks")
            db_paths = set(row['path'] for row in c.fetchall())
            scan_paths = set(audio_files)
            deleted_files = db_paths - scan_paths
            
            if deleted_files:
                for trash in deleted_files:
                    c.execute("DELETE FROM tracks WHERE path = ?", (trash,))
                print(f"[Library] Removed {len(deleted_files)} ghost files.")

            conn.commit()
            conn.close()
            
            elapsed = time.time() - start_time
            self.status_msg = f"Done. {self.total_files} tracks in {elapsed:.1f}s"
            print(self.status_msg)
            
        except Exception as e:
            self.status_msg = f"Error: {str(e)}"
            traceback.print_exc()
        finally:
            self.scanning = False

    def get_all_tracks(self, sort_by='title'):
        try:
            conn = self.get_db_connection()
            c = conn.cursor()
            
            order_sql = "title ASC"
            if sort_by == 'artist': order_sql = "artist ASC, album ASC, title ASC"
            elif sort_by == 'album': order_sql = "album ASC, artist ASC"
            elif sort_by == 'newest': order_sql = "added_at DESC"

            # Limit dihapus, load semua
            c.execute(f"SELECT * FROM tracks ORDER BY {order_sql}")
            rows = [dict(row) for row in c.fetchall()]
            conn.close()
            return rows
        except Exception as e:
            print(f"Get Tracks Error: {e}")
            return []

    def search_tracks(self, query):
        try:
            conn = self.get_db_connection()
            c = conn.cursor()
            wildcard = f"%{query}%"
            c.execute("""SELECT * FROM tracks 
                         WHERE title LIKE ? OR artist LIKE ? OR album LIKE ? 
                         ORDER BY title ASC LIMIT 50""", (wildcard, wildcard, wildcard))
            rows = [dict(row) for row in c.fetchall()]
            conn.close()
            return rows
        except: return []

    def get_scan_status(self):
        progress = 0
        if self.total_files > 0:
            progress = int((self.scanned_files / self.total_files) * 100)
        return {
            "scanning": self.scanning, "progress": progress,
            "message": self.status_msg, "total": self.total_files
        }

lib_mgr = LibraryManager()