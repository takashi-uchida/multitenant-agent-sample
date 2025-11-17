import asyncio
from agentcore_agent import AgentCoreIntegratedAgent
from agentcore_gateway_config import AgentCoreGatewayConfig
from tenant_aware_agent import AgentConfig
from tenant_context import TenantContext

async def main():
    # Gateway設定
    gateway_config = AgentCoreGatewayConfig()
    
    # Lambda関数をツールとして登録
    gateway_config.register_lambda_tool(
        "crm_search",
        "arn:aws:lambda:us-east-1:123456789012:function:crm-search",
        {
            "enterprise-corp": "arn:aws:iam::123456789012:role/enterprise-crm-role",
            "startup-inc": "arn:aws:iam::123456789012:role/startup-basic-role"
        }
    )
    
    # REST APIをツールとして登録
    gateway_config.register_api_tool(
        "github_search",
        "https://api.github.com/search/repositories",
        {"service": "github"}
    )
    
    # エージェント初期化
    agent = AgentCoreIntegratedAgent(gateway_config)
    
    # エージェント設定
    agent.register_default_agent("assistant", AgentConfig(
        name="assistant",
        prompt_template="Tenant {tenant_id}: {user_message}\nTool results: {tool_results}",
        model="claude-3-haiku",
        tools=["crm_search", "github_search"]
    ))
    
    # テナントコンテキスト
    enterprise_context = TenantContext(
        "enterprise-corp", "user1", ["claude-3-sonnet"], "session1"
    )
    startup_context = TenantContext(
        "startup-inc", "user2", ["claude-3-haiku"], "session2"
    )
    
    # 実行
    enterprise_response = await agent.invoke_with_tools(
        enterprise_context, "assistant", "Find CRM data", ["crm_search"]
    )
    
    startup_response = await agent.invoke_with_tools(
        startup_context, "assistant", "Search GitHub", ["github_search"]
    )
    
    print(f"Enterprise: {enterprise_response}")
    print(f"Startup: {startup_response}")

if __name__ == "__main__":
    asyncio.run(main())
