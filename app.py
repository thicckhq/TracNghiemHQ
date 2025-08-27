import os
import threading
import time
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash
from sqlalchemy import create_engine, text
from werkzeug.security import check_password_hash, generate_password_hash
import pandas as pd

# ---------- Flask config ----------
app = Flask(__name__)
app.secret_key = "supersecretkey123"   # Cố định key để session không bị reset

# ---------- Session config ----------
app.config.update(
    PERMANENT_SESSION_LIFETIME = 3600,     # session sống 1 giờ
    SESSION_COOKIE_SECURE = True,          # bắt buộc dùng HTTPS
    SESSION_COOKIE_SAMESITE = "None",      # cho phép cookie khi redirect cross-site
    SESSION_COOKIE_HTTPONLY = True         # bảo mật, JS không đọc được cookie
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
                text("SELECT * FROM Nguoidung WHERE username = :u"),
                {"u": username}
            ).mappings().first()

        if user:
            if check_password_hash(user["password_hash"], password):
                session.permanent = True  # giữ session sống lâu
                session['username'] = user["username"]
                session['ten_thuc'] = user.get("ten_thuc", "Người dùng")
                session['is_admin'] = user.get("is_admin", False)
                print("LOGIN OK:", dict(session))  # debug
                return redirect(url_for('index'))
            else:
                flash("Sai mật khẩu!")
        else:
            flash("Không tìm thấy người dùng!")

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
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    print("DEBUG SESSION (index):", dict(session))  # debug
    return render_template(
        'index.html',
        ten_thuc=session.get("ten_thuc", "Người dùng"),
        is_admin=session.get("is_admin") or False
    )

# ---------- Trang Tài khoản ----------
@app.route('/tai-khoan', methods=['GET', 'POST'])
def tai_khoan():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']

    # --- Cập nhật thông tin nếu POST ---
    if request.method == 'POST':
        new_pw = request.form.get('password')
        ten_thuc = request.form.get('ten_thuc')
        so_dien_thoai = request.form.get('so_dien_thoai')
        email = request.form.get('email')

        with engine.begin() as conn:
            if new_pw:
                pw_hash = generate_password_hash(new_pw)
                conn.execute(text("""
                    UPDATE Nguoidung 
                    SET password_hash=:pw, ten_thuc=:t, so_dien_thoai=:sdt, email=:e 
                    WHERE username=:u
                """), {"pw": pw_hash, "t": ten_thuc, "sdt": so_dien_thoai, "e": email, "u": username})
            else:
                conn.execute(text("""
                    UPDATE Nguoidung 
                    SET ten_thuc=:t, so_dien_thoai=:sdt, email=:e 
                    WHERE username=:u
                """), {"t": ten_thuc, "sdt": so_dien_thoai, "e": email, "u": username})

        flash("Cập nhật thông tin thành công!")
        return redirect(url_for('tai_khoan'))

    # --- Lấy lại thông tin user ---
    with engine.connect() as conn:
        user = conn.execute(
            text("""SELECT username, ten_thuc, so_dien_thoai, email, mon_dang_ky, ngay_het_han 
                    FROM Nguoidung WHERE username=:u"""),
            {"u": username}
        ).mappings().first()

    if not user:
        flash("Không tìm thấy thông tin người dùng!")
        return redirect(url_for('index'))

    # --- Xử lý môn đăng ký (có thể nhiều giá trị) ---
    mon_map = {
        "1": "Pháp luật hải quan",
        "2": "Kỹ thuật nghiệp vụ ngoại thương",
        "3": "Kỹ thuật nghiệp vụ hải quan"
    }

    raw_mon = str(user.get("mon_dang_ky") or "").strip()
    if not raw_mon:
        mon_dk = "Chưa đăng ký môn học"
    else:
        mon_list = [mon_map.get(x.strip(), f"Không rõ ({x.strip()})") for x in raw_mon.split(",") if x.strip()]
        mon_dk = ", ".join(mon_list) if mon_list else "Chưa đăng ký môn học"

    # --- Xử lý ngày hết hạn ---
    ngay_het_han = user.get("ngay_het_han")
    if ngay_het_han is None:
        ngay_het_han = "Chưa có"
    else:
        ngay_het_han = str(ngay_het_han)

    return render_template("tai_khoan.html", user=user, mon_dk=mon_dk, ngay_het_han=ngay_het_han)

