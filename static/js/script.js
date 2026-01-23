// =========================================
// ST4 PLAYER - CORE LOGIC (FINAL)
// =========================================

let currentScanPath = ''; 
let isSeeking = false;
let currentLyricIndex = -1; 
let lastFrameTime = performance.now(); 

let activeKnob = null;
let activeKnobRect = null; 

let volTimer = null;
let eqTimer = null;
let balTimeout = null;

let lyricsData = [];
let lyricsType = ''; 
let lastLyricsTitle = '';
let globalTime = 0;      
let isPlaying = false;   
let totalDuration = 0;   

let settings;
try {
    settings = JSON.parse(localStorage.getItem('st4_set')) || getDefaultSettings();
} catch (e) {
    settings = getDefaultSettings();
}

function getDefaultSettings() {
    return { f1:0,f2:0,f3:0,f4:0,f5:0,f6:0,f7:0,f8:0,f9:0,f10:0, vol:50, active_preset: 'Normal' };
}

window.onload = () => {
    updateUI(); 
    setupKnobs(); 
    checkBitPerfect(); 
    checkCrossfeed();
    initPath();
    
    const pb = document.getElementById('pb');
    if(pb) {
        pb.addEventListener('mousedown', () => isSeeking = true);
        pb.addEventListener('touchstart', () => isSeeking = true, {passive:true});
        pb.addEventListener('change', (e) => {
            isSeeking = false;
            const seekPct = parseFloat(e.target.value);
            const seekTime = (seekPct / 100) * totalDuration;
            globalTime = seekTime; 
            fetch('/control/seek?val=' + seekPct);
        });
        pb.addEventListener('mouseup', () => isSeeking = false);
        pb.addEventListener('touchend', () => isSeeking = false);
    }
    
    if(localStorage.getItem('st4_theme') === 'light') {
        document.body.classList.add('light-theme');
    }
    
    startSmoothEngine();
};

