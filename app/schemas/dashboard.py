from pydantic import BaseModel
from typing import Dict


class DashboardSummary(BaseModel):
    total_requests: int
    by_type: Dict[str, int]
    by_subcommittee: Dict[str, int]
    by_status: Dict[str, int]
    cpf_selected_count: int
    cpf_selected_slots_remaining: int
