"""Tests for safety layer."""

import pytest

from sokol.core.types import RiskLevel
from sokol.safety.risk import RiskAssessor, assess_tool_risk
from sokol.safety.confirm import ConfirmationManager, ConfirmationTimeout


class TestRiskAssessor:
    """Tests for RiskAssessor."""

    def test_read_operations_are_safe(self):
        """Read operations return READ risk level."""
        assessor = RiskAssessor()
        risk = assessor.assess_action("file_read", {"path": "/test.txt"})
        assert risk == RiskLevel.READ

    def test_delete_is_dangerous(self):
        """Delete operations return DANGEROUS risk level."""
        assessor = RiskAssessor()
        risk = assessor.assess_action(
            "file_ops",
            {"action": "delete", "path": "/test.txt"},
            description="delete file",
        )
        assert risk == RiskLevel.DANGEROUS

    def test_dangerous_patterns_detected(self):
        """Dangerous patterns in description are detected."""
        assessor = RiskAssessor()
        risk = assessor.assess_action(
            "custom_tool",
            {},
            description="shutdown the system",
        )
        assert risk == RiskLevel.DANGEROUS

    def test_dangerous_tools_list(self):
        """Tools in dangerous list are marked dangerous."""
        assessor = RiskAssessor()
        risk = assessor.assess_action("file_delete", {})
        assert risk == RiskLevel.DANGEROUS

    def test_requires_confirmation(self):
        """Dangerous actions require confirmation."""
        assessor = RiskAssessor()
        assert assessor.requires_confirmation(RiskLevel.DANGEROUS)
        assert not assessor.requires_confirmation(RiskLevel.READ)


class TestConfirmationManager:
    """Tests for ConfirmationManager."""

    def test_create_request(self):
        """Can create confirmation request."""
        manager = ConfirmationManager()
        request = manager.create_request(
            tool_name="file_delete",
            action_description="Delete file test.txt",
            risk_level=RiskLevel.DANGEROUS,
            parameters={"path": "/test.txt"},
            consequences="File will be permanently deleted",
        )

        assert request.tool_name == "file_delete"
        assert request.risk_level == RiskLevel.DANGEROUS
        assert manager.is_pending(request.id)

    def test_respond_approved(self):
        """Can respond with approval."""
        manager = ConfirmationManager()
        request = manager.create_request(
            tool_name="test",
            action_description="Test action",
            risk_level=RiskLevel.WRITE,
            parameters={},
            consequences="Test",
        )

        result = manager.respond(request.id, approved=True)
        assert result
        assert not manager.is_pending(request.id)

        response = manager.get_response(request.id)
        assert response.approved

    def test_respond_denied(self):
        """Can respond with denial."""
        manager = ConfirmationManager()
        request = manager.create_request(
            tool_name="test",
            action_description="Test",
            risk_level=RiskLevel.DANGEROUS,
            parameters={},
            consequences="Test",
        )

        manager.respond(request.id, approved=False, reason="User declined")
        response = manager.get_response(request.id)
        assert not response.approved
        assert response.reason == "User declined"

    def test_timeout(self):
        """Request times out after timeout."""
        manager = ConfirmationManager(default_timeout=0.1)
        request = manager.create_request(
            tool_name="test",
            action_description="Test",
            risk_level=RiskLevel.DANGEROUS,
            parameters={},
            consequences="Test",
            timeout=0.1,
        )

        with pytest.raises(ConfirmationTimeout):
            manager.wait_for_response(request.id, timeout=0.1)

    def test_cancel_request(self):
        """Can cancel pending request."""
        manager = ConfirmationManager()
        request = manager.create_request(
            tool_name="test",
            action_description="Test",
            risk_level=RiskLevel.DANGEROUS,
            parameters={},
            consequences="Test",
        )

        assert manager.cancel(request.id)
        assert not manager.is_pending(request.id)

    def test_cancel_all(self):
        """Can cancel all pending requests."""
        manager = ConfirmationManager()
        for i in range(3):
            manager.create_request(
                tool_name=f"test_{i}",
                action_description="Test",
                risk_level=RiskLevel.DANGEROUS,
                parameters={},
                consequences="Test",
            )

        count = manager.cancel_all()
        assert count == 3
        assert len(manager.get_pending()) == 0