function startSmoothEngine() {
    const loop = (now) => {
        const dt = (now - lastFrameTime) / 1000;
        lastFrameTime = now;

        if(isPlaying && !isSeeking) {
            globalTime += dt; 
            syncLyrics(globalTime);
            updateProgressBarSmooth();
        }
        
        requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
}

function updateProgressBarSmooth() {
    if(!isSeeking && totalDuration > 0) {
        const pb = document.getElementById('pb');
        if(pb) {
            pb.value = (globalTime / totalDuration) * 100;
            setTextSafe('t-cur', fmtTime(globalTime));
        }
    }
}

function toggleQuickMenu() {
    const menu = document.getElementById('quick-menu');
    const btn = document.getElementById('btn-main-menu');
    
    if (menu.classList.contains('active')) {
        menu.classList.remove('active');
        btn.classList.remove('active-state');
    } else {
        menu.classList.add('active');
        btn.classList.add('active-state');
        
        setTimeout(() => {
            const closeMenu = (e) => {
                if (!menu.contains(e.target) && !btn.contains(e.target)) {
                    menu.classList.remove('active');
                    btn.classList.remove('active-state');
                    document.removeEventListener('click', closeMenu);
                }
            };
            document.addEventListener('click', closeMenu);
        }, 100);
    }
}

async function playSong(url, mode = 'play_now', title = '') {
    const encodedUrl = encodeURIComponent(url);
    const encodedTitle = encodeURIComponent(title);
    try {
        const r = await fetch(`/play?url=${encodedUrl}&mode=${mode}&title=${encodedTitle}`);
        const data = await r.json();

        if (mode === 'play_now') {
            document.body.classList.add('playing');
            showToast(`Playing: ${title || 'Track'}`);
            isPlaying = true;
        } else {
            showToast(`Added to Queue (${data.queue_len})`);
        }
        if(document.getElementById('tab-queue').classList.contains('active')) loadQueue();
    } catch (e) {
        showToast("Error Playing Track");
    }
}

function ctl(action) {
    if(action === 'pause') {
        const btnIcon = document.getElementById('pi');
        if(isPlaying) {
            isPlaying = false;
            btnIcon.className = "fa-solid fa-play";
            document.body.classList.remove('playing');
        } else {
            isPlaying = true;
            btnIcon.className = "fa-solid fa-pause";
            document.body.classList.add('playing');
        }
    }

    fetch(`/control/${action}`)
        .then(r => r.json())
        .then(d => {
            if(action === 'stop') {
                globalTime = 0;
                isPlaying = false;
                setTextSafe('t-cur', "0:00");
                const pb = document.getElementById('pb');
                if(pb) pb.value = 0;
            } else if(action === 'shuffle') {
                showToast("Queue Shuffled");
                loadQueue();
            } else if(action === 'loop') {
                showToast("Loop Toggled");
            }
        });
}

setInterval(() => {
    fetch('/status')
        .then(r => r.json())
        .then(d => {
            setTextSafe('tit', d.title || "Ready");
            setTextSafe('art', d.artist || "ST4 Player");
            
            if (Math.abs(globalTime - d.current_time) > 0.5) {
                globalTime = d.current_time;
            }
            totalDuration = d.total_time;
            setTextSafe('t-tot', fmtTime(d.total_time));

            const alb = document.getElementById('alb');
            if(alb) {
                alb.textContent = d.album || "";
                alb.style.display = d.album ? 'block' : 'none';
            }

            const gn = document.getElementById('genre');
            if(gn) {
                gn.textContent = d.genre || "";
                gn.style.display = d.genre ? 'inline-block' : 'none';
            }

            const yr = document.getElementById('year');
            if(yr) {
                yr.textContent = d.year || "";
                yr.style.display = d.year ? 'inline-block' : 'none';
            }

            setTextSafe('tech-specs', d.tech_info || "WAITING SIGNAL...");

            const btnIcon = document.getElementById('pi');
            const vinylImg = document.getElementById('cover-img');
            
            if(d.status === 'playing') {
                isPlaying = true;
                if(btnIcon) btnIcon.className = "fa-solid fa-pause";
                document.body.classList.add('playing');
                if(vinylImg) vinylImg.classList.add('spinning');
            } else {
                isPlaying = false;
                if(btnIcon) btnIcon.className = "fa-solid fa-play";
                document.body.classList.remove('playing');
                if(vinylImg) vinylImg.classList.remove('spinning');
            }

            if(vinylImg) {
                if(d.thumb && vinylImg.src !== d.thumb) {
                    vinylImg.src = d.thumb;
                } else if (!d.thumb && !vinylImg.src.includes('default.png')) {
                    vinylImg.src = '/static/img/default.png';
                }
            }

            const badge = document.getElementById('timer-badge');
            const btnTimer = document.getElementById('btn-timer');
            if(badge && btnTimer) {
                if(d.timer_active) {
                    badge.textContent = d.timer_display;
                    badge.style.display = 'block';
                    btnTimer.classList.add('active-state');
                } else {
                    badge.style.display = 'none';
                    btnTimer.classList.remove('active-state');
                }
            }
            
            const xfDot = document.getElementById('xf-indicator');
            if(xfDot) xfDot.style.display = (d.status_crossfeed === 'on' || d.crossfeed_active) ? 'block' : 'none';
            
            const bpDot = document.getElementById('bp-indicator');
            if(bpDot) bpDot.style.display = (d.bitperfect_active) ? 'block' : 'none';

        })
        .catch(() => {});
}, 1000);

function toggleLyrics() {
    tg('lym'); 
    setTimeout(() => {
        if (document.getElementById('lym').classList.contains('active')) {
            const currentTitle = document.getElementById('tit').innerText;
            const cont = document.getElementById('lyrics-container');
            if (currentTitle !== lastLyricsTitle || cont.innerText.length < 50) {
                fetchLyrics();
            }
        }
    }, 100);
}

function fetchLyrics() {
    const cont = document.getElementById('lyrics-container');
    const title = document.getElementById('tit').innerText;

    cont.innerHTML = `
        <div style="margin-top:20px;">
            <i class="fa-solid fa-compact-disc fa-spin" style="font-size:2rem; color:var(--primary);"></i>
            <p style="margin-top:15px; color:#ccc;">Searching for:<br>
            <span style="color:#fff; font-weight:bold;">${title}</span></p>
        </div>`;
    
    if (title === "Ready" || title === "ST4 Player") {
        cont.innerHTML = '<div style="margin-top:50px;">Play music to see lyrics</div>';
        return;
    }

    fetch('/get_lyrics')
        .then(r => r.json())
        .then(d => {
            lastLyricsTitle = title;
            lyricsData = [];
            
            if (d.error) {
                cont.innerHTML = `
                    <div style="margin-top:50px; color:#888;">
                        Lyrics not found.<br>
                        <button onclick="fetchLyrics()" class="btn-preset-compact" style="margin-top:20px; background:rgba(255,255,255,0.1);">Retry</button>
                    </div>`;
                return;
            }

            lyricsType = d.type;
            if (d.type === 'synced') {
                parseLRC(d.lyrics);
                renderLyrics();
                syncLyrics(globalTime);
            } else {
                cont.innerHTML = '';
                const safeDiv = document.createElement('div');
                safeDiv.style.cssText = "white-space: pre-wrap; line-height: 1.8; color:#eee; font-size:1.1rem; padding: 20px 10px 100px;";
                safeDiv.innerText = d.lyrics;
                cont.appendChild(safeDiv);
            }
        })
        .catch(() => {
            cont.innerHTML = '<div style="margin-top:50px; color:red;">Connection Error</div>';
        });
}

function parseLRC(lrcText) {
    const lines = lrcText.split('\n');
    const regex = /^\[(\d{2}):(\d{2}\.\d{2})\](.*)/;
    lyricsData = [];
    lines.forEach(line => {
        const match = line.match(regex);
        if (match) {
            const min = parseInt(match[1]);
            const sec = parseFloat(match[2]);
            const text = match[3].trim();
            if (text) {
                lyricsData.push({ time: min * 60 + sec, text: text });
            }
        }
    });
}

function renderLyrics() {
    const cont = document.getElementById('lyrics-container');
    cont.innerHTML = '';
    currentLyricIndex = -1;
    lyricsData.forEach((line, index) => {
        const div = document.createElement('div');
        div.className = 'lyric-line';
        div.id = `line-${index}`;
        div.innerText = line.text;
        div.onclick = () => { fetch('/control/seek?val=' + ((line.time / totalDuration) * 100));
            globalTime = line.time; };
        cont.appendChild(div);
    });
}

function syncLyrics(currentTime) {
    const cont = document.getElementById('lyrics-container');
    if (!document.getElementById('lym').classList.contains('active')) return;
    if (lyricsType !== 'synced' || lyricsData.length === 0) return;

    let activeIndex = -1;
    for (let i = lyricsData.length - 1; i >= 0; i--) {
        if (currentTime >= lyricsData[i].time) {
            activeIndex = i;
            break;
        }
    }

    if (activeIndex !== currentLyricIndex) {
        const prevLine = document.getElementById(`line-${currentLyricIndex}`);
        if(prevLine) {
            prevLine.classList.remove('active');
            prevLine.style.transform = "scale(1)";
        }

        currentLyricIndex = activeIndex;
        
        const activeLine = document.getElementById(`line-${activeIndex}`);
        if (activeLine) {
            activeLine.classList.add('active');
            const containerHeight = cont.clientHeight;
            const lineHeight = activeLine.offsetHeight;
            const lineTop = activeLine.offsetTop;
            const targetScroll = lineTop - (containerHeight / 2) + (lineHeight / 2);

            cont.scrollTo({
                top: targetScroll,
                behavior: 'smooth'
            });
        }
    }
}

function setupKnobs() {
    const knobs = document.querySelectorAll('.knob-common');
    
    knobs.forEach(knob => {
        const startDrag = (e) => {
            activeKnob = knob;
            activeKnobRect = knob.getBoundingClientRect();
            e.preventDefault(); 
        };
        knob.addEventListener('mousedown', startDrag);
        knob.addEventListener('touchstart', startDrag, {passive: false});
    });

    const handleMove = (e) => {
        if (!activeKnob || !activeKnobRect) return;
        if (e.cancelable && e.type === 'touchmove') e.preventDefault();

        const knob = activeKnob;
        const type = knob.dataset.type;

        const cx = activeKnobRect.left + activeKnobRect.width / 2;
        const cy = activeKnobRect.top + activeKnobRect.height / 2;

        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;

        const x = clientX - cx;
        const y = clientY - cy;

        let deg = Math.atan2(y, x) * (180 / Math.PI) + 90;
        if (deg < 0) deg += 360;

        if (type === 'vol') {
            let val = 0;
            if (deg >= 210) val = ((deg - 210) / 300) * 100;
            else if (deg <= 150) val = ((150 + deg) / 300) * 100;
            else val = (Math.abs(deg-210) < Math.abs(deg-150)) ? 0 : 100;
            
            val = Math.round(Math.min(100, Math.max(0, val)));
            
            if(settings.vol !== val) { 
                settings.vol = val; 
                updateUI(); 
                sendVol(val); 
            }
        } else {
            let p = 0;
            if (deg >= 210) p = (deg - 210) / 300;
            else if (deg <= 150) p = (150 + deg) / 300;
            else p = (Math.abs(deg-210) < Math.abs(deg-150)) ? 0 : 1;
            
            let v = Math.round((p * 24) - 12);
            if(settings[type] !== v) { 
                settings[type] = v; 
                updateUI(); 
                sendEq(); 
            }
        }
    };

    const stopDrag = () => { activeKnob = null; activeKnobRect = null; };

    document.addEventListener('mousemove', handleMove);
    document.addEventListener('touchmove', handleMove, {passive: false});
    document.addEventListener('mouseup', stopDrag);
    document.addEventListener('touchend', stopDrag);
}

function updateUI() {
    ['f1','f2','f3','f4','f5','f6','f7','f8','f9','f10'].forEach(t => {
        const val = settings[t] || 0;
        const el = document.getElementById('k-'+t);
        const txt = document.getElementById('v-'+t);
        let deg = ((val + 12) / 24) * 270 - 135;
        if(el) el.style.transform = `rotate(${deg}deg)`;
        if(txt) txt.textContent = val;
    });
    
    const vK = document.getElementById('k-vol');
    let volDeg = ((settings.vol / 100) * 270) - 135;
    if(vK) vK.style.transform = `rotate(${volDeg}deg)`;
    const vV = document.getElementById('v-vol-val');
    if(vV) vV.textContent = settings.vol + '%';
    
    localStorage.setItem('st4_set', JSON.stringify(settings));
}

function sendVol(v) {
    if(volTimer) clearTimeout(volTimer);
    volTimer = setTimeout(() => fetch('/control/volume?val='+v), 50);
}

function sendEq() {
    if(eqTimer) clearTimeout(eqTimer);
    eqTimer = setTimeout(() => {
        let q = [];
        for(let i=1; i<=10; i++) q.push(`f${i}=${settings['f'+i]}`);
        fetch(`/control/eq?${q.join('&')}`);
    }, 100);
}

function updateBalance(val) {
    val = parseInt(val);
    let l_vol = 1.0;
    let r_vol = 1.0;

    if (val < 0) r_vol = 1 - (Math.abs(val) / 100);
    else if (val > 0) l_vol = 1 - (val / 100);

    const label = document.getElementById('bal-label');
    if (label) {
        if (val === 0) label.textContent = "CENTER";
        else if (val === -100) label.textContent = "ONLY LEFT";
        else if (val === 100) label.textContent = "ONLY RIGHT";
        else label.textContent = val < 0 ? `L +${Math.abs(val)}%` : `R +${val}%`;
        label.style.cursor = "pointer";
        label.onclick = resetBalance; 
    }
    sendBalance(l_vol, r_vol);
}

function resetBalance() {
    const slider = document.getElementById('balanceSlider');
    if(slider) {
        slider.value = 0;
        updateBalance(0);
        document.getElementById('btn-mute-l').classList.remove('active');
        document.getElementById('btn-mute-r').classList.remove('active');
    }
}

function toggleMuteSide(side) {
    const slider = document.getElementById('balanceSlider');
    if (!slider) return;
    let newValue = parseInt(slider.value);
    if (side === 'L') newValue = (newValue === 100) ? 0 : 100;
    else newValue = (newValue === -100) ? 0 : -100;
    slider.value = newValue;
    updateBalance(newValue);
}

function sendBalance(l, r) {
    const btnL = document.getElementById('btn-mute-l');
    const btnR = document.getElementById('btn-mute-r');
    if (btnL) {
        if (l < 0.1) btnL.classList.add('active'); 
        else btnL.classList.remove('active');
    }
    if (btnR) {
        if (r < 0.1) btnR.classList.add('active'); 
        else btnR.classList.remove('active');
    }
    if(balTimeout) clearTimeout(balTimeout);
    balTimeout = setTimeout(() => {
        fetch(`/control/balance?l=${l.toFixed(2)}&r=${r.toFixed(2)}`);
    }, 100);
}

function setTextSafe(id, text) {
    const el = document.getElementById(id);
    if(el) el.textContent = text;
}

function fmtTime(s) {
    if (!s || isNaN(s)) return "0:00";
    let m = Math.floor(s / 60);
    let sec = Math.floor(s % 60);
    return m + ":" + (sec < 10 ? "0" + sec : sec);
}

function tg(id) {
    const el = document.getElementById(id);
    if (el) {
        if (el.classList.contains('active') || el.classList.contains('show')) {
            el.classList.remove('active');
            el.classList.remove('show');
            setTimeout(() => { 
                if(!el.classList.contains('active')) el.style.display = 'none'; 
            }, 300);
        } else {
            el.style.display = 'flex';
            void el.offsetWidth;
            setTimeout(() => el.classList.add(id === 'search-popup' ? 'show' : 'active'), 10);
            if(id === 'pm') switchTab('lib');
            if(id === 'pr-om') initPresets();
        }
    }
}

function showToast(msg) {
    let box = document.getElementById('toast-box');
    if (!box) {
        box = document.createElement('div');
        box.id = 'toast-box';
        box.style.cssText = "position:fixed; bottom:90px; left:50%; transform:translateX(-50%); z-index:9999; text-align:center; pointer-events:none;";
        document.body.appendChild(box);
    }
    const el = document.createElement('div');
    el.textContent = msg;
    el.style.cssText = "background:rgba(0,255,0,0.15); color:#fff; border:1px solid #0f0; padding:10px 20px; border-radius:30px; margin-top:10px; opacity:0; transition:opacity 0.3s ease; font-size:12px; font-weight:bold; backdrop-filter:blur(5px);";
    box.appendChild(el);
    requestAnimationFrame(() => el.style.opacity = '1');
    setTimeout(() => { 
        el.style.opacity = '0'; 
        setTimeout(() => el.remove(), 300); 
    }, 2500);
}

function initPath() {
    fetch('/system/default_path').then(r=>r.json()).then(d => {
        currentScanPath = d.path; loadLocalFiles(d.path);
    }).catch(() => loadLocalFiles('/root/music'));
}

async function loadLocalFiles(path) {
    const l = document.getElementById('lib-list');
    l.innerHTML = '<div style="text-align:center; padding:20px;"><i class="fa-solid fa-spinner fa-spin"></i></div>';
    const pathInput = document.getElementById('scan-path');
    if(pathInput) pathInput.value = path;
    
    try {
        const items = await (await fetch('/get_files?path=' + encodeURIComponent(path))).json();
        l.innerHTML = '';
        items.forEach(item => {
            const row = document.createElement('div');
            row.className = `lib-item ${item.type === 'dir' ? 'is-folder' : 'is-file'}`;
            
            const iconDiv = document.createElement('div');
            iconDiv.className = 'lib-icon';
            const iconI = document.createElement('i');
            iconI.className = `fa-solid ${item.type === 'dir' ? 'fa-folder' : 'fa-music'}`;
            iconDiv.appendChild(iconI);
            
            const infoDiv = document.createElement('div');
            infoDiv.className = 'lib-info';
            const nameDiv = document.createElement('div');
            nameDiv.className = 'lib-name';
            nameDiv.textContent = item.name;
            
            infoDiv.appendChild(nameDiv);
            row.appendChild(iconDiv);
            row.appendChild(infoDiv);
            
            row.onclick = () => {
                if(item.type === 'dir') loadLocalFiles(item.path);
                else { playSong(item.path, 'play_now', item.name); tg('pm'); }
            };
            l.appendChild(row);
        });
        currentScanPath = path;
    } catch(e) { l.innerHTML = '<div style="text-align:center; padding:20px; color:red">Error loading files</div>'; }
}

function browsePath() { loadLocalFiles(document.getElementById('scan-path').value); }
function jumpTo(p) { loadLocalFiles(p); }
function setAsDefaultPath() {
    fetch('/system/default_path', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({path: currentScanPath})
    }).then(()=> showToast("Path Saved as Default"));
}

