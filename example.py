import asyncio
from tenant_aware_agent import TenantAwareAgent, AgentConfig
from tenant_context import TenantContext

async def main():
    agent = TenantAwareAgent()
    
    # デフォルトエージェント設定
    agent.register_default_agent("assistant", AgentConfig(
        name="assistant",
        prompt_template="You are a helpful assistant for tenant {tenant_id}. User: {user_message}",
        model="claude-3-haiku",
        tools=["search", "calculator"]
    ))
    
    # テナント固有のカスタマイズ
    agent.register_tenant_agent("enterprise-corp", "assistant", AgentConfig(
        name="assistant", 
        prompt_template="You are a corporate assistant. Respond formally. Tenant: {tenant_id}. User: {user_message}",
        model="claude-3-sonnet",
        tools=["search", "calculator", "crm"]
    ))
    
    # テナントコンテキスト
    context1 = TenantContext("startup-inc", "user1", ["claude-3-haiku"], "session1")
    context2 = TenantContext("enterprise-corp", "user2", ["claude-3-sonnet"], "session2")
    
    # 実行
    response1 = await agent.invoke(context1, "assistant", "Hello")
    response2 = await agent.invoke(context2, "assistant", "Hello")
    
    print(f"Startup response: {response1}")
    print(f"Enterprise response: {response2}")

if __name__ == "__main__":
    asyncio.run(main())
