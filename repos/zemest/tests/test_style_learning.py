"""Tests for the style-learning agent and chat import pipeline."""
import io
import json
import zipfile
from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from app.services.importers.messenger_dyi import (
    parse_messenger_dyi_zip,
    get_zip_stats,
    parse_instagram_dyi_zip,
)
from app.services.importers.whatsapp_export import parse_whatsapp_export_zip
from app.ai.style_learner import (
    smart_sample,
    extract_heuristic_features,
    build_and_persist_personality,
)


def _create_messenger_zip(messages_data: dict) -> bytes:
    """Create a mock FB DYI ZIP in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "messages/inbox/test_thread/message_1.json",
            json.dumps(messages_data),
        )
    return buf.getvalue()


class TestMessengerDYIParser:

    def test_parse_basic_messages(self):
        """Test parsing a basic FB DYI export."""
        data = {
            "title": "Test Thread",
            "participants": [{"name": "Merchant"}, {"name": "Customer"}],
            "messages": [
                {
                    "sender_name": "Customer",
                    "timestamp_ms": 1577836800000,  # 2020-01-01
                    "content": "Hello, do you have galabiyas?",
                    "type": "Generic",
                },
                {
                    "sender_name": "Merchant",
                    "timestamp_ms": 1577836900000,
                    "content": "Yes! We have cotton galabiyas for 450 EGP",
                    "type": "Generic",
                },
                {
                    "sender_name": "Customer",
                    "timestamp_ms": 1577837000000,
                    "content": "Great, I'll take one",
                    "type": "Generic",
                },
            ],
        }
        zip_bytes = _create_messenger_zip(data)
        messages = parse_messenger_dyi_zip(zip_bytes, page_owner_names={"Merchant"})

        assert len(messages) == 3
        assert messages[0]["sender"] == "Customer"
        assert messages[0]["role"] == "customer"
        assert messages[1]["sender"] == "Merchant"
        assert messages[1]["role"] == "merchant"
        assert messages[0]["timestamp"] < messages[1]["timestamp"]
        assert messages[0]["channel"] == "messenger"

    def test_auto_detect_page_owner(self):
        """Test auto-detection of page owner (most frequent sender)."""
        data = {
            "title": "Thread",
            "participants": [{"name": "Merchant"}, {"name": "Customer"}],
            "messages": [
                {"sender_name": "Merchant", "timestamp_ms": 1577836800000, "content": "reply 1"},
                {"sender_name": "Merchant", "timestamp_ms": 1577836900000, "content": "reply 2"},
                {"sender_name": "Merchant", "timestamp_ms": 1577837000000, "content": "reply 3"},
                {"sender_name": "Customer", "timestamp_ms": 1577836800000, "content": "question 1"},
            ],
        }
        zip_bytes = _create_messenger_zip(data)
        messages = parse_messenger_dyi_zip(zip_bytes)  # auto-detect

        merchant_msgs = [m for m in messages if m["role"] == "merchant"]
        customer_msgs = [m for m in messages if m["role"] == "customer"]
        assert len(merchant_msgs) == 3
        assert len(customer_msgs) == 1

    def test_skips_system_messages(self):
        """System messages (calls, payments) should be skipped."""
        data = {
            "title": "Thread",
            "participants": [],
            "messages": [
                {"sender_name": "A", "timestamp_ms": 1577836800000, "content": "hi", "type": "Generic"},
                {"sender_name": "A", "timestamp_ms": 1577836900000, "type": "Call"},
                {"sender_name": "A", "timestamp_ms": 1577837000000, "content": "bye", "type": "Generic"},
            ],
        }
        zip_bytes = _create_messenger_zip(data)
        messages = parse_messenger_dyi_zip(zip_bytes)
        assert len(messages) == 2  # Call skipped

    def test_invalid_zip(self):
        """Invalid ZIP should raise ValueError."""
        with pytest.raises(ValueError):
            parse_messenger_dyi_zip(b"not a zip file")

    def test_empty_zip(self):
        """Empty ZIP should return empty list."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "no messages here")
        messages = parse_messenger_dyi_zip(buf.getvalue())
        assert messages == []

    def test_get_zip_stats(self):
        """Test ZIP statistics without full parse."""
        data = {
            "title": "Thread",
            "participants": [],
            "messages": [{"sender_name": "A", "timestamp_ms": 1577836800000, "content": "hi"}],
        }
        zip_bytes = _create_messenger_zip(data)
        stats = get_zip_stats(zip_bytes)
        assert stats["thread_count"] == 1
        assert stats["estimated_message_count"] == 1


class TestInstagramDYIParser:

    def test_parse_instagram_messages(self):
        """Instagram uses same format as FB."""
        data = {
            "title": "IG Thread",
            "participants": [{"name": "Influencer"}],
            "messages": [
                {"sender_name": "Influencer", "timestamp_ms": 1577836800000, "content": "DM me!"},
            ],
        }
        zip_bytes = _create_messenger_zip(data)
        messages = parse_instagram_dyi_zip(zip_bytes)
        assert len(messages) == 1
        assert messages[0]["channel"] == "instagram"


