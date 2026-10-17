from app.database.seed import DOCUMENT_REQUIREMENTS, FORM_REQUIREMENTS, SERVICES, requirements_for

def test_service_catalog_has_21_entries_and_unique_codes():
    assert len(SERVICES)==21
    assert len({x[0] for x in SERVICES})==21
    assert all(x[1] for x in SERVICES)
    assert {service[0] for service in SERVICES} == set(DOCUMENT_REQUIREMENTS)
    assert all(DOCUMENT_REQUIREMENTS[service[0]] for service in SERVICES)

def test_information_requirements_are_not_seeded_as_uploads():
    documents, fields = requirements_for("ITR")
    assert [item["label"]["mr"] for item in documents] == ["पॅन कार्ड", "आधार कार्ड", "फॉर्म १६"]
    assert [item["label"]["mr"] for item in fields] == FORM_REQUIREMENTS["ITR"]
    assert "मोबाईल नंबर" in [item["label"]["mr"] for item in requirements_for("PAN_CARD")[1]]
    for code in FORM_REQUIREMENTS:
        document_labels = [item["label"]["mr"] for item in requirements_for(code)[0]]
        assert all(label not in document_labels for label in FORM_REQUIREMENTS[code])
