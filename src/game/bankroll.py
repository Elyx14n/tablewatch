from pydantic import BaseModel, ConfigDict


class Bankroll(BaseModel):
    dealer_wins: float = 0.0
    dealer_losses: float = 0.0
    hands_played: int = 0
    blackjacks_dealt: int = 0
    model_config = ConfigDict(frozen=False)

    def record_dealer_win(self, amount: float) -> None:
        self.dealer_wins += amount
        self.hands_played += 1

    def record_dealer_loss(self, amount: float, is_blackjack: bool = False) -> None:
        payout = amount * 1.5 if is_blackjack else amount
        self.dealer_losses += payout
        self.hands_played += 1
        self.blackjacks_dealt += int(is_blackjack)

    def record_push(self) -> None:
        self.hands_played += 1

    @property
    def house_profit(self) -> float:
        return self.dealer_wins - self.dealer_losses

    @property
    def house_edge(self) -> float:
        total_wagered = self.dealer_wins + self.dealer_losses
        if total_wagered == 0:
            return 0.0
        return (self.house_profit / total_wagered) * 100
