import os
import threading
import socket
import subprocess
import time
import json
import qrcode
from datetime import datetime
from flask import Flask, request, render_template_string, jsonify, make_response
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFilter
from tkinter import Toplevel, Canvas
import tkinter as tk
import secrets
from base64 import b64decode
import io
# =========================
# CONFIG
# =========================

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

UPLOAD_FOLDER = os.path.join(os.path.expanduser("~"), "LanDrop")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

pending_files = []
transfer_history = []  # {"name", "size", "time", "status"}

# =========================
# FLASK — PÁGINA WEB PRO
# =========================
app = Flask(__name__)
app.config["DEVICE_CONNECTED"] = False

HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LanDrop — Enviar archivo</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">

<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg: #0a0a0f;
    --surface: #111118;
    --border: rgba(255,255,255,0.07);
    --accent: #4f8aff;
    --accent-glow: rgba(79,138,255,0.25);
    --text: #e8eaf0;
    --muted: rgba(232,234,240,0.45);
    --success: #34d399;
    --danger: #f87171;
  }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Syne', sans-serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }

  /* Background grid */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(rgba(79,138,255,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(79,138,255,0.04) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }

  /* Glow orbs */
  body::after {
    content: '';
    position: fixed;
    width: 500px; height: 500px;
    background: radial-gradient(circle, rgba(79,138,255,0.12) 0%, transparent 70%);
    top: -100px; left: -100px;
    border-radius: 50%;
    pointer-events: none;
    z-index: 0;
  }

  .orb2 {
    position: fixed;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(100,60,255,0.10) 0%, transparent 70%);
    bottom: -100px; right: -100px;
    border-radius: 50%;
    pointer-events: none;
    z-index: 0;
  }

  .card {
    position: relative;
    z-index: 1;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 40px 36px;
    width: 92%;
    max-width: 420px;
    backdrop-filter: blur(20px);
    box-shadow: 0 0 0 1px var(--border), 0 40px 80px rgba(0,0,0,0.5);
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
  }

  .logo-icon {
    width: 36px; height: 36px;
    background: var(--accent);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 18px;
    box-shadow: 0 0 20px var(--accent-glow);
  }

  .logo-text {
    font-size: 22px;
    font-weight: 800;
    letter-spacing: -0.5px;
  }

  .subtitle {
    font-family: 'DM Mono', monospace;
    font-size: 12px;
    color: var(--muted);
    margin-bottom: 28px;
    letter-spacing: 0.5px;
  }

  /* Drop zone */
  .drop-zone {
    border: 1.5px dashed rgba(79,138,255,0.35);
    border-radius: 14px;
    padding: 36px 20px;
    text-align: center;
    cursor: pointer;
    transition: all 0.25s ease;
    background: rgba(79,138,255,0.04);
    position: relative;
    overflow: hidden;
  }

  .drop-zone:hover, .drop-zone.drag-over {
    border-color: var(--accent);
    background: rgba(79,138,255,0.10);
    box-shadow: 0 0 30px var(--accent-glow);
  }

  .drop-icon {
    font-size: 36px;
    margin-bottom: 10px;
    display: block;
  }

  .drop-label {
    font-size: 15px;
    font-weight: 700;
    color: var(--text);
  }

  .drop-sub {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--muted);
    margin-top: 4px;
  }

  input[type="file"] {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
    width: 100%;
    height: 100%;
  }

  /* File preview */
  .file-preview {
    display: none;
    align-items: center;
    gap: 12px;
    background: rgba(79,138,255,0.08);
    border: 1px solid rgba(79,138,255,0.2);
    border-radius: 10px;
    padding: 12px 14px;
    margin-top: 14px;
  }

  .file-preview.show { display: flex; }

  .file-preview-icon { font-size: 22px; }

  .file-preview-info { flex: 1; }

  .file-preview-name {
    font-size: 13px;
    font-weight: 700;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 220px;
  }

  .file-preview-size {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--muted);
  }

  /* Button */
  .btn {
    margin-top: 18px;
    width: 100%;
    padding: 14px;
    border: none;
    border-radius: 12px;
    background: var(--accent);
    color: white;
    font-family: 'Syne', sans-serif;
    font-size: 14px;
    font-weight: 700;
    cursor: pointer;
    letter-spacing: 0.3px;
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
  }

  .btn:hover {
    background: #3a75f0;
    box-shadow: 0 6px 24px rgba(79,138,255,0.4);
    transform: translateY(-1px);
  }

  .btn:active { transform: translateY(0); }

  .btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }

  /* Progress bar */
  .progress-wrap {
    display: none;
    margin-top: 14px;
    background: rgba(255,255,255,0.06);
    border-radius: 100px;
    height: 6px;
    overflow: hidden;
  }
  .progress-wrap.show { display: block; }
  .progress-bar {
    height: 100%;
    background: var(--accent);
    border-radius: 100px;
    width: 0%;
    transition: width 0.3s ease;
    box-shadow: 0 0 10px var(--accent-glow);
  }

  /* Alert */
  .alert {
    display: none;
    align-items: center;
    gap: 10px;
    padding: 12px 14px;
    border-radius: 10px;
    margin-top: 14px;
    font-size: 13px;
    font-weight: 600;
  }
  .alert.show { display: flex; }
  .alert.success { background: rgba(52,211,153,0.12); border: 1px solid rgba(52,211,153,0.3); color: var(--success); }
  .alert.error { background: rgba(248,113,113,0.12); border: 1px solid rgba(248,113,113,0.3); color: var(--danger); }

  /* Footer */
  .footer {
    margin-top: 24px;
    text-align: center;
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    color: var(--muted);
  }
