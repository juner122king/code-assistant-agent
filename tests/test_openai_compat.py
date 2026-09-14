"""OpenAI 兼容层：tool/message 转换与客户端工厂。"""

from app.config import Settings
from app.llm.claude_client import ClaudeClient
from app.llm.factory import get_llm_client
from app.llm.openai_client import OpenAIClient
from app.llm.openai_compat import (
    anthropic_messages_to_openai,
    anthropic_tools_to_openai,
    openai_response_to_anthropic,
)


def test_tools_schema_conversion():
    tools = [
        {
            "name": "read_file",
            "description": "Read a file",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        }
    ]
    out = anthropic_tools_to_openai(tools)
    assert out[0]["type"] == "function"
    assert out[0]["function"]["name"] == "read_file"
    assert out[0]["function"]["parameters"]["required"] == ["path"]


def test_roundtrip_tool_use_and_result():
    messages = [
        {"role": "user", "content": "分析仓库"},
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "先看目录"},
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "list_directory_tree",
                    "input": {"path": "."},
                },
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_1",
                    "content": "src/\nREADME.md",
                }
            ],
        },
    ]
    converted = anthropic_messages_to_openai(messages, system="you are an agent")
    assert converted[0] == {"role": "system", "content": "you are an agent"}
    assert converted[1]["role"] == "user"
    assert converted[2]["role"] == "assistant"
    assert converted[2]["tool_calls"][0]["function"]["arguments"] == '{"path": "."}'
    assert converted[3] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": "src/\nREADME.md",
    }


def test_openai_tool_calls_become_tool_use():
    data = {
        "choices": [
            {
                "finish_reason": "tool_calls",
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_9",
                            "type": "function",
                            "function": {
                                "name": "read_file",
                                "arguments": '{"path": "src/app.py"}',
                            },
                        }
                    ],
                },
            }
        ]
    }
    msg = openai_response_to_anthropic(data)
    assert msg.stop_reason == "tool_use"
    assert msg.content[0]["type"] == "tool_use"
    assert msg.content[0]["name"] == "read_file"
    assert msg.content[0]["input"] == {"path": "src/app.py"}


def test_openai_stop_becomes_end_turn():
    data = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": '{"structure": {}}'},
            }
        ]
    }
    msg = openai_response_to_anthropic(data)
    assert msg.stop_reason == "end_turn"
    assert msg.content[0]["text"] == '{"structure": {}}'


def test_factory_openai_vs_anthropic():
    openai_settings = Settings(
        llm_provider="openai",
        llm_api_key="sk-test",
        llm_model="Qwen/Qwen3-8B",
        llm_base_url="https://api.siliconflow.cn/v1",
    )
    assert openai_settings.resolved_provider == "openai"
    client = get_llm_client(openai_settings)
    assert isinstance(client, OpenAIClient)
    assert client.model == "Qwen/Qwen3-8B"

    anthropic_settings = Settings(
        llm_provider="anthropic",
        anthropic_api_key="x",
        anthropic_model="grok-4.5",
    )
    assert anthropic_settings.resolved_provider == "anthropic"
    client = get_llm_client(anthropic_settings)
    assert isinstance(client, ClaudeClient)
    assert client.model == "grok-4.5"


def test_default_model_when_openai_model_blank():
    settings = Settings(llm_provider="openai", llm_api_key="sk-test")
    assert settings.resolved_model == "Qwen/Qwen3-8B"
    assert settings.resolved_base_url == "https://api.siliconflow.cn/v1"
