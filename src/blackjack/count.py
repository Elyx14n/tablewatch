from .card import Card, Rank

class HiLoCount:
    def __init__(self):
        self.running_count: int = 0
        self._cards_seen: int = 0
    
    def update(self, card: Card) -> None:
        if 2 <= card.value <= 6:
            self.running_count += 1
        elif card.value == 10 or card.rank == Rank.ACE:
            self.running_count -= 1
        self._cards_seen += 1
    
    def get_true_count(self, decks_remaining: float) -> float:
        if decks_remaining <= 0:
            return 0.0
        return self.running_count / decks_remaining
    
    def get_running_count(self) -> int:
        return self.running_count
    
    def reset(self) -> None:
        self.running_count = 0
        self._cards_seen = 0
    
    @property
    def cards_seen(self) -> int:
        return self._cards_seen