async function loadQueue() {
    const l = document.getElementById('queue-list');
    l.innerHTML = ''; 
    try {
        const d = await (await fetch('/queue/list')).json();
        const header = document.querySelector('#tab-queue');
        if(header) header.innerText = `QUEUE (${d.queue.length})`;

        if(d.queue.length === 0) {
            l.innerHTML = '<div style="padding:20px; text-align:center; color:#666">Queue is Empty</div>';
            return;
        }

        d.queue.forEach((item, i) => {
            const row = document.createElement('div');
            const isActive = (i === d.current_index);
            row.className = `lib-item ${isActive ? 'is-active' : ''}`;
            if(isActive) row.style.background = "rgba(0,255,0,0.1)";
            
            const info = document.createElement('div');
            info.className = 'lib-info';
            
            const num = document.createElement('span');
            num.style.cssText = "color:#666; font-size:0.7rem; margin-right:10px; font-family:monospace;";
            num.textContent = (i + 1) + ".";

            const name = document.createElement('div');
            name.className = 'lib-name';
            name.textContent = item.title; 
            if(isActive) name.style.color = "var(--primary)";
            
            info.appendChild(num);
            info.appendChild(name);
            row.appendChild(info);

            row.style.cursor = "pointer";
            row.onclick = () => {
                fetch('/control/jump?index=' + i)
                    .then(r => r.json())
                    .then(res => {
                        if(res.status === 'ok') {
                            showToast("Jumping to: " + res.title);
                            setTimeout(loadQueue, 500); 
                        }
                    });
            };
            l.appendChild(row);
        });

        if(d.current_index > 3) {
            const activeRow = l.children[d.current_index];
            if(activeRow) activeRow.scrollIntoView({behavior: "smooth", block: "center"});
        }
    } catch(e) { console.error("Queue error", e); }
}

