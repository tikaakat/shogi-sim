import subprocess
import time
import re


class UsiEngine:
    def __init__(self, path, eval_dir=None, think_time_ms=100):
        self.proc = subprocess.Popen(
            [path], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self.think_time_ms = think_time_ms
        self._send("usi")
        self._wait_for("usiok")
        if eval_dir:
            self._send(f"setoption name EvalDir value {eval_dir}")
        self._send("isready")
        self._wait_for("readyok")
        self._send("usinewgame")

    def _send(self, cmd):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def _wait_for(self, token, timeout=30):
        start = time.time()
        while time.time() - start < timeout:
            line = self.proc.stdout.readline().strip()
            if token in line:
                return line
        raise TimeoutError(f"USI応答待ちタイムアウト: {token}")

    def best_move(self, sfen_moves):
        self._send(f"position startpos moves {' '.join(sfen_moves)}" if sfen_moves else "position startpos")
        self._send(f"go movetime {self.think_time_ms}")
        while True:
            line = self.proc.stdout.readline().strip()
            if line.startswith("bestmove"):
                return line.split()[1]

    def get_multipv_candidates(self, sfen_moves, multipv=5):
        """MultiPVで候補手を取得。[(move_usi, score_cp), ...] を評価値降順で返す"""
        self._send(f"setoption name MultiPV value {multipv}")
        self._send(f"position startpos moves {' '.join(sfen_moves)}" if sfen_moves else "position startpos")
        self._send(f"go movetime {self.think_time_ms}")

        pv_scores = {}
        while True:
            line = self.proc.stdout.readline().strip()
            if line.startswith("bestmove"):
                break
            if line.startswith("info") and "multipv" in line and " pv " in line:
                mpv_match = re.search(r"multipv (\d+)", line)
                score_match = re.search(r"score (cp|mate) (-?\d+)", line)
                pv_match = re.search(r" pv (\S+)", line)
                if mpv_match and score_match and pv_match:
                    idx = int(mpv_match.group(1))
                    kind, val = score_match.group(1), int(score_match.group(2))
                    score_cp = val if kind == "cp" else (100000 if val > 0 else -100000)
                    pv_scores[idx] = (pv_match.group(1), score_cp)

        candidates = [pv_scores[i] for i in sorted(pv_scores.keys()) if i in pv_scores]
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def quit(self):
        self._send("quit")
        self.proc.terminate()
