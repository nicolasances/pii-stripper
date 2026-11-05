from scripts.recall_check import score


def test_recall_is_the_share_of_expected_items_that_were_found():
    expected = {("PERSON", "Mette Hansen"), ("PERSON", "Jens Nielsen")}
    found = {("PERSON", "Mette Hansen")}

    assert score([(expected, found)])["PERSON"]["recall"] == 0.5


def test_an_expected_item_covered_by_a_longer_finding_counts_as_found():
    expected = {("PERSON", "Mette Hansen")}
    found = {("PERSON", "Kære Mette Hansen")}

    assert score([(expected, found)])["PERSON"]["recall"] == 1.0


def test_precision_is_the_share_of_found_items_that_overlap_an_expected_item():
    expected = {("PERSON", "Mette Hansen")}
    found = {("PERSON", "Mette Hansen"), ("PERSON", "Vi har talt")}

    assert score([(expected, found)])["PERSON"]["precision"] == 0.5


def test_a_finding_of_another_type_does_not_count_as_a_hit():
    expected = {("LOCATION", "Risskov")}
    found = {("PERSON", "Du bor i Risskov")}

    result = score([(expected, found)])

    assert result["LOCATION"]["recall"] == 0.0
    assert result["PERSON"]["precision"] == 0.0


def test_counts_are_summed_over_documents():
    first = ({("PERSON", "Mette Hansen")}, {("PERSON", "Mette Hansen")})
    second = ({("PERSON", "Jens Nielsen")}, set())

    assert score([first, second])["PERSON"]["recall"] == 0.5


def test_precision_is_undefined_when_nothing_of_the_type_was_found():
    result = score([({("LOCATION", "Aarhus")}, set())])

    assert result["LOCATION"]["precision"] is None
