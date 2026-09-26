import io
import os
import pickle
import uuid
import face_recognition
from flask import (
    Flask, flash, redirect, render_template_string,
    request, send_from_directory, session, url_for, abort, make_response
)
import qrcode
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix

# Automated tunneling for mobile access
from pyngrok import ngrok

app = Flask(__name__)
app.secret_key = "super-secret-event-key-2026"
VIP_ACCESS_CODE = "VIP2026"

# Ensure Flask generates HTTPS links when running behind ngrok proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# --- NGROK INTERSTITIAL BYPASS HOOKS ---
@app.after_request
def add_ngrok_bypass_headers(response):
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response

@app.route("/entry")
def ngrok_auto_bypass():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="0; url=/guest">
        <script>
            document.cookie = "ngrok-skip-browser-warning=true; path=/; max-age=31536000";
            window.location.replace("/guest");
        </script>
    </head>
    <body style="background:#0a0f1a; color:#fff; display:flex; align-items:center; justify-content:center; height:100vh; font-family:sans-serif;">
        <p>Connecting to Photo Share...</p>
    </body>
    </html>
    """
    resp = make_response(html)
    resp.set_cookie("ngrok-skip-browser-warning", "true", max_age=31536000, path="/")
    return resp

# Directory Structure
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")

EVENT_PHOTOS_DIR = os.path.join(UPLOAD_ROOT, "public", "photos")
EVENT_VIDEOS_DIR = os.path.join(UPLOAD_ROOT, "public", "videos")
SPECIAL_PHOTOS_DIR = os.path.join(UPLOAD_ROOT, "special", "photos")
SPECIAL_VIDEOS_DIR = os.path.join(UPLOAD_ROOT, "special", "videos")
SELFIES_DIR = os.path.join(UPLOAD_ROOT, "selfies")
CACHE_DIR = os.path.join(UPLOAD_ROOT, "cache")

for folder in [
    EVENT_PHOTOS_DIR, EVENT_VIDEOS_DIR,
    SPECIAL_PHOTOS_DIR, SPECIAL_VIDEOS_DIR,
    SELFIES_DIR, CACHE_DIR
]:
    os.makedirs(folder, exist_ok=True)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

PUBLIC_CACHE_PATH = os.path.join(CACHE_DIR, "public_encodings.pkl")
SPECIAL_CACHE_PATH = os.path.join(CACHE_DIR, "special_encodings.pkl")


def load_cache(filepath):
    if os.path.exists(filepath):
        try:
            with open(filepath, "rb") as f:
                return pickle.load(f)
        except Exception:
            return {}
    return {}


def save_cache(data, filepath):
    with open(filepath, "wb") as f:
        pickle.dump(data, f)


PUBLIC_PHOTO_ENCODINGS = load_cache(PUBLIC_CACHE_PATH)
SPECIAL_PHOTO_ENCODINGS = load_cache(SPECIAL_CACHE_PATH)


def get_file_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext in IMAGE_EXTENSIONS:
        return "photo"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


# --- HTML Templates ---

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>AllPhoto Admin Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 1.5rem; color: #fff; min-height: 100vh;
            background: linear-gradient(rgba(10, 13, 22, 0.88), rgba(10, 13, 22, 0.94)),
                        url('https://images.unsplash.com/photo-1519741497674-611481863552?auto=format&fit=crop&w=1920&q=80') center/cover fixed no-repeat;
        }
        .container { max-width: 960px; margin: auto; }
        h1 { color: #00d2ff; text-transform: uppercase; letter-spacing: 1px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px; margin-top: 1.5rem; }
        .card {
            background: rgba(21, 26, 40, 0.75); backdrop-filter: blur(10px);
            border: 1px solid rgba(0, 210, 255, 0.25); border-radius: 14px;
            padding: 1.75rem; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.37);
        }
        .special { border-color: rgba(255, 215, 0, 0.4); box-shadow: 0 8px 32px rgba(255, 215, 0, 0.1); }
        .special h3 { color: #ffd700; }
        input[type="file"] { margin: 1rem 0; width: 100%; color: #cbd5e1; }
        button {
            background: linear-gradient(135deg, #00d2ff, #0077ff);
            color: #fff; font-weight: bold; border: none; padding: 12px 18px;
            border-radius: 8px; cursor: pointer; width: 100%; transition: opacity 0.2s;
        }
        button:hover { opacity: 0.9; }
        .btn-gold { background: linear-gradient(135deg, #ffd700, #ff9900); color: #000; }
        .stats { margin-top: 12px; font-size: 0.85rem; color: #94a3b8; }
        .qr-card {
            text-align: center; margin-top: 2rem; background: rgba(21, 26, 40, 0.75);
            backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 2rem; border-radius: 14px;
        }
        a { color: #00d2ff; text-decoration: none; font-weight: 500; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>AllPhoto Event Admin</h1>
        <p style="color: #94a3b8;">Upload photos/videos. Encrypted QR codes below direct guests right to mobile access.</p>

        <div class="grid">
            <div class="card">
                <h3 style="color: #00d2ff; margin-top: 0;">General Event Media</h3>
                <p style="font-size: 0.9rem; color: #cbd5e1;">Upload public event pictures & videos (AI face-scan enabled).</p>
                <form action="{{ url_for('upload_public_media') }}" method="post" enctype="multipart/form-data">
                    <input type="file" name="files" multiple accept="image/*,video/*" required>
                    <button type="submit">Upload Public Media</button>
                </form>
                <div class="stats">Photos: {{ public_photos }} | Videos: {{ public_videos }}</div>
            </div>

            <div class="card special">
                <h3 style="margin-top: 0;">Special Guests Vault (VIP)</h3>
                <p style="font-size: 0.9rem; color: #cbd5e1;">Passcode protected vault (Code: <code>{{ vip_code }}</code>).</p>
                <form action="{{ url_for('upload_special_media') }}" method="post" enctype="multipart/form-data">
                    <input type="file" name="files" multiple accept="image/*,video/*" required>
                    <button type="submit" class="btn-gold">Upload to VIP Vault</button>
                </form>
                <div class="stats">Special Photos: {{ special_photos }} | Special Videos: {{ special_videos }}</div>
            </div>
        </div>

        <div class="qr-card">
            <h3 style="margin-top: 0;">Scan from Android / Mobile Data</h3>
            <div style="display: flex; justify-content: space-around; flex-wrap: wrap; gap: 20px; margin-top: 1.5rem;">
                <div>
                    <p><strong>Standard Guest Portal</strong></p>
                    <img src="{{ url_for('get_qr', target='public') }}" width="160" style="background:#fff; padding:6px; border-radius:10px;">
                    <p><a href="{{ url_for('ngrok_auto_bypass', _external=True) }}" target="_blank">Direct Mobile Link &rarr;</a></p>
                </div>
                <div>
                    <p><strong style="color: #ffd700;">VIP Guest Portal</strong></p>
                    <img src="{{ url_for('get_qr', target='vip') }}" width="160" style="background:#fff; padding:6px; border-radius:10px;">
                    <p><a href="{{ url_for('vip_login', _external=True) }}" target="_blank" style="color: #ffd700;">Direct VIP Link &rarr;</a></p>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

GUEST_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Find My Photos - AllPhoto</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 1.5rem; color: #fff; min-height: 100vh;
            display: flex; align-items: center; justify-content: center;
            background: linear-gradient(rgba(10, 15, 26, 0.85), rgba(10, 15, 26, 0.95)),
                        url('https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=1920&q=80') center/cover fixed no-repeat;
        }
        .box {
            background: rgba(20, 25, 38, 0.9); backdrop-filter: blur(14px);
            border: 1px solid rgba(0, 210, 255, 0.3); border-radius: 16px;
            max-width: 420px; width: 100%; padding: 2rem; text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.6); box-sizing: border-box;
        }
        h2 { color: #00d2ff; margin-top: 0; }
        button {
            background: linear-gradient(135deg, #00d2ff, #0077ff); color: #fff;
            border: none; padding: 14px 24px; font-weight: bold; font-size: 1rem;
            border-radius: 8px; cursor: pointer; width: 100%; margin-top: 1rem;
        }
        input[type="file"] { margin: 1.5rem 0; width: 100%; font-size: 0.9rem; }
        a { color: #ffd700; text-decoration: none; font-size: 0.9rem; display: inline-block; margin-top: 1.5rem; }
        .loading { display: none; margin-top: 1rem; color: #00d2ff; font-weight: 500; }
    </style>
</head>
<body>
    <div class="box">
        <h2>Find Your Photos</h2>
        <p style="color: #94a3b8; font-size: 0.95rem;">Snap a clear selfie using your camera. Our AI scans all photos taken at the event.</p>
        <form action="{{ url_for('match_selfie') }}" method="post" enctype="multipart/form-data" onsubmit="document.getElementById('load-txt').style.display='block';">
            <input type="file" name="selfie" accept="image/*" capture="user" required>
            <button type="submit">Scan & Retrieve Photos</button>
            <div id="load-txt" class="loading">Searching photos with AI... please wait</div>
        </form>
        <a href="{{ url_for('vip_login') }}">VIP or Special Guest? Unlock here &rarr;</a>
    </div>
</body>
</html>
"""

