import requests
from dotenv import dotenv_values

# 企业微信消息推送配置说明
# https://developer.work.weixin.qq.com/document/path/91770

KEY = dotenv_values().get("Work_Weixin_KEY")
URL = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={KEY}"


def message(msg):
    # 要发送的消息内容
    payload = {
        "msgtype": "markdown",
        "markdown": {"content": f"{msg}"},
    }

    # 发送 POST 请求，json 参数会自动设置 Content-Type 并序列化字典
    response = requests.post(URL, json=payload)

    return response


if __name__ == "__main__":
    r = message("ping")

    # 输出响应状态码和返回的 JSON 数据
    print("状态码:", r.status_code)
    print("响应内容:", r.json())
