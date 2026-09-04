"""Adversarial dashboard-data tests — one test per audit PoC (wave F10).

Audit sources: findings/B8-frontend-datalayer.md (list payload bloat),
findings/B6-dashboard-admin.md (dead owner-mode feature).

* B8: the conversations LIST response must NOT embed message threads —
  the dashboard polls it every 10 s; payload grew with chat history.
  The list must carry ``last_message_preview`` + ``message_count``.
* B6: owner-mode chat posted to /test/chat — users believing they talked
  to the owner-side agent were silently generating CUSTOMER
  conversations. The frontend now calls /test/postiz-chat.
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio

from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message


@pytest_asyncio.fixture
async def conv_with_messages(db_session, test_tenant, test_customer):
    conversation = Conversation(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        customer_id=test_customer.id,
    )
    db_session.add(conversation)
    await db_session.flush()

    # Two customer messages + one assistant message.
    msgs = []
    for i, (role, content) in enumerate([
        ("customer", "السلام عليكم، عايز أعرف السعر"),
        ("assistant", "أهلاً بيك! المنتج بـ 350 جنيه"),
        ("customer", "تمام، عايز أطلب واحد"),
    ]):
        m = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role=role,
            content=content,
        )
        db_session.add(m)
        msgs.append(m)
    await db_session.commit()
    return conversation, msgs


# --------------------------------------------------------------------------- #
# B8 — list payload contract
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
class TestConversationListPayload:
    async def test_list_has_no_message_threads(
        self, client, auth_headers, test_tenant, conv_with_messages
    ):
        """The list response must not contain any messages array."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 1
        for conv in body["conversations"]:
            assert "messages" not in conv, (
                "list response embeds message threads — B8 payload bloat "
                "on a 10s-polled endpoint"
            )

    async def test_list_has_preview_and_count(
        self, client, auth_headers, test_tenant, conv_with_messages
    ):
        """Preview = last message content (bounded), count = 3."""
        conv, _ = conv_with_messages
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations",
            headers=auth_headers,
        )
        body = resp.json()
        mine = next(c for c in body["conversations"] if c["id"] == str(conv.id))
        assert mine["message_count"] == 3
        assert "عايز أطلب واحد" in mine["last_message_preview"]

    async def test_preview_bounded_to_80_chars(
        self, client, auth_headers, test_tenant, db_session, test_customer
    ):
        """A 10,000-char last message must not ship in the list."""
        conversation = Conversation(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            customer_id=test_customer.id,
        )
        db_session.add(conversation)
        await db_session.flush()
        db_session.add(Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="customer",
            content="ح" * 10000,
        ))
        await db_session.commit()

        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations",
            headers=auth_headers,
        )
        mine = next(
            c for c in resp.json()["conversations"]
            if c["id"] == str(conversation.id)
        )
        assert len(mine["last_message_preview"]) <= 80

    async def test_detail_still_returns_messages(
        self, client, auth_headers, test_tenant, conv_with_messages
    ):
        """The thread view keeps full messages (that's where they belong)."""
        conv, _ = conv_with_messages
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations/{conv.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["messages"]) == 3

    async def test_list_across_tenants_isolated(
        self, client, second_auth_headers, test_tenant, conv_with_messages
    ):
        """Tenant B sees nothing of tenant A's conversations."""
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/conversations",
            headers=second_auth_headers,
        )
        assert resp.status_code == 404  # get_tenant: not your tenant


# --------------------------------------------------------------------------- #
# B6 — owner chat wiring (source-level contract)
# --------------------------------------------------------------------------- #
class TestOwnerChatWiring:
    def test_frontend_owner_mode_calls_postiz_chat(self):
        """The chat page must route owner-mode sends to /test/postiz-chat
        (B6 PoC: it posted to /test/chat, creating fake customer convs)."""
        page = (
            __import__("pathlib").Path(__file__).resolve().parents[4]
            / "src" / "app" / "dashboard" / "[tenantId]" / "chat" / "page.tsx"
        ).read_text()
        # Owner branch exists and uses sendOwner.
        assert "ownerMode" in page and "sendOwner" in page, (
            "owner mode is not wired to the owner-side agent"
        )
        # The owner branch must come BEFORE the customer send (or at least
        # not fall through): check it returns before sendMutation.
        owner_branch = page.split("if (ownerMode) {")[1].split("return;")[0]
        assert "sendOwner" in owner_branch

    def test_send_owner_api_method_targets_postiz(self):
        api = (
            __import__("pathlib").Path(__file__).resolve().parents[4]
            / "src" / "lib" / "zemest-api.ts"
        ).read_text()
        assert '""/test/postiz-chat"' in api or '"/test/postiz-chat"' in api

    def test_backend_owner_endpoint_enforces_ownership(self):
        """The backend /test/postiz-chat checks Tenant.owner_id == user.id."""
        from app.api import test_chat
        import inspect

        src = inspect.getsource(test_chat)
        postiz = src.split("postiz_chat")[1]
        assert "Tenant.owner_id == user.id" in postiz

    def test_list_schema_is_summary_not_full(self):
        from app.schemas.conversation import (
            ConversationListResponse,
            ConversationSummaryResponse,
        )

        item_field_names = set(ConversationSummaryResponse.model_fields.keys())
        assert "messages" not in item_field_names
        assert "last_message_preview" in item_field_names
        assert "message_count" in item_field_names
        assert ConversationListResponse.model_fields["conversations"].annotation.__args__[0] is ConversationSummaryResponse
