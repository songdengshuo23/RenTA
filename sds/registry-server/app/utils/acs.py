import requests
import json
import logging
from app.agent.exception import AgentException, AgentError
from fastapi import status
from jsonschema import validate as jsonValidate, ValidationError
import os
from urllib.parse import urlparse

from app.core.config import settings
logger = logging.getLogger(__name__)

ACS_PROTOCOL_V0200 = "02.00"
ACS_PROTOCOL_V0201 = "02.01"
SUPPORTED_ACS_PROTOCOL_VERSIONS = (ACS_PROTOCOL_V0200, ACS_PROTOCOL_V0201)
ACS_SCHEMA_FILES = {
    ACS_PROTOCOL_V0200: "acsSchema.json",
    ACS_PROTOCOL_V0201: "acsSchema-v02.01.json",
}

_TRANSPORT_SCHEME_MAP = {
    "AMQP": {"amqp", "amqps"},
    "GRPC": {"grpc", "grpcs", "http", "https"},
    "HTTP_JSON": {"http", "https"},
    "JSONRPC": {"http", "https"},
    "REST": {"http", "https"},
}


def is_url_reachable(url, expected_status_code=None):
    try:
        response = requests.get(url, timeout=5)
        
        if expected_status_code is None:
            # If no specific status code is required, any response means it's reachable
            return True
        else:
            # If a specific status code is required, check if it matches
            return response.status_code == expected_status_code
    except requests.RequestException:
        # If an exception occurs (e.g., connection error, timeout), it's not reachable
        return False
    

def check_url_format(url, transport=None):
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return False
        allowed_schemes = _TRANSPORT_SCHEME_MAP.get(str(transport or "").upper())
        if allowed_schemes and parsed_url.scheme not in allowed_schemes:
            return False
        return True
    except Exception as e:
        logger.info(f"URL parsing error: {url}, error: {e}")
        return False
    
    
# 检查 x-caChallengeBaseUrl 是否可达且符合要求，复合返回None，否则返回错误信息
def check_ca_challenge_base_url(url):
    ca_challenge_status_path_type = settings.CA_CHALLENGE_STATUS_PATH_TYPE
    status_url = None
    parsed_url = None
    try:
        parsed_url = urlparse(url)
        if ca_challenge_status_path_type == "root":
            status_url = f"{parsed_url.scheme}://{parsed_url.netloc}/status"
        else:
            path = parsed_url.path.rsplit('/', 2)[0]
            status_url = f"{parsed_url.scheme}://{parsed_url.netloc}{path}/status"
    except Exception as e:
        msg = f"URL parsing error: {url}, error: {e}"
        logger.info(msg)
        return False, msg
    
    try:
        response = requests.get(status_url, timeout=5)
        if (response.status_code != 200):
            msg = f"response status: {response.status_code}"
            logger.info(msg)
            return False, msg

        if not is_valid_json(response.text):
            msg = f"Invalid response: {response.text}"
            logger.info(msg)
            return False, msg
        
        response_json = json.loads(response.text)

        if response_json.get("status") != "running":
            msg = f"Invalid response: {response.text}"
            logger.info(msg)
            return False, msg
        
        if response_json.get("api_base_path").rstrip("/") != parsed_url.path.rstrip("/"):
            msg = f"different from challenge server: {response_json.get('api_base_path')}"
            logger.info(msg)
            return False, msg

        return True, None
    except requests.RequestException as e:
        msg = f"{url} is not reachable"
        logger.info(msg)
        return False, msg


def is_valid_json(json_string):
    try:
        json.loads(json_string)
        return True
    except ValueError as e:
        logger.warning(f"Invalid JSON string: {json_string}, error: {e}")
        return False
    

def get_acs_protocol_version(acs: str | dict) -> str:
    instance = acs if isinstance(acs, dict) else json.loads(acs)
    protocol_version = instance.get("protocolVersion")
    if protocol_version not in SUPPORTED_ACS_PROTOCOL_VERSIONS:
        raise AgentException(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_name=AgentError.INVALID_ACS,
            error_msg=(
                "Unsupported ACS protocolVersion: "
                f"{protocol_version!r}; expected one of "
                f"{', '.join(SUPPORTED_ACS_PROTOCOL_VERSIONS)}"
            ),
            input_params={"protocolVersion": protocol_version},
        )
    return protocol_version


def get_acs_schema_path(protocol_version: str) -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "app/agent", ACS_SCHEMA_FILES[protocol_version])


