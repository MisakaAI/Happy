#!/usr/bin/env python3
# Large Language Model
# 大语言模型调用工具：统一封装 OpenAI 兼容接口，支持多模型切换

from dataclasses import dataclass
from typing import Any

from dotenv import dotenv_values
from openai import OpenAI

# 读取 .env 文件中的环境变量，统一用于获取各模型的 API 密钥
ENV = dotenv_values()


@dataclass(frozen=True)  # frozen=True 使配置实例不可变，避免运行时被误改
class APIConfig:
    """模型 API 配置，各服务均兼容 OpenAI 接口规范。"""

    model: str  # 模型名称
    api_key: str | None  # API 密钥（从环境变量读取）
    base_url: str | None = None  # 服务地址，None 表示使用官方默认地址
    thinking_mode: str = "none"  # openai | glm


# OpenAI 官方模型
GPT = APIConfig(
    model="gpt-5.5",
    api_key=ENV.get("OPENAI_API_KEY"),
    thinking_mode="openai",
)

# 智谱 GLM 模型（通过 OpenAI 兼容接口接入）
GLM = APIConfig(
    model="glm-5.2",
    base_url="https://open.bigmodel.cn/api/coding/paas/v4",
    api_key=ENV.get("ZAI_API_KEY"),
    thinking_mode="glm",
)

# DeepSeek 模型（通过 OpenAI 兼容接口接入）
DEEPSEEK = APIConfig(
    model="deepseek-v4-pro",
    base_url="https://api.deepseek.com",
    api_key=ENV.get("DEEPSEEK_API_KEY"),
    thinking_mode="deepseek",
)

# 系统提示词
SYSTEM_PROMPT = """
你是一个像贾维斯一样的 AI 助手：
- 冷静、专业、礼貌
- 回答简洁准确可靠
- 优先提供可执行方案
- 主动指出潜在问题
- 使用中文回复
- 不进行夸张的角色扮演
""".strip()


def chat(
    content: str,
    api: APIConfig = GLM,
    thinking: bool = True,
) -> str:
    """调用大模型进行单轮对话，返回模型生成的回复文本。

    Args:
        content: 用户输入的提示词。
        api: 使用的模型配置，默认为 GLM。
        thinking: 是否开启思维链推理模式，开启后回复质量更高但耗时更长。

    Returns:
        模型回复内容。
    """

    if not api.api_key:
        raise ValueError(f"Missing API key for model '{api.model}'")

    # 构造客户端参数：仅当配置了自定义服务地址时才传入 base_url
    client_kwargs = {"api_key": api.api_key}

    if api.base_url:
        client_kwargs["base_url"] = api.base_url

    client = OpenAI(**client_kwargs)

    # 构造对话请求参数
    request_kwargs: dict[str, Any] = {
        "model": api.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        "stream": False,
    }

    # 启用推理模式
    if thinking:
        if api.thinking_mode in {"glm", "deepseek"}:
            request_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}

        elif api.thinking_mode == "openai":
            request_kwargs["reasoning"] = {"effort": "high"}

    response = client.chat.completions.create(**request_kwargs)

    # 取出第一条回复的文本内容；末尾 or "" 用于在内容为 None 时兜底返回空字符串
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    # 自测：使用默认模型（GLM）回答一道推理题，并打印回复与耗时
    import time

    text = """在一个黑色的袋子里放有三种口味的糖果，每种糖果有两种不同的形状。
（圆形和五角星形，不同的形状靠手感可以分辨）
现已知不同口味的糖和不同形状的数量统计如下表。
苹果味|桃子味|西瓜味
圆形|7|9|8
五角星形|7|6|4
参赛者需要在活动前决定摸出的糖果数目。
那么，最少取出多少个糖果才能保证手中同时拥有不同形状的苹果味和桃子味的糖？
（同时手中有圆形苹果味匹配五角星桃子味糖果，或者有圆形桃子味匹配五角星苹果味糖果都满足要求）
"""  # 答案应为 21

    start = time.perf_counter()

    print(chat(text))

    elapsed = time.perf_counter() - start

    print("-" * 30)
    if elapsed >= 60:
        print(f"耗时: {int(elapsed // 60)} 分 {elapsed % 60:.3f} 秒")
    else:
        print(f"耗时: {elapsed:.3f} 秒")
