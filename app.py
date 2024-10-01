from flask import Flask, render_template, request, redirect, url_for, session, flash
import datetime
import hashlib
import uuid
import psycopg2

# Flask アプリの作成
app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key_here'  # シークレットキーを設定

# PostgreSQL接続設定
def connect_db():
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password="kobayu4869",
        host="localhost",
        port="5432"
    )
    # エンコーディングをUTF-8に設定
    conn.set_client_encoding('UTF8')
    return conn

# ハードコードされたユーザー情報
users = {
    "user1": "pass",
    "user2": "pass",
    "リサイクラー1": "pass",
    "紡績1": "pass",
    "製品化1": "pass"
}

pet_status = {}

trace_urls = []

# トレーサビリティ機能
class Traceability:
    def __init__(self, pet_id, weight, location, username):
        self.pet_id = pet_id
        self.weight = weight
        self.initial_location = location
        self.user_name = username
        self.creation_timestamp = datetime.datetime.now()
        self.trace_log = []

    def add_trace(self, location, status, trace_type):
        trace_entry = {
            'timestamp': datetime.datetime.now(),
            'location': location,
            'status': status,
            'trace_type': trace_type
        }
        self.trace_log.append(trace_entry)

    def get_trace_log(self):
        return self.trace_log

class TraceabilityManager:
    def __init__(self):
        self.pets = {}

    def generate_pet_id(self, weight, location):
        # 現在の日時を取得
        now = datetime.datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
        # 重量と場所のデータを結合
        data = f"{now}-{weight}-{location}"
        # SHA-256ハッシュを使ってユニークなIDを生成
        pet_id = now + "_" + hashlib.sha256(data.encode()).hexdigest()[:16]
        return pet_id

    def add_pet(self, weight, location, username):
        pet_id = self.generate_pet_id(weight, location)
        self.pets[pet_id] = Traceability(pet_id, weight, location, username)
        return pet_id

    def add_trace_to_pet(self, pet_id, location, status, trace_type):
        if pet_id in self.pets:
            self.pets[pet_id].add_trace(location, status, trace_type)
        else:
            print(f"PET {pet_id} is not being tracked.")

    def get_trace_log_for_pet(self, pet_id):
        if pet_id in self.pets:
            trace_data = self.pets[pet_id]
            return {
                'weight': trace_data.weight,
                'initial_location': trace_data.initial_location,
                'initial_time':trace_data.creation_timestamp,
                'trace_log': trace_data.get_trace_log()
            }
        return None

    def get_pet_ids_by_trace_type(self, trace_type, status):
        pet_ids = []
        for pet_id, traceability in self.pets.items():
            if any(trace['trace_type'] == trace_type and trace['status'] == status for trace in traceability.get_trace_log()):
                pet_ids.append(pet_id)
        return pet_ids

# トレーサビリティマネージャを作成
manager = TraceabilityManager()

@app.route('/')
def index():
    if 'username' in session:
        username = session['username']

        # pet_idに対応するトレース履歴を取得
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM bp_initial_traceability WHERE username = %s", (username,))
        initial_trace = cursor.fetchall()
        cursor.close()
        conn.close()

        return render_template('index.html', pets=initial_trace)
    else:
        return redirect(url_for('login'))

@app.route('/add_pet', methods=['POST'])
def add_pet():
    if 'username' in session:
        username = session['username']
        weight = request.form['weight']
        location = request.form['location']
        pet_id = manager.add_pet(weight, location, username)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # PostgreSQLに保存
        conn = connect_db()
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO bp_initial_traceability (pet_id, username, initial_weight, initial_location, initial_date)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (pet_id, username, weight, location, timestamp))
        conn.commit()
        cursor.close()
        conn.close()

        return redirect(url_for('index'))

    else:
        return "You need to log in first."

