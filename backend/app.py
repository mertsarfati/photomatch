from flask import Flask, request, jsonify, render_template, send_file, send_from_directory
from flask_cors import CORS
import os, json, uuid, shutil
from io import BytesIO
import qrcode
import boto3
from botocore.config import Config

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

UPLOAD_ROOT = os.path.join(app.root_path, "uploads")
DATA_ROOT = os.path.join(app.root_path, "data")
INFO_PATH = os.path.join(app.root_path, "info.json")
USERS_PATH = os.path.join(app.root_path, "users.json")

rekognition = boto3.client("rekognition",
    region_name="eu-central-1",
    aws_access_key_id="AWS_KEY",
    aws_secret_access_key="AWS_SECRET",
    config=Config(signature_version='v4')
)

# Klasörleri ve bilgi dosyalarını oluştur
for path in [UPLOAD_ROOT, DATA_ROOT, app.static_folder, app.template_folder]:
    os.makedirs(path, exist_ok=True)
for path in [INFO_PATH, USERS_PATH]:
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False)

# Giriş ekranı
@app.route("/")
@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    with open(USERS_PATH, "r", encoding="utf-8") as f:
        users = json.load(f)
    if username in users and users[username] == password:
        return jsonify({"success": True, "redirect": f"/admin/{username}"})
    return jsonify({"success": False, "message": "Hatalı giriş"}), 401

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return jsonify({"success": False, "message": "Boş alan olamaz"}), 400
    with open(USERS_PATH, "r+", encoding="utf-8") as f:
        users = json.load(f)
        if username in users:
            return jsonify({"success": False, "message": "Kullanıcı zaten var"}), 409
        users[username] = password
        f.seek(0)
        json.dump(users, f, indent=2, ensure_ascii=False)
        f.truncate()
    return jsonify({"success": True})

# Admin paneli
@app.route("/admin/<username>")
def admin_panel(username):
    return render_template("admin.html", username=username)

# Etkinlik paneli (selfie eşleşme vs.)
@app.route("/event/<event_id>")
def user_panel(event_id):
    return render_template("user_panel.html", event_id=event_id)

# Etkinlik oluştur
@app.route("/create-event", methods=["POST"])
def create_event():
    data = request.get_json()
    name = data.get("name", "Etkinlik")
    name_slug = name.lower().replace(" ", "-")[:12]
    event_id = f"{name_slug}-{uuid.uuid4().hex[:4]}"
    os.makedirs(os.path.join(UPLOAD_ROOT, event_id), exist_ok=True)
    os.makedirs(os.path.join(DATA_ROOT, event_id), exist_ok=True)
    with open(INFO_PATH, "r+", encoding="utf-8") as f:
        info = json.load(f)
        info[event_id] = {"name": name, "location": data.get("location", "")}
        f.seek(0)
        json.dump(info, f, indent=2, ensure_ascii=False)
        f.truncate()
    return jsonify({"id": event_id, "name": name})

# Etkinlik listesi — detaylı şekilde
@app.route("/list-events")
def list_events():
    folders = [name for name in os.listdir(UPLOAD_ROOT) if os.path.isdir(os.path.join(UPLOAD_ROOT, name))]
    with open(INFO_PATH, "r", encoding="utf-8") as f:
        info = json.load(f)
    events = []
    for event_id in folders:
        entry = info.get(event_id, {})
        events.append({
            "id": event_id,
            "name": entry.get("name", event_id),
            "location": entry.get("location", ""),
            "cover": f"/uploads/{event_id}/cover.jpg" if os.path.exists(os.path.join(UPLOAD_ROOT, event_id, "cover.jpg")) else ""
        })
    return jsonify({"events": events})

# Etkinlik bilgisi (tekil)
@app.route("/event-info/<event_id>")
def event_info(event_id):
    with open(INFO_PATH, "r", encoding="utf-8") as f:
        info = json.load(f)
    return jsonify(info.get(event_id, {}))
# Yüklenen fotoğrafı sunma
@app.route("/uploads/<event_id>/<filename>")
def serve_uploaded_image(event_id, filename):
    return send_from_directory(os.path.join(UPLOAD_ROOT, event_id), filename)

