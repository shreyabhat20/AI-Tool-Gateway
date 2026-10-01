import pytest

from app.core.errors import GatewayError
from app.services.authorization import require_permission


def test_admin_is_allowed_without_explicit_mapping() -> None:
    require_permission("admin", False)


def test_developer_requires_a_mapping() -> None:
    require_permission("developer", True)
    with pytest.raises(GatewayError) as error:
        require_permission("developer", False)
    assert error.value.status_code == 403
    assert error.value.code == "permission_denied"


def test_viewer_mapping_can_grant_a_safe_tool() -> None:
    require_permission("viewer", True)

