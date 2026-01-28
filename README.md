# FY27 Appropriations Tracker

A Tier Two appropriations tracking system built with FastAPI, PostgreSQL, Alembic, and Docker Compose.

## Features

- **Three Request Types**: CPF (Community Project Funding), Programmatic, Language
- **12 Subcommittees**: Full coverage of House Appropriations subcommittees
- **CPF Compliance Validation**: TX-11 nexus, entity type, account matching, support letters
- **Selection Cap Enforcement**: Hard cap of 15 CPF selections per fiscal year
- **File Attachments**: Support letters and document uploads with local storage
- **Dashboard Summary**: Statistics by type, subcommittee, and status

## Quick Start

### Prerequisites

- Docker and Docker Compose

### Run the Application

```bash
# Start the services
docker-compose up -d

# The API will be available at http://localhost:8000
# API documentation at http://localhost:8000/docs
```

### Stop the Application

```bash
docker-compose down

# To also remove the database volume:
docker-compose down -v
```

## API Endpoints

### Requests

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/requests` | Create a new request |
| GET | `/api/requests` | List requests (with filters) |
| GET | `/api/requests/{id}` | Get a single request |
| PATCH | `/api/requests/{id}` | Update a request |
| DELETE | `/api/requests/{id}` | Delete a request |

### CPF Details

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/requests/{id}/cpf` | Create/update CPF details |
| GET | `/api/requests/{id}/cpf` | Get CPF details |
| POST | `/api/requests/{id}/cpf/validate` | Validate CPF compliance |
| POST | `/api/requests/{id}/cpf/select` | Select CPF for funding (15 cap) |

### Attachments

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/requests/{id}/attachments` | Upload attachment |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard/summary` | Get summary statistics |

### Eligible Accounts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/eligible-accounts` | List eligible CPF accounts |
| GET | `/api/eligible-accounts/{id}` | Get single account |

## curl Examples

### Create a CPF Request

```bash
curl -X POST http://localhost:8000/api/requests \
  -H "Content-Type: application/json" \
  -d '{
    "request_type": "cpf",
    "subcommittee": "transportation_hud",
    "title": "Downtown Transit Hub Renovation",
    "description": "Renovation of the central transit hub to improve accessibility",
    "requester_name": "Jane Smith",
    "requester_email": "jane.smith@example.org",
    "requester_organization": "City of Springfield",
    "requested_amount": 2500000
  }'
```

### List Requests with Filters

```bash
# All requests
curl http://localhost:8000/api/requests

# Filter by fiscal year
curl "http://localhost:8000/api/requests?fy=2027"

# Filter by type
curl "http://localhost:8000/api/requests?type=cpf"

# Filter by subcommittee
curl "http://localhost:8000/api/requests?subcommittee=transportation_hud"

# Filter by status
curl "http://localhost:8000/api/requests?status=draft"

# Combined filters
curl "http://localhost:8000/api/requests?fy=2027&type=cpf&subcommittee=transportation_hud"
```

### Get Single Request

```bash
curl http://localhost:8000/api/requests/1
```

### Add CPF Details

```bash
curl -X POST http://localhost:8000/api/requests/1/cpf \
  -H "Content-Type: application/json" \
  -d '{
    "cpf_account_id": 66,
    "tx11_nexus": true,
    "tx11_nexus_explanation": "Project located in TX-11 district",
    "entity_type": "local_government",
    "entity_name": "City of Springfield",
    "entity_address": "123 Main St, Springfield, TX 12345",
    "project_name": "Downtown Transit Hub Renovation",
    "project_address": "500 Transit Way, Springfield, TX 12345",
    "project_description": "Complete renovation of the central transit hub",
    "requested_amount": 2500000,
    "total_project_cost": 5000000,
    "cost_share_amount": 2500000,
    "cost_share_required": true,
    "cost_share_explanation": "City will provide 50% matching funds from local bond measure",
    "public_benefit_justification": "Will serve 50,000 daily commuters and improve ADA accessibility",
    "tx11_priority_justification": "Critical infrastructure for district economic development",
    "stakeholders_support": "City Council, Chamber of Commerce, Transit Riders Union",
    "eligibility_citations": "49 USC 5309 Capital Investment Grants",
    "timeline": "Construction begins Q1 2028, completion Q4 2029",
    "authorized_in_law": true,
    "authorization_citation": "FAST Act Section 3005"
  }'
```

