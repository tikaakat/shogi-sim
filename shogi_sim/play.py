import random
import shogi

from .usi_engine import UsiEngine
from .personality import engine_choose_move


def play_vs_yaneuraou(individual, engine_path, eval_dir=None,
                       individual_think_ms=300, opponent_think_ms=80,
                       multipv=5, max_moves=256):
    """
    個体 vs やねうら王（ベンチマーク相手）を1局対局する。
    opponent_think_ms を短くすることで、相手の強さを「目標としたい壁」
    （将棋ウォーズ1級〜初段程度）に調整する想定。
    """
    search_engine = UsiEngine(engine_path, eval_dir, think_time_ms=individual_think_ms)
    opponent_engine = UsiEngine(engine_path, eval_dir, think_time_ms=opponent_think_ms)

    board = shogi.Board()
    move_history_usi = []
    individual_color = random.choice([shogi.BLACK, shogi.WHITE])

    try:
        for _ in range(max_moves):
            if board.is_game_over():
                break
            if board.turn == individual_color:
                move_usi = engine_choose_move(search_engine, board, move_history_usi, individual.params, multipv=multipv)
                if move_usi is None:
                    break
            else:
                move_usi = opponent_engine.best_move(move_history_usi)
                if move_usi in ("resign", "win"):
                    break

            move = shogi.Move.from_usi(move_usi)
            move_history_usi.append(move_usi)
            board.push(move)

        if board.is_checkmate():
            loser_color = board.turn
            outcome = "loss" if loser_color == individual_color else "win"
        else:
            outcome = "draw"
        return outcome, move_history_usi
    finally:
        search_engine.quit()
        opponent_engine.quit()


def play_individual_vs_individual(ind_a, ind_b, engine_path, eval_dir=None,
                                   think_time_ms=300, multipv=5, max_moves=256):
    """個体同士の対局。探索は同じやねうら王バイナリを共有し、手番側の個性で候補手を選ぶ"""
    search_engine = UsiEngine(engine_path, eval_dir, think_time_ms=think_time_ms)
    board = shogi.Board()
    move_history_usi = []
    turn_map = {shogi.BLACK: ind_a, shogi.WHITE: ind_b}

    try:
        for _ in range(max_moves):
            if board.is_game_over():
                break
            current = turn_map[board.turn]
            move_usi = engine_choose_move(search_engine, board, move_history_usi, current.params, multipv=multipv)
            if move_usi is None:
                break
            move = shogi.Move.from_usi(move_usi)
            move_history_usi.append(move_usi)
            board.push(move)

        if board.is_checkmate():
            loser_color = board.turn
            outcome_a = "loss" if loser_color == shogi.BLACK else "win"
        else:
            outcome_a = "draw"
        return outcome_a, move_history_usi
    finally:
        search_engine.quit()