function clearQueue() { fetch('/queue/clear').then(() => loadQueue()); }

function switchTab(t) {
    ['lib','pl','queue'].forEach(x => {
        const content = document.getElementById('content-'+x);
        const tab = document.getElementById('tab-'+x);
        if(content) content.style.display = 'none';
        if(tab) tab.classList.remove('active');
    });

    const activeContent = document.getElementById('content-'+t);
    const activeTab = document.getElementById('tab-'+t);
    
    if(activeContent) activeContent.style.display = 'flex';
    if(activeTab) activeTab.classList.add('active');

    if(t === 'queue') {
        loadQueue(); 
    } 
    else if(t === 'pl') {
        loadSavedPlaylists(); 
    } 
    else if(t === 'lib') {
        const list = document.getElementById('lib-list');
        if(list && list.children.length === 0) {
            loadLibraryDB();
        }
    }
}

function handlePathKey(e) { if(e.key === 'Enter') browsePath(); }

function searchYt(e) {
    e.preventDefault();
    const q = document.getElementById('searchInput').value;
    tg('search-popup');
    const content = document.getElementById('popup-content');
    content.innerHTML = '<div style="padding:20px; text-align:center;"><i class="fa-solid fa-spinner fa-spin"></i> Searching...</div>';
    
    fetch('/search?q=' + encodeURIComponent(q)).then(r => r.json()).then(data => {
        content.innerHTML = '';
        data.forEach(v => {
            const row = document.createElement('div');
            row.className = 'yt-item';
            
            const img = document.createElement('img');
            img.src = v.thumb;
            img.className = 'yt-thumb';
            
            const info = document.createElement('div');
            info.className = 'yt-info';
            
            const t = document.createElement('div');
            t.className = 'yt-title';
            t.textContent = v.title;
            
            const a = document.createElement('div');
            a.className = 'yt-meta';
            a.textContent = v.artist;
            
            info.appendChild(t);
            info.appendChild(a);
            row.appendChild(img);
            row.appendChild(info);
            
            row.onclick = () => { playSong(v.link, 'play_now', v.title); tg('search-popup'); };
            content.appendChild(row);
        });
    });
}
function closeSearch() { tg('search-popup'); }

