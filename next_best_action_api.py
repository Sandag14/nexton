from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
import openai
import json
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

app = Flask(__name__)
allowed_origins = [
    "http://localhost:3000",       # Dev Next.js
    "https://chatbot.tavanbogd.com"    # Production Next.js
]
CORS(
    app,
    resources={r"/api/*": {"origins": allowed_origins}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"],
    methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"]
)
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "")

CSV_FILES = [
    ("37. debt collection.csv", "Зээл авах үеийн нөхцөл байдал (Өрийн мэдээлэл)"),
    ("98. debt collection.csv", "Одоогийн нөхцөл байдал (Өрийн мэдээлэл)"),
    ("37.loan history.csv", "Зээл авах үеийн нөхцөл байдал (Зээлийн эргэн төлсөн түүх)"),
    ("98. loan history.csv", "Одоогийн нөхцөл байдал (Зээлийн эргэн төлсөн түүх)"),
    ("98. Income.csv", "Одоогийн нөхцөл байдал (Орлого)")
]

@app.route('/api/next_action', methods=['POST'])
@cross_origin()
def next_action():
    customer_id = request.json.get('customer_id')
    emp_id = request.json.get('emp_id')
    if not customer_id:
        return jsonify({'error': 'customer_id required'}), 400
    if not emp_id:
        return jsonify({'error': 'emp_id required'}), 400
    details = ""
    json_data = {}
    failed = 0
    for fname, label in CSV_FILES:
        csv_path = os.path.join("data", fname)
        try:
            df = pd.read_csv(csv_path)
            if "customer_id" in df.columns:
                df = df[df["customer_id"].astype(str) == str(customer_id)]
            # Хэрэгтэй багануудыг сонгох
            if "loan history" in fname:
                main_columns = ["customer_id", "loan_status", "disbursement_date", "loanamount", "repayments_quantity", "type", "status", "amount", "comment"]
                df = df[[col for col in main_columns if col in df.columns]]
            elif "debt collection" in fname:
                main_columns = ["customer_id", "created_at", "collector_type", "collector", "type", "status", "commitment_amount", "comment", "next_action"]
                df = df[[col for col in main_columns if col in df.columns]]
            elif "Income" in fname:
                main_columns = ["customer_id", "average_income", "year", "month", "amount"]
                df = df[[col for col in main_columns if col in df.columns]]
            records = df.to_dict(orient="records")
            json_data[label] = records
            if records:
                details += f"\n[{label} - {fname}]\n"
                for i, item in enumerate(records[-10:], 1):
                    details += f"{i}. " + ", ".join([f"{k}: {v}" for k, v in item.items()]) + "\n"
        except Exception as e:
            print(f"Error reading {csv_path}: {e}")

        if not json_data[label]:
            failed += 1

    if failed == len(CSV_FILES):
        return jsonify({'error': 'Өгөгдөл олдсонгүй'}), 404

    with open("prompt0903.txt", "r", encoding="utf-8") as f:
        base_prompt = f.read()
    prompt = f"""{base_prompt}\n\nЗээлдэгчийн түүхэн мэдээлэл:\n{details}\n"""
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for debt collection."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=800,
        temperature=0.7
    )
    result = {
        "customer_id": customer_id,
        "emp_id": emp_id,
        "response": response.choices[0].message.content.strip(),
        "created": datetime.now().isoformat()
    }

    os.makedirs("response", exist_ok=True)
    filename = os.path.join("response", f"response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return jsonify(result)

@app.route('/api/filter_response', methods=['POST'])
@cross_origin()
def filter_response():
    emp_id = request.json.get('emp_id')
    if not emp_id:
        return jsonify({'error': 'emp_id required'}), 400
    results = []
    response_dir = 'response'
    for fname in os.listdir(response_dir):
        if fname.endswith('.json'):
            fpath = os.path.join(response_dir, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if str(data.get('emp_id')) == str(emp_id):
                    results.append(data)
            except Exception as e:
                print(f'Error reading {fpath}: {e}')
    # Sort by 'created' field descending if present
    results.sort(key=lambda x: x.get('created', ''), reverse=True)
    return jsonify({'results': results, 'count': len(results)})

if __name__ == "__main__":
    app.run(port=5000)
