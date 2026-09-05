import random
import time

from .individual import Individual, BASE_PIECE_VALUES
from .elo import update_elo
from .personality import select_survivors
from .play import play_vs_yaneuraou, play_individual_vs_individual

MUTATION_RATE = 0.15
MUTATION_STRENGTH = 0.2


def crossover(parent_a, parent_b, new_id, generation):
    child_params = {}

    child_piece_values = {}
    for key in BASE_PIECE_VALUES:
        source = parent_a.params["piece_values"] if random.random() < 0.5 else parent_b.params["piece_values"]
        val = source.get(key, BASE_PIECE_VALUES[key])
        if random.random() < MUTATION_RATE:
            val *= random.uniform(1 - MUTATION_STRENGTH, 1 + MUTATION_STRENGTH)
        child_piece_values[key] = val
    child_params["piece_values"] = child_piece_values

    for key in ("mobility_weight", "king_safety_weight", "aggression_weight"):
        val = parent_a.params[key] if random.random() < 0.5 else parent_b.params[key]
        if random.random() < MUTATION_RATE:
            val *= random.uniform(1 - MUTATION_STRENGTH, 1 + MUTATION_STRENGTH)
        child_params[key] = val

    child = Individual(new_id, generation, parent_a.id, parent_b.id, child_params)
    child.elo = (parent_a.elo + parent_b.elo) / 2
    return child


def is_related(ind_a, ind_b):
    """兄弟（親を共有）または親子関係にある場合 True を返す（近親交配の回避用）"""
    ids_a = {ind_a.parent_a_id, ind_a.parent_b_id} - {None}
    ids_b = {ind_b.parent_a_id, ind_b.parent_b_id} - {None}
    if ind_a.id in ids_b or ind_b.id in ids_a:
        return True  # 親子関係
    if ids_a & ids_b:
        return True  # 兄弟（共通の親を持つ）
    return False


def pick_unrelated_pair(candidates, max_attempts=10):
    """近親関係にないペアをできるだけ選ぶ。見つからなければ諦めて許容する"""
    if len(candidates) < 2:
        return random.sample(candidates, min(2, len(candidates)))
    for _ in range(max_attempts):
        pair = random.sample(candidates, 2)
        if not is_related(pair[0], pair[1]):
            return pair
    return pair  # 見つからなかった場合はそのまま許容（個体数が少ない初期はやむを得ない）


def auto_breed(population, generation, num_children=1, top_n=3):
    ranked = sorted(population, key=lambda ind: ind.elo, reverse=True)[:top_n]
    children = []
    for i in range(num_children):
        parent_a, parent_b = pick_unrelated_pair(ranked)
        new_id = f"G{generation}-{format(random.randint(0, 46655), 'x').upper()}"
        children.append(crossover(parent_a, parent_b, new_id, generation))
    return children


def generate_immigrant(generation):
    """血統と無関係な完全ランダムの新規個体（遺伝的多様性の補充）"""
    new_id = f"G{generation}-{format(random.randint(0, 46655), 'x').upper()}i"
    return Individual(ind_id=new_id, generation=generation)


def manual_breed(population_by_id, parent_a_id, parent_b_id, generation):
    parent_a = population_by_id[parent_a_id]
    parent_b = population_by_id[parent_b_id]
    new_id = f"G{generation}-{format(random.randint(0, 46655), 'x').upper()}m"
    return crossover(parent_a, parent_b, new_id, generation)


def run_generation(population, generation, matches_log, engine_path, eval_dir=None,
                    games_vs_yaneuraou=1, games_vs_peers=2,
                    individual_think_ms=300, opponent_think_ms=80, multipv=5,
                    yaneuraou_elo=2200.0, immigrant_interval=5):
    # 1. vs やねうら王（ベンチマーク）
    # ベンチマーク側のレートも通常のEloと同様に更新する（固定だとインフレの原因になるため）
    for ind in population:
        for _ in range(games_vs_yaneuraou):
            outcome, kifu, color = play_vs_yaneuraou(
                ind, engine_path, eval_dir,
                individual_think_ms=individual_think_ms,
                opponent_think_ms=opponent_think_ms,
                multipv=multipv,
            )
            ind.elo, yaneuraou_elo = update_elo(ind.elo, yaneuraou_elo, outcome)
            ind.match_history.append({"opponent": "yaneuraou", "result": outcome, "generation": generation, "color": color})
            matches_log.append({
                "individual_a_id": ind.id, "opponent_type": "yaneuraou",
                "result": outcome, "kifu": kifu, "generation": generation,
                "individual_a_color": color,
            })

    # 2. 個体同士
    for _ in range(games_vs_peers):
        if len(population) < 2:
            break
        ind_a, ind_b = random.sample(population, 2)
        outcome_a, kifu = play_individual_vs_individual(
            ind_a, ind_b, engine_path, eval_dir,
            think_time_ms=individual_think_ms, multipv=multipv,
        )
        ind_a.elo, ind_b.elo = update_elo(ind_a.elo, ind_b.elo, outcome_a)
        ind_a.match_history.append({"opponent": ind_b.id, "result": outcome_a, "generation": generation})
        outcome_b = {"win": "loss", "loss": "win", "draw": "draw"}[outcome_a]
        ind_b.match_history.append({"opponent": ind_a.id, "result": outcome_b, "generation": generation})
        matches_log.append({
            "individual_a_id": ind_a.id, "individual_b_id": ind_b.id, "opponent_type": "individual",
            "result": outcome_a, "kifu": kifu, "generation": generation,
            "individual_a_color": "sente",
        })

    # 3. 交配（上位2〜3系統ベース、近親交配は極力回避）
    children = auto_breed(population, generation + 1, num_children=1, top_n=min(3, len(population)))

    # 定期的に血統と無関係な個体（移民）を1体投入し、遺伝的多様性を補充する
    if immigrant_interval and generation > 0 and generation % immigrant_interval == 0:
        immigrant = generate_immigrant(generation + 1)
        children.append(immigrant)
        print(f"  → 移民個体 {immigrant.id} を投入しました（多様性補充）")

    # 4. 世代交代：Elo上位 + 多様性維持
    survivors = select_survivors(population, elo_slots=min(3, len(population)), diversity_slots=min(2, len(population)))

    return survivors + children, yaneuraou_elo