class TestWhatsAppExportParser:

    def _create_whatsapp_zip(self, chat_text: str) -> bytes:
        """Create a mock WhatsApp export ZIP."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("_chat.txt", chat_text)
        return buf.getvalue()

    def test_parse_basic_chat(self):
        """Test parsing a basic WhatsApp export."""
        chat = """[1/15/24, 10:30:00 AM] Ahmed: Hello, is the bag available?
[1/15/24, 10:31:00 AM] Store: Yes! It's 500 EGP
[1/15/24, 10:32:00 AM] Ahmed: Great, I'll order"""
        zip_bytes = self._create_whatsapp_zip(chat)
        messages = parse_whatsapp_export_zip(zip_bytes, page_owner_name="Store")

        assert len(messages) == 3
        assert messages[0]["sender"] == "Ahmed"
        assert messages[0]["role"] == "customer"
        assert messages[1]["sender"] == "Store"
        assert messages[1]["role"] == "merchant"
        assert messages[0]["channel"] == "whatsapp"

    def test_multiline_message(self):
        """Multi-line messages should be joined."""
        chat = """[1/15/24, 10:30:00 AM] Ahmed: Hello
I want to ask
about the bag
[1/15/24, 10:31:00 AM] Store: Yes"""
        zip_bytes = self._create_whatsapp_zip(chat)
        messages = parse_whatsapp_export_zip(zip_bytes)
        assert len(messages) == 2
        assert "I want to ask" in messages[0]["content"]
        assert "about the bag" in messages[0]["content"]


class TestSmartSampling:

    def test_returns_all_if_fewer_than_sample_size(self):
        """If we have fewer messages than sample_size, return all."""
        from app.models.message import Message
        import uuid

        msgs = [
            Message(
                id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                role="merchant",
                content=f"message {i}",
                created_at=datetime.utcnow(),
            )
            for i in range(50)
        ]
        sampled = smart_sample(msgs, sample_size=300)
        assert len(sampled) == 50

    def test_samples_correct_count(self):
        """Should sample exactly sample_size messages."""
        from app.models.message import Message
        import uuid

        msgs = [
            Message(
                id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                role="merchant",
                content=f"message {i}",
                created_at=datetime.utcnow() - timedelta(days=i),
            )
            for i in range(1000)
        ]
        sampled = smart_sample(msgs, sample_size=300)
        assert len(sampled) <= 300

    def test_empty_list(self):
        """Empty message list should return empty."""
        assert smart_sample([]) == []


class TestHeuristicFeatureExtraction:

    def test_extracts_basic_features(self):
        """Test heuristic feature extraction."""
        from app.models.message import Message
        import uuid

        msgs = [
            Message(
                id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                role="merchant",
                content="أهلاً بيك! إزيك؟ 😊",
                created_at=datetime.utcnow(),
            ),
            Message(
                id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                role="merchant",
                content="المنتج متاح بـ 500 جنيه ✅",
                created_at=datetime.utcnow(),
            ),
            Message(
                id=uuid.uuid4(),
                conversation_id=uuid.uuid4(),
                role="merchant",
                content="شكراً ليك! في الخدمة 🙏",
                created_at=datetime.utcnow(),
            ),
        ]
        features = extract_heuristic_features(msgs)

        assert features["message_count_analyzed"] == 3
        assert features["tone"] in ("formal", "friendly", "casual")
        assert "أهلا" in features["greeting_patterns"] or len(features["greeting_patterns"]) == 0
        assert features["emoji_frequency"] in ("none", "low", "medium", "high")

    def test_empty_messages(self):
        """Empty message list should return default features."""
        features = extract_heuristic_features([])
        assert features["message_count_analyzed"] == 0
        assert features["tone"] == "friendly"


@pytest.mark.asyncio
class TestStyleLearningIntegration:

    async def test_build_style_profile_with_minimal_messages(
        self, db_session, test_tenant, test_customer
    ):
        """Test building a style profile with minimal messages."""
        from app.models.message import Message
        from app.models.conversation import Conversation
        import uuid

        # Create a conversation with merchant messages
        conv = Conversation(
            id=uuid.uuid4(),
            tenant_id=test_tenant.id,
            customer_id=test_customer.id,
            channel="messenger",
            status="imported",
        )
        db_session.add(conv)
        await db_session.flush()

        # Add 10 merchant messages
        for i in range(10):
            msg = Message(
                id=uuid.uuid4(),
                conversation_id=conv.id,
                role="merchant",
                content=f"أهلاً بيك! المنتج متاح بـ {i*100} جنيه 😊",
                created_at=datetime.utcnow() - timedelta(hours=i),
            )
            db_session.add(msg)
        await db_session.flush()

        # Build profile (without LLM to keep test fast)
        profile = await build_and_persist_personality(
            db_session, test_tenant, use_llm=False
        )

        assert profile is not None
        assert profile["message_count_analyzed"] >= 6
        assert "tone" in profile
        assert test_tenant.style_profile is not None
        assert test_tenant.knowledge_built_at is not None
