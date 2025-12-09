import os
import json

from flask import Flask, request, jsonify
from flask_cors import CORS
from models import Item, SessionLocal
from datetime import datetime, timedelta
from dotenv import load_dotenv
from groq import Groq
from models import Item, ItemList, SessionLocal


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
    return jsonify([{
        "id": i.id,
        "name": i.name,
        "qty": i.qty,
        "expiry": i.expiry
    } for i in items])


@app.route("/items", methods=["POST"])
def add_item():
    data = request.get_json()
    prompt = data.get("prompt", "")

    if not prompt or not prompt.strip():
        return {"error": "Prompt is required"}, 400

    # ----------------------------------------------------
    # 1. RUN GROQ EXTRACTION FIRST (so parsed_items exists)
    # ----------------------------------------------------
    extraction_prompt = (
        "Extract all food and grocery items, quantity, AND expiration dates "
        "from the user request. Return ONLY a JSON array like: "
        '[{\"item\": \"item name\", \"qty\": \"quantity\", \"expires\": \"YYYY-MM-DD\"}]. '
        f'User Request: \"{prompt}\"'
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": extraction_prompt}],
        max_tokens=300,
        temperature=0.1
    )

    items_text = response.choices[0].message.content.strip()

    # Nothing extracted → return but still include reminders later if needed
    if not items_text or items_text.lower() in ["[]", "none"]:
        parsed_items = []
    else:
        # ----------------------------------------------------
        # 2. PARSE JSON OUTPUT FROM GROQ
        # ----------------------------------------------------
        try:
            if items_text.startswith("[") and items_text.endswith("]"):
                parsed_items = json.loads(items_text)
            else:
                import re
                match = re.search(r'\[.*\]', items_text, re.DOTALL)
                parsed_items = json.loads(match.group()) if match else []
        except Exception as e:
            return {"error": f"Failed to parse items: {str(e)}"}, 400

    # ----------------------------------------------------
    # 3. CHECK RECENTLY BOUGHT ITEMS (last 7 days)
    # ----------------------------------------------------
    today = datetime.today().date()
    last_week_start = today - timedelta(days=7)
    last_week_end = today - timedelta(days=1)  # exclude today

    recent_lists = db.query(ItemList).filter(
        ItemList.created_at >= last_week_start,
        ItemList.created_at <= last_week_end
    ).all()
    
    recent_item_names = {
        item.name.lower()
        for lst in recent_lists
        for item in lst.items
    }

    # Today's added items from parsed_items
    today_item_names = {
        item.get("item", "").lower()
        for item in parsed_items
    }

    # Items bought last week but NOT today
    missing_items = sorted(list(recent_item_names - today_item_names))

    reminders = []
    if missing_items:
        if len(missing_items) == 2:
            text = f"{missing_items[0]} and {missing_items[1]}"
        elif len(missing_items) > 2:
            text = ", ".join(missing_items[:-1]) + f", and {missing_items[-1]}"
        else:
            text = missing_items[0]

        reminders.append(
            f"You bought {text} last week, If you want to add it again, tell me with quantity and expiry date"
        )

    # If the user added nothing AND we want to show reminders anyway
    if not parsed_items:
        return jsonify({
            "message": "Please add grocery or food items list",
            "reminders": reminders
        }), 200

    # ----------------------------------------------------
    # 4. SAVE NEW LIST + ITEMS
    # ----------------------------------------------------
    new_list = ItemList()
    db.add(new_list)
    db.commit()
    db.refresh(new_list)

    for item in parsed_items:
        entry = Item(
            list_id=new_list.id,
            name=item.get("item", "Unknown"),
            qty=item.get("qty", ""),
            expiry=item.get("expires", "")
        )
        db.add(entry)

    db.commit()

    return jsonify({
        "message": "Items added successfully",
        "list_date": str(new_list.created_at),
        "items_added": len(parsed_items),
        "reminders": reminders
    })


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