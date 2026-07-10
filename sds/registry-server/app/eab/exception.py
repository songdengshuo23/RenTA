from enum import Enum
from typing import Any

from fastapi import status

from app.core.base_exception import BaseException


class EabErrorCode(str, Enum):
    EAB_DISABLED = "EAB_DISABLED"
    EAB_NOT_CONFIGURED = "EAB_NOT_CONFIGURED"
    EAB_NOT_FOUND = "EAB_NOT_FOUND"
    EAB_ALREADY_CONSUMED = "EAB_ALREADY_CONSUMED"
    EAB_EXPIRED = "EAB_EXPIRED"
    AIC_NOT_OWNED = "AIC_NOT_OWNED"
    AIC_INACTIVE = "AIC_INACTIVE"
    AIC_NOT_APPROVED = "AIC_NOT_APPROVED"
    AIC_PROTOCOL_UNSUPPORTED = "AIC_PROTOCOL_UNSUPPORTED"


class EabException(BaseException):
    def __init__(
        self,
        code: EabErrorCode,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        input_params: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            error_group="eab",
            error_name=code.value,
            error_msg=message,
            input_params=input_params,
        )
