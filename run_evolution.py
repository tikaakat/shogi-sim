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
    parser.add_argument("--games-vs-peers", type=int, default=2)        population = ranked[:5]
        start_gen = max(ind.generation for ind in all_individuals.values()) + 1

    for gen in range(start_gen, start_gen + args.generations):
        print(f"=== Generation {gen} ===")
        population = run_generation(
            population, gen, matches_log,
            engine_path=args.engine_path, eval_dir=args.eval_dir,
            games_vs_yaneuraou=args.games_vs_yaneuraou,
            games_vs_peers=args.games_vs_peers,
            individual_think_ms=args.individual_think_ms,
            opponent_think_ms=args.opponent_think_ms,
            multipv=args.multipv,
        )
        for ind in population:
            all_individuals[ind.id] = ind
            print(f"  {ind.id}: Elo={ind.elo:.1f}")

        export_population(list(all_individuals.values()), matches_log, args.data_dir)


if __name__ == "__main__":
    main()
