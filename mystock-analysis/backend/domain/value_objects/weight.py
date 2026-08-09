"""重量值物件（Weight Value Object）

不可變（frozen dataclass），以值相等比較。
封裝重量相關業務規則：不允許負值、相減取正值。
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Weight:
    """重量值物件 — 不可變、以值相等

    Attributes:
        value: 重量數值（Kg），不可為負。
        unit:  重量單位，預設 "Kg"。
    """
    value: int
    unit: str = "Kg"

    def __post_init__(self):
        if self.value < 0:
            raise ValueError(f"重量不可為負值: {self.value}")

    def subtract(self, other: "Weight") -> "Weight":
        """重量相減，結果不小於 0。

        Args:
            other: 被減的重量。

        Returns:
            相減後的 Weight（最小為 0）。

        Raises:
            ValueError: 單位不同時。
        """
        if self.unit != other.unit:
            raise ValueError(f"單位不同無法相減: {self.unit} vs {other.unit}")
        return Weight(value=max(self.value - other.value, 0), unit=self.unit)

    def __int__(self) -> int:
        return self.value

    def __repr__(self) -> str:
        return f"Weight({self.value} {self.unit})"
