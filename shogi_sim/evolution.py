import itertools
import random
import time

from .individual import Individual, BASE_PIECE_VALUES
from .elo import update_elo
from .play import play_vs_yaneuraou, play_individual_vs_individual

MUTATION_RATE = 0.15
MUTATION_STRENGTH = 0.2


# ============================================================
# 近親交配の回避
# ============================================================
def is_related(ind_a, ind_b):
    """兄弟（親を共有）または親子関係にある場合 True"""
    ids_a = {ind_a.parent_a_id, ind_a.parent_b_id} - {None}
    ids_b = {ind_b.parent_a_id, ind_b.parent_b_id} - {None}
    if ind_a.id in ids_b or ind_b.id in ids_a:
        return True
    if ids_a & ids_b:
        return True
    return False


# ============================================================
# 主副交配：主から駒の価値観・家名、副から性格を継承。必ず主副入替で2体作る
# ============================================================
def crossover_main_sub(parent_main, parent_sub, new_id, generation):
    child_params = {"piece_values": {}}
    for key in BASE_PIECE_VALUES:
        val = parent_main.params["piece_values"].get(key, BASE_PIECE_VALUES[key])
        if random.random() < MUTATION_RATE:
            val *= random.uniform(1 - MUTATION_STRENGTH, 1 + MUTATION_STRENGTH)
        child_params["piece_values"][key] = val

    for key in ("mobility_weight", "king_safety_weight", "aggression_weight"):
        val = parent_sub.params[key]
        if random.random() < MUTATION_RATE:
            val *= random.uniform(1 - MUTATION_STRENGTH, 1 + MUTATION_STRENGTH)
        child_params[key] = val

    child = Individual(
        new_id, generation, parent_main.id, parent_sub.id, child_params,
        family_label=parent_main.family_label,
    )
    child.elo = parent_main.elo  # 主の実力を起点にする（平均ではなく主基準）
    return child


def breed_pair_both_directions(ind_x, ind_y, generation):
    """主副を入れ替えて2体の子を作る（両家統が必ず1体ずつ継承機会を得る）"""
    id1 = f"G{generation}-{format(random.randint(0, 46655), 'x').upper()}"
    id2 = f"G{generation}-{format(random.randint(0, 46655), 'x').upper()}"
    child1 = crossover_main_sub(ind_x, ind_y, id1, generation)  # x が主
    child2 = crossover_main_sub(ind_y, ind_x, id2, generation)  # y が主
    return [child1, child2]


def generate_immigrant(generation):
    """血統と無関係な完全ランダムの新規個体（多様性の補充）"""
    new_id = f"G{generation}-{format(random.randint(0, 46655), 'x').upper()}i"
    return Individual(ind_id=new_id, generation=generation)


def manual_breed(population_by_id, parent_a_id, parent_b_id, generation):
    """手動交配：主=A、副=Bとして1体だけ作る（UIから明示的に指定する用途）"""
    parent_a = population_by_id[parent_a_id]
    parent_b = population_by_id[parent_b_id]
    new_id = f"G{generation}-{format(random.randint(0, 46655), 'x').upper()}m"
    return crossover_main_sub(parent_a, parent_b, new_id, generation)


# ============================================================
# スイス方式トーナメント
# ============================================================
def swiss_pairing(ranked_ids, played_pairs):
    """スコア順に並んだID列から、既対戦を避けつつペアを組む"""
    unpaired = list(ranked_ids)
    pairs = []
    while len(unpaired) >= 2:
        a = unpaired.pop(0)
        matched_idx = None
        for i, b in enumerate(unpaired):
            if frozenset((a, b)) not in played_pairs:
                matched_idx = i
                break
        if matched_idx is None:
            matched_idx = 0  # 全員と対戦済みならやむを得ず再戦を許容
        b = unpaired.pop(matched_idx)
        pairs.append((a, b))
    return pairs


