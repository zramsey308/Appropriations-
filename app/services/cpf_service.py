from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models import Request, CPFDetails, EligibleAccount
from app.schemas.cpf_details import CPFDetailsCreate, CPFDetailsUpdate, CPFValidationItem, CPFValidationResult

ALLOWED_ENTITY_TYPES = [
    "state_government",
    "local_government",
    "tribal_government",
    "nonprofit",
    "public_higher_education",
    "special_district",
]


class CPFService:
    MAX_SELECTED_SLOTS = 15

    def __init__(self, db: Session):
        self.db = db

    def get_by_request(self, request_id: int) -> Optional[CPFDetails]:
        return self.db.query(CPFDetails).filter(CPFDetails.request_id == request_id).first()

    def create_or_update(self, request_id: int, data: CPFDetailsCreate | CPFDetailsUpdate) -> Optional[CPFDetails]:
        request = self.db.query(Request).filter(Request.id == request_id).first()
        if not request:
            return None

        if request.request_type != "cpf":
            raise ValueError("Request must be of type 'cpf' to have CPF details")

        cpf_details = self.get_by_request(request_id)

        if cpf_details:
            update_data = data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(cpf_details, field, value)
        else:
            cpf_details = CPFDetails(request_id=request_id, **data.model_dump())
            self.db.add(cpf_details)

        self.db.commit()
        self.db.refresh(cpf_details)
        return cpf_details

    def validate(self, request_id: int) -> CPFValidationResult:
        request = self.db.query(Request).filter(Request.id == request_id).first()
        if not request:
            return CPFValidationResult(
                passed=False,
                items=[],
                missing_requirements=["Request not found"]
            )

        cpf_details = self.get_by_request(request_id)
        if not cpf_details:
            return CPFValidationResult(
                passed=False,
                items=[],
                missing_requirements=["CPF details not found for this request"]
            )

        items: List[CPFValidationItem] = []
        missing: List[str] = []

        # 1. TX-11 nexus requirement
        tx11_passed = cpf_details.tx11_nexus is True
        items.append(CPFValidationItem(
            field="tx11_nexus",
            requirement="TX-11 nexus must be true",
            passed=tx11_passed,
            message="TX-11 nexus confirmed" if tx11_passed else "TX-11 nexus not confirmed"
        ))
        if not tx11_passed:
            missing.append("TX-11 nexus must be confirmed (set tx11_nexus to true)")

        # 2. Entity type must be allowed
        entity_type_value = cpf_details.entity_type.value if hasattr(cpf_details.entity_type, 'value') else cpf_details.entity_type
        entity_passed = entity_type_value in ALLOWED_ENTITY_TYPES
        items.append(CPFValidationItem(
            field="entity_type",
            requirement="Entity type must be one of: state_government, local_government, tribal_government, nonprofit, public_higher_education, special_district",
            passed=entity_passed,
            message=f"Entity type is valid: {cpf_details.entity_type}" if entity_passed else "Entity type is not valid or not set"
        ))
        if not entity_passed:
            missing.append("Entity type must be set to an allowed type")

        # 3. CPF account must be valid and match subcommittee
        account_passed = False
        account_message = "CPF account not set"
        if cpf_details.cpf_account_id:
            account = self.db.query(EligibleAccount).filter(
                EligibleAccount.id == cpf_details.cpf_account_id
            ).first()
            if account:
                if account.subcommittee == request.subcommittee:
                    if account.active:
                        account_passed = True
                        account_message = f"Valid CPF account: {account.account_name}"
                    else:
                        account_message = "CPF account is not active"
                else:
                    account_message = f"CPF account subcommittee ({account.subcommittee}) does not match request subcommittee ({request.subcommittee})"
            else:
                account_message = "CPF account not found"

        items.append(CPFValidationItem(
            field="cpf_account_id",
            requirement="CPF account must be valid, active, and match request subcommittee",
            passed=account_passed,
            message=account_message
        ))
        if not account_passed:
            missing.append("Valid CPF account matching request subcommittee required")

        # 4. Support letters requirement (>= 3)
        letters_passed = cpf_details.support_letters_received >= 3
        items.append(CPFValidationItem(
            field="support_letters_received",
            requirement="At least 3 support letters required",
            passed=letters_passed,
            message=f"{cpf_details.support_letters_received} support letters received" if letters_passed else f"Only {cpf_details.support_letters_received} support letters received (need at least 3)"
        ))
        if not letters_passed:
            missing.append(f"Need at least 3 support letters (currently have {cpf_details.support_letters_received})")

        # 5. Cost share explanation if required
        cost_share_passed = True
        if cpf_details.cost_share_required:
            cost_share_passed = bool(cpf_details.cost_share_explanation and cpf_details.cost_share_explanation.strip())
        items.append(CPFValidationItem(
            field="cost_share_explanation",
            requirement="Cost share explanation required if cost share is required",
            passed=cost_share_passed,
            message="Cost share explanation provided" if cost_share_passed else "Cost share explanation required but not provided"
        ))
        if not cost_share_passed:
            missing.append("Cost share explanation must be provided when cost share is required")

        overall_passed = all(item.passed for item in items)

        return CPFValidationResult(
            passed=overall_passed,
            items=items,
            missing_requirements=missing
        )

    def select(self, request_id: int, slot: Optional[int] = None) -> CPFDetails:
        cpf_details = self.get_by_request(request_id)
        if not cpf_details:
            raise ValueError("CPF details not found for this request")

        if cpf_details.selected:
            raise ValueError(f"Already selected in slot {cpf_details.selected_slot}")

        # Check if we've hit the cap
        selected_count = self.db.query(CPFDetails).filter(CPFDetails.selected == True).count()
        if selected_count >= self.MAX_SELECTED_SLOTS:
            raise ValueError(f"Maximum selection cap of {self.MAX_SELECTED_SLOTS} reached")

        # Validate before selection
        validation = self.validate(request_id)
        if not validation.passed:
            raise ValueError(f"CPF validation failed: {', '.join(validation.missing_requirements)}")

        # Determine slot
        if slot is not None:
            if slot < 1 or slot > self.MAX_SELECTED_SLOTS:
                raise ValueError(f"Slot must be between 1 and {self.MAX_SELECTED_SLOTS}")
            existing = self.db.query(CPFDetails).filter(CPFDetails.selected_slot == slot).first()
            if existing:
                raise ValueError(f"Slot {slot} is already taken")
            assigned_slot = slot
        else:
            # Auto-assign lowest available slot
            used_slots = set(
                row[0] for row in
                self.db.query(CPFDetails.selected_slot)
                .filter(CPFDetails.selected_slot.isnot(None))
                .all()
            )
            assigned_slot = None
            for s in range(1, self.MAX_SELECTED_SLOTS + 1):
                if s not in used_slots:
                    assigned_slot = s
                    break
            if assigned_slot is None:
                raise ValueError("No slots available")

        cpf_details.selected = True
        cpf_details.selected_slot = assigned_slot
        cpf_details.selected_at = datetime.utcnow()

        # Update request status
        request = self.db.query(Request).filter(Request.id == request_id).first()
        if request:
            request.status = "selected"

        self.db.commit()
        self.db.refresh(cpf_details)
        return cpf_details

    def increment_support_letters(self, request_id: int) -> Optional[CPFDetails]:
        cpf_details = self.get_by_request(request_id)
        if cpf_details:
            cpf_details.support_letters_received += 1
            self.db.commit()
            self.db.refresh(cpf_details)
        return cpf_details

    def decrement_support_letters(self, request_id: int) -> Optional[CPFDetails]:
        cpf_details = self.get_by_request(request_id)
        if cpf_details and cpf_details.support_letters_received > 0:
            cpf_details.support_letters_received -= 1
            self.db.commit()
            self.db.refresh(cpf_details)
        return cpf_details
