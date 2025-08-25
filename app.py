import threading
import time
import requests
import pandas as pd
from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import check_password_hash
from sqlalchemy import create_engine, text

app = Flask(__name__)
app.secret_key = "supersecret"

# ---------- Database config ----------
DATABASE_URL = "postgresql+psycopg2://vinhnguyen:uDpQGHxIAMFtuWlXztNE86cDAXmNF4VH@dpg-d2m1nljuibrs73fo7dig-a.oregon-postgres.render.com/db_tracnghiemhq"
engine = create_engine(DATABASE_URL, echo=False)

# ---------- Trang đăng nhập ----------
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM Nguoidung WHERE username=:u"), {"u": username}).fetchone()

        if result and check_password_hash(result.password, password):
            session["user"] = result.username
            session["role"] = result.role
            return redirect(url_for("dashboard"))
        else:
            flash("Sai tài khoản hoặc mật khẩu!")

    return render_template("index.html")

# ---------- Trang dashboard ----------
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("index"))
    return render_template("dashboard.html", user=session["user"], role=session["role"])

# ---------- Admin: Quản trị người dùng ----------
@app.route("/admin/users")
def admin_users():
    if session.get("role") != "admin":
        return "Không có quyền!"
    with engine.connect() as conn:
        users = conn.execute(text("SELECT id, username, role FROM Nguoidung")).fetchall()
    return render_template("admin_users.html", users=users)

# ---------- Nhập bộ đề thi từ Excel ----------
@app.route("/upload_bodethi", methods=["GET", "POST"])
def upload_bodethi():
    if "user" not in session:
        return redirect(url_for("index"))
    if request.method == "POST":
        file = request.files["file"]
        if file:
            df = pd.read_excel(file)

            with engine.begin() as conn:
                # Xóa dữ liệu cũ
                conn.execute(text("DELETE FROM Bodethi"))

                # Ghi dữ liệu mới
                for _, row in df.iterrows():
                    conn.execute(text("""
                        INSERT INTO Bodethi (mamon, cauhoi, dapan_a, dapan_b, dapan_c, dapan_d, dapan_dung, ghichu)
                        VALUES (:m, :c, :a, :b, :c1, :d, :dd, :g)
                    """), {
                        "m": row["mamon"],
                        "c": row["cauhoi"],
                        "a": row["dapan_a"],
                        "b": row["dapan_b"],
                        "c1": row["dapan_c"],
                        "d": row["dapan_d"],
                        "dd": row["dapan_dung"],
                        "g": row.get("ghichu", "")
                    })
            flash("Đã nhập bộ đề thi thành công!")
            return redirect(url_for("dashboard"))
    return render_template("upload_bodethi.html")

# ---------- Thi thử ----------
@app.route("/thithu", methods=["GET", "POST"])
def thithu():
    if "user" not in session:
        return redirect(url_for("index"))

    with engine.connect() as conn:
        monthi = conn.execute(text("SELECT mamon, tenmon FROM Monthi")).fetchall()

    if request.method == "POST":
        mamon = request.form["mamon"]
        with engine.connect() as conn:
            questions = conn.execute(text("SELECT * FROM Bodethi WHERE mamon=:m"), {"m": mamon}).fetchall()
        return render_template("thi.html", questions=questions)

    return render_template("chon_monthi.html", monthi=monthi)

# ---------- Ping endpoint ----------
@app.route("/ping")
def ping():
    return "ok", 200

# ---------- Đăng xuất ----------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

# ---------- Keep-alive thread ----------
def keep_alive():
    while True:
        try:
            url = "https://your-app-name.onrender.com/ping"  # đổi thành URL thật của app Render
            requests.get(url, timeout=10)
            print("Ping thành công:", url)
        except Exception as e:
            print("Ping lỗi:", e)
        time.sleep(600)  # 600 giây = 10 phút

# ---------- Run ----------
if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=True)
