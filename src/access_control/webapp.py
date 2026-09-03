"""Panel web de seguridad de GoldenJack."""

import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urljoin

import requests
from flask import Flask, abort, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from prohibited_store import FACES_DIR, RUNTIME_DIR, alert_history, connection, delete_person, get_person, initialize, latest_alert, people_by_kind, prohibited_people
from settings import load_local_env

load_local_env()
FRIGATE_URL = os.getenv("FRIGATE_URL", "http://127.0.0.1:5000").rstrip("/")
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("WEB_SECRET_KEY", secrets.token_hex(32)),
    MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
initialize()


def logged_in(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def cameras():
    try:
        response = requests.get(f"{FRIGATE_URL}/api/config", timeout=4)
        response.raise_for_status()
        config = response.json()
        configured = config.get("cameras", {})
        return sorted(configured.keys()) if isinstance(configured, dict) else []
    except requests.RequestException:
        return []


def has_allowed_extension(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
@logged_in
def dashboard():
    available_cameras = cameras()
    selected = request.args.get("camera")
    if selected not in available_cameras:
        selected = available_cameras[0] if available_cameras else None
    return render_template("dashboard.html", cameras=available_cameras, selected_camera=selected,
                           prohibited=prohibited_people(), excluded=people_by_kind("excluded"),
                           alert=latest_alert(), frigate_online=bool(available_cameras))


@app.get("/prohibidos")
@logged_in
def prohibited_list():
    return render_template("people_list.html", kind="prohibited", people=prohibited_people())


@app.get("/autoexcluidos")
@logged_in
def excluded_list():
    return render_template("people_list.html", kind="excluded", people=people_by_kind("excluded"))


@app.get("/historia-prohibidos")
@logged_in
def prohibited_history():
    return render_template("history.html", history=alert_history())


@app.route("/personas/nuevo/<kind>", methods=["GET", "POST"])
@logged_in
def add_person(kind):
    if kind not in {"prohibited", "excluded"}:
        abort(404)
    if request.method == "GET":
        return render_template("person_form.html", kind=kind)
    name = request.form.get("name", "").strip()
    reason = request.form.get("reason", "").strip() if kind == "prohibited" else None
    reported_by = request.form.get("reported_by", "").strip() if kind == "prohibited" else None
    effective_date = request.form.get("effective_date", "").strip()
    image = request.files.get("image")
    if not name or not effective_date or not image or not has_allowed_extension(image.filename) or (kind == "prohibited" and (not reason or not reported_by)):
        flash("Completá todos los campos obligatorios y cargá una imagen JPG, PNG o WEBP.", "error")
        return render_template("person_form.html", kind=kind), 400
    extension = secure_filename(image.filename).rsplit(".", 1)[1].lower()
    filename = f"{secrets.token_hex(16)}.{extension}"
    image.save(FACES_DIR / filename)
    with connection() as db:
        db.execute("""INSERT INTO people(name, reason, reported_by, effective_date, kind, image_path, created_at)
                      VALUES (?, ?, ?, ?, ?, ?, ?)""",
                   (name, reason, reported_by, effective_date, kind, filename, datetime.now().isoformat()))
    flash("Perfil guardado y disponible para el reconocimiento en hasta 30 segundos.", "success")
    return redirect(url_for("prohibited_list" if kind == "prohibited" else "excluded_list"))


@app.get("/personas/<int:person_id>")
@logged_in
def person_detail(person_id):
    person = get_person(person_id)
    if person is None:
        abort(404)
    return render_template("person_detail.html", person=person)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        with connection() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("auth.html", mode="login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Completá los datos y usá una contraseña de al menos 8 caracteres.", "error")
        else:
            try:
                with connection() as db:
                    db.execute("INSERT INTO users(name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                               (name, email, generate_password_hash(password), datetime.now().isoformat()))
                flash("Cuenta creada. Ya podés iniciar sesión.", "success")
                return redirect(url_for("login"))
            except Exception:
                flash("Ese correo ya está registrado.", "error")
    return render_template("auth.html", mode="register")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        token = secrets.token_urlsafe(32)
        with connection() as db:
            user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if user:
                db.execute("UPDATE users SET reset_token = ?, reset_expires_at = ? WHERE id = ?",
                           (token, (datetime.now() + timedelta(minutes=30)).isoformat(), user["id"]))
                # En producción, enviar esta URL por el proveedor de correo configurado.
                app.logger.info("Restablecimiento solicitado: %s", url_for("reset_password", token=token, _external=True))
        flash("Si el correo existe, se envió el enlace de recuperación.", "success")
        return redirect(url_for("login"))
    return render_template("auth.html", mode="forgot")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    with connection() as db:
        user = db.execute("SELECT * FROM users WHERE reset_token = ?", (token,)).fetchone()
    if not user or datetime.fromisoformat(user["reset_expires_at"]) < datetime.now():
        abort(404)
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("La contraseña debe tener al menos 8 caracteres.", "error")
        else:
            with connection() as db:
                db.execute("UPDATE users SET password_hash = ?, reset_token = NULL, reset_expires_at = NULL WHERE id = ?",
                           (generate_password_hash(password), user["id"]))
            flash("Contraseña actualizada. Iniciá sesión.", "success")
            return redirect(url_for("login"))
    return render_template("auth.html", mode="reset")


@app.post("/personas/<int:person_id>/eliminar")
@logged_in
def remove_person(person_id):
    person, alert_images = delete_person(person_id)
    if person is None:
        abort(404)
    face_path = FACES_DIR / person["image_path"]
    if face_path.is_file():
        face_path.unlink()
    for image_path in alert_images:
        alert_path = (RUNTIME_DIR / image_path).resolve()
        if RUNTIME_DIR.resolve() in alert_path.parents and alert_path.is_file():
            alert_path.unlink()
    flash("Perfil, foto y capturas históricas eliminados permanentemente.", "success")
    return redirect(url_for("prohibited_list" if person["kind"] == "prohibited" else "excluded_list"))


@app.route("/media/<path:filename>")
@logged_in
def media(filename):
    # Las capturas de alertas viven en runtime y no se exponen sin sesión.
    requested = (RUNTIME_DIR / filename).resolve()
    if RUNTIME_DIR.resolve() not in requested.parents and requested != RUNTIME_DIR.resolve():
        abort(404)
    return send_from_directory(requested.parent, requested.name)


@app.route("/face/<path:filename>")
@logged_in
def face_image(filename):
    return send_from_directory(FACES_DIR, filename)


@app.route("/frigate/cameras/<camera>/latest.jpg")
@logged_in
def camera_image(camera):
    if camera not in cameras():
        abort(404)
    try:
        upstream = requests.get(f"{FRIGATE_URL}/api/{camera}/latest.jpg", timeout=8)
        upstream.raise_for_status()
    except requests.RequestException:
        abort(503)
    from flask import Response
    return Response(upstream.content, content_type=upstream.headers.get("Content-Type", "image/jpeg"),
                    headers={"Cache-Control": "no-store"})


@app.get("/alerts/latest")
@logged_in
def latest_alert_api():
    row = latest_alert()
    return {"alert": dict(row) if row else None}


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("WEB_PORT", "8080")), debug=os.getenv("FLASK_DEBUG") == "1")
