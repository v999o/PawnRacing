from __future__ import annotations

import chess
from typing import Any, Dict, List, Optional


def _count_pawns(board: chess.Board, color: chess.Color) -> int:
    n = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p and p.color == color and p.piece_type == chess.PAWN:
            n += 1
    return n


class GameState:
    """
    Победа только при превращении пешки в ферзя.
    Мат не заканчивает партию: с доски снимается король стороны под матом, игра продолжается.
    Если у обеих сторон не осталось пешек — ничья.
    """

    def __init__(self) -> None:
        self._history: List[chess.Move] = []
        self.board = chess.Board()
        self._promotion_queen_winner: Optional[chess.Color] = None
        self._draw_no_pawns: bool = False
        self._recompute()

    def reset(self) -> None:
        self._history.clear()
        self._promotion_queen_winner = None
        self._draw_no_pawns = False
        self.board = chess.Board()
        self._recompute()

    def _recompute(self) -> None:
        self._promotion_queen_winner = None
        self._draw_no_pawns = False
        b = chess.Board()

        for m in self._history:
            b.push(m)
            if m.promotion == chess.QUEEN:
                self._promotion_queen_winner = not b.turn
                self.board = b
                return
            if b.is_checkmate():
                # Сторона под матом теряет короля; ход остаётся у неё (остальные фигуры).
                c = b.turn
                ks = b.king(c)
                if ks is not None:
                    b.remove_piece_at(ks)
                    b.turn = c

        if _count_pawns(b, chess.WHITE) == 0 and _count_pawns(b, chess.BLACK) == 0:
            self._draw_no_pawns = True

        self.board = b

    @property
    def game_over(self) -> bool:
        if self._promotion_queen_winner is not None:
            return True
        if self._draw_no_pawns:
            return True
        return self.board.is_game_over()

    def legal_moves_from(self, square: chess.Square) -> List[chess.Move]:
        return [m for m in self.board.legal_moves if m.from_square == square]

    def legal_moves_to(self, from_sq: chess.Square, to_sq: chess.Square) -> List[chess.Move]:
        return [
            m
            for m in self.board.legal_moves
            if m.from_square == from_sq and m.to_square == to_sq
        ]

    def push(self, move: chess.Move) -> bool:
        if self.game_over:
            return False
        if move not in self.board.legal_moves:
            return False
        self._history.append(move)
        self._recompute()
        return True

    def undo(self) -> bool:
        if self.game_over:
            return False
        if not self._history:
            return False
        self._history.pop()
        self._recompute()
        return True

    def king_square_in_check(self) -> Optional[chess.Square]:
        """Клетка короля стороны, которой сейчас ход, если объявлен шах."""
        b = self.board
        if not b.is_check():
            return None
        k = b.king(b.turn)
        return k

    def result_message(self) -> Optional[str]:
        if not self.game_over:
            return None
        if self._promotion_queen_winner == chess.WHITE:
            return "Белые выиграли: пешка превращена в ферзя."
        if self._promotion_queen_winner == chess.BLACK:
            return "Чёрные выиграли: пешка превращена в ферзя."
        if self._draw_no_pawns:
            return "Ничья: у обеих сторон нет пешек."
        outcome = self.board.outcome()
        if outcome is None:
            return "Игра окончена."
        w, t = outcome.winner, outcome.termination
        if w == chess.WHITE:
            return "Белые выиграли."
        if w == chess.BLACK:
            return "Чёрные выиграли."
        if t == chess.Termination.STALEMATE:
            return "Ничья (пат)."
        if t == chess.Termination.INSUFFICIENT_MATERIAL:
            return "Ничья (недостаточно материала)."
        if t == chess.Termination.SEVENTYFIVE_MOVES:
            return "Ничья (правило 75 ходов)."
        if t == chess.Termination.FIVEFOLD_REPETITION:
            return "Ничья (пятикратное повторение)."
        return "Ничья."

    def move_history_uci(self) -> List[str]:
        return [move.uci() for move in self._history]

    def legal_moves_uci(self) -> List[str]:
        return [move.uci() for move in self.board.legal_moves]

    def pieces_payload(self) -> List[Dict[str, Any]]:
        pieces: List[Dict[str, Any]] = []
        for sq in chess.SQUARES:
            piece = self.board.piece_at(sq)
            if piece is None:
                continue
            pieces.append(
                {
                    "square": chess.square_name(sq),
                    "color": "white" if piece.color == chess.WHITE else "black",
                    "piece_type": chess.piece_name(piece.piece_type),
                    "symbol": piece.symbol(),
                }
            )
        return pieces

    def to_payload(self) -> Dict[str, Any]:
        check_sq = self.king_square_in_check()
        return {
            "fen": self.board.fen(),
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "game_over": self.game_over,
            "result_message": self.result_message(),
            "in_check": self.board.is_check(),
            "check_square": chess.square_name(check_sq) if check_sq is not None else None,
            "pieces": self.pieces_payload(),
            "legal_moves": self.legal_moves_uci(),
            "move_history": self.move_history_uci(),
        }
