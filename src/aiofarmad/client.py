"""The FarmadClient facade: one typed method per endpoint."""

import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime
from typing import Self

import aiohttp

from ._auth import OtpProvider, async_login
from ._endpoints import (
    ACCOUNT,
    BASKETS,
    CANCEL_BASKET,
    CONVERSATION_MESSAGES,
    CONVERSATIONS,
    DRAFT_BASKET,
    DRAFT_CLEAR,
    DRAFT_SAVE,
    DRAFT_UPDATE,
    KAVA_PRODUCT,
    MESSAGE_ATTACHMENT_DELETE,
    MESSAGE_ATTACHMENT_UPLOAD,
    MESSAGE_DRAFT,
    MESSAGE_DRAFT_SAVE,
    MESSAGE_DRAFT_SEND,
    MESSAGE_DRAFT_UPDATE,
    MESSAGE_MARK_READ,
    ORGANIZATION,
    PATIENT,
    PAY_BASKET,
    PHARMACY_PREFERENCES,
    PRESCRIPTION,
    PRESCRIPTIONS,
    PRODUCT_IN_APB,
    PRODUCT_IN_APB_BY_GTIN,
    SCHEME_DAY,
    SCHEME_NONDAILY,
    SCHEME_PRODUCT,
    SEARCH_PRODUCTS,
    SELF_ONBOARDING,
    SERVICE_MESSAGES,
    SUBMIT_BASKET,
    TECHNICAL_INTERRUPTIONS,
    AccountArgs,
    BasketIdArgs,
    BasketsArgs,
    ConversationMessagesArgs,
    ConversationsArgs,
    DraftArgs,
    DraftUpdateArgs,
    DraftWriteArgs,
    Endpoint,
    KavaProductArgs,
    MessageAttachmentDeleteArgs,
    MessageAttachmentUploadArgs,
    MessageDraftArgs,
    MessageDraftIdArgs,
    MessageDraftSaveArgs,
    MessageDraftUpdateArgs,
    MessageMarkReadArgs,
    PatientArgs,
    PayBasketArgs,
    PharmacyArgs,
    PlatformArgs,
    PrescriptionArgs,
    PrescriptionsArgs,
    ProductInApbArgs,
    ProductInApbByGtinArgs,
    SchemeDayArgs,
    SchemeNondailyArgs,
    SchemeProductArgs,
    SearchProductsArgs,
    SelfOnboardingArgs,
    SubmitBasketArgs,
)
from ._tokens import TokenLifecycle
from ._transport import OwnedSession, request_json
from .const import USER_AGENT
from .exceptions import (
    FarmadAuthenticationError,
    FarmadClientClosedError,
    FarmadEhealthAuthorizationRequiredError,
    FarmadNotFoundError,
)
from .models import (
    BasketPayment,
    CatalogProduct,
    ConversationSummary,
    CustomerBasket,
    DraftBasket,
    DraftProduct,
    FarmadAccount,
    FarmadMessage,
    FarmadPatient,
    FarmadTokens,
    KavaProduct,
    MedicationDayScheme,
    MedicationNondailyProduct,
    MedicationSchemeProductEntry,
    MessageDraft,
    Pharmacy,
    PharmacyPreferences,
    Prescription,
    ServiceMessage,
)

_LOGGER = logging.getLogger(__name__)

TokenRefreshCallback = Callable[[str, str | None], Awaitable[None]]


