import os
import threading
import time
import requests
from flask import Flask, render_template, request, redirect, url_for, session
from sqlalchemy import create_engine, text
from werkzeug.security import check_password_hash
import pandas as pd

# ---------- Flask config ----------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret123")

# ---------- Database config ----------
DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://vinhnguyen:uDpQGHxIAMFtuWlXztNE86cDAXmNF4VH@dpg-d2m1nljuibrs73fo7dig-a.oregon-postgres.render.com/db_tracnghiemhq"
)
engine = create_engine(DATABASE_URL, echo=False)

# ---------- Ping thread để tránh ngủ đông ----------
def ping_server():
    while True:
        try:
            url = os.getenv("PING_URL", "https://your-app.onrender.com")
            requests.get(url)
        except Exception as e:
            print("Ping error:", e)
        time.sleep(600)  # 10 phút

threading.Thread(target=ping_server, daemon=True).start()


# ---------- Auth ----------
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
                session['username'] = user["username"]
                session['ten_thuc'] = user["ten_thuc"]
                session['is_admin'] = user["is_admin"]
                return redirect(url_for('index'))
            else:
                return "Sai mật khẩu!"
        else:
            return "Không tìm thấy người dùng!"

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ---------- Trang chính ----------
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))

    return render_template(
        'index.html',
        ten_thuc=session.get("ten_thuc"),
        is_admin=session.get("is_admin")
    )


# ---------- Quản trị người dùng (chỉ Admin) ----------
@app.route('/quan-tri')
def quan_tri():
    if not session.get("is_admin"):
        return "Bạn không có quyền truy cập!"

    with engine.connect() as conn:
        users = conn.execute(text("SELECT username, ten_thuc, email, cong_ty, is_admin FROM Nguoidung")).mappings().all()

    return render_template('quan_tri.html', users=users)


# ---------- Nhập bộ đề thi từ Excel ----------
@app.route('/nhap-bodethi', methods=['GET', 'POST'])
def nhap_bodethi():
    if request.method == 'POST':
        file = request.files['file']
        if file.filename.endswith('.xlsx'):
            df = pd.read_excel(file)

            with engine.begin() as conn:
                conn.execute(text("DELETE FROM Bodethi"))  # xoá dữ liệu cũ
                for _, row in df.iterrows():
                    conn.execute(text("""
                        INSERT INTO Bodethi (ma_mon, cau_hoi, dap_an_a, dap_an_b, dap_an_c, dap_an_d, dap_an_dung, ghi_chu)
                        VALUES (:ma_mon, :cau_hoi, :a, :b, :c, :d, :dung, :ghichu)
                    """), {
                        "ma_mon": row["Mã môn thi"],
                        "cau_hoi": row["Câu hỏi"],
                        "a": row["Đáp án A"],
                        "b": row["Đáp án B"],
                        "c": row["Đáp án C"],
                        "d": row["Đáp án D"],
                        "dung": row["Đáp án đúng"],
                        "ghichu": row.get("Ghi chú", "")
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
        ma_mon = request.form.get('ma_mon')
        with engine.connect() as conn:
            cauhoi = conn.execute(
                text("SELECT * FROM Bodethi WHERE ma_mon = :m"),
                {"m": ma_mon}
            ).mappings().all()
        return render_template('lam_bai.html', cauhoi=cauhoi)

    return render_template('thi_thu.html', monthi=monthi)


# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)
