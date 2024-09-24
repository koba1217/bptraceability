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

# ユーザーごとのPETデータを保持する
user_pets = {
    'user1': [],
    'user2': [],
    'リサイクラー1': [],
    '紡績1': [],
    '製品化1': []
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
        pets = user_pets.get(username, [])  # 現在のユーザーのPETリストを取得
        return render_template('index.html', pets=pets)
    else:
        return redirect(url_for('login'))

@app.route('/add_pet', methods=['POST'])
def add_pet():
    if 'username' in session:
        username = session['username']
        weight = request.form['weight']
        location = request.form['location']
        pet_id = manager.add_pet(weight, location, username)
        # 現在のユーザーのPETリストに追加
        user_pets[username].append({
            'pet_id': pet_id,
            'weight': weight,
            'location': location,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
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
        manufacture_timestamp = datetime.datetime.now()
        manager.add_trace_to_pet(pet_id, location, status, trace_type)
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
                product_id = f"{pet_id}-{uuid.uuid4().hex[:8]}"
                trace_urls.append({'product_id': product_id, 'trace_url': trace_url})
                trace_data = manager.get_trace_log_for_pet(pet_id)
                trace_logs = trace_data['trace_log']

                 # PostgreSQLに保存
                conn = connect_db()
                cursor = conn.cursor()

                for trace in trace_logs:
                    insert_query = """
                    INSERT INTO bp_traceability (pet_id, product_id, date, location, status, type)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_query, (pet_id, product_id, trace['timestamp'], trace['location'], trace['status'], trace['trace_type']))

                conn.commit()
                cursor.close()
                conn.close()

                pet_ids = manager.get_pet_ids_by_trace_type('spinning', '出荷')
                display_pet_ids = [id for id in pet_ids if pet_status.get(id) not in ['Shipped from manufacturing']]
                return render_template('add_trace_manufacturing.html', trace_urls=trace_urls ,pet_ids=display_pet_ids)
            return redirect(url_for('add_trace', trace_type='manufacturing'))
        return redirect(url_for('index'))  # その他のユーザーやエラー時はホーム画面にリダイレクト
    else:
        if trace_type == 'recycler':
            pet_ids = list(manager.pets.keys())
            display_pet_ids = [id for id in pet_ids if pet_status.get(id) not in ['Shipped from recycler','Shipped from spinning','Shipped from manufacturing']]
        elif trace_type == 'spinning':
            pet_ids = manager.get_pet_ids_by_trace_type('recycler', '出荷')
            display_pet_ids = [id for id in pet_ids if pet_status.get(id) not in ['Shipped from spinning','Shipped from manufacturing']]
        elif trace_type == 'manufacturing':
            pet_ids = manager.get_pet_ids_by_trace_type('spinning', '出荷')
            display_pet_ids = [id for id in pet_ids if pet_status.get(id) not in ['Shipped from manufacturing']]
        return render_template(f'add_trace_{trace_type}.html',trace_urls=trace_urls ,pet_ids=display_pet_ids)

    return render_template(f'add_trace_{trace_type}.html')

@app.route('/trace_log/<pet_id>')
def trace_log(pet_id):
    trace_data = manager.get_trace_log_for_pet(pet_id)
    if trace_data:
        return render_template('trace_log.html', pet_id=pet_id, weight=trace_data['weight'], initial_location=trace_data['initial_location'], trace_log=trace_data['trace_log'], data=trace_data)
    return render_template('trace_log.html', pet_id=pet_id, message="No trace log found for this PET.")

#@app.route('/trace_history/<pet_id>')
#def trace_history(pet_id):
    #trace_data = manager.get_trace_log_for_pet(pet_id)
    #if trace_data:
        #return render_template('trace_history.html', pet_id=pet_id, weight=trace_data['weight'], initial_location=trace_data['initial_location'], initial_time=trace_data['initial_time'], trace_log=trace_data['trace_log'])
    #return render_template('trace_history.html', pet_id=pet_id, message="No trace log found for this PET.")

@app.route('/trace_history/<pet_id>')
def trace_history(pet_id):
    trace_data = manager.get_trace_log_for_pet(pet_id)
    conn = connect_db()
    cursor = conn.cursor()

    # pet_idに対応するトレース履歴を取得
    cursor.execute("SELECT * FROM bp_traceability WHERE pet_id = %s", (pet_id,))
    trace_logs = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('trace_history.html', pet_id=pet_id, weight=trace_data['weight'], initial_location=trace_data['initial_location'], initial_time=trace_data['initial_time'], trace_logs=trace_logs)

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