</style>
</head>
<body>

<div class="orb2"></div>

<div class="card">
  <div class="logo">
    <div class="logo-icon">⚡</div>
    <span class="logo-text">LanDrop</span>
  </div>
  <p class="subtitle">// transferencia en red local</p>

  <form id="uploadForm" enctype="multipart/form-data">
    <div class="drop-zone" id="dropZone">
      <input type="file" name="file" id="fileInput" required>
      <span class="drop-icon">📂</span>
      <div class="drop-label">Arrastra un archivo o haz clic</div>
      <div class="drop-sub">Cualquier tipo · Sin límite de tamaño</div>
    </div>

    <div class="file-preview" id="filePreview">
      <span class="file-preview-icon" id="fileIcon">📄</span>
      <div class="file-preview-info">
        <div class="file-preview-name" id="fileName">—</div>
        <div class="file-preview-size" id="fileSize">—</div>
      </div>
    </div>

    <div class="progress-wrap" id="progressWrap">
      <div class="progress-bar" id="progressBar"></div>
    </div>

    <div class="alert success" id="alertSuccess">✔ Archivo enviado correctamente</div>
    <div class="alert error" id="alertError">✖ Error al enviar el archivo</div>

    <button class="btn" type="submit" id="submitBtn" disabled>Enviar archivo →</button>
  </form>

    <div id="keyBox" style="
      margin-top: 10px;
      padding: 10px 12px;
      border-radius: 10px;
      background: rgba(79,138,255,0.08);
      border: 1px solid rgba(79,138,255,0.25);
      font-family: 'DM Mono', monospace;
      font-size: 12px;
      color: var(--text);
      word-break: break-all;
    ">
      KEY: <span id="keyDisplay">—</span>
    </div>
  <div class="footer">LanDrop · Red local segura</div>
</div>
<script>
const hash = window.location.hash;
let KEY = null;
if (hash.includes("key=")) KEY = hash.split("key=")[1];

document.getElementById("keyDisplay").textContent = KEY || "NO KEY";

const fileInput  = document.getElementById('fileInput');
const filePreview= document.getElementById('filePreview');
const fileName   = document.getElementById('fileName');
const fileSize   = document.getElementById('fileSize');
const fileIcon   = document.getElementById('fileIcon');
const submitBtn  = document.getElementById('submitBtn');
const dropZone   = document.getElementById('dropZone');
const progressWrap = document.getElementById('progressWrap');
const progressBar  = document.getElementById('progressBar');
const alertSuccess = document.getElementById('alertSuccess');
const alertError   = document.getElementById('alertError');

