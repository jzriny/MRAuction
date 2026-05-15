# 🔨 Marvel Rivals Auction House

A real-time online auction app for you and friends to bid on Marvel Rivals characters chosen by spinning wheels.

---

## Features

- **Host/Join rooms** with a 6-character room code
- **$10,000 starting balance** per player
- **Role Wheel** — spins between Vanguard, Duelist, Strategist
- **Character Wheel** — spins through all characters in the selected role
- **Live bidding** with a 30-second countdown timer
  - Timer extends by 10 seconds if a bid is placed in the last 10s (sniping protection)
- **Quick bid buttons** (+$100, +$500, +$1,000) or custom amount
- **Real-time updates** via WebSockets — all players see bids instantly
- **All 38 Marvel Rivals characters** included at launch

## Character Roster

| Vanguard | Duelist | Strategist |
|---|---|---|
| Doctor Strange, Groot, Hulk, Magneto, Peni Parker, Thor, Venom, Captain America, The Thing, Emma Frost | Black Panther, Black Widow, Hawkeye, Hela, Iron Fist, Iron Man, Magik, Mister Fantastic, Moon Knight, Namor, Psylocke, Scarlet Witch, Spider-Man, Squirrel Girl, Star-Lord, Storm, The Punisher, Winter Soldier, Wolverine, Human Torch | Adam Warlock, Cloak & Dagger, Invisible Woman, Jeff the Land Shark, Loki, Luna Snow, Mantis, Rocket Raccoon |

---

## Setup

### Requirements
- Python 3.10+

### Install

```bash
cd marvel-auction
pip install -r requirements.txt
```

### Run

```bash
python server.py
# or for hot-reload during development:
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Then open **http://localhost:8000** in your browser.

To play with friends on your local network, share your **local IP address** (e.g. `http://192.168.1.x:8000`).

---

## How to Play

1. **Host** opens the site, picks "HOST ROOM", enters a username, clicks Enter
2. **Friends** open the site, pick "JOIN ROOM", enter the room code shown in the host's header
3. Once everyone is in, the **host clicks "SPIN THE WHEEL"**
4. The **Role Wheel** spins → host clicks Spin Role → lands on Vanguard/Duelist/Strategist
5. The **Character Wheel** spins → host clicks Spin Character → lands on a specific hero
6. **30-second auction begins** — anyone can bid using quick buttons or a custom amount
7. Highest bidder wins the character; their balance is deducted
8. Host clicks **NEXT AUCTION** to go again
9. Play as many rounds as you want!

## Configuration (server.py)

| Setting | Default | Description |
|---|---|---|
| `STARTING_BALANCE` | 10000 | Starting $ per player |
| `BID_INCREMENT` | 100 | Minimum bid increment |
| `AUCTION_DURATION` | 30 | Auction timer in seconds |

---

## Project Structure

```
marvel-auction/
├── server.py           # FastAPI backend + WebSocket logic
├── requirements.txt    # Python dependencies
├── README.md
└── static/
    └── index.html      # Full frontend (HTML + CSS + JS)
```
