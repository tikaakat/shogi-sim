import argparse
import random

from shogi_sim.individual import Individual
from shogi_sim.evolution import run_generation
from shogi_sim.io_utils import load_checkpoint, export_population


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-path", required=True, help="やねうら王バイナリのパス")
    parser.add_argument("--eval-dir", default=None, help="評価関数ファイルのディレクトリ（MATERIAL版なら不要）")
    parser.add_argument("--data-dir", default="data", help="individuals.json / matches.json の保存先")
    parser.add_argument("--generations", type=int, default=3)
    parser.add_argument("--games-vs-yaneuraou", type=int, default=1)
    parser.add_argument("--games-vs-peers", type=int, default=2)
    parser.add_argument("--individual-think-ms", type=int, default=300)
    parser.add_argument("--opponent-think-ms", type=int, default=80)
    parser.add_argument("--multipv", type=int, default=5)
    parser.add_argument("--init-population", type=int, default=3)
    args = parser.parse_args()

    all_individuals, matches_log = load_checkpoint(args.data_dir)

    if all_individuals is None:
        random.seed()
        all_individuals = {}
        matches_log = []
        population = []
        for i in range(args.init_population):
            ind = Individual(ind_id=f"gen0_{i}", generation=0)
            population.append(ind)
            all_individuals[ind.id] = ind
        start_gen = 0
    else:
        ranked = sorted(all_individuals.values(), key=lambda ind: ind.elo, reverse=True)
        population = ranked[:5]
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