@app.route('/add_trace/<trace_type>', methods=['GET', 'POST'])
def add_trace(trace_type):
    if 'username' in session:
        username = session['username']
    else:
        return redirect(url_for('login'))
    if request.method == 'POST':
        pet_id = request.form['pet_id']
        location = request.form['location']
        status = request.form['status']
        action_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        manager.add_trace_to_pet(pet_id, location, status, trace_type)
        if trace_type == 'manufacturing':
            product_id = f"{pet_id}-{uuid.uuid4().hex[:8]}"

        # PostgreSQLに保存
        conn = connect_db()
        cursor = conn.cursor()
        insert_query = """
        INSERT INTO bp_traceability (pet_id, product_id, date, location, status, type)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        if trace_type == 'manufacturing':
            cursor.execute(insert_query, (pet_id, product_id, action_time, location, status, trace_type))
        else:
            cursor.execute(insert_query, (pet_id, 0, action_time, location, status, trace_type))
        conn.commit()
        cursor.close()
        conn.close()

        if username == 'リサイクラー1' and trace_type == 'recycler':
            if status == "出荷":
                pet_status[pet_id] = 'Shipped from recycler'
            return redirect(url_for('add_trace', trace_type='recycler'))
        elif username == '紡績1' and trace_type == 'spinning':
            if status == "出荷":
                pet_status[pet_id] = 'Shipped from spinning'
            return redirect(url_for('add_trace', trace_type='spinning'))
        elif username == '製品化1' and trace_type == 'manufacturing':
            if status == "出荷":
                pet_status[pet_id] = 'Shipped from manufacturing'
                trace_url = url_for('trace_history', pet_id=pet_id)
                trace_urls.append({'product_id': product_id, 'trace_url': trace_url})
                pet_ids = manager.get_pet_ids_by_trace_type('spinning', '出荷')
                display_pet_ids = [id for id in pet_ids if pet_status.get(id) not in ['Shipped from manufacturing']]
                return render_template('add_trace_manufacturing.html', trace_urls=trace_urls ,pet_ids=display_pet_ids)
            return redirect(url_for('add_trace', trace_type='manufacturing'))
        return redirect(url_for('index'))  # その他のユーザーやエラー時はホーム画面にリダイレクト
    else:
        conn = connect_db()
        cursor = conn.cursor()
        if trace_type == 'recycler':
            cursor.execute("SELECT pet_id FROM bp_initial_traceability")
            initial_trace_pet_id = cursor.fetchall()
            cursor.execute("SELECT pet_id FROM bp_traceability WHERE type =%s and status =%s",('recycler','出荷'))
            Shipped_from_recycler = cursor.fetchall()
            display_pet_ids = list(set(initial_trace_pet_id)-set(Shipped_from_recycler))
            #pet_ids = list(manager.pets.keys())
            #display_pet_ids = [id for id in pet_ids if pet_status.get(id) not in ['Shipped from recycler','Shipped from spinning','Shipped from manufacturing']]
        elif trace_type == 'spinning':
            cursor.execute("SELECT pet_id FROM bp_traceability WHERE type =%s and status =%s",('recycler','出荷'))
            Shipped_from_recycler = cursor.fetchall()
            cursor.execute("SELECT pet_id FROM bp_traceability WHERE type =%s and status =%s",('spinning','出荷'))
            Shipped_from_spinning = cursor.fetchall()
            display_pet_ids = list(set(Shipped_from_recycler)-set(Shipped_from_spinning))
            #pet_ids = manager.get_pet_ids_by_trace_type('recycler', '出荷')
            #display_pet_ids = [id for id in pet_ids if pet_status.get(id) not in ['Shipped from spinning','Shipped from manufacturing']]
        elif trace_type == 'manufacturing':
            cursor.execute("SELECT pet_id FROM bp_traceability WHERE type =%s and status =%s",('spinning','出荷'))
            Shipped_from_spinning = cursor.fetchall()
            cursor.execute("SELECT pet_id FROM bp_traceability WHERE type =%s and status =%s",('manufacturing','出荷'))
            Shipped_from_manufacturing = cursor.fetchall()
            display_pet_ids = list(set(Shipped_from_spinning)-set(Shipped_from_manufacturing))
            #pet_ids = manager.get_pet_ids_by_trace_type('spinning', '出荷')
            #display_pet_ids = [id for id in pet_ids if pet_status.get(id) not in ['Shipped from manufacturing']]
        cursor.close()
        conn.close()
        return render_template(f'add_trace_{trace_type}.html',trace_urls=trace_urls ,pet_ids=display_pet_ids)

    return render_template(f'add_trace_{trace_type}.html')

@app.route('/trace_log/<pet_id>')
def trace_log(pet_id):
    # pet_idに対応するトレース履歴を取得
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bp_traceability WHERE pet_id = %s", (pet_id,))
    trace_logs = cursor.fetchall()
    cursor.execute("SELECT * FROM bp_initial_traceability WHERE pet_id = %s", (pet_id,))
    initial_trace = cursor.fetchall()
    cursor.close()
    conn.close()
    if initial_trace:
        return render_template('trace_log.html', pet_id=pet_id, initial_log=initial_trace, trace_logs=trace_logs)
    return render_template('trace_log.html', pet_id=pet_id, message="No trace log found for this PET.")

#@app.route('/trace_history/<pet_id>')
#def trace_history(pet_id):
    #trace_data = manager.get_trace_log_for_pet(pet_id)
    #if trace_data:
        #return render_template('trace_history.html', pet_id=pet_id, weight=trace_data['weight'], initial_location=trace_data['initial_location'], initial_time=trace_data['initial_time'], trace_log=trace_data['trace_log'])
    #return render_template('trace_history.html', pet_id=pet_id, message="No trace log found for this PET.")

@app.route('/trace_history/<pet_id>')
def trace_history(pet_id):
    # pet_idに対応するトレース履歴を取得
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bp_traceability WHERE pet_id = %s", (pet_id,))
    trace_logs = cursor.fetchall()
    cursor.execute("SELECT * FROM bp_initial_traceability WHERE pet_id = %s", (pet_id,))
    initial_trace = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('trace_history.html', pet_id=pet_id, initial_log=initial_trace, trace_logs=trace_logs)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 認証の確認
        if username in users and users[username] == password:
            session['username'] = username  # セッションにユーザー名を保存

            # ユーザー名に応じてリダイレクト先を変更
            if username == 'リサイクラー1':
                return redirect(url_for('add_trace', trace_type='recycler'))
            elif username == '紡績1':
                return redirect(url_for('add_trace', trace_type='spinning'))
            elif username == '製品化1':
                return redirect(url_for('add_trace', trace_type='manufacturing'))
            else:
                return redirect(url_for('index'))

        else:
            return "Invalid credentials. Please try again."

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)  # セッションからユーザー名を削除
    return redirect(url_for('login'))

@app.before_request
def require_login():
    allowed_routes = ['login']
    if 'username' not in session and request.endpoint not in allowed_routes:
        return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
