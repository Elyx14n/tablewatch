from pydantic import BaseModel, ConfigDict, Field

class HouseRules(BaseModel):
    dealer_stands_on: int = Field(default=17, ge=17, le=18)
    double_after_split: bool = True
    resplit_aces: bool = True
    late_surrender: bool = True
    double_on_soft_total: bool = True
    blackjack_payout: float = Field(default=1.5, ge=1.0, le=2.0)
    max_splits: int = Field(default=3, ge=1, le=4)
    model_config = ConfigDict(frozen=True)