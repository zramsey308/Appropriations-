from app.api.upload import _best_eligible_account_match, _is_meaningful_text
from app.models.eligible_account import EligibleAccount
from app.services.docx_parser import _clean_field_value, _project_name_from_project_info


def test_meaningful_text_filters_labels():
    assert not _is_meaningful_text("Project Name:")
    assert not _is_meaningful_text("  ")
    assert not _is_meaningful_text("Requested FY’27 Funding Amount:\nSubcommittee:\nAgency:")
    assert _is_meaningful_text("Angelo State University")


def test_clean_field_value_strips_artifacts():
    assert _clean_field_value("/Entity: Angelo State University") == "Angelo State University"
    assert _clean_field_value("(See list above): Scientific and Technical Research Services (STRS)") == "Scientific and Technical Research Services (STRS)"
    assert _clean_field_value("Agency:") == ""


def test_project_name_fallback_from_project_info_line():
    text = "Project Information: $650,000 to expand Angelo State University engineering workforce program"
    result = _project_name_from_project_info(text)
    assert "expand Angelo State University engineering workforce program" == result


def test_best_eligible_account_match_handles_strs_abbrev():
    accounts = [
        EligibleAccount(id=1, subcommittee="commerce_justice_science", agency="National Institute of Standards and Technology", account_name="Scientific and Technical Research and Services", active=True),
        EligibleAccount(id=2, subcommittee="commerce_justice_science", agency="National Oceanic and Atmospheric Administration", account_name="Operations, Research, and Facilities", active=True),
    ]

    match_id = _best_eligible_account_match(
        accounts,
        eligible_account_raw="Scientific and Technical Research Services (STRS)",
        agency_raw="National Institutes of Standards and Technology",
    )
    assert match_id == 1