async function addPl() {
    const nameInput = document.getElementById('pl-name');
    const urlInput = document.getElementById('pl-url');
    const name = nameInput.value.trim();
    const url = urlInput.value.trim();

    if (!name || !url) return showToast("Name & URL required!");

    try {
        const r = await fetch('/get_playlist');
        const currentList = await r.json();

        currentList.push({ title: name, link: url, added_at: Date.now() });

        await fetch('/save_playlist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentList)
        });

        showToast("Saved to Playlist");
        nameInput.value = '';
        urlInput.value = '';
        loadSavedPlaylists(); 
    } catch (e) {
        showToast("Error Saving Playlist");
        console.error(e);
    }
}

function loadSavedPlaylists() {
    const l = document.getElementById('pl-list');
    l.innerHTML = '<div style="text-align:center; padding:20px; color:#666;"><i class="fa-solid fa-spinner fa-spin"></i> Loading...</div>';

    fetch('/get_playlist')
        .then(r => r.json())
        .then(data => {
            l.innerHTML = '';
            if (data.length === 0) {
                l.innerHTML = '<div style="text-align:center; padding:20px; color:#666;">No saved items</div>';
                return;
            }

            data.forEach((item, index) => {
                const row = document.createElement('div');
                row.className = 'lib-item';
                
                const delBtn = document.createElement('div');
                delBtn.className = 'lib-icon';
                delBtn.style.background = 'rgba(255,0,0,0.1)';
                delBtn.style.color = '#ff4444';
                delBtn.innerHTML = '<i class="fa-solid fa-trash"></i>';
                delBtn.onclick = (e) => {
                    e.stopPropagation();
                    deletePlItem(index);
                };

                const info = document.createElement('div');
                info.className = 'lib-info';
                
                const name = document.createElement('div');
                name.className = 'lib-name';
                name.textContent = item.title;

                const link = document.createElement('div');
                link.className = 'lib-type';
                link.style.fontSize = '0.7rem';
                link.textContent = item.link.substring(0, 40) + '...';

                info.appendChild(name);
                info.appendChild(link);
                row.appendChild(delBtn);
                row.appendChild(info);

                row.onclick = () => {
                    playSong(item.link, 'play_now', item.title);
                    showToast(`Playing: ${item.title}`);
                };

                l.appendChild(row);
            });
        })
        .catch(() => {
            l.innerHTML = '<div style="text-align:center; color:red;">Error Loading Data</div>';
        });
}

