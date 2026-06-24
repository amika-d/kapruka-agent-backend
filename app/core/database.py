import time
import json
import os
from collections import OrderedDict
from typing import Dict, Any, List

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sessions.json")

class SessionStore:
    def __init__(self, max_sessions: int = 100, ttl_seconds: int = 7200):
        self.max_sessions = max_sessions
        self.ttl_seconds = ttl_seconds
        self._sessions: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._load_from_disk()
    
    def _load_from_disk(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    data = json.load(f)
                    for k, v in data.items():
                        self._sessions[k] = v
            except Exception as e:
                print(f"Error loading sessions: {e}")

    def _save_to_disk(self):
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        try:
            with open(DATA_FILE, "w") as f:
                json.dump(self._sessions, f, indent=2)
        except Exception as e:
            print(f"Error saving sessions: {e}")

    def _evict_expired(self):
        now = time.time()
        keys_to_delete = []
        for session_id, data in self._sessions.items():
            if now - data["last_accessed"] > self.ttl_seconds:
                keys_to_delete.append(session_id)
        
        for k in keys_to_delete:
            del self._sessions[k]
            
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)
            
        if keys_to_delete:
            self._save_to_disk()

    def get_session(self, session_id: str) -> Dict[str, Any]:
        self._evict_expired()
        if session_id in self._sessions:
            self._sessions.move_to_end(session_id)
            self._sessions[session_id]["last_accessed"] = time.time()
            self._save_to_disk()
            return self._sessions[session_id]
        
        # Initialize new session
        new_session = {
            "messages": [],
            "cart": [],
            "language": "english",
            "occasion": None,
            "delivery_city": None,
            "browsed_products": [],
            "rejected_products": [],
            "last_query": None,
            "last_accessed": time.time()
        }
        self._sessions[session_id] = new_session
        self._evict_expired()
        self._save_to_disk()
        return new_session

    def update_session(self, session_id: str, **kwargs):
        session = self.get_session(session_id)
        for k, v in kwargs.items():
            session[k] = v
        session["last_accessed"] = time.time()
        self._save_to_disk()

    def append_message(self, session_id: str, message: dict):
        session = self.get_session(session_id)
        session["messages"].append(message)
        session["last_accessed"] = time.time()
        self._save_to_disk()

    def add_browsed_product(self, session_id: str, product_id: str):
        session = self.get_session(session_id)
        if product_id not in session["browsed_products"]:
            session["browsed_products"].append(product_id)
        session["last_accessed"] = time.time()
        self._save_to_disk()

    def add_rejected_product(self, session_id: str, product_id: str):
        session = self.get_session(session_id)
        if product_id not in session["rejected_products"]:
            session["rejected_products"].append(product_id)
        session["last_accessed"] = time.time()
        self._save_to_disk()

    def clear_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save_to_disk()

    def list_sessions(self) -> List[str]:
        self._evict_expired()
        return list(self._sessions.keys())
        
    def list_all_session_details(self) -> List[Dict[str, Any]]:
        self._evict_expired()
        result = []
        for sid, data in self._sessions.items():
            result.append({"session_id": sid, **data})
        # Return sorted by last accessed descending
        return sorted(result, key=lambda x: x["last_accessed"], reverse=True)

_store_instance: SessionStore | None = None

def get_session_store() -> SessionStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = SessionStore()
    return _store_instance
