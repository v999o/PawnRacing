from __future__ import annotations

import sys

import chess
import pygame

from game_state import GameState
from renderer import BoardRenderer, draw_promotion_bar, draw_status_bar, load_piece_font

STATUS_H = 64
PROMO_H = 48
RESTART_BTN_W = 128
RESTART_BTN_H = 28


def main() -> None:
    pygame.init()
    square_px = 64
    render = BoardRenderer(square_px)
    board_px = render.board_px
    promo_choice_font = load_piece_font(28)

    game = GameState()
    selected: chess.Square | None = None
    pending_promotion_moves: list[chess.Move] | None = None
    promo_buttons: list[tuple[chess.Move, pygame.Rect]] = []

    win_h = board_px + STATUS_H + PROMO_H
    screen = pygame.display.set_mode((board_px, win_h))
    pygame.display.set_caption("Pawn Racing — MVP")
    clock = pygame.time.Clock()

    def restart_rect() -> pygame.Rect | None:
        if not game.game_over:
            return None
        return pygame.Rect(
            board_px - RESTART_BTN_W - 8,
            board_px + (STATUS_H - RESTART_BTN_H) // 2,
            RESTART_BTN_W,
            RESTART_BTN_H,
        )

    def rebuild_promo_buttons() -> None:
        nonlocal promo_buttons
        promo_buttons = []
        if not pending_promotion_moves:
            return
        by_prom: dict[int, chess.Move] = {}
        for m in pending_promotion_moves:
            by_prom[m.promotion] = m
        order = [
            (chess.QUEEN, "\u2655"),
            (chess.ROOK, "\u2656"),
            (chess.BISHOP, "\u2657"),
            (chess.KNIGHT, "\u2658"),
        ]
        y0 = board_px + STATUS_H + 8
        bw, bh = 52, 36
        gap = 10
        x0 = max(8, (board_px - (len(order) * bw + (len(order) - 1) * gap)) // 2)
        x = x0
        for pt, sym in order:
            if pt not in by_prom:
                continue
            rect = pygame.Rect(x, y0, bw, bh)
            promo_buttons.append((by_prom[pt], rect))
            x += bw + gap

    def status_line() -> str:
        if game.game_over:
            return game.result_message() or "Игра окончена."
        if pending_promotion_moves:
            return "Превращение: нажмите фигуру снизу или Esc — отмена."
        turn = "Белые" if game.board.turn == chess.WHITE else "Чёрные"
        base = f"Ход: {turn}.  U — отменить ход."
        if game.board.is_check():
            return "Шах!  " + base
        return base

    def legal_target_squares() -> set[chess.Square]:
        if selected is None:
            return set()
        return {m.to_square for m in game.legal_moves_from(selected)}

    def new_game() -> None:
        nonlocal selected, pending_promotion_moves
        game.reset()
        selected = None
        pending_promotion_moves = None
        rebuild_promo_buttons()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pending_promotion_moves = None
                    rebuild_promo_buttons()
                elif event.key == pygame.K_u and not game.game_over:
                    if game.undo():
                        selected = None
                        pending_promotion_moves = None
                        rebuild_promo_buttons()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                mx, my = event.pos
                rr = restart_rect()
                if rr is not None and rr.collidepoint(mx, my):
                    new_game()
                    continue
                if pending_promotion_moves:
                    for move, rect in promo_buttons:
                        if rect.collidepoint(mx, my):
                            if game.push(move):
                                selected = None
                                pending_promotion_moves = None
                                rebuild_promo_buttons()
                            break
                    continue
                if game.game_over:
                    continue
                if mx >= board_px or my >= board_px:
                    continue
                sq = render.square_at_pixel(mx, my)
                if sq is None:
                    continue

                piece = game.board.piece_at(sq)
                if selected is not None:
                    moves = game.legal_moves_to(selected, sq)
                    if moves:
                        if len(moves) == 1:
                            if game.push(moves[0]):
                                selected = None
                        else:
                            pending_promotion_moves = moves
                            rebuild_promo_buttons()
                    else:
                        selected = None
                        if piece and piece.color == game.board.turn:
                            selected = sq
                else:
                    if piece and piece.color == game.board.turn:
                        selected = sq

        check_sq = None
        if not game.game_over:
            check_sq = game.king_square_in_check()

        screen.fill((30, 30, 34))
        board_surf = pygame.Surface((board_px, board_px))
        render.draw_board(
            board_surf,
            game.board,
            selected,
            legal_target_squares() if not game.game_over else None,
            check_sq,
        )
        screen.blit(board_surf, (0, 0))
        draw_status_bar(
            screen,
            board_px,
            board_px,
            status_line(),
            status_bar_height=STATUS_H,
            restart_rect=restart_rect(),
            restart_label="Новая партия",
        )

        labels_for_bar: list[tuple[str, pygame.Rect]] = []
        if pending_promotion_moves:
            for move, rect in promo_buttons:
                sym = {
                    chess.QUEEN: "\u2655",
                    chess.ROOK: "\u2656",
                    chess.BISHOP: "\u2657",
                    chess.KNIGHT: "\u2658",
                }.get(move.promotion, "?")
                labels_for_bar.append((sym, rect))
        draw_promotion_bar(
            screen,
            board_px + STATUS_H,
            board_px,
            promo_choice_font,
            labels_for_bar,
        )

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
