#!/usr/bin/env python3

import os
import time

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

load_dotenv()
MODEL = {
    "glm": {
        "model": "glm-5.1",
        "api_key": os.getenv("ZAI_API_KEY"),
        "url": "https://open.bigmodel.cn/api/coding/paas/v4/",
        "extra_body": {
            # 深度思考，默认开启。
            "thinking": {
                "type": "enabled",
            },
        },
    },
    "deepseek": {
        "model": "deepseek-ai/deepseek-v3.2",
        "api_key": os.getenv("NVIDIA_KEY"),
        "url": "https://integrate.api.nvidia.com/v1",
        "extra_body": {
            "chat_template_kwargs": {
                # 开启“思考过程”（reasoning）输出
                "thinking": True
            }
        },
    },
}


class AI:
    def __init__(self, model="glm", max_retries=3):
        self.model_key = model
        config = MODEL[model]

        self.model = config["model"]
        self.api_key = config["api_key"]
        self.url = config["url"]
        self.extra_body = config["extra_body"]

        self.max_retries = max_retries  # 最大重试次数

        # 创建客户端
        self.client = OpenAI(api_key=self.api_key, base_url=self.url)

    def chat(self, msg):
        for attempt in range(self.max_retries):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一个有用的AI助手。"},
                        {"role": "user", "content": msg},
                    ],
                    # temperature 默认为 1.0, top_p 默认为 0.95, 不建议同时调整两者。
                    temperature=0.5,  # 控制随机性；数值更高更发散，数值更低更稳定。
                    top_p=0.95,  # 控制核采样；更高值扩大候选集，更低值收敛候选集。
                    stream=False,  # 开启响应的流式输出。
                    extra_body=self.extra_body,  # 额外参数
                )

                return completion.choices[0].message.content
            except RateLimitError as e:
                # 命中限流
                if attempt < self.max_retries - 1:
                    print(
                        f"[重试] 请求被限流，3秒后重试... ({attempt + 1}/{self.max_retries})"
                    )
                    time.sleep(5)
                else:
                    return str(e)

            except Exception as e:
                # 其他错误直接抛（避免误重试）
                return str(e)


if __name__ == "__main__":
    from datetime import datetime

    text = """在一个黑色的袋子里放有三种口味的糖果，每种糖果有两种不同的形状。
（圆形和五角星形，不同的形状靠手感可以分辨）
现已知不同口味的糖和不同形状的数量统计如下表。
苹果味|桃子味|西瓜味
圆形|7|9|8
五角星形|7|6|4
参赛者需要在活动前决定摸出的糖果数目。
那么，最少取出多少个糖果才能保证手中同时拥有不同形状的苹果味和桃子味的糖？
（同时手中有圆形苹果味匹配五角星桃子味糖果，或者有圆形桃子味匹配五角星苹果味糖果都满足要求）
"""

    start = time.time()
    bigmodel = AI()
    # 选择其他模型
    # bigmodel.model = "glm-4.7-flash"

    content = bigmodel.chat(text)
    print(content)

    end = time.time()
    elapsed = end - start

    print("-" * 30)
    print("开始时间:", datetime.fromtimestamp(start).strftime("%H:%M:%S"))
    print("结束时间:", datetime.fromtimestamp(end).strftime("%H:%M:%S"))
    print(f"耗时: {elapsed:.3f} 秒")