# Kapak fotoğrafı yükleme
@app.route("/upload-cover/<event_id>", methods=["POST"])
def upload_cover(event_id):
    file = request.files.get("cover")
    if not file:
        return "No file", 400
    path = os.path.join(UPLOAD_ROOT, event_id, "cover.jpg")
    file.save(path)
    return jsonify({"path": f"/uploads/{event_id}/cover.jpg"})

# Fotoğraf yükleme
@app.route("/upload/<event_id>", methods=["POST"])
def upload_image(event_id):
    file = request.files.get("file")
    if not file:
        return "No file", 400
    name = f"{uuid.uuid4().hex[:8]}.jpg"
    path = os.path.join(UPLOAD_ROOT, event_id, name)
    file.save(path)
    return jsonify({"photo_id": name})

# Fotoğrafları listeleme
@app.route("/photos/<event_id>")
def list_photos(event_id):
    folder = os.path.join(UPLOAD_ROOT, event_id)
    if not os.path.exists(folder):
        return jsonify({"photos": []})
    photos = [f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    return jsonify({"photos": photos})

# Fotoğraf silme
@app.route("/delete-photo/<event_id>/<photo_id>", methods=["DELETE"])
def delete_photo(event_id, photo_id):
    path = os.path.join(UPLOAD_ROOT, event_id, photo_id)
    if os.path.exists(path):
        os.remove(path)
        return "", 204
    return "Not found", 404

# Etkinlik silme
@app.route("/delete-event/<event_id>", methods=["DELETE"])
def delete_event(event_id):
    for folder in [UPLOAD_ROOT, DATA_ROOT]:
        full = os.path.join(folder, event_id)
        if os.path.exists(full):
            shutil.rmtree(full)
    with open(INFO_PATH, "r+", encoding="utf-8") as f:
        info = json.load(f)
        info.pop(event_id, None)
        f.seek(0)
        json.dump(info, f, indent=2, ensure_ascii=False)
        f.truncate()
    return "", 204

# QR kod üretimi
@app.route("/qrcode/<event_id>")
def get_qr(event_id):
    url = request.host_url.rstrip("/") + f"/event/{event_id}"
    qr = qrcode.make(url)
    buffer = BytesIO()
    qr.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")

# İstatistikleri getirme
@app.route("/stats/<event_id>")
def event_stats(event_id):
    file = os.path.join(DATA_ROOT, event_id, "faces.json")
    stats = {"total_faces": 0, "tagged_photos": 0, "female": 0, "male": 0}
    if os.path.exists(file):
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for entry in data:
                faces = entry.get("faces_detected", [])
                stats["total_faces"] += len(faces)
                if any(face.get("user_id") for face in faces):
                    stats["tagged_photos"] += 1
                for face in faces:
                    g = face.get("gender")
                    if g == "female":
                        stats["female"] += 1
                    elif g == "male":
                        stats["male"] += 1
    return jsonify(stats)

# Selfie eşleştirme
@app.route("/match-selfie/<event_id>", methods=["POST"])
def match_selfie(event_id):
    selfie = request.files.get("selfie")
    if not selfie:
        return jsonify({"photos": []})

    selfie_bytes = selfie.read()
    folder = os.path.join(UPLOAD_ROOT, event_id)
    matched = []

    for fname in os.listdir(folder):
        if fname.startswith("cover") or not fname.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        try:
            with open(os.path.join(folder, fname), "rb") as f:
                result = rekognition.compare_faces(
                    SourceImage={"Bytes": selfie_bytes},
                    TargetImage={"Bytes": f.read()},
                    SimilarityThreshold=90
                )
                if result["FaceMatches"]:
                    matched.append(fname)
        except Exception as e:
            print(f"⚠️ Eşleşme hatası ({fname}):", e)
            continue

    return jsonify({"photos": matched})

# Galeri zip olarak indirme
@app.route("/download/<event_id>")
def download_zip(event_id):
    from zipfile import ZipFile
    buffer = BytesIO()
    folder = os.path.join(UPLOAD_ROOT, event_id)
    if not os.path.exists(folder):
        return "Not found", 404
    with ZipFile(buffer, "w") as z:
        for fname in os.listdir(folder):
            if fname.startswith("cover") or not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            z.write(os.path.join(folder, fname), arcname=fname)
    buffer.seek(0)
    return send_file(buffer, mimetype="application/zip", as_attachment=True, download_name="fotograflar.zip")

# Uygulamayı çalıştır
if __name__ == "__main__":
    app.run(debug=True)