const ICONS = { image:'🖼️', pdf:'📕', video:'🎬', audio:'🎵', zip:'📦', default:'📄' };
function getIcon(name) {
  if (/\.(jpg|jpeg|png|gif|webp|svg)$/i.test(name)) return ICONS.image;
  if (/\.pdf$/i.test(name)) return ICONS.pdf;
  if (/\.(mp4|mov|avi|mkv)$/i.test(name)) return ICONS.video;
  if (/\.(mp3|wav|flac|ogg)$/i.test(name)) return ICONS.audio;
  if (/\.(zip|rar|7z|tar|gz)$/i.test(name)) return ICONS.zip;
  return ICONS.default;
}
function fmtSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/1048576).toFixed(1) + ' MB';
}
function showFile(file) {
  fileName.textContent = file.name;
  fileSize.textContent = fmtSize(file.size);
  fileIcon.textContent = getIcon(file.name);
  filePreview.classList.add('show');
  submitBtn.disabled = false;
}

fileInput.addEventListener('change', () => { if (fileInput.files[0]) showFile(fileInput.files[0]); });
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) { fileInput.files = e.dataTransfer.files; showFile(e.dataTransfer.files[0]); }
});

// ── ENCRIPTACIÓN con Web Crypto API nativa ──────────────────────────
function arrayBufferToBase64(buffer) {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  // Procesar en chunks para evitar límite de argumentos del stack
  const chunkSize = 8192;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

async function encryptFile(base64Data, password) {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    "raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]
  );
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const key  = await crypto.subtle.deriveKey(
    { name: "PBKDF2", salt, iterations: 100000, hash: "SHA-256" },
    keyMaterial,
    { name: "AES-GCM", length: 256 },
    false, ["encrypt"]
  );
  const iv         = crypto.getRandomValues(new Uint8Array(12));
  const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, enc.encode(base64Data));

  const payload = {
    salt: arrayBufferToBase64(salt),
    iv:   arrayBufferToBase64(iv),
    ct:   arrayBufferToBase64(ciphertext)
  };
  return btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
}
function xorEncrypt(buffer, password) {
  const bytes = new Uint8Array(buffer);
  const key = new TextEncoder().encode(password);
  const out = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) {
    out[i] = bytes[i] ^ key[i % key.length];
  }
  return arrayBufferToBase64(out.buffer);
}
function rc4(key, data) {
  const k = new TextEncoder().encode(key);
  const S = Array.from({length: 256}, (_, i) => i);
  let j = 0;
  for (let i = 0; i < 256; i++) {
    j = (j + S[i] + k[i % k.length]) & 255;
    [S[i], S[j]] = [S[j], S[i]];
  }
  let i = 0; j = 0;
  const out = new Uint8Array(data.byteLength);
  const bytes = new Uint8Array(data);
  for (let n = 0; n < bytes.length; n++) {
    i = (i + 1) & 255;
    j = (j + S[i]) & 255;
    [S[i], S[j]] = [S[j], S[i]];
    out[n] = bytes[n] ^ S[(S[i] + S[j]) & 255];
  }
  return out;
}
document.getElementById('uploadForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  alertSuccess.classList.remove('show');
  alertError.classList.remove('show');
  progressWrap.classList.add('show');
  progressBar.style.width = '0%';
  submitBtn.disabled = true;

  const file = fileInput.files[0];
  try {
    const buffer = await file.arrayBuffer();
    const out = rc4(KEY, buffer);
    
    const formData = new FormData();
    formData.append("file", new Blob([out]), file.name);
    formData.append("original_name", file.name);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/upload");
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) progressBar.style.width = (ev.loaded / ev.total * 100) + "%";
    };
    xhr.onload = () => {
      progressBar.style.width = "100%";
      setTimeout(() => {
        progressWrap.classList.remove("show");
        if (xhr.status === 200) {
          alertSuccess.classList.add("show");
          filePreview.classList.remove("show");
          submitBtn.disabled = true;
          fileInput.value = "";
        } else {
          alertError.textContent = '✖ Error servidor: ' + xhr.status;
          alertError.classList.add("show");
          submitBtn.disabled = false;
        }
      }, 400);
    };
    xhr.onerror = () => { alertError.classList.add('show'); submitBtn.disabled = false; };
    xhr.send(formData);
  } catch(err) {
    alertError.textContent = '✖ ' + err.message;
    alertError.classList.add('show');
    submitBtn.disabled = false;
    progressWrap.classList.remove('show');
  }
});

</script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    response = make_response(render_template_string(HTML_PAGE))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    app.config["DEVICE_CONNECTED"] = True
    return response

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    original_name = request.form.get("original_name", "archivo")
    if not f:
        return jsonify({"ok": False, "error": "sin datos"}), 400
    data = f.read()
    pending_files.append({
        "name": original_name,
        "data": data,
        "size": len(data),
        "time": datetime.now().strftime("%H:%M:%S")
    })
    return jsonify({"ok": True})
