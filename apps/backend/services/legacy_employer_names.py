"""Conservative employer-name aliases: do not collapse distinct LCS stations."""
import re


def canonical_employer_name(name: str) -> str:
    cleaned = " ".join((name or "").strip().split())
    compact = re.sub(r"[^a-z0-9]", "", cleaned.casefold())
    aliases = {
        "lcs": "Lesotho Correctional Service",
        "lesothocorrectionalservice": "Lesotho Correctional Service",
        "lcscentral": "LCS Central",
        "lesothocorrectionalservicecentral": "LCS Central",
        "lcshq": "LCS Headquarters",
        "lcsheadquarters": "LCS Headquarters",
        "lcslesothocorrectionalservicehq": "LCS Headquarters",
        "lesothocorrectionalservicehq": "LCS Headquarters",
        "lesothocorrectionalserviceheadquarters": "LCS Headquarters",
    }
    return aliases.get(compact, cleaned)


def employer_key(name: str) -> str:
    return canonical_employer_name(name).casefold()