### Validate CPF Compliance

```bash
curl -X POST http://localhost:8000/api/requests/1/cpf/validate
```

### Upload Support Letter

```bash
curl -X POST http://localhost:8000/api/requests/1/attachments \
  -F "file=@support_letter.pdf" \
  -F "attachment_type=cpf_support_letter"
```

### Select CPF for Funding

```bash
# Auto-assign lowest available slot
curl -X POST http://localhost:8000/api/requests/1/cpf/select

# Specify slot number (1-15)
curl -X POST "http://localhost:8000/api/requests/1/cpf/select?slot=1"
```

### Get Dashboard Summary

```bash
curl http://localhost:8000/api/dashboard/summary

# Filter by fiscal year
curl "http://localhost:8000/api/dashboard/summary?fy=2027"
```

### List Eligible Accounts

```bash
# All active accounts
curl http://localhost:8000/api/eligible-accounts

# Filter by subcommittee
curl "http://localhost:8000/api/eligible-accounts?subcommittee=transportation_hud"

# Include inactive accounts
curl "http://localhost:8000/api/eligible-accounts?active_only=false"
```

### Create Programmatic Request

```bash
curl -X POST http://localhost:8000/api/requests \
  -H "Content-Type: application/json" \
  -d '{
    "request_type": "programmatic",
    "subcommittee": "labor_hhs_education",
    "title": "Increase Funding for Community Health Centers",
    "description": "Request to increase CHC funding by $500M",
    "program_name": "Health Center Program",
    "requested_amount": 500000000,
    "programmatic_justification": "CHCs serve 30M patients annually in underserved areas"
  }'
```

### Create Language Request

```bash
curl -X POST http://localhost:8000/api/requests \
  -H "Content-Type: application/json" \
  -d '{
    "request_type": "language",
    "subcommittee": "commerce_justice_science",
    "title": "Rural Broadband Deployment Report Language",
    "description": "Report language requiring broadband deployment metrics",
    "bill_section": "Title II - Department of Commerce",
    "proposed_language": "The Committee directs NTIA to submit quarterly reports on rural broadband deployment progress...",
    "language_justification": "Ensures accountability for broadband infrastructure investments"
  }'
```

## CPF Compliance Rules

A CPF request passes validation when:

1. **TX-11 Nexus**: `tx11_nexus` must be `true`
2. **Entity Type**: Must be one of: `state_government`, `local_government`, `tribal_government`, `nonprofit`, `public_higher_education`, `special_district`
3. **Valid Account**: `cpf_account_id` must reference an active account matching the request's subcommittee
4. **Support Letters**: At least 3 support letters must be uploaded (tracked automatically)
5. **Cost Share**: If `cost_share_required` is true, `cost_share_explanation` must be provided

## Selection Cap

- Maximum 15 CPF requests can be selected per fiscal year
- `selected_slot` must be unique (1-15)
- If no slot specified, lowest available slot is auto-assigned

## Database Schema

### Tables

- `requests` - General request data for all types
- `cpf_details` - CPF-specific compliance form fields (1:1 with CPF requests)
- `eligible_accounts` - Reference table of CPF-eligible appropriations accounts
- `attachments` - File uploads linked to requests

## Development

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set database URL
export DATABASE_URL=postgresql://user:pass@localhost:5432/appropriations_db

# Run migrations
alembic upgrade head

# Seed eligible accounts
python -m app.seed_accounts

# Start server
uvicorn app.main:app --reload
```

### Run Migrations

```bash
# Inside container
docker-compose exec api alembic upgrade head

# Create new migration
docker-compose exec api alembic revision --autogenerate -m "description"
```

## Subcommittees

- `agriculture`
- `commerce_justice_science`
- `defense`
- `energy_water`
- `financial_services_general_government`
- `homeland_security`
- `interior_environment`
- `labor_hhs_education`
- `legislative_branch`
- `milcon_va`
- `state_foreign_operations`
- `transportation_hud`

## Request Types

- `cpf` - Community Project Funding
- `programmatic` - Programmatic funding requests
- `language` - Report/bill language requests

## Attachment Types

- `cpf_support_letter` - Support letters for CPF (auto-increments counter)
- `budget_document` - Budget documentation
- `project_description` - Project description documents
- `authorization_citation` - Authorization citations
- `other` - Other documents
