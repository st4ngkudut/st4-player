#!/bin/bash
echo "🔥 Starting ST4 Player..."

# Pindah ke direktori script berada (biar bisa dijalanin dari mana aja)
cd "$(dirname "$0")"

# Pastikan permission play.sh bener
chmod +x play.sh

# Jalanin Python
python app.py