async function deletePlItem(index) {
    if(!confirm("Delete this item?")) return;
    try {
        const r = await fetch('/get_playlist');
        const list = await r.json();
        list.splice(index, 1);

        await fetch('/save_playlist', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(list)
        });
        loadSavedPlaylists();
        showToast("Item Deleted");
    } catch(e) { showToast("Error Deleting"); }
}

function toggleTheme() {
    document.body.classList.toggle('light-theme');
    const isLight = document.body.classList.contains('light-theme');
    localStorage.setItem('st4_theme', isLight ? 'light' : 'dark');
}

function initPresets() {
    const c = document.getElementById('preset-container');
    if(!c) return;
    c.innerHTML = '';
    const pList = ["Normal","Bass","Rock","Pop","Jazz","Vocal","Metal","Soft","Classic","RnB","Live","Techno","KZEDCPro","Party"];
    pList.forEach(n => {
        const b = document.createElement('button');
        b.className = `btn-preset-compact ${settings.active_preset === n ? 'active' : ''}`;
        b.textContent = n;
        b.onclick = () => {
            settings.active_preset = n;
            fetch('/control/preset?name='+n).then(r=>r.json()).then(d => {
                for(let k in d) settings[k] = d[k];
                updateUI();
                tg('pr-om');
                showToast(`Preset: ${n}`);
            });
        };
        c.appendChild(b);
    });
}

