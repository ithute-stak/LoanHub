from services.legacy_employer_names import canonical_employer_name, employer_key


def test_lcs_basic_spelling_variants_are_one_employer():
    for name in ("LCS", "lcs", "Lesotho Correctional Service", "LESOTHO CORRECTIONAL SERVICE"):
        assert canonical_employer_name(name) == "Lesotho Correctional Service"


def test_central_and_headquarters_aliases_remain_separate():
    assert canonical_employer_name("LCS CENTRAL") == "LCS Central"
    assert canonical_employer_name("LCS — Lesotho Correctional Service HQ") != "LCS Central"
    assert canonical_employer_name("Lesotho Correctional ServiceCENTRAL") == "LCS Central"
    assert canonical_employer_name("LCS — Lesotho Correctional Service HQ") != "Lesotho Correctional Service"
    assert employer_key("LCS JTC") != employer_key("LCS LEPERENG")
    assert employer_key("LCS JTC") != employer_key("LCS Central")


def test_non_lcs_names_are_not_reclassified():
    assert canonical_employer_name("Motheo") == "Motheo"
    assert canonical_employer_name("TSEPONG") == "TSEPONG"