class FarmadClient:
    """Asynchronous client for the Mijn Farmad Apotheek customer API."""

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        *,
        email: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
        on_token_refresh: TokenRefreshCallback | None = None,
        ehealth_cookie: str | None = None,
        otp_provider: OtpProvider | None = None,
        request_timeout: float = 30.0,
    ) -> None:
        """Create a client from a session, credentials, or an existing token pair.

        The otp provider is awaited only when the login demands a
        one-time code.
        """
        self._owned_session = OwnedSession(
            session=aiohttp.ClientSession() if session is None else session,
            owned=session is None,
        )
        self._email = email
        self._password = password
        self._request_timeout = request_timeout
        self._ehealth_cookie = ehealth_cookie
        self._otp_provider = otp_provider
        self._closed = False
        self._lifecycle = TokenLifecycle(
            session_provider=lambda: self._owned_session.session,
            timeout=request_timeout,
            access_token=access_token,
            refresh_token=refresh_token,
            on_rotation=on_token_refresh,
        )

    @property
    def access_token(self) -> str | None:
        """The current access token, if one is known."""
        return self._lifecycle.access_token

    @property
    def refresh_token(self) -> str | None:
        """The current refresh token, if one is known."""
        return self._lifecycle.refresh_token

    @property
    def account_id(self) -> str | None:
        """The account id carried by the current access token."""
        return self._lifecycle.account_id

    @property
    def patient_id(self) -> str | None:
        """The patient id carried by the current access token."""
        return self._lifecycle.patient_id

    async def async_login(self) -> FarmadTokens:
        """Log in with the configured credentials and return the issued token pair.

        The otp provider is awaited only when the account requires a
        one-time code.
        """
        self._assert_open()
        if self._email is None or self._password is None:
            msg = "Credentials are required: pass email and password to the client"
            raise FarmadAuthenticationError(msg)
        tokens = await async_login(
            self._owned_session.session,
            self._email,
            self._password,
            timeout=self._request_timeout,
            otp_provider=self._otp_provider,
        )
        await self._lifecycle.adopt(tokens["access_token"], tokens.get("refresh_token"))
        return FarmadTokens.from_token_response(tokens)

    async def async_get_account(self, account_id: str | None = None) -> FarmadAccount:
        """Fetch the account, defaulting to the account of the current token."""
        resolved = self._require(account_id or self.account_id, "account_id")
        return await self._call(
            ACCOUNT,
            AccountArgs(account_id=resolved),
        )

    async def async_get_organization(self, apb: str) -> Pharmacy:
        """Fetch public information for one pharmacy."""
        return await self._call(ORGANIZATION, PharmacyArgs(apb=apb))

    async def async_get_patient(self, patient_id: str | None = None) -> FarmadPatient:
        """Fetch the patient record, defaulting to the patient of the current token."""
        resolved = self._require(patient_id or self.patient_id, "patient_id")
        return await self._call(PATIENT, PatientArgs(patient_id=resolved))

    async def async_get_pharmacy_preferences(self, apb: str) -> PharmacyPreferences:
        """Fetch what one pharmacy allows for online orders."""
        return await self._call(PHARMACY_PREFERENCES, PharmacyArgs(apb=apb))

    async def async_get_medication_day_scheme(
        self,
        apb: str,
        *,
        from_: datetime,
        until: datetime,
        patient_id: str | None = None,
        language: str = "nl",
    ) -> tuple[MedicationDayScheme, ...]:
        """Fetch every day scheme in a window for one patient at one pharmacy."""
        resolved = self._require(patient_id or self.patient_id, "patient_id")
        return await self._call(
            SCHEME_DAY,
            SchemeDayArgs(
                apb=apb,
                patient_id=resolved,
                from_=from_,
                until=until,
                language=language,
            ),
        )

    async def async_get_medication_nondaily_products(
        self,
        apb: str,
        *,
        day: date,
        patient_id: str | None = None,
        language: str = "nl",
    ) -> tuple[MedicationNondailyProduct, ...]:
        """Fetch the nondaily medications for one patient at one pharmacy."""
        resolved = self._require(patient_id or self.patient_id, "patient_id")
        return await self._call(
            SCHEME_NONDAILY,
            SchemeNondailyArgs(apb=apb, patient_id=resolved, day=day, language=language),
        )

    async def async_get_medication_scheme_for_product(
        self,
        apb: str,
        cnk: str,
        *,
        patient_id: str | None = None,
        language: str = "nl",
    ) -> tuple[MedicationSchemeProductEntry, ...]:
        """Fetch the scheme entries of one product for one patient at one pharmacy.

        The entries stay raw because the test account takes no medication
        in its scheme, so the live answer is empty and the payload shape
        is unknown.
        """
        resolved = self._require(patient_id or self.patient_id, "patient_id")
        return await self._call(
            SCHEME_PRODUCT,
            SchemeProductArgs(apb=apb, cnk=cnk, patient_id=resolved, language=language),
        )

    async def async_get_conversations(
        self,
        apb: str,
        *,
        limit: int = 25,
        page: int = 0,
    ) -> tuple[ConversationSummary, ...]:
        """Fetch one page of conversations with one pharmacy."""
        return await self._call(CONVERSATIONS, ConversationsArgs(apb=apb, limit=limit, page=page))

    async def async_get_conversation_messages(
        self,
        apb: str,
        customer_account_id: str,
        *,
        limit: int = 25,
        page: int = 0,
    ) -> tuple[FarmadMessage, ...]:
        """Fetch one page of messages in one conversation."""
        return await self._call(
            CONVERSATION_MESSAGES,
            ConversationMessagesArgs(
                apb=apb,
                limit=limit,
                page=page,
                customer_account_id=customer_account_id,
            ),
        )

    async def async_get_baskets(
        self,
        apb: str,
        *,
        patient_id: str | None = None,
        skip: int = 0,
        take: int = 50,
    ) -> tuple[CustomerBasket, ...]:
        """Fetch one page of baskets for one patient at one pharmacy."""
        resolved = self._require(patient_id or self.patient_id, "patient_id")
        return await self._call(
            BASKETS,
            BasketsArgs(apb=apb, patient_id=resolved, skip=skip, take=take),
        )

    async def async_get_draft_basket(
        self,
        apb: str,
        *,
        account_id: str | None = None,
    ) -> DraftBasket | None:
        """Fetch the draft basket, or None when the account has no draft."""
        resolved = self._require(account_id or self.account_id, "account_id")
        return await self._call(DRAFT_BASKET, DraftArgs(apb=apb, account_id=resolved))

    async def async_save_draft_basket(
        self,
        apb: str,
        *,
        patient_id: str | None = None,
        products: tuple[DraftProduct, ...] = (),
        account_id: str | None = None,
    ) -> str | None:
        """Create the draft basket with the given product lines."""
        resolved_account = self._require(account_id or self.account_id, "account_id")
        resolved_patient = self._require(patient_id or self.patient_id, "patient_id")
        return await self._call(
            DRAFT_SAVE,
            DraftWriteArgs(
                apb=apb,
                account_id=resolved_account,
                patient_id=resolved_patient,
                products=products,
            ),
        )

    async def async_update_draft_basket(
        self,
        apb: str,
        basket_id: str,
        *,
        patient_id: str | None = None,
        products: tuple[DraftProduct, ...] = (),
        account_id: str | None = None,
    ) -> str | None:
        """Replace the product lines of an existing draft basket."""
        resolved_account = self._require(account_id or self.account_id, "account_id")
        resolved_patient = self._require(patient_id or self.patient_id, "patient_id")
        return await self._call(
            DRAFT_UPDATE,
            DraftUpdateArgs(
                apb=apb,
                account_id=resolved_account,
                basket_id=basket_id,
                patient_id=resolved_patient,
                products=products,
            ),
        )

    async def async_clear_draft_basket(
        self,
        apb: str,
        *,
        account_id: str | None = None,
    ) -> None:
        """Delete the draft basket."""
        resolved = self._require(account_id or self.account_id, "account_id")
        await self._call(DRAFT_CLEAR, DraftArgs(apb=apb, account_id=resolved))

    async def async_submit_basket(
        self,
        apb: str,
        basket_id: str,
        *,
        patient_id: str | None = None,
        products: tuple[DraftProduct, ...] = (),
        comment: str | None = None,
        unit_prices: tuple[tuple[str, float], ...] = (),
        pay_online: bool = False,
    ) -> str | None:
        """Submit a draft basket as an order at one pharmacy.

        Paying at pickup is the default because most pharmacies do not
        allow online payments. Passing pay_online True against such a
        pharmacy answers 400.
        """
        resolved = self._require(patient_id or self.patient_id, "patient_id")
        return await self._call(
            SUBMIT_BASKET,
            SubmitBasketArgs(
                apb=apb,
                basket_id=basket_id,
                patient_id=resolved,
                products=products,
                comment=comment,
                unit_prices=unit_prices,
                pay_online=pay_online,
            ),
        )

    async def async_cancel_basket(self, apb: str, basket_id: str) -> None:
        """Cancel a submitted order.

        Customer accounts are regularly denied this action: the pharmacy
        decides which orders can still be cancelled. A denial surfaces as
        FarmadAuthorizationError.
        """
        await self._call(CANCEL_BASKET, BasketIdArgs(apb=apb, basket_id=basket_id))

    async def async_pay_basket(
        self, apb: str, basket_id: str, redirect_url: str
    ) -> BasketPayment | None:
        """Start the online payment of one submitted order and return the session.

        The answer is the raw payment session, which the app hands to a
        browser because the checkout itself runs at the payment provider.
        Most pharmacies disallow online payments, which answers 400. The
        success shape stays unconfirmed because the test pharmacy allows
        none.
        """
        return await self._call(
            PAY_BASKET,
            PayBasketArgs(apb=apb, basket_id=basket_id, redirect_url=redirect_url),
        )

    async def async_get_product_in_apb(self, apb: str, cnk: str) -> CatalogProduct | None:
        """Fetch one product by its CNK as one pharmacy sells it.

        The answer is None when the pharmacy does not carry the product.
        """
        return await self._call(PRODUCT_IN_APB, ProductInApbArgs(cnk=cnk, apb=apb))

    async def async_get_product_in_apb_by_gtin(self, apb: str, gtin: str) -> CatalogProduct | None:
        """Fetch one product by its GTIN barcode as one pharmacy sells it.

        The answer is None when the pharmacy does not carry the product.
        """
        return await self._call(
            PRODUCT_IN_APB_BY_GTIN,
            ProductInApbByGtinArgs(gtin=gtin, apb=apb),
        )

    async def async_search_products_in_apb(
        self,
        apb: str,
        query: str,
        *,
        limit: int = 25,
        page: int = 1,
        language: str = "nl",
    ) -> tuple[CatalogProduct, ...]:
        """Search the catalog of one pharmacy and return one page of products.

        The query matches product names and a full CNK matches its own
        product. Pages count from 1 and a page past the last result is
        empty. A query without matches answers an empty tuple.
        """
        return await self._call(
            SEARCH_PRODUCTS,
            SearchProductsArgs(apb=apb, query=query, language=language, limit=limit, page=page),
        )

    async def async_get_kava_product(self, cnk: str) -> KavaProduct:
        """Fetch the reimbursement data of one product by its CNK.

        The answer carries the repayment and prescription flags and the
        official patient information links per language.
        """
        return await self._call(KAVA_PRODUCT, KavaProductArgs(cnk=cnk))

    async def async_get_message_draft(
        self,
        apb: str,
        *,
        account_id: str | None = None,
    ) -> MessageDraft | None:
        """Fetch the message draft, or None when no draft is open."""
        resolved = self._require(account_id or self.account_id, "account_id")
        return await self._call(MESSAGE_DRAFT, MessageDraftArgs(apb=apb, account_id=resolved))

    async def async_save_message_draft(
        self,
        apb: str,
        body: str,
        *,
        reference: str = "",
        account_id: str | None = None,
    ) -> MessageDraft | None:
        """Create a message draft and return it, or None on an empty answer."""
        resolved = self._require(account_id or self.account_id, "account_id")
        return await self._call(
            MESSAGE_DRAFT_SAVE,
            MessageDraftSaveArgs(apb=apb, account_id=resolved, body=body, reference=reference),
        )

    async def async_update_message_draft(
        self,
        apb: str,
        draft_id: str,
        body: str,
        *,
        reference: str = "",
        account_id: str | None = None,
    ) -> None:
        """Replace the text of an existing message draft."""
        resolved = self._require(account_id or self.account_id, "account_id")
        await self._call(
            MESSAGE_DRAFT_UPDATE,
            MessageDraftUpdateArgs(
                apb=apb, account_id=resolved, draft_id=draft_id, body=body, reference=reference
            ),
        )

    async def async_send_message_draft(
        self,
        apb: str,
        draft_id: str,
        *,
        account_id: str | None = None,
    ) -> None:
        """Send one message draft to the pharmacy as a new message."""
        resolved = self._require(account_id or self.account_id, "account_id")
        await self._call(
            MESSAGE_DRAFT_SEND,
            MessageDraftIdArgs(apb=apb, account_id=resolved, draft_id=draft_id),
        )

    async def async_upload_message_attachment(
        self,
        apb: str,
        draft_id: str,
        filename: str,
        content: bytes,
        *,
        content_type: str = "application/pdf",
        account_id: str | None = None,
    ) -> str | None:
        """Attach one file to a message draft and return the attachment id.

        The service accepts pdf attachments only: any other content type
        answers 500 instead of a clean refusal, so the content type
        defaults to application/pdf.
        """
        resolved = self._require(account_id or self.account_id, "account_id")
        return await self._call(
            MESSAGE_ATTACHMENT_UPLOAD,
            MessageAttachmentUploadArgs(
                apb=apb,
                account_id=resolved,
                draft_id=draft_id,
                filename=filename,
                content=content,
                content_type=content_type,
            ),
        )

    async def async_delete_message_attachment(
        self,
        apb: str,
        attachment_id: str,
        *,
        account_id: str | None = None,
    ) -> None:
        """Remove one attachment from the message draft."""
        resolved = self._require(account_id or self.account_id, "account_id")
        await self._call(
            MESSAGE_ATTACHMENT_DELETE,
            MessageAttachmentDeleteArgs(apb=apb, account_id=resolved, attachment_id=attachment_id),
        )

    async def async_mark_message_as_read(
        self,
        apb: str,
        message_id: str,
        *,
        account_id: str | None = None,
    ) -> None:
        """Mark one message in a conversation as read."""
        resolved = self._require(account_id or self.account_id, "account_id")
        await self._call(
            MESSAGE_MARK_READ,
            MessageMarkReadArgs(apb=apb, account_id=resolved, message_id=message_id),
        )

    async def async_get_service_messages(self) -> tuple[ServiceMessage, ...]:
        """Fetch the platform banners the app shows outside the pharmacy data."""
        return await self._call(SERVICE_MESSAGES, PlatformArgs())

    async def async_has_technical_interruptions(self) -> bool:
        """Answer whether the Farmad platform reports a technical interruption."""
        return await self._call(TECHNICAL_INTERRUPTIONS, PlatformArgs())

    async def async_get_prescriptions(
        self,
        *,
        page: int = 0,
        language: str = "nl",
    ) -> tuple[Prescription, ...]:
        """Fetch one page of prescriptions through the eHealth service."""
        return await self._call(PRESCRIPTIONS, PrescriptionsArgs(page=page, language=language))

    async def async_get_prescription(
        self,
        prescription_id: str,
        *,
        language: str = "nl",
    ) -> Prescription | None:
        """Fetch one prescription by its Recip-e id through the eHealth service."""
        return await self._call(
            PRESCRIPTION,
            PrescriptionArgs(prescription_id=prescription_id, language=language),
        )

    async def async_link_pharmacy(self, apb: str) -> bool:
        """Link the account to one pharmacy through the app's self-onboarding."""
        resolved = self._require(self.account_id, "account_id")
        return await self._call(
            SELF_ONBOARDING,
            SelfOnboardingArgs(account_id=resolved, apb=apb),
        )

    async def _call[ArgsT, ModelT](
        self,
        endpoint: Endpoint[ArgsT, ModelT],
        args: ArgsT,
    ) -> ModelT:
        """Run one endpoint: authenticate, request, retry once on a stale token, parse."""
        self._assert_open()
        await self._lifecycle.ensure_fresh()
        try:
            payload = await self._request_json_with_refresh(endpoint, args)
        except FarmadNotFoundError:
            if not endpoint.not_found_is_none:
                raise
            payload = None
        return endpoint.parse(payload, args)

    async def _request_json_with_refresh[ArgsT, ModelT](
        self,
        endpoint: Endpoint[ArgsT, ModelT],
        args: ArgsT,
    ) -> object:
        """Request one endpoint and retry once with refreshed tokens after a 401."""
        try:
            return await self._request_json_authenticated(endpoint, args)
        except FarmadAuthenticationError as err:
            if endpoint.ehealth:
                msg = (
                    "The eHealth session is missing or expired: complete the "
                    "consent step and pass its session cookie to the client"
                )
                raise FarmadEhealthAuthorizationRequiredError(msg) from err
            if self._lifecycle.refresh_token is None:
                raise
            _LOGGER.debug("401 with a live token: refreshing once and retrying")
            await self._lifecycle.refresh()
            return await self._request_json_authenticated(endpoint, args)

    async def _request_json_authenticated[ArgsT, ModelT](
        self,
        endpoint: Endpoint[ArgsT, ModelT],
        args: ArgsT,
    ) -> object:
        """Request one endpoint with the current bearer token."""
        params = {"api-version": endpoint.version}
        params.update(endpoint.params(args))
        headers = {
            "Authorization": self._lifecycle.bearer(),
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if endpoint.ehealth and self._ehealth_cookie:
            headers["Cookie"] = self._ehealth_cookie
        return await request_json(
            self._owned_session.session,
            method=endpoint.method,
            url=f"{endpoint.base_url}{endpoint.url(args)}",
            headers=headers,
            params=params,
            json_body=endpoint.json_body(args) if endpoint.json_body is not None else None,
            form_body=endpoint.form_body(args) if endpoint.form_body is not None else None,
            timeout=self._request_timeout,
        )

    def _require(self, value: str | None, name: str) -> str:
        """Return the value or raise when it cannot be resolved."""
        if not value:
            msg = f"{name} is required: pass it explicitly or log in first"
            raise FarmadAuthenticationError(msg)
        return value

    def _assert_open(self) -> None:
        if self._closed:
            msg = "The client is closed"
            raise FarmadClientClosedError(msg)

    async def async_close(self) -> None:
        """Close the session when this library created it."""
        self._closed = True
        await self._owned_session.close_if_owned()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.async_close()
