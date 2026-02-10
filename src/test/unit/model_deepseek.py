import sys
import os
from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件
# 注意：因为测试文件在多层目录下，我们可以指定路径或者依靠默认寻找逻辑
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))

# 将项目根目录添加到 sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.model import DeepSeekModel

def test_chat():
    try:
        model = DeepSeekModel()
        result = model.chat("你好，请简短介绍一下你自己。")
        print("Model Response:")
        print(result)
    except Exception as e:
        print(f"Error: {e}")

def test_stream_chat():
    try:
        model = DeepSeekModel()
        result = model.stream_chat("你好，请简短介绍一下你自己。")
        print("Model Response:")
        for chunk in result:
            print(chunk, end="", flush=True)
    except Exception as e:
        print(f"Error: {e}")

def test_tool_call():
    try:
        model = DeepSeekModel()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the weather in a given location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "The location to get the weather for"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        ]
        result = model.chat("北京现在的天气怎么样？", tools=tools)
        print("Model Response:")
        print(result)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # test_chat()
    # test_stream_chat()
    test_tool_call()
