import os, threading, time, requests, uuid, pandas as pd
import os

from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import create_engine, text
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps

# ---------- Flask config ----------
app = Flask(__name__)
app.secret_key = "supersecretkey123"

# ---------- Session config ----------
app.config.update(
    PERMANENT_SESSION_LIFETIME=3600,       # 1 giờ timeout
    SESSION_COOKIE_SECURE=True,            # bắt buộc HTTPS
    SESSION_COOKIE_SAMESITE="None",        # cho phép cross-site cookie
    SESSION_COOKIE_HTTPONLY=True
)

# ---------- Database config ----------
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://vinhnguyen:uDpQGHxIAMFtuWlXztNE86cDAXmNF4VH@dpg-d2m1nljuibrs73fo7dig-a.oregon-postgres.render.com/db_tracnghiemhq"
)
engine = create_engine(DATABASE_URL, echo=False)

# ---------- Ping thread tránh Render ngủ đông ----------
def ping_server():
    while True:
        try:
            url = os.getenv("PING_URL", "https://tracnghiemhq.onrender.com")
            requests.get(url)
        except Exception as e:
            print("Ping error:", e)
        time.sleep(600)

threading.Thread(target=ping_server, daemon=True).start()

# ---------- Decorator kiểm tra đăng nhập ----------
def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "username" not in session or "session_id" not in session:
            flash("Bạn chưa đăng nhập!", "error")
            return redirect(url_for("login"))

        username = session["username"]
        sid = session["session_id"]

        with engine.connect() as conn:
            user = conn.execute(
                text("SELECT ten_thiet_bi FROM Nguoidung WHERE username=:u"),
                {"u": username}
            ).mappings().first()

        if not user:
            session.clear()
            flash("Tài khoản không tồn tại!", "error")
            return redirect(url_for("login"))

        if user["ten_thiet_bi"] != sid:
            session.clear()
            flash("Bạn đã đăng nhập tài khoản này trên thiết bị khác!", "error")
            return redirect(url_for("login"))

        return f(*args, **kwargs)
    return wrapper

# ---------- Trang mặc định ----------
@app.route('/')
def home():
    return redirect(url_for('login'))

# ---------- Đăng nhập ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        with engine.connect() as conn:
            user = conn.execute(
                text("SELECT * FROM Nguoidung WHERE username=:u"),
                {"u": username}
            ).mappings().first()

        if user and check_password_hash(user["password_hash"], password):
            session_id = str(uuid.uuid4())
            session.permanent = True
            session['username'] = user["username"]
            session['ten_thuc'] = user.get("ten_thuc", "Người dùng")
            session['is_admin'] = user.get("is_admin", False)
            session['session_id'] = session_id

            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE Nguoidung SET ten_thiet_bi=:sid WHERE username=:u"),
                    {"sid": session_id, "u": username}
                )
            return redirect(url_for('index'))
        else:
            flash("Sai tài khoản hoặc mật khẩu!")

    return render_template('login.html')

# ---------- Đăng ký ----------
@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    display_name = request.form.get('display_name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    company = request.form.get('company')

    if not username or not password:
        flash("Thiếu thông tin bắt buộc!")
        return redirect(url_for('login'))

    with engine.begin() as conn:
        exist = conn.execute(
            text("SELECT 1 FROM Nguoidung WHERE username=:u OR email=:e"),
            {"u": username, "e": email}
        ).first()
        if exist:
            flash("Tên đăng nhập hoặc Email đã tồn tại!")
            return redirect(url_for('login'))

        pw_hash = generate_password_hash(password)
        conn.execute(text("""
            INSERT INTO Nguoidung 
            (username, password_hash, ten_thuc, so_dien_thoai, email, cong_ty)
            VALUES (:u, :p, :t, :ph, :e, :c)
        """), {
            "u": username, "p": pw_hash, "t": display_name,
            "ph": phone, "e": email, "c": company
        })

    flash("Đăng ký thành công, vui lòng đăng nhập!")
    return redirect(url_for('login'))

# ---------- Quên mật khẩu ----------
@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    flash("Chức năng này đang cập nhật, hãy liên hệ Admin để lấy lại mật khẩu.")
    return redirect(url_for('login'))

# ---------- Đăng xuất ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ---------- Trang chính ----------
@app.route('/index')
@require_login
def index():
    return render_template(
        'index.html',
        ten_thuc=session.get("ten_thuc", "Người dùng"),
        is_admin=session.get("is_admin") or False
    )

# ---------- Trang Tài khoản ----------
@app.route('/tai-khoan', methods=['GET', 'POST'])
@require_login
def tai_khoan():
    username = session['username']
    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT * FROM Nguoidung WHERE username=:u"),
            {"u": username}
        ).mappings().first()
    return render_template("tai_khoan.html", user=user)

# ---------- Quản trị ----------
@app.route('/quan-tri')
@require_login
def quan_tri():
    if not session.get("is_admin"):
        return "Bạn không có quyền truy cập!"
    return render_template("admin.html")

#--- Tổng hợp kiến thức -----
@app.route("/tong-hop-kien-thuc")
@require_login
def tong_hop_kien_thuc():
    return render_template("tong_hop_kien_thuc.html")

#----- Ôn Tập ------
@app.route("/on-tap")
@require_login
def on_tap():
    return render_template("on_tap.html")


# ---------- Nhập bộ đề thi ----------
@app.route('/nhap-bodethi', methods=['GET', 'POST'])
@require_login
def nhap_bodethi():
    if request.method == "POST":
        file = request.files.get("file")
        if file:
            filepath = os.path.join("uploads", file.filename)
            os.makedirs("uploads", exist_ok=True)
            file.save(filepath)
            df = pd.read_excel(filepath)
            # TODO: cập nhật DB
            flash("Đã cập nhật bộ đề thi!", "success")
            return redirect(url_for("quan_tri"))
    return render_template("nhap_bodethi.html")

# ---------- Thi thử ----------
@app.route('/thi-thu', methods=['GET', 'POST'])
@require_login
def thi_thu():
    # TODO: code thi thử giữ nguyên của bạn
    return render_template("thi_thu.html")

# ---------- Thanh toán ----------
@app.route('/tao-thanh-toan', methods=['POST'])
@require_login
def tao_thanh_toan():
    # TODO: code xử lý thanh toán bạn đã viết trước đó
    return {"status": "ok"}

@app.route("/thanh-toan")
@require_login
def thanh_toan_page():
    return render_template("thanh_toan.html", username=session["username"])




if __name__ == "__main__":
    app.run(debug=True)
