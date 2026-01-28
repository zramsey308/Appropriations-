from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Request, CPFDetails
from app.models.enums import RequestType, Subcommittee, RequestStatus
from app.schemas.request import RequestCreate, RequestUpdate


class RequestService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: RequestCreate) -> Request:
        request = Request(**data.model_dump())
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        return request

    def get(self, request_id: int) -> Optional[Request]:
        return self.db.query(Request).filter(Request.id == request_id).first()

    def list(
        self,
        fy: Optional[int] = None,
        request_type: Optional[RequestType] = None,
        subcommittee: Optional[Subcommittee] = None,
        status: Optional[RequestStatus] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[Request], int]:
        query = self.db.query(Request)

        if fy is not None:
            query = query.filter(Request.fiscal_year == fy)
        if request_type is not None:
            query = query.filter(Request.request_type == request_type)
        if subcommittee is not None:
            query = query.filter(Request.subcommittee == subcommittee)
        if status is not None:
            query = query.filter(Request.status == status)

        total = query.count()
        items = query.order_by(Request.created_at.desc()).offset(skip).limit(limit).all()
        return items, total

    def update(self, request_id: int, data: RequestUpdate) -> Optional[Request]:
        request = self.get(request_id)
        if not request:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(request, field, value)

        self.db.commit()
        self.db.refresh(request)
        return request

    def delete(self, request_id: int) -> bool:
        request = self.get(request_id)
        if not request:
            return False

        self.db.delete(request)
        self.db.commit()
        return True

    def get_dashboard_summary(self, fy: Optional[int] = None) -> dict:
        query = self.db.query(Request)
        if fy:
            query = query.filter(Request.fiscal_year == fy)

        total = query.count()

        # By type
        by_type = {}
        type_counts = (
            query.with_entities(Request.request_type, func.count(Request.id))
            .group_by(Request.request_type)
            .all()
        )
        for rt, count in type_counts:
            by_type[rt.value] = count

        # By subcommittee
        by_subcommittee = {}
        sub_counts = (
            query.with_entities(Request.subcommittee, func.count(Request.id))
            .group_by(Request.subcommittee)
            .all()
        )
        for sub, count in sub_counts:
            by_subcommittee[sub.value] = count

        # By status
        by_status = {}
        status_counts = (
            query.with_entities(Request.status, func.count(Request.id))
            .group_by(Request.status)
            .all()
        )
        for st, count in status_counts:
            by_status[st.value] = count

        # CPF selected count
        cpf_selected_count = (
            self.db.query(CPFDetails)
            .filter(CPFDetails.selected == True)
            .count()
        )

        return {
            "total_requests": total,
            "by_type": by_type,
            "by_subcommittee": by_subcommittee,
            "by_status": by_status,
            "cpf_selected_count": cpf_selected_count,
            "cpf_selected_slots_remaining": 15 - cpf_selected_count,
        }
