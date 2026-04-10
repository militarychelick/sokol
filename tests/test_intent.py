"""
Tests for intent parsing
"""

import pytest

from sokol.intent.parser import IntentParser
from sokol.core.config import Config


def test_quick_parse():
    """Test quick pattern-based parsing."""
    config = Config()
    parser = IntentParser(config)
    
    # Test app launch
    intent = parser._try_quick_parse("open chrome")
    assert intent is not None
    assert intent.intent_type.value == "command"
    assert intent.action_category.value == "app_launch"
    
    # Test file search
    intent = parser._try_quick_parse("find document")
    assert intent is not None
    assert intent.action_category.value == "file_search"


def test_is_affirmative():
    """Test affirmative response detection."""
    config = Config()
    parser = IntentParser(config)
    
    assert parser.is_affirmative("yes")
    assert parser.is_affirmative("sure")
    assert parser.is_affirmative("ok")
    assert not parser.is_affirmative("no")


def test_is_negative():
    """Test negative response detection."""
    config = Config()
    parser = IntentParser(config)
    
    assert parser.is_negative("no")
    assert parser.is_negative("cancel")
    assert not parser.is_negative("yes")
