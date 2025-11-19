import os
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Restaurant, Review

app = FastAPI(title="Local Eats Chat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utilities

def oid(oid_str: str) -> ObjectId:
    try:
        return ObjectId(oid_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id")


def collection_name(model_cls) -> str:
    return model_cls.__name__.lower()


@app.get("/")
def root():
    return {"message": "Local Eats Chat API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# Seed minimal demo data if empty
@app.post("/api/seed")
def seed_demo():
    rest_col = collection_name(Restaurant)
    if db[rest_col].count_documents({}) > 0:
        return {"status": "ok", "message": "Already seeded"}

    demo = [
        {
            "name": "GraffiTaco",
            "address": "12 Brick Lane",
            "city": "London",
            "cuisine": ["mexican", "street"],
            "dishes": ["al pastor tacos", "elote"],
            "takeaway": True,
            "price_level": 2,
            "tags": ["late-night", "colourful"],
            "photo_url": "https://images.unsplash.com/photo-1601050690597-9bff8f1f1a5d",
            "rating_avg": 4.6,
            "rating_count": 128
        },
        {
            "name": "Neon Noodles",
            "address": "88 Market St",
            "city": "Manchester",
            "cuisine": ["asian", "thai"],
            "dishes": ["pad thai", "green curry"],
            "takeaway": True,
            "price_level": 1,
            "tags": ["vegan-options", "spicy"],
            "photo_url": "https://images.unsplash.com/photo-1544025162-d76694265947",
            "rating_avg": 4.3,
            "rating_count": 93
        },
        {
            "name": "Ramen Graffiti",
            "address": "5 Shoreditch High St",
            "city": "London",
            "cuisine": ["japanese", "ramen"],
            "dishes": ["tonkotsu", "spicy miso"],
            "takeaway": True,
            "price_level": 3,
            "tags": ["cozy", "neo-tokyo"],
            "photo_url": "https://images.unsplash.com/photo-1543352634-78b3b2fd0de7",
            "rating_avg": 4.8,
            "rating_count": 210
        },
    ]
    ids = []
    for d in demo:
        rid = create_document(rest_col, d)
        ids.append(rid)
    return {"status": "ok", "inserted": ids}


# Simple search endpoint used by the chatbot
class ChatQuery(BaseModel):
    query: str
    city: Optional[str] = None


@app.post("/api/chat")
def chatbot_search(body: ChatQuery):
    q = (body.query or "").lower()
    city = (body.city or "").strip()
    rest_col = collection_name(Restaurant)

    filt: Dict[str, Any] = {}
    if city:
        filt["city"] = {"$regex": f"^{city}$", "$options": "i"}

    # Heuristic parsing: cuisine keywords, price, takeaway, dish names
    cuisines = []
    dishes = []
    tags = []
    price_level: Optional[int] = None
    takeaway = None

    cuisine_keywords = [
        "mexican","taco","thai","asian","japanese","ramen","italian","pizza","indian","burger",
        "sushi","korean","bbq","vegan","vegetarian","halal","dessert","noodle","chinese"
    ]

    for word in q.split():
        w = word.strip('.,!?')
        if w in {"cheap","budget","inexpensive"}: price_level = 1
        if w in {"mid","moderate","affordable"}: price_level = 2
        if w in {"fancy","premium","expensive"}: price_level = 4
        if w in {"takeaway","takeout","to-go"}: takeaway = True
        if w in {"dine-in","eat-in"}: takeaway = False
        if w in {"spicy","late-night","cozy","colourful","family"}: tags.append(w)
        if w in cuisine_keywords:
            cuisines.append(w.replace('taco','mexican'))

    if cuisines:
        filt["cuisine"] = {"$in": list(set(cuisines))}
    if dishes:
        filt["dishes"] = {"$in": list(set(dishes))}
    if tags:
        filt["tags"] = {"$in": list(set(tags))}
    if price_level:
        filt["price_level"] = {"$lte": price_level}
    if takeaway is not None:
        filt["takeaway"] = takeaway

    results = list(db[rest_col].find(filt).limit(12))

    # Fallback to any text match in name/dishes/tags if empty
    if not results and q:
        results = list(db[rest_col].find({
            "$or": [
                {"name": {"$regex": q, "$options": "i"}},
                {"dishes": {"$elemMatch": {"$regex": q, "$options": "i"}}},
                {"cuisine": {"$elemMatch": {"$regex": q, "$options": "i"}}},
                {"tags": {"$elemMatch": {"$regex": q, "$options": "i"}}}
            ]
        }).limit(12))

    def transform(doc):
        doc["id"] = str(doc.pop("_id"))
        return doc

    payload = [transform(r) for r in results]

    if not payload:
        return {
            "answer": "I couldn't find an exact match. Try mentioning a cuisine, dish, price range (cheap/fancy), or city.",
            "results": []
        }

    # Compose a friendly answer
    top = sorted(payload, key=lambda x: x.get("rating_avg", 0), reverse=True)[:3]
    names = ", ".join([t["name"] for t in top])
    city_txt = f" in {city}" if city else ""
    answer = f"Top picks{city_txt}: {names}. Tap a card to see details and reviews."

    return {"answer": answer, "results": payload}


# Create a review and update restaurant aggregates
class ReviewCreate(BaseModel):
    restaurant_id: str
    user_name: str
    rating: int
    comment: Optional[str] = None
    photos: Optional[List[str]] = None


@app.post("/api/reviews")
def add_review(body: ReviewCreate):
    rest_col = collection_name(Restaurant)
    rev_col = collection_name(Review)

    # Insert review
    rid = create_document(rev_col, {
        "restaurant_id": body.restaurant_id,
        "user_name": body.user_name,
        "rating": body.rating,
        "comment": body.comment,
        "photos": body.photos or []
    })

    # Recompute rating aggregates
    from statistics import mean
    reviews = list(db[rev_col].find({"restaurant_id": body.restaurant_id}))
    ratings = [r.get("rating", 0) for r in reviews]
    avg = round(mean(ratings), 1) if ratings else 0
    count = len(ratings)
    db[rest_col].update_one({"_id": oid(body.restaurant_id)}, {"$set": {"rating_avg": avg, "rating_count": count}})

    return {"status": "ok", "review_id": rid, "rating_avg": avg, "rating_count": count}


@app.get("/api/restaurants")
def list_restaurants(city: Optional[str] = None):
    rest_col = collection_name(Restaurant)
    filt: Dict[str, Any] = {}
    if city:
        filt["city"] = {"$regex": f"^{city}$", "$options": "i"}
    items = list(db[rest_col].find(filt).limit(50))
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items


@app.get("/api/restaurants/{restaurant_id}")
def get_restaurant(restaurant_id: str):
    rest_col = collection_name(Restaurant)
    rev_col = collection_name(Review)
    doc = db[rest_col].find_one({"_id": oid(restaurant_id)})
    if not doc:
        raise HTTPException(404, "Restaurant not found")
    doc["id"] = str(doc.pop("_id"))
    reviews = list(db[rev_col].find({"restaurant_id": restaurant_id}).sort("created_at", -1).limit(20))
    for r in reviews:
        r["id"] = str(r.pop("_id"))
    return {"restaurant": doc, "reviews": reviews}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
