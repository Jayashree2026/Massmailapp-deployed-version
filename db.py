# db.py
import os
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from bson import ObjectId
from datetime import datetime
import streamlit as st

MONGO_URI = os.getenv("MONGO_URI") or (st.secrets["MONGO_URI"] if "MONGO_URI" in st.secrets else None)

def get_db():
    try:
        uri = st.secrets["mongo"]["uri"]
        db_name = st.secrets["mongo"].get("database", "massmaildb")  # default fallback
        client = MongoClient(uri)
        db = client[db_name]
        return client, db
    except Exception as e:
        st.error(f"Error connecting to MongoDB: {e}")
        return None, None

def to_object_id(val):
    """Try converting to ObjectId, otherwise return None."""
    try:
        return ObjectId(val)
    except Exception:
        return None

def now():
    return datetime.utcnow()
