from dataclasses import dataclass
from typing import Optional
import jwt

@dataclass
class TenantContext:
    tenant_id: str
    user_id: str
    allowed_models: list[str]
    session_id: str

class TenantContextManager:
    @staticmethod
    def extract_from_jwt(token: str) -> TenantContext:
        """JWTトークンからテナントコンテキストを抽出"""
        payload = jwt.decode(token, options={"verify_signature": False})
        return TenantContext(
            tenant_id=payload["tenant_id"],
            user_id=payload["sub"],
            allowed_models=payload.get("allowed_models", ["claude-3-haiku"]),
            session_id=payload.get("session_id", "")
        )
    
    @staticmethod
    def validate_model_access(context: TenantContext, model: str) -> bool:
        """テナントのモデルアクセス権限をチェック"""
        return model in context.allowed_models
