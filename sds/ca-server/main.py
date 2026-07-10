"""
Agent CA 认证服务 - 应用入口点

这是基于 FastAPI 开发的 Agent CA 认证系统的主入口文件。
"""

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from dotenv import load_dotenv
from app.core.config import settings
from sqlmodel import Session

# Import database initialization
from app.core.db_session import create_db_and_tables, engine

# Import ACME router and error handler
from app.acme.api import router as acme_router
from app.acme.error_handler import ACMEErrorHandler

# Import ATR management IP filter middleware
from app.core.atr_ip_filter import ATRManagementIPFilterMiddleware
from app.core.security import require_ca_admin_token

# Import certificate management router
from app.certificates.api import router as certificates_router

# Import extension API router
from app.certificates.api_ext import router as ext_router

# Import CRL router
from app.crl.api import router as crl_router

# Import OCSP router
from app.ocsp.api import router as ocsp_router
from app.common.ocsp_service import OCSPService
from app.core.ca_manager import get_ca_manager

# 加载环境变量
load_dotenv()


def ensure_mock_ocsp_responder() -> None:
    """在 mock 模式下自动初始化一个默认 OCSP responder。"""
    if not settings.agent_registry_mock and not settings.http01_validation_mock:
        return

    with Session(engine) as session:
        ocsp_service = OCSPService(session)
        if ocsp_service.get_active_responder():
            return

        ca_manager = get_ca_manager()
        responder_name = "Mock OCSP Responder"
        ocsp_service.create_responder(
            name=responder_name,
            certificate_pem=ca_manager.get_ca_certificate_pem(),
            private_key_pem=ca_manager.get_ca_private_key_pem(),
            endpoints={"primary": f"http://localhost:{settings.uvicorn_port}/acps-atr-v2/ocsp"},
            supported_extensions=["nonce"],
            response_timeout_seconds=30,
        )
        print(f"已创建默认 OCSP responder: {responder_name}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    create_db_and_tables()
    ensure_mock_ocsp_responder()
    yield
    # 关闭时的清理工作（如果需要）


# 创建 FastAPI 应用实例
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Agent CA 认证系统后端 API",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    lifespan=lifespan,
)

# 添加 ACME 错误处理中间件
app.add_middleware(ACMEErrorHandler)

# 添加 ATR 管理功能 IP 过滤中间件
app.add_middleware(ATRManagementIPFilterMiddleware)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册 ACME 路由
app.include_router(acme_router, prefix="/acps-atr-v2/acme", tags=["ACME"])

# 注册证书管理路由
app.include_router(
    certificates_router,
    prefix="/admin/certificates",
    tags=["不在ACPs体系中的证书管理，基本的功能"],
    dependencies=[Depends(require_ca_admin_token)],
)

# 注册扩展 API 路由 (Trust Bundle & Revoke Notify)
app.include_router(
    ext_router,
    prefix="/acps-atr-v2/ca",
    tags=["Extension API"],
)

# 注册CRL路由
app.include_router(crl_router, prefix="/acps-atr-v2/crl", tags=["CRL"])

# 注册OCSP路由
app.include_router(ocsp_router, prefix="/acps-atr-v2/ocsp", tags=["OCSP"])


# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "Agent CA API",
        "version": settings.app_version,
        "environment": os.getenv("APP_ENV", "development"),
    }


# 根路径
@app.get("/")
async def root():
    """根路径欢迎信息"""
    return {
        "message": "欢迎使用 Agent CA 认证服务 API",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


# 当直接运行此文件时启动服务器
if __name__ == "__main__":
    # 启动服务器
    uvicorn.run(
        "main:app",
        host=settings.uvicorn_host,
        port=settings.uvicorn_port,
        reload=settings.uvicorn_reload,
        log_level=settings.uvicorn_log_level,
    )
