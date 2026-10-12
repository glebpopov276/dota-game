# language: Python, file: shared/protocol.py
import json

def encode(msg_type: str, payload: dict) -> bytes:
    return (json.dumps({"t": msg_type, "p": payload}) + "\n").encode("utf-8")

def decode(raw: bytes) -> dict:
    return json.loads(raw.decode("utf-8").strip())