function setTimer(m) {
    fetch('/system/timer?min='+m).then(()=>{
        showToast(m > 0 ? `Sleep: ${m}m` : "Timer Off");
        tg('tm');
    });
}

function checkBitPerfect() {
    fetch('/get_bitperfect').then(r=>r.json()).then(d => {
        const ind = document.getElementById('bp-indicator');
        if(ind) ind.style.display = d.active ? 'block' : 'none';
        const btn = document.getElementById('btn-bp');
        if(btn && d.active) btn.classList.add('active-state');
        else if(btn) btn.classList.remove('active-state');
    });
}

function toggleBitPerfect() {
    fetch('/control/bitperfect').then(r=>r.json()).then(d => {
        checkBitPerfect();
        showToast(d.bitperfect ? "Bit Perfect ON" : "Bit Perfect OFF");
    });
}

function checkCrossfeed() {
    fetch('/get_crossfeed').then(r=>r.json()).then(d => {
        const ind = document.getElementById('xf-indicator');
        if(ind) ind.style.display = d.active ? 'block' : 'none';
        const btn = document.getElementById('btn-xf');
        if(btn) {
            if(d.active) {
                btn.classList.add('active-state');
                btn.style.color = "#ff00ff";
                btn.style.borderColor = "rgba(255, 0, 255, 0.3)";
            } else {
                btn.classList.remove('active-state');
                btn.style.color = "";
                btn.style.borderColor = "";
            }
        }
    });
}

