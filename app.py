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

        if user and user["password_hash"] == password:
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

        pw_hash = password
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

    # --- Cập nhật thông tin nếu POST ---
    if request.method == 'POST':
        new_pw = request.form.get('password')
        ten_thuc = request.form.get('ten_thuc')
        so_dien_thoai = request.form.get('so_dien_thoai')
        email = request.form.get('email')

        with engine.begin() as conn:
            if new_pw:
                pw_hash = new_pw
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
@require_login
def quan_tri():
    if not session.get("is_admin"):
        return "Bạn không có quyền truy cập!"

    with engine.connect() as conn:
        users = conn.execute(text("SELECT * FROM Nguoidung ORDER BY thoi_gian_tao DESC")).mappings().all()

    return render_template("admin.html", users=users)


@app.route('/edit-user/<username>', methods=['GET', 'POST'])
@require_login
def edit_user(username):
    if not session.get("is_admin"):
        return "Bạn không có quyền truy cập!"

    if request.method == 'POST':
        new_password = request.form.get("password_hash")
        ten_thuc = request.form.get("ten_thuc")
        so_dien_thoai = request.form.get("so_dien_thoai")
        email = request.form.get("email")
        cong_ty = request.form.get("cong_ty")
        is_admin = True if request.form.get("is_admin") == "on" else False
        mon_dang_ky = request.form.get("mon_dang_ky")
        ngay_het_han = request.form.get("ngay_het_han")
        ten_thiet_bi = request.form.get("ten_thiet_bi")

        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE Nguoidung
                SET password_hash=:p, ten_thuc=:t, so_dien_thoai=:s,
                    email=:e, cong_ty=:c, is_admin=:a,
                    mon_dang_ky=:m, ngay_het_han=:n, ten_thiet_bi=:tb
                WHERE username=:u
            """), {
                "p": new_password,   # Lưu plain text
                "t": ten_thuc,
                "s": so_dien_thoai,
                "e": email,
                "c": cong_ty,
                "a": is_admin,
                "m": mon_dang_ky,
                "n": ngay_het_han,
                "tb": ten_thiet_bi,
                "u": username
            })

        flash("Cập nhật người dùng thành công!", "success")
        return redirect(url_for("quan_tri"))

    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT * FROM Nguoidung WHERE username=:u"),
            {"u": username}
        ).mappings().first()

    return render_template("edit_user.html", user=user)


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

#---- Trả lời câu sai -----
@app.route("/cau-tra-loi-sai")
@require_login
def cau_tra_loi_sai():
    return render_template("cau_tra_loi_sai.html")



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

@app.route("/upload_exam")
@require_login
def upload_exam():
    return render_template("upload_exam.html")

@app.route('/upload-bodethi', methods=['POST'])
@require_login
def upload_bodethi():
    if not session.get("is_admin"):
        return "Bạn không có quyền truy cập!"

    if 'file' not in request.files:
        flash("Không tìm thấy file!", "danger")
        return redirect(url_for("quan_tri"))

    file = request.files['file']
    if file.filename == '':
        flash("Chưa chọn file!", "danger")
        return redirect(url_for("quan_tri"))

    try:
        # Đọc file Excel bằng pandas
        df = pd.read_excel(file)

        # Lấy danh sách cột từ excel (giả định trùng với table bodethi)
        columns = list(df.columns)

        with engine.begin() as conn:
            # Xóa dữ liệu cũ
            conn.execute(text("DELETE FROM bodethi"))

            # Chèn dữ liệu mới
            for _, row in df.iterrows():
                placeholders = ", ".join([f":{col}" for col in columns])
                sql = f"INSERT INTO bodethi ({', '.join(columns)}) VALUES ({placeholders})"
                conn.execute(text(sql), row.to_dict())

        flash("Cập nhật bộ đề thành công!", "success")

    except Exception as e:
        flash(f"Lỗi khi cập nhật bộ đề: {e}", "danger")

    return redirect(url_for("quan_tri"))

#---- Tạo ôn tập----
# ---------- API: Lấy câu hỏi ngẫu nhiên theo lĩnh vực ----------
@app.route("/api/get-question", methods=["POST"])
@require_login
def api_get_question():
    try:
        data = request.get_json()
        linh_vuc = data.get("ten_mon_thi")   # thực ra giờ là tên lĩnh vực
        exclude_ids = data.get("exclude_ids", [])

        # Hardcode mapping lĩnh vực -> ma_mon_thi
        topic_map = {
            "Pháp luật hải quan": 11,
            "Chính sách thuế": 12,
            "Vi phạm hành chính": 13,
            "Giao nhận vận tải": 21,
            "Ngoại thương": 22,
            "Thanh toán quốc tế": 23,
            "Thủ tục hải quan": 31,
            "Chính sách mặt hàng": 32,
            "Trị giá hải quan": 33,
            "Xuất xứ hàng hóa": 34,
            "Sở hữu trí tuệ": 35,
            "Phân loại hàng hóa": 36,
        }

        ma_mon_thi = topic_map.get(linh_vuc)
        if not ma_mon_thi:
            return {"error": f"Không tìm thấy mã cho lĩnh vực {linh_vuc}"}, 404

        with engine.connect() as conn:
            if exclude_ids:
                query = text("""
                    SELECT * FROM bodethi 
                    WHERE ma_mon_thi=:m AND id NOT IN :ids
                """)
                params = {"m": ma_mon_thi, "ids": tuple(exclude_ids)}
            else:
                query = text("SELECT * FROM bodethi WHERE ma_mon_thi=:m")
                params = {"m": ma_mon_thi}

            questions = conn.execute(query, params).mappings().all()

        if not questions:
            return {"questions": []}

        import random
        q = random.choice(questions)

        formatted = {
            "id": q.get("id"),
            "question": q.get("cau_hoi", "Không có nội dung"),
            "answers": [
                q.get("dap_an_a"),
                q.get("dap_an_b"),
                q.get("dap_an_c"),
                q.get("dap_an_d"),
            ],
            "correct_indices": q["dap_an_dung"] if q.get("dap_an_dung") else [],
            "note": q.get("ghi_chu", "")   # 👈 thêm ghi chú
        }

        return {"questions": [formatted]}

    except Exception as e:
        import traceback
        print("API /api/get-question lỗi:", e)
        traceback.print_exc()
        return {"error": str(e)}, 500





if __name__ == "__main__":
    app.run(debug=True)