# =========================
# UTILIDADES
# =========================
def generate_qr(data, color="#4f8aff", bg="#111118"):
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        fill_color=color,
        back_color=bg
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
def decrypt_aes(data_bytes, password):
    k = password.encode("utf-8")
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + k[i % len(k)]) % 256
        S[i], S[j] = S[j], S[i]
    i = j = 0
    out = bytearray()
    for byte in data_bytes:
        i = (i + 1) % 256
        j = (j + S[i]) % 256
        S[i], S[j] = S[j], S[i]
        out.append(byte ^ S[(S[i] + S[j]) % 256])
    return bytes(out)

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def get_wifi_ssid():
    import platform
    system = platform.system()
    try:
        if system == "Windows":
            result = subprocess.check_output("netsh wlan show interfaces", shell=True).decode(errors="ignore")
            for line in result.split("\n"):
                if "SSID" in line and "BSSID" not in line:
                    return line.split(":", 1)[1].strip()
        elif system == "Darwin":
            result = subprocess.check_output(
                ["/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport", "-I"],
                stderr=subprocess.DEVNULL
            ).decode(errors="ignore")
            for line in result.split("\n"):
                if " SSID:" in line:
                    return line.split(":", 1)[1].strip()
        elif system == "Linux":
            for cmd in [["iwgetid", "-r"], ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"]]:
                try:
                    result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode(errors="ignore").strip()
                    if result:
                        if ":" in result:
                            for line in result.split("\n"):
                                if line.startswith("yes:"):
                                    return line.split(":", 1)[1].strip()
                        else:
                            return result.split("\n")[0].strip()
                except Exception:
                    continue
    except Exception:
        pass
    return "Red_local"
def get_wifi_security():
    import subprocess

    try:
        result = subprocess.check_output(
            "netsh wlan show interfaces",
            shell=True
        ).decode(errors="ignore")

        auth = None

        for line in result.split("\n"):
            line = line.strip()

            if "Authentication" in line or "Autenticación" in line:
                auth = line.split(":", 1)[1].strip()

        if not auth:
            return "WPA"

        auth = auth.upper()

        if "WPA3" in auth:
            return "WPA3"
        elif "WPA2" in auth:
            return "WPA2"
        elif "WPA" in auth:
            return "WPA"
        elif "WEP" in auth:
            return "WEP"
        else:
            return "WPA"

    except Exception as e:
        print("Error seguridad WiFi:", e)
        return "WPA"
def get_wifi_password(ssid):
    try:
        command = f'netsh wlan show profile name="{ssid}" key=clear'
        result = subprocess.check_output(command, shell=True).decode(errors="ignore")

        for line in result.split("\n"):
            if "Contenido de la clave" in line or "Key Content" in line:
                return line.split(":", 1)[1].strip()

    except Exception as e:
        print("Error obteniendo contraseña:", e)

    return ""

def format_size(size):
    if size < 1024: return f"{size} B"
    if size < 1024*1024: return f"{size/1024:.1f} KB"
    return f"{size/(1024*1024):.1f} MB"

def get_file_emoji(name):
    name = name.lower()
    if any(name.endswith(e) for e in [".jpg",".jpeg",".png",".gif",".webp",".svg"]): return "🖼️"
    if name.endswith(".pdf"): return "📕"
    if any(name.endswith(e) for e in [".mp4",".mov",".avi",".mkv"]): return "🎬"
    if any(name.endswith(e) for e in [".mp3",".wav",".flac",".ogg"]): return "🎵"
    if any(name.endswith(e) for e in [".zip",".rar",".7z",".tar",".gz"]): return "📦"
    if any(name.endswith(e) for e in [".doc",".docx"]): return "📝"
    if any(name.endswith(e) for e in [".xls",".xlsx"]): return "📊"
    if any(name.endswith(e) for e in [".py",".js",".html",".css",".json"]): return "💻"
    return "📄"

# =========================
# COLORES TEMA
# =========================
DARK_BG    = "#0d0d14"
SURFACE    = "#13131e"
SURFACE2   = "#1a1a28"
ACCENT     = "#4f8aff"
ACCENT2    = "#6e40c9"
TEXT       = "#e8eaf0"
MUTED      = "#6b7280"
SUCCESS    = "#34d399"
DANGER     = "#f87171"
BORDER     = "#2a2a3d"

# =========================
# POPUP MODERNO
# =========================
class FilePopup(ctk.CTkToplevel):
    def __init__(self, master, file, on_accept, on_reject):
        super().__init__(master)
        self.title("")
        self.geometry("400x260")
        self.configure(fg_color=SURFACE)
        self.resizable(False, False)
        self.grab_set()
        self.lift()

        # Header strip
        header = ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=0, height=5)
        header.pack(fill="x")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=28, pady=22)

        # Icon + label
        top_row = ctk.CTkFrame(body, fg_color="transparent")
        top_row.pack(fill="x")

        emoji = get_file_emoji(file["name"])
        ctk.CTkLabel(top_row, text=emoji, font=("Segoe UI Emoji", 32), text_color=TEXT).pack(side="left")

        title_col = ctk.CTkFrame(top_row, fg_color="transparent")
        title_col.pack(side="left", padx=14)
        ctk.CTkLabel(title_col, text="Archivo entrante", font=("Segoe UI", 11), text_color=MUTED).pack(anchor="w")
        ctk.CTkLabel(title_col, text="Transferencia recibida", font=("Segoe UI", 14, "bold"), text_color=TEXT).pack(anchor="w")

        # File info card
        info = ctk.CTkFrame(body, fg_color=SURFACE2, corner_radius=10)
        info.pack(fill="x", pady=14)

        name_display = file["name"] if len(file["name"]) <= 34 else file["name"][:31] + "..."
        ctk.CTkLabel(info, text=name_display, font=("Segoe UI", 13, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12,2))
        ctk.CTkLabel(info, text=f"{format_size(file['size'])}  ·  {file.get('time','—')}",
                     font=("Courier New", 11), text_color=MUTED).pack(anchor="w", padx=14, pady=(0,12))

        # Buttons
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x")
        btn_row.columnconfigure([0, 1], weight=1)

        ctk.CTkButton(btn_row, text="Rechazar", fg_color=SURFACE2, hover_color=BORDER,
                      text_color=MUTED, font=("Segoe UI", 13, "bold"), corner_radius=10, height=40,
                      command=lambda: (on_reject(), self.destroy())).grid(row=0, column=0, padx=(0,6), sticky="ew")

        ctk.CTkButton(btn_row, text="✓  Guardar", fg_color=ACCENT, hover_color="#3a75f0",
                      text_color="white", font=("Segoe UI", 13, "bold"), corner_radius=10, height=40,
                      command=lambda: (on_accept(), self.destroy())).grid(row=0, column=1, padx=(6,0), sticky="ew")

        self.bell()