function toggleCrossfeed() {
    const btn = document.getElementById('btn-xf');
    const newState = btn.classList.contains('active-state') ? 'off' : 'on';
    fetch('/control/crossfeed?state=' + newState)
        .then(r => r.json())
        .then(d => {
            checkCrossfeed(); 
            showToast(d.crossfeed ? "Crossfeed: ON (Binaural)" : "Crossfeed: OFF (Stereo)");
        });
}

function scanLibrary() {
    const statusDiv = document.getElementById('scan-status');
    statusDiv.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Starting...';
    
    fetch('/library/scan')
        .then(r => r.json())
        .then(() => {
            monitorScanProgress();
        });
}

function monitorScanProgress() {
    const statusDiv = document.getElementById('scan-status');
    
    const interval = setInterval(() => {
        fetch('/library/status')
            .then(r => r.json())
            .then(d => {
                if (d.scanning) {
                    statusDiv.textContent = `Scanning: ${d.progress}% (${d.total} found)`;
                } else {
                    clearInterval(interval);
                    statusDiv.textContent = `Done. ${d.total} Tracks.`;
                    showToast("Library Updated!");
                    loadLibraryDB(); 
                }
            });
    }, 1000);
}

async function loadLibraryDB(sortBy = 'title') {
    const l = document.getElementById('lib-list');
    l.innerHTML = '<div style="text-align:center; padding:20px; color:#666;"><i class="fa-solid fa-spinner fa-spin"></i> Loading Library...</div>';
    
    try {
        const r = await fetch(`/library/tracks?sort=${sortBy}`);
        const tracks = await r.json();
        
        l.innerHTML = '';
        if (tracks.length === 0) {
            l.innerHTML = '<div style="text-align:center; padding:30px; color:#666;">Library Empty.<br>Click RESCAN to start.</div>';
            return;
        }

        tracks.forEach(t => {
            const row = document.createElement('div');
            row.className = 'lib-item';
            row.dataset.meta = `${t.name} ${t.artist} ${t.album}`.toLowerCase();
            const currentTitle = document.getElementById('tit').textContent;
            if (t.name === currentTitle) {
                row.style.background = "rgba(0, 255, 0, 0.1)"; // Ijo transparan
                row.style.borderLeft = "3px solid var(--primary)";
            }
            const iconDiv = document.createElement('div');
            iconDiv.className = 'lib-icon';
            iconDiv.style.background = 'rgba(0,255,0,0.1)';
            iconDiv.style.color = 'var(--primary)';
            iconDiv.innerHTML = '<i class="fa-solid fa-music"></i>';

            const info = document.createElement('div');
            info.className = 'lib-info';

            const title = document.createElement('div');
            title.className = 'lib-name';
            title.textContent = t.name;

            const meta = document.createElement('div');
            meta.className = 'lib-type';
            meta.textContent = t.meta; 

            info.appendChild(title);
            info.appendChild(meta);
            row.appendChild(iconDiv);
            row.appendChild(info);

            row.onclick = () => {
                playSong(t.path, 'play_now', t.name);
            };

            l.appendChild(row);
        });
        
        document.getElementById('scan-status').textContent = `Total: ${tracks.length} Tracks`;

    } catch (e) {
        l.innerHTML = '<div style="text-align:center; color:red;">Database Error</div>';
    }
}

function filterLibraryLocal(query) {
    const q = query.toLowerCase();
    const rows = document.querySelectorAll('#lib-list .lib-item');
    rows.forEach(row => {
        const meta = row.dataset.meta || "";
        if (meta.includes(q)) {
            row.style.display = "flex";
        } else {
            row.style.display = "none";
        }
    });
}