"""
MCP 功能测试脚本
通过 stdio 连接 MCP 服务器，测试 list_tools 和 call_tool
"""
import asyncio
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters


async def test():
    params = StdioServerParameters(
        command='python3',
        args=['mcp/server.py'],
        env={'BACKEND_API_URL': 'http://127.0.0.1:8000'}
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. 获取工具列表
            tools = await session.list_tools()
            print('=== 工具列表 ===')
            for t in tools.tools:
                print(f'  {t.name}: {t.description}')

            # 2. 调用 sys_check
            print('\n=== 调用 sys_check ===')
            result = await session.call_tool('sys_check', {})
            for c in result.content:
                print(c.text)

            # 3. 调用 get_time
            print('\n=== 调用 get_time ===')
            result = await session.call_tool('get_time', {})
            for c in result.content:
                print(c.text)


if __name__ == '__main__':
    asyncio.run(test())