# =========================
# APP PRINCIPAL
# =========================
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("LanDrop")
        self.geometry("760x540")
        self.minsize(700, 500)
        self.configure(fg_color=DARK_BG)
        self._device_connected = False
        self.ip = get_ip()
        self.ssid = get_wifi_ssid()
        self.password = get_wifi_password(self.ssid)
        self.security=get_wifi_security()
        self.key = self.generate_key()
        app.config["KEY"] = self.key
        self.url = f"http://{self.ip}:5000/?v={int(time.time())}#key={self.key}"
        self._received_count = 0

        self._build_sidebar()
        self._build_main()
        self._generate_qr_images()
        self.check_connection()
        self._show_section("connect")
        self.check_files()
        app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 500  # 500 MB
    # ---- SIDEBAR ----
    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, fg_color=SURFACE, width=180, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=(28, 10), padx=16, anchor="w")

        logo_badge = ctk.CTkLabel(logo_frame, text="⚡", font=("Segoe UI Emoji", 22),
                                   fg_color=ACCENT, corner_radius=8, width=36, height=36, text_color="white")
        logo_badge.pack(side="left")
        ctk.CTkLabel(logo_frame, text="LanDrop", font=("Segoe UI", 17, "bold"), text_color=TEXT).pack(side="left", padx=8)

        ctk.CTkLabel(self.sidebar, text="v2.0  ·  Local", font=("Courier New", 10), text_color=MUTED).pack(pady=(0,20), padx=16, anchor="w")

        # Separador
        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=BORDER)
        sep.pack(fill="x", padx=14, pady=4)

        # Nav buttons
        self.nav_buttons = {}
        nav_items = [
            ("connect",  "📶", "Conectar"),
            ("transfer", "⚡", "Transferir"),
            ("history",  "📋", "Historial"),
        ]
        for key, icon, label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=f"  {icon}  {label}",
                anchor="w",
                font=("Segoe UI", 13),
                fg_color="transparent",
                hover_color=SURFACE2,
                text_color=MUTED,
                height=42,
                corner_radius=10,
                command=lambda k=key: self._show_section(k)
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = btn

        # Status indicator
        self.sidebar.pack_propagate(False)
        status_frame = ctk.CTkFrame(self.sidebar, fg_color=SURFACE2, corner_radius=10)
        status_frame.pack(side="bottom", fill="x", padx=12, pady=16)

        dot = ctk.CTkLabel(status_frame, text="●", font=("Arial", 10), text_color=SUCCESS)
        dot.pack(side="left", padx=(10,4), pady=10)
        ctk.CTkLabel(status_frame, text="Servidor activo", font=("Segoe UI", 11), text_color=TEXT).pack(side="left", pady=10)

        ctk.CTkLabel(self.sidebar, text="", height=2).pack(side="bottom")

        self.received_label = ctk.CTkLabel(self.sidebar, text="0 archivos recibidos",
                                            font=("Courier New", 10), text_color=MUTED)
        self.received_label.pack(side="bottom", pady=4)

    # ---- MAIN AREA ----
    def _build_main(self):
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(side="right", fill="both", expand=True)

        self.sections = {}
        self.sections["connect"]  = self._build_connect_section()
        self.sections["transfer"] = self._build_transfer_section()
        self.sections["history"]  = self._build_history_section()
        self._regenerate_wifi_qr()

    def _section_container(self):
        f = ctk.CTkFrame(self.main, fg_color="transparent")
        return f

    def _section_title(self, parent, title, subtitle=""):
        ctk.CTkLabel(parent, text=title, font=("Segoe UI", 22, "bold"), text_color=TEXT).pack(anchor="w", pady=(30,2), padx=30)
        if subtitle:
            ctk.CTkLabel(parent, text=subtitle, font=("Segoe UI", 12), text_color=MUTED).pack(anchor="w", padx=30, pady=(0,20))

    # ---- CONNECT SECTION ----
    def _build_connect_section(self):
        f = self._section_container()
        self._section_title(f, "Conectar dispositivo", "Rellena tus datos WiFi y escanea el QR con el móvil")

        # ---- QR card ----
        card = ctk.CTkFrame(f, fg_color=SURFACE, corner_radius=16)
        card.pack(padx=30, fill="x")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=30, pady=24)

        self.wifi_qr_label = ctk.CTkLabel(inner, text="⏳", font=("Segoe UI", 32), image=None)
        self.wifi_qr_label.pack(side="left")

        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(side="left", padx=28, anchor="n")

        ctk.CTkLabel(info, text="Red WiFi", font=("Segoe UI", 11), text_color=MUTED).pack(anchor="w", pady=(8,0))
        self.ssid_display = ctk.CTkLabel(info, text=self.ssid, font=("Segoe UI", 16, "bold"), text_color=TEXT)
        self.ssid_display.pack(anchor="w")

        sep = ctk.CTkFrame(info, height=1, fg_color=BORDER)
        sep.pack(fill="x", pady=12)

        ctk.CTkLabel(info, text="IP local", font=("Segoe UI", 11), text_color=MUTED).pack(anchor="w")
        ctk.CTkLabel(info, text=self.ip, font=("Courier New", 15, "bold"), text_color=ACCENT).pack(anchor="w")

        # ---- Formulario WiFi editable ----
        form_card = ctk.CTkFrame(f, fg_color=SURFACE, corner_radius=16)
        form_card.pack(padx=30, pady=(12, 0), fill="x")

        form_inner = ctk.CTkFrame(form_card, fg_color="transparent")
        form_inner.pack(padx=24, pady=20, fill="x")

        ctk.CTkLabel(form_inner, text="⚙️  Configurar QR WiFi", font=("Segoe UI", 13, "bold"), text_color=TEXT).pack(anchor="w", pady=(0,12))

        row1 = ctk.CTkFrame(form_inner, fg_color="transparent")
        row1.pack(fill="x", pady=4)
        ctk.CTkLabel(row1, text="Nombre de red (SSID)", font=("Segoe UI", 11), text_color=MUTED, width=170, anchor="w").pack(side="left")
        self.ssid_entry = ctk.CTkEntry(row1, font=("Courier New", 12), fg_color=SURFACE2,
                                        border_color=BORDER, text_color=TEXT, height=34)
        self.ssid_entry.insert(0, self.ssid)
        self.ssid_entry.pack(side="left", fill="x", expand=True)

        row2 = ctk.CTkFrame(form_inner, fg_color="transparent")
        row2.pack(fill="x", pady=4)
        ctk.CTkLabel(row2, text="Contraseña", font=("Segoe UI", 11), text_color=MUTED, width=170, anchor="w").pack(side="left")
        self.wifi_pass_entry = ctk.CTkEntry(row2, font=("Courier New", 12), fg_color=SURFACE2,
                                             border_color=BORDER, text_color=TEXT, height=34, show="•")
        
        self.wifi_pass_entry.pack(side="left", fill="x", expand=True)
        self.wifi_pass_entry.insert(0, self.password)
        row3 = ctk.CTkFrame(form_inner, fg_color="transparent")
        row3.pack(fill="x", pady=4)

        tip = ctk.CTkFrame(f, fg_color=SURFACE2, corner_radius=10)
        tip.pack(padx=30, pady=14, fill="x")
        ctk.CTkLabel(tip, text="💡  Rellena los datos de tu WiFi y pulsa «Generar QR» — el móvil se conectará automáticamente",
                     font=("Segoe UI", 11), text_color=MUTED).pack(padx=16, pady=12, anchor="w")

        return f

    def _regenerate_wifi_qr(self):

        def esc(s):
            return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace('"', '\\"')

        wifi_data = f"WIFI:T:{self.security};S:{self.ssid};P:{self.password};;"
        try:
            wifi_img = ctk.CTkImage(Image.open(generate_qr(wifi_data)), size=(180, 180))
            self.wifi_qr_label.configure(image=wifi_img, text="")
            self.wifi_qr_label.image = wifi_img
            self.ssid_display.configure(text=self.ssid)
            self.ssid = self.ssid
        except Exception as e:
            print(f"Error generando QR WiFi: {e}")

    # ---- TRANSFER SECTION ----
    def check_connection(self):
      if app.config.get("DEVICE_CONNECTED") and not self._device_connected:
          self._device_connected = True
          self.web_qr_label.configure(image=None, text="📱 Dispositivo conectado")
          self.web_qr_label.image=None
          app.config["DEVICE_CONNECTED"] = False
      self.after(1000, self.check_connection)
    def _build_transfer_section(self):
        f = self._section_container()
        self._section_title(f, "Enviar archivos", "Abre esta URL en tu dispositivo o escanea el QR")

        card = ctk.CTkFrame(f, fg_color=SURFACE, corner_radius=16)
        card.pack(padx=30, fill="x")

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(padx=30, pady=24)

        self.web_qr_label = ctk.CTkLabel(inner, text="", image=None)
        self.web_qr_label.pack(side="left")

        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(side="left", padx=28, anchor="n")

        ctk.CTkLabel(info, text="URL de transferencia", font=("Segoe UI", 11), text_color=MUTED).pack(anchor="w", pady=(8,4))

        url_box = ctk.CTkFrame(info, fg_color=SURFACE2, corner_radius=8)
        url_box.pack(anchor="w")
        ctk.CTkLabel(url_box, text=self.url, font=("Courier New", 14, "bold"), text_color=ACCENT).pack(padx=14, pady=10)

        sep = ctk.CTkFrame(info, height=1, fg_color=BORDER)
        sep.pack(fill="x", pady=12)

        ctk.CTkLabel(info, text="Puerto", font=("Segoe UI", 11), text_color=MUTED).pack(anchor="w")
        ctk.CTkLabel(info, text="5000", font=("Courier New", 15, "bold"), text_color=TEXT).pack(anchor="w")

        ctk.CTkLabel(info, text="Protocolo", font=("Segoe UI", 11), text_color=MUTED).pack(anchor="w", pady=(10,0))
        ctk.CTkLabel(info, text="HTTP · Local", font=("Courier New", 15, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkButton(info, text="Abrir archivos", font=("Segoe UI", 13, "bold"),
                      fg_color=ACCENT, hover_color="#3a75f0", text_color="white",
                      height=38, corner_radius=10,
                      command=self.open_folder).pack(anchor="e", pady=(14,0))
        return f
    def generate_key(self):
        return secrets.token_urlsafe(16)
    # ---- HISTORY SECTION ----
    def open_folder(self):
        os.startfile(UPLOAD_FOLDER)
    def _build_history_section(self):
        f = self._section_container()
        self._section_title(f, "Historial", "Archivos recibidos en esta sesión")

        self.history_frame = ctk.CTkScrollableFrame(f, fg_color="transparent", corner_radius=0)
        self.history_frame.pack(fill="both", expand=True, padx=30, pady=(0,20))

        self.history_empty = ctk.CTkLabel(
            self.history_frame,
            text="Ningún archivo recibido aún.\nEnvía un archivo desde tu dispositivo.",
            font=("Segoe UI", 13), text_color=MUTED, justify="center"
        )
        self.history_empty.pack(pady=40)

        return f

    def _add_history_row(self, file, status):
        if hasattr(self, 'history_empty') and self.history_empty.winfo_exists():
            self.history_empty.pack_forget()

        row = ctk.CTkFrame(self.history_frame, fg_color=SURFACE, corner_radius=10)
        row.pack(fill="x", pady=4)

        emoji = get_file_emoji(file["name"])
        ctk.CTkLabel(row, text=emoji, font=("Segoe UI Emoji", 20), text_color=TEXT, width=40).pack(side="left", padx=(14,0), pady=14)

        mid = ctk.CTkFrame(row, fg_color="transparent")
        mid.pack(side="left", padx=12, pady=12, fill="x", expand=True)

        name_display = file["name"] if len(file["name"]) <= 36 else file["name"][:33] + "..."
        ctk.CTkLabel(mid, text=name_display, font=("Segoe UI", 13, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(mid, text=f"{format_size(file['size'])}  ·  {file.get('time','—')}",
                     font=("Courier New", 11), text_color=MUTED).pack(anchor="w")

        status_color = SUCCESS if status == "Guardado" else DANGER
        ctk.CTkLabel(row, text=status, font=("Segoe UI", 11, "bold"), text_color=status_color).pack(side="right", padx=16)

    # ---- NAVEGACIÓN ----
    def _show_section(self, key):
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(fg_color=SURFACE2, text_color=TEXT)
            else:
                btn.configure(fg_color="transparent", text_color=MUTED)

        for k, section in self.sections.items():
            section.pack_forget()

        self.sections[key].pack(fill="both", expand=True)

    # ---- QR GENERATION ----
    def _generate_qr_images(self):
        try:
            wifi_data = f"WIFI:T:{self.security};S:{self.ssid};P:;;"

            wifi_img = ctk.CTkImage(Image.open(generate_qr(wifi_data)), size=(180, 180))
            self.wifi_qr_label.configure(image=wifi_img)
            self.wifi_qr_label.image = wifi_img

            web_img = ctk.CTkImage(Image.open(generate_qr(self.url)), size=(180, 180))
            self.web_qr_label.configure(image=web_img)
            self.web_qr_label.image = web_img
        except Exception as e:
            print(f"QR error: {e}")

    # ---- FILE CHECKING ----
    def check_files(self):
        if pending_files:
            file = pending_files.pop(0)
            self._received_count += 1
            self.received_label.configure(text=f"{self._received_count} archivo{'s' if self._received_count != 1 else ''} recibido{'s' if self._received_count != 1 else ''}")

            def on_accept():
              try:
                  decrypted_bytes = decrypt_aes(file["data"], self.key)
                  safe_name = os.path.basename(file["name"])
                  path = os.path.join(UPLOAD_FOLDER, safe_name)
                  with open(path, "wb") as f_out:
                      f_out.write(decrypted_bytes)
                  self._add_history_row(file, "Guardado")
              except Exception as e:
                  print(f"Error: {e}")
                  self._add_history_row(file, "Error")


            def on_reject():
                self._add_history_row(file, "Rechazado")

            FilePopup(self, file, on_accept, on_reject)

        self.after(1000, self.check_files)


# =========================
# RUN
# =========================
def run_flask():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    gui = App()
    gui.mainloop()