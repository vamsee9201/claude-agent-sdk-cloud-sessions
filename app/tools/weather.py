from claude_agent_sdk import tool, create_sdk_mcp_server


@tool("get_weather", "Get current weather for a city", {"city": str})
async def get_weather(args):
    city = args["city"]
    return {
        "content": [
            {"type": "text", "text": f"Weather in {city}: 72°F, Sunny, Humidity: 45%"}
        ]
    }


weather_server = create_sdk_mcp_server(
    name="weather",
    version="1.0.0",
    tools=[get_weather],
)
