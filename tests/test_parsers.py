"""Parser tests against captured wire fixtures."""

from collections.abc import Callable
from datetime import date
from typing import Any

from aiofarmad.models import MedicationTemporality
from aiofarmad.parsers import (
    _TEMPORALITY_ORDER,
    parse_account,
    parse_basket_items,
    parse_baskets,
    parse_conversation,
    parse_conversations,
    parse_day_scheme,
    parse_day_scheme_range,
    parse_draft_basket,
    parse_message,
    parse_nondaily_products,
    parse_organization,
    parse_patient,
    parse_pharmacy_preferences,
    parse_prescription,
    parse_prescriptions,
)

from .conftest import ACCOUNT_ID, PATIENT_ID


def test_parse_account(load_fixture: Callable[[str], Any]) -> None:
    account = parse_account(load_fixture("account.json"))
    assert account.id == ACCOUNT_ID
    assert account.full_name == "Test User"
    assert account.language == "nl"
    assert account.blocked is False
    assert account.logins_count == 7
    assert account.entitled_pharmacies == ("343602",)
    assert len(account.memberships) == 1
    membership = account.memberships[0]
    assert membership.group_owner == "343602"
    assert membership.group_name == "Patients"
    assert membership.from_ is not None
    assert membership.from_.year == 2026
    assert account.raw is not None
    assert account.raw["id"] == ACCOUNT_ID


def test_parse_account_lenient_fields() -> None:
    account = parse_account({"id": "a", "memberships": "not-a-list"})
    assert account.memberships == ()
    assert account.logins_count == 0
    assert account.email == ""


def test_parse_patient(load_fixture: Callable[[str], Any]) -> None:
    patient = parse_patient(load_fixture("patient.json"))
    assert patient.patient_id == PATIENT_ID
    assert [p.apb_number for p in patient.pharmacies] == ["343602", "344107"]
    at_mahieu = patient.pharmacy("343602")
    assert at_mahieu is not None
    assert at_mahieu.customer_number == 31136
    assert at_mahieu.date_of_birth is not None
    assert at_mahieu.date_of_birth.year == 2001
    assert at_mahieu.last_visit is None
    at_other = patient.pharmacy("344107")
    assert at_other is not None
    assert at_other.last_visit is not None
    assert patient.pharmacy("000000") is None


def test_parse_patient_without_records() -> None:
    patient = parse_patient({"patientId": "p1", "patient_in_apbs": None})
    assert patient.pharmacies == ()


def test_parse_organization(load_fixture: Callable[[str], Any]) -> None:
    pharmacy = parse_organization(load_fixture("organization.json"))
    assert pharmacy.apb == "343602"
    assert pharmacy.name == "Apotheek Voorbeeld"
    assert pharmacy.city == "Voorbeeldstad"
    assert pharmacy.email == "info@apotheekvoorbeeld.example"


def test_parse_organization_missing_email() -> None:
    pharmacy = parse_organization({"apb": "1", "name": "N", "city": "C", "email": ""})
    assert pharmacy.email is None


def test_parse_pharmacy_preferences(load_fixture: Callable[[str], Any]) -> None:
    preferences = parse_pharmacy_preferences(load_fixture("pharmacy_preferences.json"))
    assert preferences.allow_online_payments is False
    assert preferences.can_receive_payment_at_delivery_hatch is True
    assert preferences.allow_automatic_export is True
    assert preferences.is_lochting_pharmacy is False


def test_parse_day_scheme_groups_and_orders(load_fixture: Callable[[str], Any]) -> None:
    raw_days = load_fixture("scheme_day.json")
    scheme = parse_day_scheme(raw_days[0])
    assert scheme.date == date(2026, 10, 1)
    assert scheme.skipped_moments == 1
    assert [moment.title for moment in scheme.intake_moments] == [
        "ADHOC",
        "OPSTAAN",
        "ONTBIJT",
        "AVONDMAAL",
    ]
    assert scheme.medication_count == 5
    breakfast = scheme.intake_moments[2]
    assert breakfast.title == "ONTBIJT"
    assert [p.product_description for p in breakfast.products] == [
        "aspirine cardio",
        "vitamine d",
    ]
    assert breakfast.products[0].temporality is MedicationTemporality.ACUTE
    adhoc = scheme.intake_moments[0]
    assert adhoc.title == "ADHOC"
    assert adhoc.products[0].cnk == "4455667"


def test_parse_day_scheme_range(load_fixture: Callable[[str], Any]) -> None:
    days = parse_day_scheme_range(load_fixture("scheme_day.json"))
    assert [d.date for d in days] == [date(2026, 10, 1), date(2026, 10, 2)]
    assert days[1].medication_count == 1
    assert days[1].intake_moments[0].title == "MIDDAGMAAL"


