from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.account.model import RoleType, User
from app.core.auth import check_user_role
from app.core.db_session import get_db
from app.core.service_auth import require_registry_service_token
from app.eab.schema import EabConsumeRequest, EabConsumeResponse, EabCredentialResponse
from app.eab.service import consume_eab_credential, generate_eab_credential

router_atr = APIRouter(tags=["ATR EAB"])
router_internal = APIRouter(prefix="/internal", tags=["Internal EAB"])
require_client_user = check_user_role([RoleType.CLIENT])


@router_atr.post(
    "/eab/{agent_aic}",
    response_model=EabCredentialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="为指定 Agent 生成一次性 EAB 凭据",
)
def create_eab_credential(
    agent_aic: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client_user),
) -> EabCredentialResponse:
    return generate_eab_credential(db, current_user.id, agent_aic)


@router_internal.post(
    "/eab/consume",
    response_model=EabConsumeResponse,
    status_code=status.HTTP_200_OK,
    summary="消费一次性 EAB 凭据",
)
def consume_eab_credential_endpoint(
    request: EabConsumeRequest,
    _auth: None = Depends(require_registry_service_token),
    db: Session = Depends(get_db),
) -> EabConsumeResponse:
    return consume_eab_credential(db, request.key_id)
