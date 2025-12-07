import os
import json

from flask import Flask, request, jsonify
from flask_cors import CORS
from models import Item, SessionLocal
from datetime import datetime
from dotenv import load_dotenv
from google import genai


app = Flask(__name__)
CORS(app)


db = SessionLocal()
load_dotenv()

# Gemini API Setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set in environment variables")

client = genai.Client(api_key=GEMINI_API_KEY)
print("Gemini API client initialized")


HEALTHY = {
"White Bread": "Brown Bread",
"Sugar": "Honey",
"Milk": "Low Fat Milk",
"Chips": "Roasted Peanuts"
}


@app.route("/items", methods=["GET"])
def get_items():
    items = db.query(Item).all()
    return jsonify([{"id":i.id,"name":i.name,"qty":i.qty,"expiry":i.expiry} for i in items])


@app.route("/items", methods=["POST"])
def add_item():
    data = request.get_json()
    prompt = data.get("prompt", "")

    if not prompt or not prompt.strip():
        return {"error": "Prompt is required in the request body"}, 400

    extraction_prompt = (
        "Extract all food and grocery items, quantity, AND expiration dates from the user request. "
        "Return ONLY a JSON array of objects in this format: "
        '[{"item": "item name", "qty": "quantity or empty string", "expires": "YYYY-MM-DD or empty string"}]. '
        f'User Request: "{prompt}"'
    )
    
    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=extraction_prompt
    )
    
    try:
        items_text = response.text.strip()
        if items_text.startswith("[") and items_text.endswith("]"):
            items_list = json.loads(items_text)
        else:
            import re
            json_match = re.search(r'\[.*\]', items_text, re.DOTALL)
            items_list = json.loads(json_match.group()) if json_match else []
        
        for item in items_list:
            new = Item(
                name=item.get("item", "Unknown"),
                qty=int(item.get("qty", 1)) if item.get("qty") else 1,
                expiry=item.get("expires", "")
            )
            db.add(new)
        
        db.commit()
        return jsonify({"message": "Items Added", "count": len(items_list)})
    
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return {"error": f"Failed to parse items: {str(e)}"}, 400


@app.route("/expiry")
def expiring():
    today = datetime.today().strftime("%Y-%m-%d")
    items = db.query(Item).filter(Item.expiry <= today).all()
    return jsonify([i.name for i in items])


@app.route("/recommend/<name>")
def recommend(name):
    return jsonify({"alternative": HEALTHY.get(name, "No suggestion")})


@app.route("/missing")
def missing():
    items = db.query(Item).all()
    if len(items) < 3:
        return jsonify(["Rice", "Vegetables"])
    return jsonify([])


if __name__ == "__main__":
    app.run(debug=True)