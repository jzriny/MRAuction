"""
Marvel Rivals Auction House - Backend Server
Run with: uvicorn server:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import random
import string
import time
from typing import Dict, Optional, Set
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="Marvel Rivals Auction House")

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

STARTING_BALANCE = 10000
BID_INCREMENT = 100
AUCTION_DURATION = 30  # seconds
TIME_EXTENDER = 10  # seconds added when bid placed near end
ROOM_CODE_LENGTH = 6

# ─── In-Memory State ────────────────────────────────────────────────────────────

rooms: Dict[str, dict] = {}
# room = {
#   "code": str,
#   "host": str,
#   "players": { username: { balance, characters: [], connected: bool } },
#   "connections": { username: WebSocket },
#   "state": "lobby" | "bidding" | "sold" | "finished",
#   "auction": { role, character, current_bid, current_bidder, end_time, timer_task },
#   "bid_log": []
# }


def make_room_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=ROOM_CODE_LENGTH))


def room_public_state(room: dict, viewer: str = None) -> dict:
    """Serialize room state safe to broadcast to all clients."""
    players_public = {}
    for username, pdata in room["players"].items():
        players_public[username] = {
            "balance": pdata["balance"],
            "characters": pdata["characters"],
            "connected": pdata["connected"],
        }

    auction = None
    if room.get("auction"):
        a = room["auction"]
        auction = {
            "character": a.get("character"),
            "current_bid": a.get("current_bid"),
            "current_bidder": a.get("current_bidder"),
            "end_time": a.get("end_time"),
            "winner": a.get("winner"),
            "final_amount": a.get("final_amount"),
        }

    return {
        "code": room["code"],
        "host": room["host"],
        "players": players_public,
        "state": room["state"],
        "auction": auction,
        "bid_log": room.get("bid_log", [])[-20:],  # last 20 entries
        "settings": {
            "starting_balance": room.get("starting_balance", STARTING_BALANCE),
            "bid_increment": room.get("bid_increment", BID_INCREMENT),
            "max_players": room.get("max_players", 20),
            "auction_duration": room.get("auction_duration", AUCTION_DURATION),
            "time_extender": room.get("time_extender", TIME_EXTENDER),
        },
    }


async def broadcast(room: dict, message: dict):
    """Send a message to all connected players in a room."""
    dead = []
    for username, ws in list(room["connections"].items()):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(username)
    for u in dead:
        room["connections"].pop(u, None)
        if u in room["players"]:
            room["players"][u]["connected"] = False


async def end_auction(room_code: str):
    """Called when auction timer expires."""
    await asyncio.sleep(0.1)  # small buffer
    room = rooms.get(room_code)
    if not room or room["state"] != "bidding":
        return

    auction = room["auction"]
    winner = auction.get("current_bidder")
    char = auction["character"]
    amount = auction["current_bid"]

    if winner:
        room["players"][winner]["balance"] -= amount
        room["players"][winner]["characters"].append({
            "name": char["name"],
            "paid": amount,
        })
        log_entry = f"🏆 {winner} won {char['name']} for ${amount:,}!"
    else:
        log_entry = f"😶 No bids — {char['name']} went unsold."

    room["bid_log"].append(log_entry)
    room["state"] = "sold"
    room["auction"]["winner"] = winner
    room["auction"]["final_amount"] = amount

    await broadcast(room, {
        "type": "state_update",
        "room": room_public_state(room),
        "toast": log_entry,
    })


# ─── HTTP Endpoints ─────────────────────────────────────────────────────────────

@app.get("/")
async def serve_index():
    return FileResponse("static/index.html")


@app.get("/game")
async def serve_game():
    return FileResponse("static/game.html")


class CreateRoomRequest(BaseModel):
    username: str
    starting_balance: int = 10000
    bid_increment: int = 100
    max_players: int = 20
    auction_duration: int = 30
    time_extender: int = 10


class JoinRoomRequest(BaseModel):
    username: str
    room_code: str


@app.post("/api/create-room")
async def create_room(req: CreateRoomRequest):
    username = req.username.strip()
    if not username or len(username) > 20:
        raise HTTPException(400, "Invalid username")

    starting_balance = max(100, req.starting_balance)
    bid_increment = max(10, req.bid_increment)
    max_players = max(2, min(100, req.max_players))
    auction_duration = max(10, min(300, req.auction_duration))
    time_extender = max(0, min(60, req.time_extender))

    code = make_room_code()
    while code in rooms:
        code = make_room_code()

    rooms[code] = {
        "code": code,
        "host": username,
        "starting_balance": starting_balance,
        "bid_increment": bid_increment,
        "max_players": max_players,
        "auction_duration": auction_duration,
        "time_extender": time_extender,
        "players": {
            username: {"balance": starting_balance, "characters": [], "connected": False}
        },
        "connections": {},
        "state": "lobby",
        "auction": None,
        "bid_log": [],
    }

    return {"room_code": code, "username": username, "starting_balance": starting_balance, "bid_increment": bid_increment}


@app.post("/api/join-room")
async def join_room(req: JoinRoomRequest):
    username = req.username.strip()
    code = req.room_code.strip().upper()

    if not username or len(username) > 20:
        raise HTTPException(400, "Invalid username")

    room = rooms.get(code)
    if not room:
        raise HTTPException(404, "Room not found")

    if room["state"] not in ("lobby",):
        if username not in room["players"]:
            raise HTTPException(400, "Game already in progress")

    if username not in room["players"]:
        if len(room["players"]) >= room.get("max_players", 20):
            raise HTTPException(400, "Room is full")
        room["players"][username] = {
            "balance": room.get("starting_balance", STARTING_BALANCE),
            "characters": [],
            "connected": False,
        }

    return {"room_code": code, "username": username, "starting_balance": room.get("starting_balance", STARTING_BALANCE)}



# ─── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws/{room_code}/{username}")
async def websocket_endpoint(ws: WebSocket, room_code: str, username: str):
    room = rooms.get(room_code)
    if not room or username not in room["players"]:
        await ws.close(code=4004)
        return

    await ws.accept()
    room["connections"][username] = ws
    room["players"][username]["connected"] = True

    # Send current state on connect
    await ws.send_json({
        "type": "state_update",
        "room": room_public_state(room),
        "toast": f"👋 {username} joined the room!",
    })

    # Notify others
    await broadcast(room, {
        "type": "state_update",
        "room": room_public_state(room),
        "toast": f"👋 {username} joined!",
    })

    try:
        while True:
            data = await ws.receive_json()
            await handle_ws_message(room, username, data)
    except WebSocketDisconnect:
        if username in room["players"]:
            room["players"][username]["connected"] = False
        room["connections"].pop(username, None)
        if username not in room["players"]:
            return  # player was already removed by host
        await broadcast(room, {
            "type": "state_update",
            "room": room_public_state(room),
            "toast": f"📴 {username} disconnected.",
        })


async def handle_ws_message(room: dict, username: str, data: dict):
    action = data.get("action")
    is_host = username == room["host"]

    # ── Host: start auction with a character name ──────────────────────────────
    if action == "start_auction" and is_host:
        if room["state"] != "lobby":
            return
        character_name = data.get("character", "").strip()
        if not character_name:
            return

        duration = room.get("auction_duration", AUCTION_DURATION)
        end_time = time.time() + duration
        room["auction"] = {
            "character": {"name": character_name},
            "current_bid": 0,
            "current_bidder": None,
            "end_time": end_time,
        }
        room["state"] = "bidding"

        task = asyncio.create_task(
            _auction_countdown(room["code"], end_time)
        )
        room["auction"]["_task"] = task

        await broadcast(room, {
            "type": "state_update",
            "room": room_public_state(room),
            "toast": f"🔨 Auction started for {character_name}! {duration}s on the clock!",
        })

    # ── Any player: place a bid ─────────────────────────────────────────────────
    elif action == "bid":
        if room["state"] != "bidding":
            return

        auction = room["auction"]
        player = room["players"][username]
        amount = data.get("amount", 0)

        bid_inc = room.get("bid_increment", BID_INCREMENT)
        min_bid = auction["current_bid"] + bid_inc
        if amount < min_bid:
            await room["connections"][username].send_json({
                "type": "error",
                "message": f"Minimum bid is ${min_bid:,}",
            })
            return

        if amount > player["balance"]:
            await room["connections"][username].send_json({
                "type": "error",
                "message": "Insufficient funds!",
            })
            return

        # Extend timer if bid placed near end
        extender = room.get("time_extender", TIME_EXTENDER)
        now = time.time()
        if extender > 0 and auction["end_time"] - now < extender:
            auction["end_time"] = now + extender

        auction["current_bid"] = amount
        auction["current_bidder"] = username

        log_entry = f"💰 {username} bids ${amount:,}"
        room["bid_log"].append(log_entry)

        await broadcast(room, {
            "type": "state_update",
            "room": room_public_state(room),
            "toast": log_entry,
        })

    # ── Host: next round (after sold) ──────────────────────────────────────────
    elif action == "next_round" and is_host:
        if room["state"] != "sold":
            return
        room["state"] = "lobby"
        room["auction"] = None
        await broadcast(room, {
            "type": "state_update",
            "room": room_public_state(room),
            "toast": "🔄 Ready for next auction!",
        })

    # ── Host: adjust a player's balance ─────────────────────────────────────────
    elif action == "host_adjust_balance" and is_host:
        target = data.get("target")
        amount = data.get("amount", 0)
        if target in room["players"]:
            room["players"][target]["balance"] += amount
            entry = f"🛠️ {username} adjusted {target}'s balance by ${amount:,}"
            room["bid_log"].append(entry)
            await broadcast(room, {
                "type": "state_update",
                "room": room_public_state(room),
                "toast": entry,
            })

    # ── Host: add a character to a player ────────────────────────────────────────
    elif action == "host_add_character" and is_host:
        target = data.get("target")
        character_name = data.get("character", "").strip()
        worth = data.get("worth", 0)
        if target in room["players"] and character_name:
            room["players"][target]["characters"].append({
                "name": character_name,
                "paid": 0,
                "worth": worth,
            })
            worth_str = f" (worth ${worth:,})" if worth else ""
            entry = f"🛠️ {username} added {character_name}{worth_str} to {target}'s roster"
            room["bid_log"].append(entry)
            await broadcast(room, {
                "type": "state_update",
                "room": room_public_state(room),
                "toast": entry,
            })

    # ── Host: remove a player from the game ──────────────────────────────────────
    elif action == "host_remove_player" and is_host:
        target = data.get("target")
        if target == username:
            return
        if target in room["players"]:
            if target in room["connections"]:
                try:
                    await room["connections"][target].close(code=1000)
                except Exception:
                    pass
                del room["connections"][target]
            del room["players"][target]
            entry = f"🛠️ {username} removed {target} from the game"
            room["bid_log"].append(entry)
            await broadcast(room, {
                "type": "state_update",
                "room": room_public_state(room),
                "toast": entry,
            })

    # ── Host: remove a character from a player ───────────────────────────────────
    elif action == "host_remove_character" and is_host:
        target = data.get("target")
        index = data.get("index")
        if target in room["players"] and isinstance(index, int):
            chars = room["players"][target]["characters"]
            if 0 <= index < len(chars):
                removed = chars.pop(index)
                entry = f"🛠️ {username} removed {removed['name']} from {target}'s roster"
                room["bid_log"].append(entry)
                await broadcast(room, {
                    "type": "state_update",
                    "room": room_public_state(room),
                    "toast": entry,
                })


async def _auction_countdown(room_code: str, end_time: float):
    """Wait until end_time then finalize auction."""
    while True:
        now = time.time()
        room = rooms.get(room_code)
        if not room or room["state"] != "bidding":
            return

        # Check if end_time was extended
        actual_end = room["auction"].get("end_time", end_time)
        remaining = actual_end - now

        if remaining <= 0:
            await end_auction(room_code)
            return

        await asyncio.sleep(min(1.0, remaining))


# ─── Dev entry point ────────────────────────────────────────────────────────────
'''
if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))

    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
'''