import enum


class RequestType(str, enum.Enum):
    cpf = "cpf"
    programmatic = "programmatic"
    language = "language"


class Subcommittee(str, enum.Enum):
    agriculture = "agriculture"
    commerce_justice_science = "commerce_justice_science"
    defense = "defense"
    energy_water = "energy_water"
    financial_services_general_government = "financial_services_general_government"
    homeland_security = "homeland_security"
    interior_environment = "interior_environment"
    labor_hhs_education = "labor_hhs_education"
    legislative_branch = "legislative_branch"
    milcon_va = "milcon_va"
    state_foreign_operations = "state_foreign_operations"
    transportation_hud = "transportation_hud"


class RequestStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    selected = "selected"


class EntityType(str, enum.Enum):
    corporate_private_sector = "corporate_private_sector"
    state_government = "state_government"
    local_government = "local_government"
    tribal_government = "tribal_government"
    nonprofit = "nonprofit"
    public_higher_education = "public_higher_education"
    special_district = "special_district"


ALLOWED_ENTITY_TYPES = [
    EntityType.corporate_private_sector,
    EntityType.state_government,
    EntityType.local_government,
    EntityType.tribal_government,
    EntityType.nonprofit,
    EntityType.public_higher_education,
    EntityType.special_district,
]


class AttachmentType(str, enum.Enum):
    cpf_support_letter = "cpf_support_letter"
    budget_document = "budget_document"
    project_description = "project_description"
    authorization_citation = "authorization_citation"
    other = "other"
