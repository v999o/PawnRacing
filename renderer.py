from __future__ import annotations

import chess
import pygame

LIGHT_SQ = (240, 217, 181)
DARK_SQ = (181, 136, 99)
HIGHLIGHT = (186, 202, 68, 120)
CHECK_RING = (220, 50, 50)
MOVE_DOT = (0, 0, 0, 90)
TEXT_BG = (40, 40, 40)
TEXT_FG = (230, 230, 230)

def _text_width(font: pygame.font.Font, text: str) -> int:
    return font.render(text, True, TEXT_FG).get_width()


def _break_long_word(word: str, font: pygame.font.Font, max_width: int) -> list[str]:
    if _text_width(font, word) <= max_width:
        return [word]
    parts: list[str] = []
    chunk = ""
    for ch in word:
        trial = chunk + ch
        if _text_width(font, trial) <= max_width:
            chunk = trial
        else:
            if chunk:
                parts.append(chunk)
            chunk = ch
    if chunk:
        parts.append(chunk)
    return parts


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Перенос по словам; слишком длинные слова режутся по символам (без пробела между частями)."""
    if max_width <= 0:
        return [text] if text else [""]
    result: list[str] = []
    for paragraph in text.replace("\r", "").split("\n"):
        words = paragraph.split()
        if not paragraph.strip() and not words:
            result.append("")
            continue
        if not words:
            result.append("")
            continue
        line = ""
        for w in words:
            if _text_width(font, w) <= max_width:
                trial = w if not line else line + " " + w
                if _text_width(font, trial) <= max_width:
                    line = trial
                else:
                    if line:
                        result.append(line)
                    line = w
            else:
                if line:
                    result.append(line)
                    line = ""
                for part in _break_long_word(w, font, max_width):
                    if not line:
                        line = part
                    elif _text_width(font, line + part) <= max_width:
                        line += part
                    else:
                        result.append(line)
                        line = part
        if line:
            result.append(line)
    return result if result else [""]

UNICODE_PIECES = {
    (chess.PAWN, chess.WHITE): "\u2659",
    (chess.KNIGHT, chess.WHITE): "\u2658",
    (chess.BISHOP, chess.WHITE): "\u2657",
    (chess.ROOK, chess.WHITE): "\u2656",
    (chess.QUEEN, chess.WHITE): "\u2655",
    (chess.KING, chess.WHITE): "\u2654",
    (chess.PAWN, chess.BLACK): "\u265f",
    (chess.KNIGHT, chess.BLACK): "\u265e",
    (chess.BISHOP, chess.BLACK): "\u265d",
    (chess.ROOK, chess.BLACK): "\u265c",
    (chess.QUEEN, chess.BLACK): "\u265b",
    (chess.KING, chess.BLACK): "\u265a",
}


def _font_candidates():
    for name in (
        "Segoe UI Symbol",
        "DejaVu Sans",
        "Arial Unicode MS",
    ):
        yield name


def load_piece_font(size: int) -> pygame.font.Font:
    for name in _font_candidates():
        f = pygame.font.SysFont(name, size)
        test = f.render("\u2654", True, (0, 0, 0))
        if test.get_width() > 1:
            return f
    return pygame.font.Font(None, size)


class BoardRenderer:
    def __init__(self, square_px: int = 64) -> None:
        self.square_px = square_px
        self.board_px = 8 * square_px
        self.piece_font = load_piece_font(int(square_px * 0.72))
        self.label_font = pygame.font.SysFont("Segoe UI", 14)

    def square_at_pixel(self, x: int, y: int) -> chess.Square | None:
        if x < 0 or y < 0 or x >= self.board_px or y >= self.board_px:
            return None
        col = x // self.square_px
        row = y // self.square_px
        rank = 7 - row
        file_idx = col
        return chess.square(file_idx, rank)

    def square_rect(self, square: chess.Square) -> pygame.Rect:
        f = chess.square_file(square)
        r = chess.square_rank(square)
        row = 7 - r
        x = f * self.square_px
        y = row * self.square_px
        return pygame.Rect(x, y, self.square_px, self.square_px)

    def center_of_square(self, square: chess.Square) -> tuple[int, int]:
        rect = self.square_rect(square)
        return rect.centerx, rect.centery

    def draw_board(
        self,
        surface: pygame.Surface,
        board: chess.Board,
        selected: chess.Square | None,
        legal_targets: set[chess.Square] | None,
        king_in_check_square: chess.Square | None = None,
    ) -> None:
        sp = self.square_px
        for sq in chess.SQUARES:
            rect = self.square_rect(sq)
            light = (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 0
            color = LIGHT_SQ if light else DARK_SQ
            pygame.draw.rect(surface, color, rect)

        if selected is not None:
            s = pygame.Surface((sp, sp), pygame.SRCALPHA)
            s.fill(HIGHLIGHT)
            surface.blit(s, self.square_rect(selected).topleft)

        if legal_targets:
            for tsq in legal_targets:
                cx, cy = self.center_of_square(tsq)
                piece = board.piece_at(tsq)
                r = sp // 6 if piece else sp // 10
                dot = pygame.Surface((2 * r, 2 * r), pygame.SRCALPHA)
                pygame.draw.circle(dot, MOVE_DOT, (r, r), r)
                surface.blit(dot, (cx - r, cy - r))

        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece is None:
                continue
            ch = UNICODE_PIECES[(piece.piece_type, piece.color)]
            surf = self.piece_font.render(ch, True, (20, 20, 20))
            rect = surf.get_rect(center=self.center_of_square(sq))
            surface.blit(surf, rect)

        if king_in_check_square is not None:
            r = self.square_rect(king_in_check_square).inflate(4, 4)
            pygame.draw.rect(surface, CHECK_RING, r, width=4)

        for i in range(8):
            file_letter = chr(ord("a") + i)
            lbl = self.label_font.render(file_letter, True, (60, 60, 60))
            surface.blit(lbl, (i * sp + 4, 7 * sp + sp - 18))
            lbl_r = self.label_font.render(str(8 - i), True, (60, 60, 60))
            surface.blit(lbl_r, (4, i * sp + 4))


def draw_status_bar(
    surface: pygame.Surface,
    y_offset: int,
    width: int,
    status_text: str,
    *,
    status_bar_height: int,
    restart_rect: pygame.Rect | None = None,
    restart_label: str = "Новая партия",
    font_name: str = "Segoe UI",
    base_font_size: int = 18,
) -> None:
    pad_x = 8
    pad_y = 6
    max_text_w = width - 2 * pad_x
    if restart_rect is not None:
        max_text_w = max(40, restart_rect.x - pad_x - 4)

    inner_h = max(0, status_bar_height - 2 * pad_y)
    chosen_font = pygame.font.SysFont(font_name, 11)
    lines = wrap_text(status_text, chosen_font, max_text_w)
    for size in range(base_font_size, 10, -1):
        f = pygame.font.SysFont(font_name, size)
        ls = wrap_text(status_text, f, max_text_w)
        lh = f.get_linesize()
        if len(ls) * lh <= inner_h:
            chosen_font = f
            lines = ls
            break

    bar = pygame.Rect(0, y_offset, width, status_bar_height)
    pygame.draw.rect(surface, TEXT_BG, bar)

    y = y_offset + pad_y
    for ln in lines:
        surf = chosen_font.render(ln, True, TEXT_FG)
        surface.blit(surf, (pad_x, y))
        y += chosen_font.get_linesize()

    if restart_rect is not None:
        btn_sz = max(11, min(15, chosen_font.get_height()))
        btn_font = pygame.font.SysFont(font_name, btn_sz)
        pygame.draw.rect(surface, (70, 130, 200), restart_rect, border_radius=4)
        pygame.draw.rect(surface, (200, 220, 255), restart_rect, width=1, border_radius=4)
        rt = btn_font.render(restart_label, True, (255, 255, 255))
        surface.blit(rt, rt.get_rect(center=restart_rect.center))


def draw_promotion_bar(
    surface: pygame.Surface,
    y_offset: int,
    width: int,
    piece_font: pygame.font.Font,
    labels: list[tuple[str, pygame.Rect]],
) -> None:
    bar_h = 48
    bar = pygame.Rect(0, y_offset, width, bar_h)
    pygame.draw.rect(surface, (45, 45, 48), bar)
    if not labels:
        return
    hint = pygame.font.SysFont("Segoe UI", 16).render(
        "Превращение — выберите фигуру:", True, TEXT_FG
    )
    surface.blit(hint, (8, y_offset + 4))
    for label, rect in labels:
        pygame.draw.rect(surface, (80, 80, 88), rect, border_radius=4)
        t = piece_font.render(label, True, (240, 240, 240))
        tr = t.get_rect(center=rect.center)
        surface.blit(t, tr)
