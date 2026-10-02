"""Wire constants for the Farmad Procura customer API."""

AUTH0_DOMAIN = "signin.procura.farmad.be"
AUTH0_TENANT = "production-farmad"
AUTH0_CLIENT_ID = "5xlNthD37j7PK1vItdDKFC9H3cV0s8FN"
AUTH0_CONNECTION = "Username-Password-Authentication"
AUTH0_AUDIENCE = "api://procura.farmad.be"
AUTH0_SCOPE = "openid profile email offline_access"
AUTH_REDIRECT_URI = "https://procura.farmad.be/auth-callback.html"
AUTH_UI_LOCALES = "nl"

ALB_BASE_URL = "https://alb-prod.procura.farmad.be"
CATALOG_BASE_URL = "https://api.catalog.procura.farmad.be"
EHEALTH_BASE_URL = "https://procura.farmad.be/ehealth"

CLAIM_ACCOUNT_ID = "http://schemas.microsoft.com/ws/2008/06/identity/claims/accountId"
CLAIM_PATIENT = "http://schemas.microsoft.com/ws/2008/06/identity/claims/patient"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

MEDICATION_MOMENT_TITLES = {
    0: "OPSTAAN",
    1: "ONTBIJT",
    2: "ONTBIJT",
    3: "ONTBIJT",
    4: "TIEN",
    5: "MIDDAGMAAL",
    6: "MIDDAGMAAL",
    7: "MIDDAGMAAL",
    8: "ZESTIEN",
    9: "AVONDMAAL",
    10: "AVONDMAAL",
    11: "AVONDMAAL",
    12: "TWINTIG",
    13: "SLAPEN",
    998: "ADHOC",
    999: "OVERIG",
}
