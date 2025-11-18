from dataclasses import dataclass
from typing import Dict, Any
from .tenant_context import TenantContext, TenantContextManager

@dataclass
class AgentConfig:
    name: str
    prompt_template: str
    model: str
    tools: list[str]

class TenantAwareAgent:
    def __init__(self):
        self.default_configs = {}
        self.tenant_configs = {}  # tenant_id -> AgentConfig
    
    def register_default_agent(self, name: str, config: AgentConfig):
        self.default_configs[name] = config
    
    def register_tenant_agent(self, tenant_id: str, name: str, config: AgentConfig):
        if tenant_id not in self.tenant_configs:
            self.tenant_configs[tenant_id] = {}
        self.tenant_configs[tenant_id][name] = config
    
    def get_agent_config(self, context: TenantContext, agent_name: str) -> AgentConfig:
        # テナント固有の設定があれば優先
        if (context.tenant_id in self.tenant_configs and 
            agent_name in self.tenant_configs[context.tenant_id]):
            config = self.tenant_configs[context.tenant_id][agent_name]
        else:
            config = self.default_configs[agent_name]
        
        # モデルアクセス権限をチェック
        if not TenantContextManager.validate_model_access(context, config.model):
            # フォールバックモデルを使用
            config.model = context.allowed_models[0]
        
        return config
    
    async def invoke(self, context: TenantContext, agent_name: str, message: str) -> str:
        config = self.get_agent_config(context, agent_name)
        
        # プロンプトにテナント情報を注入
        prompt = config.prompt_template.format(
            tenant_id=context.tenant_id,
            user_message=message
        )
        
        # エージェント実行（簡略化）
        return f"Response from {config.model} for tenant {context.tenant_id}"
