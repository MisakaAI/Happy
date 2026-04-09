#!/usr/bin/env python3

import os

from dotenv import load_dotenv
from openai import OpenAI

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


def bigmodel(msg, model="glm"):

    API_KEY = MODEL[model]["api_key"]
    URL = MODEL[model]["url"]
    EXTRA_BODY = MODEL[model]["extra_body"]

    # 创建客户端
    client = OpenAI(api_key=API_KEY, base_url=URL)
    completion = client.chat.completions.create(
        model=MODEL[model]["model"],
        messages=[
            {"role": "system", "content": "你是一个有用的AI助手。"},
            {"role": "user", "content": msg},
        ],
        # temperature 默认为 1.0, top_p 默认为 0.95, 不建议同时调整两者。
        temperature=0.5,  # 控制随机性；数值更高更发散，数值更低更稳定。
        top_p=0.95,  # 控制核采样；更高值扩大候选集，更低值收敛候选集。
        stream=False,  # 开启响应的流式输出。
        extra_body=EXTRA_BODY,  # 额外参数
    )

    return completion.choices[0].message.content


if __name__ == "__main__":
    import time
    from datetime import datetime

    test = """在一个黑色的袋子里放有三种口味的糖果，每种糖果有两种不同的形状。
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
    print(bigmodel(test))
    # print(bigmodel("背出师表", "deepseek"))
    end = time.time()
    elapsed = end - start

    print("-" * 30)
    print("开始时间:", datetime.fromtimestamp(start).strftime("%H:%M:%S"))
    print("结束时间:", datetime.fromtimestamp(end).strftime("%H:%M:%S"))
    print(f"耗时: {elapsed:.3f} 秒")
