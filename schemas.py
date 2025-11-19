"""
Database Schemas for the Restaurants Chat App

Each Pydantic model represents a MongoDB collection.
Collection name is the lowercase of the class name (handled by callers).
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional

class Restaurant(BaseModel):
    name: str = Field(..., description="Restaurant name")
    address: str = Field(..., description="Street address")
    city: str = Field(..., description="City name")
    cuisine: List[str] = Field(default_factory=list, description="List of cuisines e.g. ['mexican','tacos']")
    dishes: List[str] = Field(default_factory=list, description="Signature dishes e.g. ['ramen','sushi']")
    takeaway: bool = Field(True, description="Offers takeaway")
    price_level: int = Field(2, ge=1, le=4, description="1=budget, 4=premium")
    tags: List[str] = Field(default_factory=list, description="Extra tags e.g. ['vegan','halal','late-night']")
    photo_url: Optional[HttpUrl] = Field(None, description="Hero photo URL")
    rating_avg: float = Field(0, ge=0, le=5, description="Average rating")
    rating_count: int = Field(0, ge=0, description="Number of ratings")

class Review(BaseModel):
    restaurant_id: str = Field(..., description="ID of the restaurant (string ObjectId)")
    user_name: str = Field(..., description="Reviewer display name")
    rating: int = Field(..., ge=1, le=5, description="Star rating 1-5")
    comment: Optional[str] = Field(None, description="Review text")
    photos: List[HttpUrl] = Field(default_factory=list, description="Optional photo URLs")

# You can extend with additional models (e.g., Conversation) if needed later.
