from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import openai
import json
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY", "")

app = FastAPI()

allowed_origins = [
    "http://localhost:3000",
    "https://chatbot.tavanbogd.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

CSV_FILES = [
    ("37. debt collection.csv", "Зээл авах үеийн нөхцөл байдал (Өрийн мэдээлэл)"),
    ("98. debt collection.csv", "Одоогийн нөхцөл байдал (Өрийн мэдээлэл)"),
    ("37.loan history.csv", "Зээл авах үеийн нөхцөл байдал (Зээлийн эргэн төлсөн түүх)"),
    ("98. loan history.csv", "Одоогийн нөхцөл байдал (Зээлийн эргэн төлсөн түүх)"),
    ("98. Income.csv", "Одоогийн нөхцөл байдал (Орлого)")
]

class NextActionRequest(BaseModel):
    customer_id: str
    emp_id: str

class FilterResponseRequest(BaseModel):
    emp_id: str

@app.post("/api/next_action")
async def next_action(request: NextActionRequest):
    customer_id = request.customer_id
    emp_id = request.emp_id
    details = ""
    json_data = {}
    for fname, label in CSV_FILES:
        csv_path = os.path.join("data", fname)
        try:
            df = pd.read_csv(csv_path)
            if "customer_id" in df.columns:
                df = df[df["customer_id"].astype(str) == str(customer_id)]
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
    if not json_data or all(len(v) == 0 for v in json_data.values()):
        raise HTTPException(status_code=404, detail="Өгөгдөл олдсонгүй")
    with open("prompt0903.txt", "r", encoding="utf-8") as f:
        base_prompt = f.read()
    prompt = f"{base_prompt}\n\nЗээлдэгчийн түүхэн мэдээлэл:\n{details}\n"
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
    return result

@app.post("/api/filter_response")
async def filter_response(request: FilterResponseRequest):
    emp_id = request.emp_id
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
    results.sort(key=lambda x: x.get('created', ''), reverse=True)
    return {"results": results, "count": len(results)}

@app.get("/api/test")
async def test_api():
    return {"message": "API амжилттай ажиллаж байна!"}
