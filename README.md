# Marvel Rivals Auction House

A multiplayer real-time auction game built with Python/FastAPI and vanilla HTML/JS.

## What This Program Does

**Marvel Rivals Auction House** is a browser-based multiplayer game where players auction off Marvel Rivals characters in real-time.

### Core Features:

- **Room Creation & Joining**: Hosts create themed auction rooms with customizable settings. Players join via unique room codes.
- **Character Auctions**: The host selects a character to auction. Players bid in real-time using WebSocket connections.
- **Real-time Bidding**: Current bid, highest bidder, and bid history are broadcast instantly to all connected players.
- **Auction Mechanics**:
  - Configurable duration (10-300 seconds)
  - Time extension when bids come in near expiration
  - Minimum bid increments enforced
  - Unsold items return to the market
- **Character Rosters**: Players earn characters they win and build their personal collections.
- **Host Controls**: Balance adjustments, player/character management for admin oversight.

---

## How the Front End Works

The frontend is a vanilla JavaScript application (no frameworks) that renders three main views:

### Landing Page (`/`)
- Hero section with animated grid background
- Username input and role selection (HOST / JOIN ROOM)
- Host: Configure room settings (balance, increment, duration, max players)
- Join: Enter room code
- POSTs to `/api/create-room` or `/api/join-room` on submit
- Redirects to `/game?room=CODE&user=USERNAME`

### Game Room (`/game`)
- Displays all connected players and their rosters
- Shows current character being auctioned (if bidding)
- Displays live bid log and auction timer
- WebSocket connection to `/ws/{ROOM_CODE}/{USERNAME}`
- Host can:
  - Pick a character to start auction
  - Place bids
  - Initiate next round / close auction
  - Adjust player balances and manage characters
- Player can:
  - Place bids above current minimum
  - Watch auction progress

### Styling & Animation
- Custom CSS with Marvel-inspired red/gold/dark theme
- Subtle grid animation on landing page
- Responsive, clean UI with real-time updates via WebSocket messages

---

## How the Back End Works

Built with **Python + FastAPI**, the backend handles WebSocket connections and manages in-memory game state.

### Architecture:

1. **FastAPI App**: Single `app` instance serving static files and WebSocket endpoints.
2. **Room Registry**: Dictionary of room codes → room objects.
3. **Rooms**: Each room contains:
   - Player data (balance, roster, online status)
   - Connection map (username → WebSocket)
   - Auction state (character, bid, timer, etc.)
   - Bid log (last 20 entries)
4. **WebSocket Endpoint**: `/ws/{room_code}/{username}`
   - Manages connection lifecycle
   - Broadcasts state updates on any event
   - Handles disconnects gracefully
5. **Auction Countdown**: Background task running until `end_time` expires.
6. **Bid Handling**: Validates minimum, sufficient funds, and prevents self-bidding.
7. **End Auction**: Deducts payment, adds character to winner's roster, broadcasts result.

### Core Endpoints:

| Endpoint | Method | Purpose |
|---------|--------|---------|
| `/`      | GET    | Serve landing page |
| `/game`  | GET    | Serve game page |
| `/api/create-room` | POST | Create new auction room |
| `/api/join-room` | POST | Join existing room |
| `/ws/{room}/{user}` | WebSocket | Real-time multiplayer channel |

### Key Functions:

- `room_public_state()`: Serializes room data safely for broadcast.
- `broadcast()`: Sends JSON message to all connected clients in a room.
- `_auction_countdown()`: Sleeps until `end_time`, then calls `end_auction()`.
- `end_auction()`: Finalizes auction, updates balances/rosters, sends toast notification.
- `handle_ws_message()`: Routes incoming messages (bid, start_auction, next_round, host actions).

---

## Running the Project

```bash
pip install -r requirements.txt
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000 to play.