def test_parse_day_scheme_range_rejects_non_list() -> None:
    assert parse_day_scheme_range({"day": "x"}) == ()
    assert parse_day_scheme_range([42, "junk"]) == ()


def test_parse_day_scheme_invalid_day_is_skipped() -> None:
    scheme = parse_day_scheme({"day": "not-a-date", "moments": []})
    assert scheme.date is None
    assert scheme.intake_moments == ()


def test_parse_nondaily_products(load_fixture: Callable[[str], Any]) -> None:
    products = parse_nondaily_products(load_fixture("scheme_nondaily.json"))
    assert len(products) == 2
    omeprazol = products[0]
    assert omeprazol.cnk == "5566778"
    assert omeprazol.dosages == ("1 per week",)
    magnesium = products[1]
    assert magnesium.dosages == ("2 per dag",)
    assert magnesium.skipped_dosages == 1


def test_parse_nondaily_products_rejects_non_list() -> None:
    assert parse_nondaily_products({"cnk": "1"}) == ()
    assert parse_nondaily_products([{"cnk": "1"}, 5]) is not None


def test_parse_conversations(load_fixture: Callable[[str], Any]) -> None:
    conversations = parse_conversations(load_fixture("conversations.json"))
    assert len(conversations) == 2
    first = conversations[0]
    assert first.customer_name == "Family Member"
    assert first.unread_message_count == 2
    assert first.last_message is not None
    assert first.last_message.body == "Uw bestelling ligt klaar."
    assert first.last_message.sent is not None
    second = conversations[1]
    assert second.last_message is None
    assert second.unread_message_count == 0


def test_parse_conversations_skips_non_objects(load_fixture: Callable[[str], Any]) -> None:
    assert parse_conversations([load_fixture("conversations.json")[0], "junk"])


def test_parse_conversation_single(load_fixture: Callable[[str], Any]) -> None:
    conversation = parse_conversation(load_fixture("conversations.json")[0])
    assert conversation.customer_id != ACCOUNT_ID
    assert conversation.raw is not None


def test_parse_message(load_fixture: Callable[[str], Any]) -> None:
    raw_messages = load_fixture("messages.json")
    message = parse_message(raw_messages[0])
    assert message.id == "message-1"
    assert message.sender_name == "Apotheek Voorbeeld"
    assert message.read_by_receiver is False
    reply = parse_message(raw_messages[1])
    assert reply.sender_id == ACCOUNT_ID
    assert reply.read_by_receiver is True


def test_parse_message_lenient() -> None:
    message = parse_message({"id": "x", "send": "garbage", "sender": "nope"})
    assert message.sent is None
    assert message.sender_id == ""
    assert message.body == ""


def test_parse_baskets_resolves_patient_names(load_fixture: Callable[[str], Any]) -> None:
    baskets = parse_baskets(load_fixture("baskets.json"))
    assert len(baskets) == 2
    first = baskets[0]
    assert first.id == "basket-1"
    assert first.customer_patient_name == "Test User"
    assert first.state == "Ordered"
    assert first.item_count == 3
    assert first.total_price == 9.9
    second = baskets[1]
    assert second.customer_patient_name == "fallback@example.com"
    assert second.items == ()


def test_parse_baskets_without_embedded() -> None:
    baskets = parse_baskets({"results": [{"id": "b", "state": "Ordered"}]})
    assert baskets[0].customer_patient_name is None


def test_parse_draft_basket(load_fixture: Callable[[str], Any]) -> None:
    draft = parse_draft_basket(load_fixture("draft_basket.json"))
    assert draft.id == "draft-1"
    assert draft.comment is None
    assert draft.item_count == 1
    assert draft.items[0].unit_price == 4.95


def test_parse_draft_basket_empty_items() -> None:
    draft = parse_draft_basket({"basketItems": "garbage"})
    assert draft.items == ()
    assert draft.id is None


def test_int_field_lenient_branches() -> None:
    account = parse_account({"id": "a", "blocked": True, "loginsCount": True})
    assert account.logins_count == 0
    patient = parse_patient(
        {
            "patientId": "p",
            "patient_in_apbs": {"1": {"customerNumber": "42", "apbNumber": "1"}},
        }
    )
    assert patient.pharmacies[0].customer_number == 42


def test_parse_patient_skips_non_mapping_records() -> None:
    patient = parse_patient({"patientId": "p", "patient_in_apbs": {"1": "junk", "2": {}}})
    assert len(patient.pharmacies) == 1


def test_parse_nondaily_first_product_with_empty_dosage() -> None:
    products = parse_nondaily_products([{"cnk": "1", "productDescription": "P", "dosage": ""}])
    assert products[0].dosages == ()
    assert products[0].skipped_dosages == 1


