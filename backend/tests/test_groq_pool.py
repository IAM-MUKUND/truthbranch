"""
Tests for GroqPool round-robin scheduling and transparent failover.
"""
from unittest.mock import MagicMock, patch
import pytest
from groq import RateLimitError, APIError

from backend.app.agent.groq_pool import GroqPool


def test_groq_pool_key_discovery_and_deduplication(monkeypatch):
    """Verify that GroqPool finds unique keys and strips inline comments/whitespace."""
    import os
    for k in list(os.environ.keys()):
        if k.startswith("GROQ_API_KEY"):
            monkeypatch.delenv(k, raising=False)

    monkeypatch.setenv("GROQ_API_KEY", "gsk_key1")
    monkeypatch.setenv("GROQ_API_KEY1", "gsk_key1")  # duplicate
    monkeypatch.setenv("GROQ_API_KEY2", "gsk_key2  # comment")
    monkeypatch.setenv("GROQ_API_KEY3", "gsk_key3")
    monkeypatch.setenv("GROQ_API_KEY4", "")

    pool = GroqPool()
    pool.reload()

    assert pool.key_count == 3
    assert pool.has_keys is True
    assert pool._keys == ["gsk_key1", "gsk_key2", "gsk_key3"]


def test_groq_pool_round_robin_dispatch():
    """Verify that requests rotate across keys in round-robin fashion."""
    pool = GroqPool()
    pool._keys = ["gsk_key1", "gsk_key2", "gsk_key3"]

    mock_client1 = MagicMock()
    mock_client2 = MagicMock()
    mock_client3 = MagicMock()

    mock_client1.chat.completions.create.return_value = "resp_1"
    mock_client2.chat.completions.create.return_value = "resp_2"
    mock_client3.chat.completions.create.return_value = "resp_3"

    pool._clients = [mock_client1, mock_client2, mock_client3]
    pool._initialized = True
    pool._index = 0

    r1 = pool.chat_completion(messages=[{"role": "user", "content": "1"}])
    assert r1 == "resp_1"
    assert mock_client1.chat.completions.create.called

    r2 = pool.chat_completion(messages=[{"role": "user", "content": "2"}])
    assert r2 == "resp_2"
    assert mock_client2.chat.completions.create.called

    r3 = pool.chat_completion(messages=[{"role": "user", "content": "3"}])
    assert r3 == "resp_3"
    assert mock_client3.chat.completions.create.called

    # Wraps back to first client
    r4 = pool.chat_completion(messages=[{"role": "user", "content": "4"}])
    assert r4 == "resp_1"


def test_groq_pool_automatic_failover_on_rate_limit():
    """Verify that hitting a RateLimitError rotates immediately to the next key."""
    pool = GroqPool()
    pool._keys = ["gsk_key1", "gsk_key2"]

    mock_client1 = MagicMock()
    mock_client2 = MagicMock()

    # Client 1 hits 429 RateLimitError
    dummy_req = MagicMock()
    mock_client1.chat.completions.create.side_effect = RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body={"error": {"message": "Rate limit exceeded"}}
    )
    # Client 2 succeeds
    mock_client2.chat.completions.create.return_value = "success_from_client_2"

    pool._clients = [mock_client1, mock_client2]
    pool._initialized = True
    pool._index = 0

    res = pool.chat_completion(messages=[{"role": "user", "content": "test"}])
    assert res == "success_from_client_2"
    assert mock_client1.chat.completions.create.called
    assert mock_client2.chat.completions.create.called


def test_groq_pool_all_keys_exhausted():
    """Verify that when all keys fail, an exception is raised so caller can fallback to scripted."""
    pool = GroqPool()
    pool._keys = ["gsk_key1", "gsk_key2"]

    mock_client1 = MagicMock()
    mock_client2 = MagicMock()

    mock_client1.chat.completions.create.side_effect = RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body={}
    )
    mock_client2.chat.completions.create.side_effect = RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body={}
    )

    pool._clients = [mock_client1, mock_client2]
    pool._initialized = True
    pool._index = 0

    with pytest.raises(RateLimitError):
        pool.chat_completion(messages=[{"role": "user", "content": "test"}])
