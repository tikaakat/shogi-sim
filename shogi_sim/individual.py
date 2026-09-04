import random

BASE_PIECE_VALUES = {
    "P": 100, "L": 400, "N": 450, "S": 600, "G": 700,
    "B": 900, "R": 1050, "K": 15000,
    "+P": 500, "+L": 600, "+N": 620, "+S": 670, "+B": 1150, "+R": 1300,
}


class Individual:
    def __init__(self, ind_id, generation, parent_a_id=None, parent_b_id=None, params=None):
        self.id = ind_id
        self.generation = generation
        self.parent_a_id = parent_a_id
        self.parent_b_id = parent_b_id
        self.params = params or self._random_params()
        self.elo = 1500.0
        self.match_history = []

    def _random_params(self):
        piece_values = {k: v * random.uniform(0.85, 1.15) for k, v in BASE_PIECE_VALUES.items()}
        return {
            "piece_values": piece_values,
            "mobility_weight": random.uniform(1.0, 8.0),
            "king_safety_weight": random.uniform(5.0, 25.0),
            "aggression_weight": random.uniform(-5.0, 5.0),
        }

    def to_dict(self):
        return {
            "id": self.id,
            "generation": self.generation,
            "parent_a_id": self.parent_a_id,
            "parent_b_id": self.parent_b_id,
            "params": self.params,
            "elo": self.elo,
            "match_history": self.match_history,
        }

    @staticmethod
    def from_dict(d):
        ind = Individual(d["id"], d["generation"], d.get("parent_a_id"), d.get("parent_b_id"), d["params"])
        ind.elo = d.get("elo", 1500.0)
        ind.match_history = d.get("match_history", [])
        return ind