def _validate_schema(instance: dict, acs: str | dict, protocol_version: str) -> None:
    schema_path = get_acs_schema_path(protocol_version)
    if not os.path.exists(schema_path):
        raise AgentException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_name=AgentError.INVALID_ACS,
            error_msg=f"ACS schema file missing: {os.path.basename(schema_path)}",
            input_params={"protocolVersion": protocol_version},
        )

    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)
    try:
        jsonValidate(instance=instance, schema=schema)
    except ValidationError as e:
        logger.error(f"ACS validation error: {e.message}")
        raise AgentException(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_name=AgentError.INVALID_ACS,
            error_msg=f"Json path: [ {e.json_path} ]; Error message: [ {e.message} ]",
            input_params={"acs": acs},
        )


def validate(acs: str | dict):
    if acs is None or (isinstance(acs, str) and not is_valid_json(acs)) or (isinstance(acs, dict) and not acs):
        raise AgentException(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_name=AgentError.ACS_NOT_EXISTED,
            error_msg="ACS cannot be null",
            input_params={"acs": str(acs)},
        )

    instance = acs if isinstance(acs, dict) else json.loads(acs)
    protocol_version = get_acs_protocol_version(instance)
    _validate_schema(instance, acs, protocol_version)

    security_schemes = instance.get("securitySchemes") or {}
    mutual_tls_scheme_names = set()
    legacy_challenge_urls = set()

    for schema_name, schema in security_schemes.items():
        schema_type = schema.get("type")
        if schema_type != "mutualTLS":
            continue

        mutual_tls_scheme_names.add(schema_name)
        challenge_url = schema.get("x-caChallengeBaseUrl")
        if protocol_version == ACS_PROTOCOL_V0200:
            if not isinstance(challenge_url, str) or not check_url_format(
                challenge_url, "HTTP_JSON"
            ):
                raise AgentException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_name=AgentError.INVALID_ACS,
                    error_msg=f"x-caChallengeBaseUrl format: {schema_name}",
                    input_params={"acs": acs},
                )
            challenge_url_valid, err = check_ca_challenge_base_url(challenge_url)
            if not challenge_url_valid:
                raise AgentException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_name=AgentError.INVALID_ACS,
                    error_msg=f"x-caChallengeBaseUrl: {err}",
                    input_params={"acs": acs},
                )
            legacy_challenge_urls.add(challenge_url.rstrip("/"))
        elif challenge_url is not None and not check_url_format(
            challenge_url, "HTTP_JSON"
        ):
            raise AgentException(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_name=AgentError.INVALID_ACS,
                error_msg=f"x-caChallengeBaseUrl format: {schema_name}",
                input_params={"acs": acs},
            )

    endpoints = instance.get("endPoints")
    if endpoints:
        for endpoint in endpoints:
            securities = endpoint.get("security") or []
            mtls_used = False
            for security in securities:
                for scr_name in security.keys():
                    if scr_name in mutual_tls_scheme_names:
                        mtls_used = True
                        break
                if mtls_used:
                    break
            if not mtls_used:
                raise AgentException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_name=AgentError.INVALID_ACS,
                    error_msg=f"endPoint must use mutualTLS security scheme",
                    input_params={"acs": acs},
                )
            ep_url = endpoint.get("url")
            if not isinstance(ep_url, str) or not check_url_format(
                ep_url, endpoint.get("transport")
            ):
                raise AgentException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_name=AgentError.INVALID_ACS,
                    error_msg=f"endpoint URL format: {endpoint.get('url', '')}",
                    input_params={"acs": acs},
                )
            if ep_url.rstrip("/") in legacy_challenge_urls:
                raise AgentException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_name=AgentError.INVALID_ACS,
                    error_msg=f"x-caChallengeBaseUrl must not appear in any endPoint: {ep_url}",
                    input_params={"acs": acs},
                )

    web_app_url = instance.get("webAppUrl")
    if web_app_url is None and (endpoints is None or len(endpoints) == 0):
        raise AgentException(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_name=AgentError.INVALID_ACS,
            error_msg=f"Either webAppUrl or endpoints must be present in ACS",
            input_params={"acs": acs},
        )


def validate_for_write(acs: str | dict) -> None:
    """Validate a new/updated ACS and enforce protocol write switches."""
    validate(acs)
    protocol_version = get_acs_protocol_version(acs)
    if protocol_version == ACS_PROTOCOL_V0201 and not settings.ACPS_V21_ENABLED:
        raise AgentException(
            status_code=status.HTTP_409_CONFLICT,
            error_name=AgentError.INVALID_ACS,
            error_msg="ACPs v2.1 writes are disabled",
            input_params={"protocolVersion": protocol_version},
        )
    if (
        protocol_version == ACS_PROTOCOL_V0200
        and not settings.ACPS_LEGACY_API_ENABLED
    ):
        raise AgentException(
            status_code=status.HTTP_409_CONFLICT,
            error_name=AgentError.INVALID_ACS,
            error_msg="Legacy ACS writes are disabled",
            input_params={"protocolVersion": protocol_version},
        )
