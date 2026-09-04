import random
import shogi

from .individual import BASE_PIECE_VALUES

SCORE_TOLERANCE_CP = 200   # 最善手からこの点数以内なら個性選択の対象にする
PERSONALITY_SCALE = 40     # 個性ボーナスの最大振れ幅（センチポーン換算）


def personality_bonus(board, move_usi, params):
    try:
        move = shogi.Move.from_usi(move_usi)
    except Exception:
        return 0.0

    to_sq = move.to_square if hasattr(move, 'to_square') else None
    is_capture = to_sq is not None and board.piece_at(to_sq) is not None

    bonus = 0.0

    if to_sq is not None:
        rank = to_sq // 9
        advance = rank if board.turn == shogi.BLACK else (8 - rank)
        bonus += params["aggression_weight"] * advance * 0.6
    if is_capture:
        bonus += params["aggression_weight"] * 3.0

    king_sq = None
    for sq in shogi.SQUARES:
        p = board.piece_at(sq)
        if p and p.piece_type == shogi.KING and p.color == board.turn:
            king_sq = sq
            break
    if king_sq is not None and to_sq is not None:
        kr, kf = king_sq // 9, king_sq % 9
        tr, tf = to_sq // 9, to_sq % 9
        dist = abs(kr - tr) + abs(kf - tf)
        bonus -= params["king_safety_weight"] * dist * 0.15

    return max(-PERSONALITY_SCALE, min(PERSONALITY_SCALE, bonus))


def select_move_by_personality(board, candidates, params):
    if not candidates:
        return None
    best_score = candidates[0][1]
    eligible = [(mv, sc) for mv, sc in candidates if best_score - sc <= SCORE_TOLERANCE_CP]
    if not eligible:
        eligible = candidates[:1]

    scored = [(mv, sc + personality_bonus(board, mv, params)) for mv, sc in eligible]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


def engine_choose_move(engine, board, sfen_moves, params, multipv=5):
    candidates = engine.get_multipv_candidates(sfen_moves, multipv=multipv)
    move_usi = select_move_by_personality(board, candidates, params)
    if move_usi is None:
        legal_moves = list(board.legal_moves)
        return random.choice(legal_moves).usi() if legal_moves else None
    return move_usi


# ------------------------------------------------------------
# 多様性維持セレクション
# ------------------------------------------------------------
def style_vector(individual):
    p = individual.params
    pv = p["piece_values"]
    base = BASE_PIECE_VALUES
    return [
        p["aggression_weight"] / 5.0,
        p["king_safety_weight"] / 25.0,
        p["mobility_weight"] / 8.0,
        (pv.get("R", base["R"]) / base["R"]) - 1.0,
        (pv.get("B", base["B"]) / base["B"]) - 1.0,
        (pv.get("P", base["P"]) / base["P"]) - 1.0,
    ]


def vector_distance(v1, v2):
    return sum((a - b) ** 2 for a, b in zip(v1, v2)) ** 0.5


def diversity_score(individual, population):
    others = [ind for ind in population if ind.id != individual.id]
    if not others:
        return 0.0
    v = style_vector(individual)
    dists = [vector_distance(v, style_vector(o)) for o in others]
    return sum(dists) / len(dists)


def select_survivors(population, elo_slots=3, diversity_slots=2):
    """Elo上位 elo_slots体 ＋ 個性的な diversity_slots体 を残す（重複除外）"""
    ranked_by_elo = sorted(population, key=lambda ind: ind.elo, reverse=True)
    survivors = ranked_by_elo[:elo_slots]
    survivor_ids = {ind.id for ind in survivors}

    remaining = [ind for ind in population if ind.id not in survivor_ids]
    remaining_scored = sorted(
        remaining,
        key=lambda ind: diversity_score(ind, population),
        reverse=True
    )
    survivors += remaining_scored[:diversity_slots]
    return survivors