def test_parse_baskets_with_non_mapping_notification_info() -> None:
    baskets = parse_baskets(
        {
            "results": [{"id": "b", "notificationInfo": "junk", "state": "Ordered"}],
            "embeddedPatients": [],
        }
    )
    assert baskets[0].customer_patient_name is None


def test_parse_baskets_skips_non_mapping_results() -> None:
    baskets = parse_baskets(
        {"results": ["junk", {"id": "b", "state": "Ordered"}], "embeddedPatients": []}
    )
    assert len(baskets) == 1


def test_parse_conversations_rejects_non_list() -> None:
    assert parse_conversations({"items": []}) == ()


def test_parse_account_with_single_mapping_membership() -> None:
    account = parse_account(
        {"id": "a", "memberships": {"groupOwner": "343602", "groupName": "Patients"}}
    )
    assert account.memberships[0].group_owner == "343602"


def test_parse_account_with_junk_membership_rows() -> None:
    account = parse_account({"id": "a", "memberships": ["junk", {"groupOwner": "1"}]})
    assert len(account.memberships) == 1


def test_temporality_unknown_for_non_string_values() -> None:
    scheme = parse_day_scheme(
        {
            "day": None,
            "moments": [{"order": 0, "productDescription": "X", "cnk": "1", "temporality": 5}],
        }
    )
    assert scheme.intake_moments[0].products[0].temporality is MedicationTemporality.UNKNOWN
    assert scheme.date is None


def test_temporality_order_covers_every_member() -> None:
    assert set(_TEMPORALITY_ORDER) == set(MedicationTemporality)


def test_parse_nondaily_duplicate_and_empty_dosages() -> None:
    products = parse_nondaily_products(
        [
            {"cnk": "1", "productDescription": "A", "dosage": "1"},
            {"cnk": "1", "productDescription": "A", "dosage": "1"},
            {"cnk": "1", "productDescription": "A", "dosage": ""},
        ]
    )
    assert products[0].dosages == ("1",)
    assert products[0].skipped_dosages == 1


def test_parse_basket_items_skips_junk_rows() -> None:
    items = parse_basket_items(["junk", {"productCnk": "1", "quantity": 2, "unitPrice": 1.5}])
    assert len(items) == 1
    assert items[0].quantity == 2


def test_parse_day_scheme_unknown_string_temporality() -> None:
    scheme = parse_day_scheme(
        {
            "day": "2026-10-01T00:00:00.000Z",
            "moments": [
                {"order": 0, "productDescription": "X", "cnk": "1", "temporality": "bogus"}
            ],
        }
    )
    assert scheme.intake_moments[0].products[0].temporality is MedicationTemporality.UNKNOWN


def test_parse_nondaily_appends_distinct_dosages() -> None:
    products = parse_nondaily_products(
        [
            {"cnk": "1", "productDescription": "A", "dosage": "1 per dag"},
            {"cnk": "1", "productDescription": "A", "dosage": "2 per week"},
        ]
    )
    assert products[0].dosages == ("1 per dag", "2 per week")
    assert products[0].skipped_dosages == 0


def test_parse_prescriptions_from_list(load_fixture: Callable[[str], Any]) -> None:
    prescriptions = parse_prescriptions(load_fixture("prescriptions.json"))
    assert len(prescriptions) == 2
    assert prescriptions[0].raw is not None
    assert prescriptions[0].raw["id"] == "BEP10S18PLM4"


def test_parse_prescriptions_from_wrapped_list() -> None:
    prescriptions = parse_prescriptions({"prescriptions": [{"id": "BE1"}]})
    assert len(prescriptions) == 1
    assert prescriptions[0].raw is not None


def test_parse_prescriptions_from_object() -> None:
    prescriptions = parse_prescriptions({"id": "BE1"})
    assert len(prescriptions) == 1
    assert prescriptions[0].raw is not None


def test_parse_prescriptions_rejects_other_shapes() -> None:
    assert parse_prescriptions("junk") == ()
    assert parse_prescriptions(None) == ()


def test_parse_prescription_single(load_fixture: Callable[[str], Any]) -> None:
    prescription = parse_prescription(load_fixture("prescription.json"), "BEP10S18PLM4")
    assert prescription is not None
    assert prescription.prescription_id == "BEP10S18PLM4"
    assert prescription.raw is not None


def test_parse_prescription_none_payload() -> None:
    assert parse_prescription(None) is None


def test_parse_prescription_non_dict_payload() -> None:
    prescription = parse_prescription("junk", "BE1")
    assert prescription is not None
    assert prescription.prescription_id == "BE1"
    assert prescription.raw is None
