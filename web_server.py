from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import chess
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from game_state import GameState

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "web"


@dataclass
class PlayerSession:
    player_id: str
    color: str
    websocket: Optional[WebSocket] = None


@dataclass
class Room:
    room_id: str
    game: GameState = field(default_factory=GameState)
    players: Dict[str, PlayerSession] = field(default_factory=dict)
    sockets: Dict[str, WebSocket] = field(default_factory=dict)
    restart_votes: Set[str] = field(default_factory=set)

    def add_player(self) -> PlayerSession:
        taken_colors = {player.color for player in self.players.values()}
        if "white" not in taken_colors:
            color = "white"
        elif "black" not in taken_colors:
            color = "black"
        else:
            color = "spectator"

        session = PlayerSession(
            player_id=secrets.token_urlsafe(8),
            color=color,
        )
        self.players[session.player_id] = session
        return session

    def connect(self, player_id: str, websocket: WebSocket) -> None:
        self.players[player_id].websocket = websocket
        self.sockets[player_id] = websocket

    def disconnect(self, player_id: str) -> None:
        if player_id in self.players:
            self.players[player_id].websocket = None
        self.sockets.pop(player_id, None)

    def player_color(self, player_id: str) -> str:
        return self.players[player_id].color

    def payload_for(self, player_id: Optional[str] = None) -> Dict[str, Any]:
        payload = self.game.to_payload()
        payload["room_id"] = self.room_id
        payload["players"] = [
            {
                "player_id": player.player_id,
                "color": player.color,
                "online": player.websocket is not None,
            }
            for player in self.players.values()
        ]
        payload["restart_votes"] = len(self.restart_votes)
        if player_id is not None and player_id in self.players:
            payload["you_are"] = self.players[player_id].color
            payload["your_turn"] = payload["turn"] == self.players[player_id].color
        return payload


class RoomManager:
    def __init__(self) -> None:
        self._rooms: Dict[str, Room] = {}

    def create_room(self) -> Tuple[Room, PlayerSession]:
        room_id = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:6].upper()
        while room_id in self._rooms:
            room_id = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:6].upper()
        room = Room(room_id=room_id)
        self._rooms[room_id] = room
        player = room.add_player()
        return room, player

    def get_room(self, room_id: str) -> Room:
        room = self._rooms.get(room_id.upper())
        if room is None:
            raise KeyError(room_id)
        return room

    def join_room(self, room_id: str) -> Tuple[Room, PlayerSession]:
        room = self.get_room(room_id)
        player = room.add_player()
        return room, player


manager = RoomManager()
app = FastAPI(title="Pawn Racing Online")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


def _parse_move(move_uci: str) -> chess.Move:
    try:
        return chess.Move.from_uci(move_uci)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Некорректный ход.") from exc


def _ensure_turn(room: Room, player_id: str) -> None:
    color = room.player_color(player_id)
    if color not in {"white", "black"}:
        raise HTTPException(status_code=403, detail="Наблюдатели не могут ходить.")

    turn = "white" if room.game.board.turn == chess.WHITE else "black"
    if color != turn:
        raise HTTPException(status_code=403, detail="Сейчас ход соперника.")


async def broadcast_room(room: Room) -> None:
    stale_players: List[str] = []
    for player_id, websocket in list(room.sockets.items()):
        try:
            await websocket.send_text(
                json.dumps({"type": "state", "payload": room.payload_for(player_id)})
            )
        except Exception:
            stale_players.append(player_id)

    for player_id in stale_players:
        room.disconnect(player_id)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/rooms")
async def create_room() -> Dict[str, Any]:
    room, player = manager.create_room()
    return {
        "room_id": room.room_id,
        "player_id": player.player_id,
        "color": player.color,
        "state": room.payload_for(player.player_id),
    }


@app.post("/api/rooms/{room_id}/join")
async def join_room(room_id: str) -> Dict[str, Any]:
    try:
        room, player = manager.join_room(room_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Комната не найдена.") from exc

    return {
        "room_id": room.room_id,
        "player_id": player.player_id,
        "color": player.color,
        "state": room.payload_for(player.player_id),
    }


@app.get("/api/rooms/{room_id}")
async def room_state(room_id: str, player_id: str) -> Dict[str, Any]:
    try:
        room = manager.get_room(room_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Комната не найдена.") from exc
    if player_id not in room.players:
        raise HTTPException(status_code=404, detail="Игрок не найден в комнате.")
    return room.payload_for(player_id)


@app.post("/api/rooms/{room_id}/move")
async def make_move(room_id: str, player_id: str, move: str) -> Dict[str, Any]:
    try:
        room = manager.get_room(room_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Комната не найдена.") from exc
    if player_id not in room.players:
        raise HTTPException(status_code=404, detail="Игрок не найден в комнате.")

    _ensure_turn(room, player_id)
    parsed_move = _parse_move(move)
    if not room.game.push(parsed_move):
        raise HTTPException(status_code=400, detail="Ход отклонён сервером.")

    room.restart_votes.clear()
    await broadcast_room(room)
    return room.payload_for(player_id)


@app.post("/api/rooms/{room_id}/restart")
async def request_restart(room_id: str, player_id: str) -> Dict[str, Any]:
    try:
        room = manager.get_room(room_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Комната не найдена.") from exc
    if player_id not in room.players:
        raise HTTPException(status_code=404, detail="Игрок не найден в комнате.")

    color = room.player_color(player_id)
    if color in {"white", "black"}:
        room.restart_votes.add(color)
    if room.restart_votes >= {"white", "black"}:
        room.game.reset()
        room.restart_votes.clear()

    await broadcast_room(room)
    return room.payload_for(player_id)


@app.websocket("/ws/{room_id}/{player_id}")
async def room_socket(websocket: WebSocket, room_id: str, player_id: str) -> None:
    try:
        room = manager.get_room(room_id)
    except KeyError:
        await websocket.close(code=4404)
        return
    if player_id not in room.players:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    room.connect(player_id, websocket)
    await websocket.send_text(json.dumps({"type": "state", "payload": room.payload_for(player_id)}))
    await broadcast_room(room)

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")

            if msg_type == "move":
                _ensure_turn(room, player_id)
                move = _parse_move(data.get("move", ""))
                if room.game.push(move):
                    room.restart_votes.clear()
                    await broadcast_room(room)
                else:
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": "Ход отклонён сервером."})
                    )
            elif msg_type == "restart":
                color = room.player_color(player_id)
                if color in {"white", "black"}:
                    room.restart_votes.add(color)
                    if room.restart_votes >= {"white", "black"}:
                        room.game.reset()
                        room.restart_votes.clear()
                await broadcast_room(room)
            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            else:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Неизвестный тип сообщения."})
                )
    except WebSocketDisconnect:
        room.disconnect(player_id)
        await broadcast_room(room)


if __name__ == "__main__":
    uvicorn.run("web_server:app", host="127.0.0.1", port=8010, reload=False)
