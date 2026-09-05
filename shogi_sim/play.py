import random
import shogi

from .usi_engine import UsiEngine
from .personality import engine_choose_move


def _judge_repetition(board):
    """
    詰みでない場合の終局理由を判定する。
    - 連続王手の千日手：王手をかけ続けていた側の反則負け
    - 通常の千日手：引き分け
    - その他（上限手数到達等）：引き分け扱い
    """
    try:
        if not board.is_fourfold_repetition():
            return "draw"
    except AttributeError:
        return "draw"

    history_len = len(board.move_stack)
    if history_len < 8:
        return "draw"

    snapshot_moves = list(board.move_stack)
    temp_board = shogi.Board()
    checks_by_color = {shogi.BLACK: True, shogi.WHITE: True}
    for i, mv in enumerate(snapshot_moves):
        temp_board.push(mv)
        mover_color = shogi.BLACK if i % 2 == 0 else shogi.WHITE
        if i >= history_len - 8:
            if not temp_board.is_check():
                checks_by_color[mover_color] = False

    if checks_by_color[shogi.BLACK] and not checks_by_color[shogi.WHITE]:
        return "perpetual_check_loss_black"
    if checks_by_color[shogi.WHITE] and not checks_by_color[shogi.BLACK]:
        return "perpetual_check_loss_white"
    return "draw"


def _final_outcome(board, my_color):
    """my_color視点での対局結果（'win'/'loss'/'draw'）を返す"""
    if board.is_checkmate():
        loser_color = board.turn
        return "loss" if loser_color == my_color else "win"

    verdict = _judge_repetition(board)
    if verdict == "draw":
        return "draw"
    losing_color = shogi.BLACK if verdict == "perpetual_check_loss_black" else shogi.WHITE
    return "loss" if losing_color == my_color else "win"


def play_vs_yaneuraou(individual, engine_path, eval_dir=None,
                       individual_think_ms=300, opponent_think_ms=80,
                       multipv=5, max_moves=256):
    """
    個体 vs やねうら王（ベンチマーク相手）を1局対局する。
    戻り値: (outcome, move_history_usi, individual_color) ※color は 'sente'/'gote'
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

        outcome = _final_outcome(board, individual_color)
        color_str = "sente" if individual_color == shogi.BLACK else "gote"
        return outcome, move_history_usi, color_str
    finally:
        search_engine.quit()
        opponent_engine.quit()


def play_individual_vs_individual(ind_a, ind_b, engine_path, eval_dir=None,
                                   think_time_ms=300, multipv=5, max_moves=256):
    """個体同士の対局。ind_a=先手、ind_b=後手で固定。"""
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

        outcome_a = _final_outcome(board, shogi.BLACK)
        return outcome_a, move_history_usi
    finally:
        search_engine.quit()