# ---------- Quản trị ----------
@app.route('/quan-tri')
def quan_tri():
    if not session.get("is_admin"):
        return "Bạn không có quyền truy cập!"

    with engine.connect() as conn:
        users = conn.execute(text(
            "SELECT username, ten_thuc, email, cong_ty, is_admin FROM Nguoidung"
        )).mappings().all()

    return render_template('quan_tri.html', users=users)

# ---------- Nhập bộ đề thi ----------
@app.route('/nhap-bodethi', methods=['GET', 'POST'])
def nhap_bodethi():
    if request.method == 'POST':
        file = request.files['file']
        if file.filename.endswith('.xlsx'):
            df = pd.read_excel(file)
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM Bodethi"))
                for _, row in df.iterrows():
                    conn.execute(text("""
                        INSERT INTO Bodethi (ma_mon_thi, cau_hoi, dap_an_a, dap_an_b, dap_an_c, dap_an_d, dap_an_dung, ghi_chu)
                        VALUES (:ma_mon, :cau_hoi, :a, :b, :c, :d, :dung, :ghichu)
                    """), {
                        "ma_mon": row["Ma_mon_thi"],
                        "cau_hoi": row["CAU_HOI"],
                        "a": row["DAP_AN_A"],
                        "b": row["DAP_AN_B"],
                        "c": row["DAP_AN_C"],
                        "d": row["DAP_AN_D"],
                        "dung": row["DAP_AN_DUNG"],
                        "ghichu": row.get("GHI_CHU", "")
                    })
            return "Đã nhập bộ đề thi thành công!"
        else:
            return "Chỉ chấp nhận file Excel .xlsx"
    return render_template('nhap_bodethi.html')

# ---------- Thi thử ----------
@app.route('/thi-thu', methods=['GET', 'POST'])
def thi_thu():
    with engine.connect() as conn:
        monthi = conn.execute(text("SELECT * FROM Monthi")).mappings().all()
    if request.method == 'POST':
        ma_mon = request.form.get('ten_mon_thi')
        with engine.connect() as conn:
            cauhoi = conn.execute(
                text("SELECT * FROM Bodethi WHERE ma_mon_thi = :m"),
                {"m": ma_mon}
            ).mappings().all()
        return render_template('lam_bai.html', cauhoi=cauhoi)
    return render_template('thi_thu.html', monthi=monthi)

# ---------- Dummy route để tránh lỗi ----------
@app.route('/tong-hop-kien-thuc')
def tong_hop_kien_thuc():
    return "Trang Tổng hợp kiến thức (đang phát triển)"

@app.route('/on-tap')
def on_tap():
    return "Trang Ôn tập (đang phát triển)"

@app.route('/cau-tra-loi-sai')
def cau_tra_loi_sai():
    return "Trang Câu trả lời sai (đang phát triển)"

# ----------Tạo mã thanh toán --------



import urllib.parse

@app.route('/tao-thanh-toan', methods=['POST'])
def tao_thanh_toan():
    if 'username' not in session:
        return {"error": "Bạn chưa đăng nhập!"}, 403

    username = session['username']
    mon_selected = request.form.getlist('mon')
    so_mon = len(mon_selected)

    if so_mon == 0:
        return {"error": "Vui lòng chọn ít nhất 1 môn!"}, 400

    # Lấy ngày hết hạn từ DB
    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT ngay_het_han FROM Nguoidung WHERE username=:u"),
            {"u": username}
        ).mappings().first()

    ngay_het_han = user.get("ngay_het_han") if user else None

    # Tính số tiền
    if not ngay_het_han:
        if so_mon == 1:
            so_tien = 200000
        elif so_mon == 2:
            so_tien = 350000
        else:
            so_tien = 500000
    else:
        so_tien = so_mon * 100000

    noi_dung = f"{username} . Gia han TracNghiemHQ . {so_mon} mon"

    # Dùng VietQR API
    bank_code = "970415"  # Vietinbank
    account_no = "109004999631"
    url_qr = (
        f"https://img.vietqr.io/image/{bank_code}-{account_no}-qr_only.png"
        f"?amount={so_tien}&addInfo={urllib.parse.quote(noi_dung)}"
    )

    return {
        "amount": so_tien,
        "noi_dung": noi_dung,
        "qr_url": url_qr
    }


#----- Hiện Thanh toán -----
@app.route("/thanh-toan")
def thanh_toan_page():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("thanh_toan.html", username=session["username"])

# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)
