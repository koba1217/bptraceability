from flask import Flask, request, render_template
import datetime
import hashlib

# Flask アプリの作成
app = Flask(__name__)

# トレーサビリティ機能
class Traceability:
    def __init__(self, pet_id, weight, location):
        self.pet_id = pet_id
        self.weight = weight
        self.initial_location = location
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
        now = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        # 重量と場所のデータを結合
        data = f"{now}-{weight}-{location}"
        # SHA-256ハッシュを使ってユニークなIDを生成
        pet_id = hashlib.sha256(data.encode()).hexdigest()[:16]
        return pet_id

    def add_pet(self, weight, location):
        pet_id = self.generate_pet_id(weight, location)
        self.pets[pet_id] = Traceability(pet_id, weight, location)
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
    return render_template('index.html', pets=manager.pets)

@app.route('/add_pet', methods=['POST'])
def add_pet():
    weight = request.form['weight']
    location = request.form['location']
    pet_id = manager.add_pet(weight, location)
    return render_template('index.html', pets=manager.pets, message=f"New PET added with ID {pet_id}")

@app.route('/add_trace/<trace_type>', methods=['GET', 'POST'])
def add_trace(trace_type):
    if request.method == 'POST':
        pet_id = request.form['pet_id']
        location = request.form['location']
        status = request.form['status']
        manager.add_trace_to_pet(pet_id, location, status, trace_type)
        return index()
    else:
        if trace_type == 'recycler':
            pet_ids = list(manager.pets.keys())
        elif trace_type == 'spinning':
            pet_ids = manager.get_pet_ids_by_trace_type('recycler', '出荷')
        elif trace_type == 'manufacturing':
            pet_ids = manager.get_pet_ids_by_trace_type('spinning', '出荷')
        return render_template(f'add_trace_{trace_type}.html', pet_ids=pet_ids)

@app.route('/trace_log/<pet_id>')
def trace_log(pet_id):
    trace_data = manager.get_trace_log_for_pet(pet_id)
    if trace_data:
        return render_template('trace_log.html', pet_id=pet_id, weight=trace_data['weight'], initial_location=trace_data['initial_location'], trace_log=trace_data['trace_log'])
    return render_template('trace_log.html', pet_id=pet_id, message="No trace log found for this PET.")

if __name__ == '__main__':
    app.run(debug=True)