def run_swiss_tournament(population, generation, matches_log, engine_path, eval_dir=None,
                          rounds=4, think_time_ms=300, multipv=5):
    """
    個体同士のスイス方式トーナメント。
    総当たりより少ない対局数で、実力順に近い結果を得る。
    ここで得た結果が唯一のEloの更新源になる（やねうら王戦はEloに影響させない）。
    """
    by_id = {ind.id: ind for ind in population}
    score = {ind.id: 0.0 for ind in population}
    played_pairs = set()

    for _ in range(rounds):
        ranked_ids = sorted(by_id.keys(), key=lambda i: (-score[i], -by_id[i].elo))
        pairs = swiss_pairing(ranked_ids, played_pairs)

        for (a_id, b_id) in pairs:
            played_pairs.add(frozenset((a_id, b_id)))
            ind_a, ind_b = by_id[a_id], by_id[b_id]

            outcome_a, kifu = play_individual_vs_individual(
                ind_a, ind_b, engine_path, eval_dir,
                think_time_ms=think_time_ms, multipv=multipv,
            )
            ind_a.elo, ind_b.elo = update_elo(ind_a.elo, ind_b.elo, outcome_a)

            if outcome_a == "win":
                score[a_id] += 1.0
            elif outcome_a == "loss":
                score[b_id] += 1.0
            else:
                score[a_id] += 0.5
                score[b_id] += 0.5

            outcome_b = {"win": "loss", "loss": "win", "draw": "draw"}[outcome_a]
            ind_a.match_history.append({"opponent": b_id, "result": outcome_a, "generation": generation})
            ind_b.match_history.append({"opponent": a_id, "result": outcome_b, "generation": generation})
            matches_log.append({
                "individual_a_id": a_id, "individual_b_id": b_id, "opponent_type": "individual",
                "result": outcome_a, "kifu": kifu, "generation": generation,
                "individual_a_color": "sente",
            })

    return score


# ============================================================
# やねうら王「温度計」：Eloには影響させず、現在のレベルを監視するためだけの対局
# ============================================================
def run_yaneuraou_thermometer(top_individual, generation, matches_log, engine_path, eval_dir=None,
                               games=2, individual_think_ms=300, opponent_think_ms=80, multipv=5):
    for _ in range(games):
        outcome, kifu, color = play_vs_yaneuraou(
            top_individual, engine_path, eval_dir,
            individual_think_ms=individual_think_ms,
            opponent_think_ms=opponent_think_ms,
            multipv=multipv,
        )
        # 意図的にEloは更新しない（温度計としての記録のみ）
        top_individual.match_history.append({
            "opponent": "yaneuraou", "result": outcome, "generation": generation, "color": color,
        })
        matches_log.append({
            "individual_a_id": top_individual.id, "opponent_type": "yaneuraou",
            "result": outcome, "kifu": kifu, "generation": generation,
            "individual_a_color": color,
        })


# ============================================================
# 新規参入個体の生成：移民 + 上位個体同士の主副交配
# ============================================================
def generate_new_entrants(survivors, generation, population_size, immigrant_count=2):
    new_entrants = []
    for _ in range(immigrant_count):
        new_entrants.append(generate_immigrant(generation))

    needed = population_size - len(survivors) - len(new_entrants)
    if needed <= 0:
        return new_entrants[:max(0, population_size - len(survivors))]

    top_pool = sorted(survivors, key=lambda ind: -ind.elo)[:max(3, min(len(survivors), 4))]
    combos = list(itertools.combinations(top_pool, 2))
    random.shuffle(combos)

    idx = 0
    attempts = 0
    while len(new_entrants) < population_size - len(survivors) and combos and attempts < len(combos) * 3:
        x, y = combos[idx % len(combos)]
        attempts += 1
        idx += 1
        if is_related(x, y) and attempts < len(combos) * 2:
            continue
        for child in breed_pair_both_directions(x, y, generation):
            if len(new_entrants) < population_size - len(survivors):
                new_entrants.append(child)

    return new_entrants


# ============================================================
# 1世代分の処理
# ============================================================
def run_generation(population, generation, matches_log, engine_path, eval_dir=None,
                    population_size=16, swiss_rounds=4,
                    individual_think_ms=300, opponent_think_ms=80, multipv=5,
                    yaneuraou_games=2, immigrant_count=2, immigrant_interval=5):
    # 1. スイス方式トーナメント（Eloの唯一の更新源）
    score = run_swiss_tournament(
        population, generation, matches_log, engine_path, eval_dir,
        rounds=swiss_rounds, think_time_ms=individual_think_ms, multipv=multipv,
    )

    # 2. 順位確定：トーナメント成績 → 同点はEloで判定
    ranked = sorted(population, key=lambda ind: (-score[ind.id], -ind.elo))

    # 3. やねうら王との温度計対局（首位のみ、Eloには影響なし）
    if ranked:
        run_yaneuraou_thermometer(
            ranked[0], generation, matches_log, engine_path, eval_dir,
            games=yaneuraou_games,
            individual_think_ms=individual_think_ms,
            opponent_think_ms=opponent_think_ms,
            multipv=multipv,
        )

    # 4. 上位半分が残留
    survivors = ranked[:max(1, population_size // 2)]

    # 5. 残りの枠を移民＋交配で補充（定期的に移民を増やす）
    this_gen_immigrants = immigrant_count
    if immigrant_interval and generation > 0 and generation % immigrant_interval == 0:
        this_gen_immigrants += 1

    new_entrants = generate_new_entrants(survivors, generation + 1, population_size, this_gen_immigrants)

    return survivors + new_entrants
