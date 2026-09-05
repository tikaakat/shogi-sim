import argparse
import random

from shogi_sim.individual import Individual
from shogi_sim.evolution import run_generation
from shogi_sim.io_utils import load_checkpoint, export_population, load_training_state, save_training_state

# ベンチマーク相手（やねうら王）の思考時間を自動で引き上げるための設定
OPPONENT_THINK_MS_MAX = 1000       # 上限（これ以上は強くしない）
OPPONENT_THINK_MS_STEP = 50        # 1回に引き上げる幅
WIN_RATE_UPGRADE_THRESHOLD = 0.65  # この勝率を超えたら相手を格上げする
WIN_RATE_DOWNGRADE_THRESHOLD = 0.25  # この勝率を下回ったら相手を少し弱める（やり過ぎ防止）


def compute_win_rate_vs_yaneuraou(matches_log, generation):
    """指定した世代の、個体 vs やねうら王 の勝率を計算する"""
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
    parser.add_argument("--games-vs-yaneuraou", type=int, default=1)
    parser.add_argument("--games-vs-peers", type=int, default=2)
    parser.add_argument("--individual-think-ms", type=int, default=300)
    parser.add_argument("--opponent-think-ms", type=int, default=80,
                         help="ベンチマーク相手の初期思考時間。2回目以降は training_state.json に保存された値が優先される")
    parser.add_argument("--multipv", type=int, default=5)
    parser.add_argument("--init-population", type=int, default=3)
    args = parser.parse_args()

    all_individuals, matches_log = load_checkpoint(args.data_dir)
    training_state = load_training_state(args.data_dir)

    # 相手の思考時間：保存済みの値があればそれを使う。無ければCLI引数の初期値
    opponent_think_ms = training_state.get("opponent_think_ms") or args.opponent_think_ms
    win_rate_history = training_state.get("win_rate_history", [])
    # ベンチマーク（やねうら王）側のレートも、固定せず通常のEloと同様に更新していく
    yaneuraou_elo = training_state.get("yaneuraou_elo") or 2200.0

    if all_individuals is None:
        random.seed()
        all_individuals = {}
        matches_log = []
        population = []
        for i in range(args.init_population):
            ind = Individual(ind_id=f"G0-{i:03d}", generation=0)
            population.append(ind)
            all_individuals[ind.id] = ind
        start_gen = 0
    else:
        ranked = sorted(all_individuals.values(), key=lambda ind: ind.elo, reverse=True)
        population = ranked[:5]
        start_gen = max(ind.generation for ind in all_individuals.values()) + 1

    for gen in range(start_gen, start_gen + args.generations):
        print(f"=== Generation {gen} (opponent_think_ms={opponent_think_ms}, yaneuraou_elo={yaneuraou_elo:.1f}) ===")
        population, yaneuraou_elo = run_generation(
            population, gen, matches_log,
            engine_path=args.engine_path, eval_dir=args.eval_dir,
            games_vs_yaneuraou=args.games_vs_yaneuraou,
            games_vs_peers=args.games_vs_peers,
            individual_think_ms=args.individual_think_ms,
            opponent_think_ms=opponent_think_ms,
            multipv=args.multipv,
            yaneuraou_elo=yaneuraou_elo,
        )
        for ind in population:
            all_individuals[ind.id] = ind
            print(f"  {ind.id}: Elo={ind.elo:.1f}")
        print(f"  (やねうら王ベンチマークの現在レート: {yaneuraou_elo:.1f})")

        export_population(list(all_individuals.values()), matches_log, args.data_dir)

        # --- この世代の勝率を見て、次世代の相手の強さを自動調整 ---
        win_rate = compute_win_rate_vs_yaneuraou(matches_log, gen)
        if win_rate is not None:
            win_rate_history.append({"generation": gen, "win_rate": round(win_rate, 3), "opponent_think_ms": opponent_think_ms})
            print(f"  勝率(vs やねうら王, 世代{gen}): {win_rate:.1%}")

            if win_rate >= WIN_RATE_UPGRADE_THRESHOLD and opponent_think_ms < OPPONENT_THINK_MS_MAX:
                opponent_think_ms = min(OPPONENT_THINK_MS_MAX, opponent_think_ms + OPPONENT_THINK_MS_STEP)
                print(f"  → 勝率が高いため、相手の思考時間を {opponent_think_ms}ms に引き上げました")
            elif win_rate <= WIN_RATE_DOWNGRADE_THRESHOLD and opponent_think_ms > args.opponent_think_ms:
                opponent_think_ms = max(args.opponent_think_ms, opponent_think_ms - OPPONENT_THINK_MS_STEP)
                print(f"  → 勝率が低いため、相手の思考時間を {opponent_think_ms}ms に引き下げました")

        save_training_state(args.data_dir, {
            "opponent_think_ms": opponent_think_ms,
            "win_rate_history": win_rate_history,
            "yaneuraou_elo": yaneuraou_elo,
        })


if __name__ == "__main__":
    main()
