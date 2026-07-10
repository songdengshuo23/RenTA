        #!/usr/bin/env bash
        set -euo pipefail
        cd /workspace
        pip install --upgrade pip
        pip install .
        python - <<'PY'
from sqlmodel import Session
from app.core.db_session import create_db_and_tables, engine
from app.common.ocsp_service import OCSPService
from app.core.ca_manager import get_ca_manager
from app.core.config import settings
create_db_and_tables()
with Session(engine) as session:
    service = OCSPService(session)
    if not service.get_active_responder():
        ca = get_ca_manager()
        service.create_responder(
            name='SDS OCSP Responder',
            certificate_pem=ca.get_ca_certificate_pem(),
            private_key_pem=ca.get_ca_private_key_pem(),
            endpoints={'primary': f'http://ca-server:{settings.uvicorn_port}/acps-atr-v2/ocsp'},
            supported_extensions=['nonce'],
            response_timeout_seconds=30,
        )
PY
        exec python main.py
