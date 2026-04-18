const boardEl = document.getElementById("board");
const createRoomBtn = document.getElementById("create-room-btn");
const joinRoomBtn = document.getElementById("join-room-btn");
const restartBtn = document.getElementById("restart-btn");
const roomIdInput = document.getElementById("room-id-input");
const roomLabel = document.getElementById("room-label");
const youLabel = document.getElementById("you-label");
const turnLabel = document.getElementById("turn-label");
const statusText = document.getElementById("status-text");
const votesText = document.getElementById("votes-text");
const playersList = document.getElementById("players-list");
const movesList = document.getElementById("moves-list");
const connectionHint = document.getElementById("connection-hint");

const files = ["a", "b", "c", "d", "e", "f", "g", "h"];
const ranks = ["8", "7", "6", "5", "4", "3", "2", "1"];
const pieceGlyphs = {
  P: "♙",
  N: "♘",
  B: "♗",
  R: "♖",
  Q: "♕",
  K: "♔",
  p: "♟",
  n: "♞",
  b: "♝",
  r: "♜",
  q: "♛",
  k: "♚",
};

const state = {
  roomId: null,
  playerId: null,
  color: null,
  socket: null,
  payload: null,
  selectedSquare: null,
};

function squareName(fileIndex, rankIndex) {
  return `${files[fileIndex]}${ranks[rankIndex]}`;
}

function pieceBySquare(payload) {
  const map = new Map();
  if (!payload) {
    return map;
  }
  for (const piece of payload.pieces) {
    map.set(piece.square, piece.symbol);
  }
  return map;
}

function legalTargetsFrom(square) {
  if (!state.payload) {
    return new Set();
  }
  const targets = new Set();
  for (const move of state.payload.legal_moves) {
    if (move.slice(0, 2) === square) {
      targets.add(move.slice(2, 4));
    }
  }
  return targets;
}

function legalMovesBetween(from, to) {
  if (!state.payload) {
    return [];
  }
  return state.payload.legal_moves.filter(
    (move) => move.slice(0, 2) === from && move.slice(2, 4) === to,
  );
}

function statusLine(payload) {
  if (!payload) {
    return "Ожидание подключения.";
  }
  if (payload.result_message) {
    return payload.result_message;
  }
  if (payload.in_check) {
    return `Шах. Ходят ${payload.turn === "white" ? "белые" : "чёрные"}.`;
  }
  return `Ходят ${payload.turn === "white" ? "белые" : "чёрные"}.`;
}

function renderBoard() {
  boardEl.innerHTML = "";
  const payload = state.payload;
  const pieces = pieceBySquare(payload);
  const targets = state.selectedSquare ? legalTargetsFrom(state.selectedSquare) : new Set();

  for (let rankIndex = 0; rankIndex < 8; rankIndex += 1) {
    for (let fileIndex = 0; fileIndex < 8; fileIndex += 1) {
      const sq = squareName(fileIndex, rankIndex);
      const square = document.createElement("button");
      square.className = "square";
      square.classList.add((fileIndex + rankIndex) % 2 === 0 ? "light" : "dark");
      square.dataset.square = sq;

      if (sq === state.selectedSquare) {
        square.classList.add("selected");
      }
      if (targets.has(sq)) {
        square.classList.add("target");
      }
      if (payload?.check_square === sq) {
        square.classList.add("check");
      }

      const pieceSymbol = pieces.get(sq);
      if (pieceSymbol) {
        square.classList.add("occupied");
        square.textContent = pieceGlyphs[pieceSymbol] || pieceSymbol;
      }

      const coord = document.createElement("span");
      coord.className = "coord";
      if (fileIndex === 0 || rankIndex === 7) {
        coord.textContent = sq;
      }
      square.appendChild(coord);

      square.addEventListener("click", () => onSquareClick(sq));
      boardEl.appendChild(square);
    }
  }
}

