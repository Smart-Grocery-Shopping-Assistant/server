import os
import json

from flask import Flask, request, jsonify
from flask_cors import CORS
from models import Item, SessionLocal
from datetime import datetime, timedelta
from dotenv import load_dotenv
from groq import Groq


app = Flask(__name__)
CORS(app)


db = SessionLocal()
load_dotenv()

GROK_API_KEY = os.getenv("GROK_API_KEY")
if not GROK_API_KEY:
    raise RuntimeError("GROK_API_KEY is not set in environment variables")

client = Groq(api_key=os.environ.get("GROK_API_KEY"))
print("Grok API client initialized")


HEALTHY = {
    "White Bread": "Brown Bread (or Whole Grain)",
    "White Rice": "Brown Rice (or Quinoa)",
    "Regular Pasta": "Whole Wheat Pasta",
    "Sugar": "Honey (or Maple Syrup)",
    "Candy": "Dark Chocolate (70%+ Cocoa)",
    "Ice Cream": "Frozen Yogurt (or Fruit Sorbet)",
    "Milk": "Low Fat Milk (or Skim Milk)",
    "Full Fat Milk": "Low Fat Milk",
    "Sour Cream": "Plain Greek Yogurt",
    "Butter": "Olive Oil (or Avocado)",
    "Regular Mayonnaise": "Light Mayonnaise (or Hummus)",
    "Chips": "Roasted Peanuts (or Popcorn)",
    "Potato Chips": "Baked Veggie Chips",
    "Soda": "Sparkling Water (with fruit)",
    "Bacon": "Lean Turkey Bacon",
    "Ground Beef (high fat)": "Lean Ground Beef (90/10 or higher)",
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
        f'User Request: \"{prompt}\"'
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": extraction_prompt}],
        max_tokens=300,
        temperature=0.2
    )

    # Correct way
    items_text = response.choices[0].message.content.strip()
   

    if items_text == "" or items_text.lower() in ["[]", "none"]:
        return jsonify({"message": "Please add grocery or food items list"}), 200
    
    try:
        # Try JSON load directly
        if items_text.startswith("[") and items_text.endswith("]"):
            items_list = json.loads(items_text)
        else:
            # Fallback: extract JSON from free-text
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
        return jsonify({"message": "Items added successfully", "count": len(items_list)})

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        return {"error": f"Failed to parse items: {str(e)}"}, 400


@app.route("/expiry")
def expiring():
    today = datetime.today().date()
    target = today + timedelta(days=7)

    items = db.query(Item).filter(Item.expiry == target).all()
    return jsonify([{"name": i.name, "expiry": i.expiry} for i in items])



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
    app.run(host="0.0.0.0", port=8000, debug=True)