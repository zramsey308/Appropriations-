from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from app.models import Request, CPFDetails
from app.models.enums import RequestType, Subcommittee, RequestStatus
from app.schemas.request import RequestCreate, RequestUpdate

logger = logging.getLogger(__name__)


class RequestService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, data: RequestCreate) -> Request:
        request = Request(**data.model_dump())
        self.db.add(request)
        self.db.commit()
        self.db.refresh(request)
        logger.info(f"Created request #{request.id} - {request.title}")
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
        """Get dashboard summary with comprehensive error handling."""
        try:
            total = self.db.query(Request).count()
        except Exception as e:
            logger.error(f"Error counting requests: {e}")
            total = 0

        # Total requested amount
        total_requested_amount = 0
        try:
            result = self.db.query(func.sum(Request.requested_amount)).scalar()
            total_requested_amount = float(result) if result else 0
        except Exception as e:
            logger.error(f"Error summing amounts: {e}")

        # By type
        by_type = {}
        try:
            type_counts = (
                self.db.query(Request.request_type, func.count(Request.id))
                .group_by(Request.request_type)
                .all()
            )
            for rt, count in type_counts:
                if rt is not None:
                    by_type[rt] = count
        except Exception as e:
            logger.error(f"Error getting type counts: {e}")

        # By subcommittee
        by_subcommittee = {}
        try:
            sub_counts = (
                self.db.query(Request.subcommittee, func.count(Request.id))
                .group_by(Request.subcommittee)
                .all()
            )
            for sub, count in sub_counts:
                if sub is not None:
                    by_subcommittee[sub] = count
        except Exception as e:
            logger.error(f"Error getting subcommittee counts: {e}")

        # By status
        by_status = {}
        try:
            status_counts = (
                self.db.query(Request.status, func.count(Request.id))
                .group_by(Request.status)
                .all()
            )
            for st, count in status_counts:
                if st is not None:
                    by_status[st] = count
        except Exception as e:
            logger.error(f"Error getting status counts: {e}")

        # CPF selected count
        cpf_selected_count = 0
        try:
            cpf_selected_count = (
                self.db.query(func.count(CPFDetails.id))
                .filter(CPFDetails.selected == True)
                .scalar() or 0
            )
        except Exception as e:
            logger.warning(f"Could not query CPF selected count: {e}")

        return {
            "total_requests": total,
            "total_requested_amount": total_requested_amount,
            "by_type": by_type,
            "by_subcommittee": by_subcommittee,
            "by_status": by_status,
            "cpf_selected": cpf_selected_count,
            "cpf_selected_count": cpf_selected_count,
            "cpf_selected_slots_remaining": 15 - cpf_selected_count,
        }