function renderSidebar() {
  const payload = state.payload;
  roomLabel.textContent = state.roomId ? `Код: ${state.roomId}` : "Не подключено";
  youLabel.textContent = `Роль: ${state.color || "-"}`;
  turnLabel.textContent = `Ход: ${payload ? payload.turn : "-"}`;
  statusText.textContent = statusLine(payload);
  votesText.textContent = payload ? `Голоса за рестарт: ${payload.restart_votes}/2` : "";

  playersList.innerHTML = "";
  if (payload?.players) {
    for (const player of payload.players) {
      const li = document.createElement("li");
      const marker = player.online ? "в сети" : "не в сети";
      li.textContent = `${player.color} (${marker})`;
      playersList.appendChild(li);
    }
  }

  movesList.innerHTML = "";
  if (payload?.move_history) {
    for (const move of payload.move_history) {
      const li = document.createElement("li");
      li.textContent = move;
      movesList.appendChild(li);
    }
  }
}

function renderAll() {
  renderBoard();
  renderSidebar();
}

function isOwnTurn() {
  return Boolean(
    state.payload &&
      (state.color === "white" || state.color === "black") &&
      state.payload.turn === state.color,
  );
}

function sendSocketMessage(message) {
  if (state.socket && state.socket.readyState === WebSocket.OPEN) {
    state.socket.send(JSON.stringify(message));
    return true;
  }
  return false;
}

async function postJson(url) {
  const response = await fetch(url, { method: "POST" });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Ошибка запроса");
  }
  return payload;
}

function connectSocket() {
  if (!state.roomId || !state.playerId) {
    return;
  }
  if (state.socket) {
    state.socket.close();
  }

  const wsProtocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(
    `${wsProtocol}://${window.location.host}/ws/${state.roomId}/${state.playerId}`,
  );

  socket.addEventListener("open", () => {
    connectionHint.textContent = "Соединение установлено. Отправляйте ходы из браузера.";
  });

  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "state") {
      state.payload = message.payload;
      state.selectedSquare = null;
      renderAll();
    } else if (message.type === "error") {
      statusText.textContent = message.message;
    }
  });

  socket.addEventListener("close", () => {
    connectionHint.textContent = "Соединение закрыто. Можно переподключиться повторным входом.";
  });

  state.socket = socket;
}

async function createRoom() {
  const result = await postJson("/api/rooms");
  state.roomId = result.room_id;
  state.playerId = result.player_id;
  state.color = result.color;
  state.payload = result.state;
  roomIdInput.value = result.room_id;
  connectSocket();
  renderAll();
}

async function joinRoom() {
  const roomId = roomIdInput.value.trim().toUpperCase();
  if (!roomId) {
    statusText.textContent = "Введите код комнаты.";
    return;
  }
  const result = await postJson(`/api/rooms/${roomId}/join`);
  state.roomId = result.room_id;
  state.playerId = result.player_id;
  state.color = result.color;
  state.payload = result.state;
  connectSocket();
  renderAll();
}

function chooseMove(moves) {
  if (moves.length <= 1) {
    return moves[0];
  }
  const queenPromotion = moves.find((move) => move.endsWith("q"));
  return queenPromotion || moves[0];
}

function submitMove(move) {
  if (!move) {
    return;
  }
  const sent = sendSocketMessage({ type: "move", move });
  if (!sent) {
    statusText.textContent = "Нет активного соединения с сервером.";
  }
}

function onSquareClick(square) {
  if (!state.payload || state.payload.game_over || !isOwnTurn()) {
    return;
  }

  const pieces = pieceBySquare(state.payload);
  const clickedOwnPiece = (() => {
    const symbol = pieces.get(square);
    if (!symbol) {
      return false;
    }
    return state.color === "white" ? symbol === symbol.toUpperCase() : symbol === symbol.toLowerCase();
  })();

  if (!state.selectedSquare) {
    if (clickedOwnPiece) {
      state.selectedSquare = square;
      renderBoard();
    }
    return;
  }

  const moves = legalMovesBetween(state.selectedSquare, square);
  if (moves.length) {
    submitMove(chooseMove(moves));
    return;
  }

  if (clickedOwnPiece) {
    state.selectedSquare = square;
  } else {
    state.selectedSquare = null;
  }
  renderBoard();
}

createRoomBtn.addEventListener("click", async () => {
  try {
    await createRoom();
  } catch (error) {
    statusText.textContent = error.message;
  }
});

joinRoomBtn.addEventListener("click", async () => {
  try {
    await joinRoom();
  } catch (error) {
    statusText.textContent = error.message;
  }
});

restartBtn.addEventListener("click", () => {
  const sent = sendSocketMessage({ type: "restart" });
  if (!sent) {
    statusText.textContent = "Нет активного соединения с сервером.";
  }
});

renderAll();
