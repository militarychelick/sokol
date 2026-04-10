"""
Tests for safety policy
"""

import pytest

from sokol.policy.safety import SafetyPolicy
from sokol.core.config import SafetyConfig
from sokol.core.constants import ActionCategory, SafetyLevel


def test_safety_classification():
    """Test safety level classification."""
    config = SafetyConfig()
    policy = SafetyPolicy(config)
    
    # Test safe actions
    level = policy.classify(ActionCategory.APP_LAUNCH, {})
    assert level == SafetyLevel.SAFE
    
    # Test caution actions
    level = policy.classify(ActionCategory.APP_CLOSE, {})
    assert level == SafetyLevel.CAUTION
    
    # Test dangerous actions
    level = policy.classify(ActionCategory.FILE_DELETE, {})
    assert level == SafetyLevel.DANGEROUS


def test_dangerous_patterns():
    """Test dangerous pattern detection."""
    config = SafetyConfig()
    policy = SafetyPolicy(config)
    
    # Test dangerous file patterns
    entities = {"paths": ["test.exe"]}
    level = policy.classify(ActionCategory.FILE_MODIFY, entities)
    assert level == SafetyLevel.DANGEROUS
