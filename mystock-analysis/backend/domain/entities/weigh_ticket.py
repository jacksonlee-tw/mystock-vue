"""磅單領域實體（WeighTicket Entity）

封裝磅單的核心業務規則，不依賴任何外部框架或基礎設施。
業務規則包含：
  - 淨重計算（退貨歸零 / 正常出廠 A1 - B1）
  - 工作流程代碼對應（scaleType → workFlow）
"""


class WeighTicket:
    """磅單領域實體

    具有唯一識別碼（ticket_no）的生命週期物件，
    承載入廠→出廠完整過磅流程中的業務規則。
    """

    def __init__(
        self,
        ticket_no: str,
        truck_no: str = "",
        po_no: str = "",
        material_name: str = "",
        supplier: str = "",
        entry_weight_a1: int = 0,
        workflow: str = "1",
        batch_no: str = "",
        boat_no: str = "",
        carrier: str = "",
        s_net: int | None = None,
        n_net: int | None = None,
    ):
        self._ticket_no = ticket_no
        self.truck_no = truck_no
        self.po_no = po_no
        self.material_name = material_name
        self.supplier = supplier
        self.entry_weight_a1 = entry_weight_a1
        self.workflow = workflow
        self.batch_no = batch_no
        self.boat_no = boat_no
        self.carrier = carrier
        self.s_net = s_net
        self.n_net = n_net

    @property
    def ticket_no(self) -> str:
        """磅單號碼（唯一識別碼，設定後不可變更）"""
        return self._ticket_no

    # ── 業務規則 ──────────────────────────────────────────────────────────

    def calculate_net_weight(self, exit_weight_b1: int, is_return: bool = False) -> int:
        """計算淨重（Domain Rule）

        退貨時淨重歸零；正常出廠為入廠重量 A1 減去出廠重量 B1，不小於 0。

        Args:
            exit_weight_b1: 出廠重量 B1（Kg）。
            is_return:      是否為退貨。

        Returns:
            淨重（Kg），退貨時為 0。
        """
        if is_return:
            return 0
        return max(self.entry_weight_a1 - exit_weight_b1, 0)

    @staticmethod
    def resolve_workflow(scale_type: str) -> str:
        """磅秤類型對應工作流程代碼（Domain Rule）

        對應 Delphi 端的 workFlow 欄位邏輯：
          - "double" → "3"（雙磅）
          - "scale1" → "1"（第一磅）
          - "scale2" → "2"（第二磅）
          - 其餘    → "1"（預設）

        Args:
            scale_type: 磅秤類型字串。

        Returns:
            工作流程代碼（"1"/"2"/"3"）。
        """
        return {"double": "3", "scale1": "1", "scale2": "2"}.get(scale_type, "1")

    def __repr__(self) -> str:
        return (
            f"WeighTicket(ticket_no={self._ticket_no!r}, "
            f"truck_no={self.truck_no!r}, po_no={self.po_no!r}, "
            f"a1={self.entry_weight_a1})"
        )
