from pydantic import BaseModel, Field, computed_field, ConfigDict
from typing import List, Optional

from .hand import Hand
from .strategy import Strategy, PlayerRole


class Player(BaseModel):
    player_id: str
    bankroll: float = Field(gt=0)
    initial_bankroll: float = Field(gt=0)
    hands: List[Hand] = Field(default_factory=list)
    hands_won: int = 0
    hands_lost: int = 0
    hands_pushed: int = 0
    total_wagered: float = 0.0
    strategy: Strategy
    role: PlayerRole = PlayerRole.CASUAL
    team_id: Optional[str] = None
    max_session_loss_pct: float = Field(default=0.5)
    max_session_win_pct: float = Field(default=1.0)
    entry_tc: Optional[float] = None
    exit_tc: Optional[float] = None

    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)

    @computed_field
    @property
    def net_profit(self) -> float:
        return self.bankroll - self.initial_bankroll

    @computed_field
    @property
    def total_hands(self) -> int:
        return self.hands_won + self.hands_lost + self.hands_pushed

    @computed_field
    @property
    def win_rate(self) -> float:
        return self.hands_won / self.total_hands if self.total_hands > 0 else 0.0

    @property
    def can_bet(self) -> bool:
        return self.bankroll > 0

    def add_hand(self, hand: Hand) -> None:
        self.hands.append(hand)

    def remove_hand(self, hand: Hand) -> None:
        self.hands.remove(hand)

    def clear_hands(self) -> None:
        self.hands.clear()

    def place_bet(self, amount: float) -> None:
        if amount > self.bankroll:
            raise ValueError(f"Insufficient funds: ${self.bankroll:.2f}")
        self.bankroll -= amount
        self.total_wagered += amount

    def receive_payout(self, amount: float) -> None:
        self.bankroll += amount

    def record_win(self) -> None:
        self.hands_won += 1

    def record_loss(self) -> None:
        self.hands_lost += 1

    def record_push(self) -> None:
        self.hands_pushed += 1

    def hit_stop_loss(self) -> bool:
        max_loss = self.initial_bankroll * self.max_session_loss_pct
        return self.net_profit < -max_loss

    def hit_win_target(self) -> bool:
        win_target = self.initial_bankroll * self.max_session_win_pct
        return self.net_profit > win_target

    def should_quit_individual(self) -> bool:
        return self.hit_stop_loss() or self.hit_win_target()
