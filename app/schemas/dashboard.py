from pydantic import BaseModel
from typing import Dict, Optional


class DashboardSummary(BaseModel):
    total_requests: int
    total_requested_amount: Optional[float] = 0
    by_type: Dict[str, int]
    by_subcommittee: Dict[str, int]
    by_status: Dict[str, int]
    amount_by_subcommittee: Dict[str, float] = {}
    cpf_selected: int = 0
    cpf_selected_count: int = 0
    cpf_selected_slots_remaining: int = 15
