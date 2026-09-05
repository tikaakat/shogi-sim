import argparse
import random

from shogi_sim.individual import Individual
from shogi_sim.evolution import run_generation
from shogi_sim.io_utils import load_checkpoint, export_population, load_training_state, save_training_state
from shogi_sim.family_names import assign_initial_family_names

# ベンチマーク相手（やねうら王）の思考時間を自動で引き上げるための設定
# ※Eloには影響しない「温度計」としての難易度調整
OPPONENT_THINK_MS_MAX = 1000
OPPONENT_THINK_MS_STEP = 50
WIN_RATE_UPGRADE_THRESHOLD = 0.65
WIN_RATE_DOWNGRADE_THRESHOLD = 0.25


def compute_win_rate_vs_yaneuraou(matches_log, generation):
    relevant = [m for m in matches_log if m.get("opponent_type") == "yaneuraou" and m.get("generation") == generation]
    if not relevant:
        return None
    wins = sum(1 for m in relevant if m["result"] == "win")
    draws = sum(1 for m in relevant if m["result"] == "draw")
    return (wins + 0.5 * draws) / len(relevant)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-path", required=True, help="やねうら王バイナリのパス")
    parser.add_argument("--eval-dir", default=None, help="評価関数ファイルのディレクトリ（MATERIAL版なら不要）")
    parser.add_argument("--data-dir", default="data", help="individuals.json / matches.json の保存先")
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--population-size", type=int, default=16, help="個体数（固定）")
    parser.add_argument("--swiss-rounds", type=int, default=4, help="スイス方式トーナメントのラウンド数")
    parser.add_argument("--yaneuraou-games", type=int, default=2, help="首位個体がやねうら王と対局する回数（温度計）")
    parser.add_argument("--immigrant-count", type=int, default=2, help="毎世代投入する移民の基本数")
    parser.add_argument("--immigrant-interval", type=int, default=5, help="この世代数おきに移民を1体増やす。0で無効")
    parser.add_argument("--individual-think-ms", type=int, default=300)
    parser.add_argument("--opponent-think-ms", type=int, default=80,
                         help="ベンチマーク相手の初期思考時間。2回目以降は training_state.json の値が優先")
    parser.add_argument("--multipv", type=int, default=5)
    args = parser.parse_args()

    all_individuals, matches_log = load_checkpoint(args.data_dir)
    training_state = load_training_state(args.data_dir)

    opponent_think_ms = training_state.get("opponent_think_ms") or args.opponent_think_ms
    win_rate_history = training_state.get("win_rate_history", [])
    active_population_ids = training_state.get("active_population_ids")

    if all_individuals is None:
        random.seed()
        all_individuals = {}
        matches_log = []
        population = []
        family_names = assign_initial_family_names(args.population_size)
        for i in range(args.population_size):
            ind = Individual(ind_id=f"G0-{i:03d}", generation=0, family_label=family_names[i])
            population.append(ind)
            all_individuals[ind.id] = ind
        start_gen = 0
    else:
        start_gen = max(ind.generation for ind in all_individuals.values()) + 1
        if active_population_ids:
            # 前回終了時点の「現役メンバー」をそのまま引き継ぐ（淘汰された個体は復活させない）
            population = [all_individuals[i] for i in active_population_ids if i in all_individuals]
            missing = len(active_population_ids) - len(population)
            if missing > 0:
                print(f"  ※ 前回の現役個体のうち{missing}体が見つかりませんでした（データ不整合の可能性）")
        else:
            # training_state に現役リストが無い場合のみ、やむを得ずElo上位から復元する
            print("  ※ 現役個体リストが見つからないため、Elo上位から復元します（淘汰済み個体が混じる可能性があります）")
            ranked = sorted(all_individuals.values(), key=lambda ind: ind.elo, reverse=True)
            population = ranked[:args.population_size]

    for gen in range(start_gen, start_gen + args.generations):
        print(f"=== Generation {gen} (opponent_think_ms={opponent_think_ms}, population={len(population)}) ===")
        population = run_generation(
            population, gen, matches_log,
            engine_path=args.engine_path, eval_dir=args.eval_dir,
            population_size=args.population_size,
            swiss_rounds=args.swiss_rounds,
            individual_think_ms=args.individual_think_ms,
            opponent_think_ms=opponent_think_ms,
            multipv=args.multipv,
            yaneuraou_games=args.yaneuraou_games,
            immigrant_count=args.immigrant_count,
            immigrant_interval=args.immigrant_interval,
        )
        for ind in population:
            all_individuals[ind.id] = ind

        ranked_now = sorted(population, key=lambda ind: -ind.elo)
        for ind in ranked_now[:5]:
            print(f"  {ind.id} [{ind.family_label}家]: Elo={ind.elo:.1f}")

        export_population(list(all_individuals.values()), matches_log, args.data_dir)

        # --- 温度計の勝率を見て、次世代のやねうら王の強さを自動調整 ---
        win_rate = compute_win_rate_vs_yaneuraou(matches_log, gen)
        if win_rate is not None:
            win_rate_history.append({"generation": gen, "win_rate": round(win_rate, 3), "opponent_think_ms": opponent_think_ms})
            print(f"  温度計勝率(首位 vs やねうら王, 世代{gen}): {win_rate:.1%}")

            if win_rate >= WIN_RATE_UPGRADE_THRESHOLD and opponent_think_ms < OPPONENT_THINK_MS_MAX:
                opponent_think_ms = min(OPPONENT_THINK_MS_MAX, opponent_think_ms + OPPONENT_THINK_MS_STEP)
                print(f"  → 勝率が高いため、やねうら王の思考時間を {opponent_think_ms}ms に引き上げました")
            elif win_rate <= WIN_RATE_DOWNGRADE_THRESHOLD and opponent_think_ms > args.opponent_think_ms:
                opponent_think_ms = max(args.opponent_think_ms, opponent_think_ms - OPPONENT_THINK_MS_STEP)
                print(f"  → 勝率が低いため、やねうら王の思考時間を {opponent_think_ms}ms に引き下げました")

        save_training_state(args.data_dir, {
            "opponent_think_ms": opponent_think_ms,
            "win_rate_history": win_rate_history,
            "active_population_ids": [ind.id for ind in population],
        })


if __name__ == "__main__":
    main()
