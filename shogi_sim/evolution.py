import random
import time

from .individual import Individual, BASE_PIECE_VALUES
from .elo import update_elo
from .personality import select_survivors
from .play import play_vs_yaneuraou, play_individual_vs_individual

MUTATION_RATE = 0.15
MUTATION_STRENGTH = 0.2
YANEURAOU_FIXED_ELO = 2200.0  # ベンチマーク相手の目安Elo（think_time調整である程度動く）


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


def auto_breed(population, generation, num_children=1, top_n=3):
    ranked = sorted(population, key=lambda ind: ind.elo, reverse=True)[:top_n]
    children = []
    for i in range(num_children):
        parent_a, parent_b = random.sample(ranked, 2)
        new_id = f"G{generation}-{format(random.randint(0, 46655), 'x').upper()}"
        children.append(crossover(parent_a, parent_b, new_id, generation))
    return children


def manual_breed(population_by_id, parent_a_id, parent_b_id, generation):
    parent_a = population_by_id[parent_a_id]
    parent_b = population_by_id[parent_b_id]
    new_id = f"G{generation}-{format(random.randint(0, 46655), 'x').upper()}m"
    return crossover(parent_a, parent_b, new_id, generation)


def run_generation(population, generation, matches_log, engine_path, eval_dir=None,
                    games_vs_yaneuraou=1, games_vs_peers=2,
                    individual_think_ms=300, opponent_think_ms=80, multipv=5):
    # 1. vs やねうら王（ベンチマーク）
    for ind in population:
        for _ in range(games_vs_yaneuraou):
            outcome, kifu = play_vs_yaneuraou(
                ind, engine_path, eval_dir,
                individual_think_ms=individual_think_ms,
                opponent_think_ms=opponent_think_ms,
                multipv=multipv,
            )
            ind.elo, _ = update_elo(ind.elo, YANEURAOU_FIXED_ELO, outcome)
            ind.match_history.append({"opponent": "yaneuraou", "result": outcome, "generation": generation})
            matches_log.append({
                "individual_a_id": ind.id, "opponent_type": "yaneuraou",
                "result": outcome, "kifu": kifu, "generation": generation,
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
        })

    # 3. 交配（上位2〜3系統ベース）
    children = auto_breed(population, generation + 1, num_children=1, top_n=min(3, len(population)))

    # 4. 世代交代：Elo上位 + 多様性維持
    survivors = select_survivors(population, elo_slots=min(3, len(population)), diversity_slots=min(2, len(population)))

    return survivors + children