VIP_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>VIP Access - AllPhoto</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 1.5rem; color: #fff; min-height: 100vh;
            display: flex; align-items: center; justify-content: center;
            background: linear-gradient(rgba(12, 10, 5, 0.85), rgba(12, 10, 5, 0.92)),
                        url('https://images.unsplash.com/photo-1511578314322-379afb476865?auto=format&fit=crop&w=1920&q=80') center/cover fixed no-repeat;
        }
        .box {
            background: rgba(26, 23, 16, 0.9); backdrop-filter: blur(14px);
            border: 1px solid rgba(255, 215, 0, 0.4); border-radius: 16px;
            max-width: 380px; width: 100%; padding: 2rem; text-align: center;
            box-shadow: 0 10px 40px rgba(0,0,0,0.7); box-sizing: border-box;
        }
        h2 { color: #ffd700; margin-top: 0; }
        input[type="password"] {
            padding: 12px; width: 80%; border-radius: 8px; border: 1px solid #ffd700;
            background: rgba(0,0,0,0.6); color: #fff; margin: 1.2rem 0;
            text-align: center; font-size: 1.2rem; letter-spacing: 2px;
        }
        button {
            background: linear-gradient(135deg, #ffd700, #ff9900); color: #000;
            font-weight: bold; font-size: 1rem; border: none; padding: 12px 24px;
            border-radius: 8px; cursor: pointer; width: 90%;
        }
        .error { color: #ff5252; font-size: 0.9rem; margin-bottom: 0.5rem; }
    </style>
</head>
<body>
    <div class="box">
        <h2>VIP Special Vault</h2>
        <p style="color: #d1c7a7; font-size: 0.95rem;">Enter the security passcode to access private event photos.</p>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
        <form method="post">
            <input type="password" name="pin" placeholder="••••••••" required><br>
            <button type="submit">Unlock Gallery</button>
        </form>
    </div>
</body>
</html>
"""

VIP_VAULT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>VIP Special Vault</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 1.5rem; color: #fff; min-height: 100vh;
            background: linear-gradient(rgba(10, 9, 6, 0.92), rgba(10, 9, 6, 0.96)),
                        url('https://images.unsplash.com/photo-1511578314322-379afb476865?auto=format&fit=crop&w=1920&q=80') center/cover fixed no-repeat;
        }
        h1, h2 { color: #ffd700; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; margin: 1.5rem 0 3rem; }
        .card {
            background: rgba(26, 23, 16, 0.7); border: 1px solid rgba(255, 215, 0, 0.3);
            border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.5);
        }
        img, video { width: 100%; height: 220px; object-fit: cover; display: block; }
        .topbar { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 215, 0, 0.25); padding-bottom: 1rem; }
        a.btn { background: rgba(255, 255, 255, 0.1); border: 1px solid #ffd700; color: #ffd700; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-size: 0.9rem; }
    </style>
</head>
<body>
    <div class="topbar">
        <h1 style="font-size: 1.4rem;">VIP Private Collection</h1>
        <a href="{{ url_for('vip_logout') }}" class="btn">Logout</a>
    </div>

    <h2>Special Pictures</h2>
    <div class="grid">
        {% for photo in photos %}
        <div class="card">
            <a href="{{ url_for('serve_special_photo', filename=photo) }}" target="_blank">
                <img src="{{ url_for('serve_special_photo', filename=photo) }}" alt="VIP Photo">
            </a>
        </div>
        {% else %}
        <p style="color: #94a3b8;">No special photos uploaded yet.</p>
        {% endfor %}
    </div>

    <h2>Special Videos</h2>
    <div class="grid">
        {% for video in videos %}
        <div class="card">
            <video controls preload="metadata">
                <source src="{{ url_for('serve_special_video', filename=video) }}">
            </video>
        </div>
        {% else %}
        <p style="color: #94a3b8;">No special videos uploaded yet.</p>
        {% endfor %}
    </div>
</body>
</html>
"""

GALLERY_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Your Personal Gallery</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 1.5rem; color: #fff; min-height: 100vh;
            background: linear-gradient(rgba(10, 15, 26, 0.9), rgba(10, 15, 26, 0.96)),
                        url('https://images.unsplash.com/photo-1492684223066-81342ee5ff30?auto=format&fit=crop&w=1920&q=80') center/cover fixed no-repeat;
        }
        h1 { color: #00d2ff; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; margin-top: 1.5rem; }
        .card {
            background: rgba(20, 25, 38, 0.7); border: 1px solid rgba(0, 210, 255, 0.3);
            border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.5);
        }
        img { width: 100%; height: 240px; object-fit: cover; display: block; }
        a.back { color: #00d2ff; text-decoration: none; display: inline-block; margin-top: 2rem; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Your Event Matches</h1>
    <p style="color: #cbd5e1;">Found <strong>{{ matches|length }}</strong> photos matching your face.</p>
    
    <div class="grid">
        {% for photo in matches %}
        <div class="card">
            <a href="{{ url_for('serve_public_photo', filename=photo) }}" target="_blank">
                <img src="{{ url_for('serve_public_photo', filename=photo) }}" alt="Matched Photo">
            </a>
        </div>
        {% endfor %}
    </div>

    {% if not matches %}
        <p style="margin-top: 2rem; color: #94a3b8;">No matching photos found. Make sure your selfie is well-lit and faces forward.</p>
    {% endif %}

    <a class="back" href="{{ url_for('guest_lookup') }}">&larr; Scan another selfie</a>
</body>
</html>
"""


# --- Routes ---

@app.route("/")
def admin_dashboard():
    return render_template_string(
        ADMIN_HTML,
        public_photos=len(os.listdir(EVENT_PHOTOS_DIR)),
        public_videos=len(os.listdir(EVENT_VIDEOS_DIR)),
        special_photos=len(os.listdir(SPECIAL_PHOTOS_DIR)),
        special_videos=len(os.listdir(SPECIAL_VIDEOS_DIR)),
        vip_code=VIP_ACCESS_CODE
    )


@app.route("/admin/upload-public", methods=["POST"])
def upload_public_media():
    files = request.files.getlist("files")
    updated = False
    for file in files:
        if not file.filename:
            continue
        clean_name = secure_filename(file.filename)
        ftype = get_file_type(clean_name)
        filename = f"{uuid.uuid4().hex}_{clean_name}"

        if ftype == "photo":
            save_path = os.path.join(EVENT_PHOTOS_DIR, filename)
            file.save(save_path)
            img = face_recognition.load_image_file(save_path)
            PUBLIC_PHOTO_ENCODINGS[filename] = face_recognition.face_encodings(img)
            updated = True

        elif ftype == "video":
            save_path = os.path.join(EVENT_VIDEOS_DIR, filename)
            file.save(save_path)

    if updated:
        save_cache(PUBLIC_PHOTO_ENCODINGS, PUBLIC_CACHE_PATH)

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/upload-special", methods=["POST"])
def upload_special_media():
    files = request.files.getlist("files")
    updated = False
    for file in files:
        if not file.filename:
            continue
        clean_name = secure_filename(file.filename)
        ftype = get_file_type(clean_name)
        filename = f"{uuid.uuid4().hex}_{clean_name}"

        if ftype == "photo":
            save_path = os.path.join(SPECIAL_PHOTOS_DIR, filename)
            file.save(save_path)
            img = face_recognition.load_image_file(save_path)
            SPECIAL_PHOTO_ENCODINGS[filename] = face_recognition.face_encodings(img)
            updated = True

        elif ftype == "video":
            save_path = os.path.join(SPECIAL_VIDEOS_DIR, filename)
            file.save(save_path)

    if updated:
        save_cache(SPECIAL_PHOTO_ENCODINGS, SPECIAL_CACHE_PATH)

    return redirect(url_for("admin_dashboard"))


@app.route("/guest")
def guest_lookup():
    return render_template_string(GUEST_HTML)


@app.route("/match-selfie", methods=["POST"])
def match_selfie():
    selfie = request.files.get("selfie")
    if not selfie or not selfie.filename:
        return redirect(url_for("guest_lookup"))

    clean_name = secure_filename(selfie.filename)
    path = os.path.join(SELFIES_DIR, f"{uuid.uuid4().hex}_{clean_name}")
    selfie.save(path)

    guest_img = face_recognition.load_image_file(path)
    encodings = face_recognition.face_encodings(guest_img)

    matches = []
    if encodings:
        target = encodings[0]
        for name, photo_encodings in PUBLIC_PHOTO_ENCODINGS.items():
            if photo_encodings and any(face_recognition.compare_faces(photo_encodings, target, tolerance=0.55)):
                matches.append(name)

    return render_template_string(GALLERY_HTML, matches=matches)


@app.route("/vip", methods=["GET", "POST"])
def vip_login():
    error = None
    if request.method == "POST":
        pin = request.form.get("pin")
        if pin == VIP_ACCESS_CODE:
            session["is_vip"] = True
            return redirect(url_for("vip_vault"))
        error = "Invalid VIP Passcode. Please try again."

    return render_template_string(VIP_LOGIN_HTML, error=error)


@app.route("/vip/vault")
def vip_vault():
    if not session.get("is_vip"):
        return redirect(url_for("vip_login"))

    photos = [f for f in os.listdir(SPECIAL_PHOTOS_DIR) if get_file_type(f) == "photo"]
    videos = [f for f in os.listdir(SPECIAL_VIDEOS_DIR) if get_file_type(f) == "video"]
    return render_template_string(VIP_VAULT_HTML, photos=photos, videos=videos)


@app.route("/vip/logout")
def vip_logout():
    session.pop("is_vip", None)
    return redirect(url_for("guest_lookup"))


@app.route("/qr/<target>")
def get_qr(target):
    # QR code points directly to /entry to bypass the ngrok warning
    endpoint = url_for("vip_login" if target == "vip" else "ngrok_auto_bypass", _external=True)

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(endpoint)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue(), 200, {"Content-Type": "image/png"}


@app.route("/media/public/photos/<filename>")
def serve_public_photo(filename):
    return send_from_directory(EVENT_PHOTOS_DIR, secure_filename(filename))


@app.route("/media/public/videos/<filename>")
def serve_public_video(filename):
    return send_from_directory(EVENT_VIDEOS_DIR, secure_filename(filename))


@app.route("/media/special/photos/<filename>")
def serve_special_photo(filename):
    if not session.get("is_vip"):
        abort(403)
    return send_from_directory(SPECIAL_PHOTOS_DIR, secure_filename(filename))


@app.route("/media/special/videos/<filename>")
def serve_special_video(filename):
    if not session.get("is_vip"):
        abort(403)
    return send_from_directory(SPECIAL_VIDEOS_DIR, secure_filename(filename))


if __name__ == "__main__":
    try:
        ngrok.set_auth_token("3Js97R5RIIS2uqlwvX2emIIyd9G_4xL3WJMAjCu9HHoQTXvkU")
        public_url = ngrok.connect(5000).public_url
        print("\n" + "=" * 60)
        print(" PUBLIC MOBILE ACCESS IS LIVE! ")
        print(f" Web URL: {public_url}")
        print(f" Direct Guest Entry: {public_url}/entry")
        print(" Anyone on Mobile Data / 4G / 5G can now access this link!")
        print("=" * 60 + "\n")
    except Exception as e:
        print(f"[!] Tunneling initialization: {e}")
        print("Running on local network mode only.")

    app.run(host="0.0.0.0", port=5000, debug=False)