import requests
import json

# --- 准备工作 ---

# 1. 定义 Ollama 的 API 地址
OLLAMA_ENDPOINT = "http://localhost:11434/api/chat"

# *** 新增：解决 noproxy 问题的关键 ***
# 告诉 requests 库不要为 http 或 https 请求使用任何代理
# 这会覆盖掉系统环境变量中的 http_proxy/https_proxy
proxies_to_use = {
    "http": None,
    "https": None
}

# 2. 定义我们的“工具说明书” (JSON Schema)
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_country_info",
            "description": "根据一个国家的英文或官方名称，从 restcountries.com API 获取该国的详细信息，如首都、人口、货币等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "country_name": {
                        "type": "string",
                        "description": "要查询的国家的英文名称，例如: Germany, France, Japan"
                    }
                },
                "required": ["country_name"]
            }
        }
    }
]

# 3. 我们的初始问题
user_prompt = "帮我查询一下德国的国家信息，特别是它的首都是哪里？"

# 4. 准备好我们的“双手”（执行器）
def execute_function_call(function_name, arguments):
    """
    一个“执行器”函数，负责映射 AI 的决策到真实的网络请求。
    """
    if function_name == "get_country_info":
        print(f"✋ 正在执行工具：查询 {arguments['country_name']}...")
        try:
            country_name = arguments['country_name']
            api_url = f"https://restcountries.com/v3.1/name/{country_name}"
            
            # *** 修改：在这里也为外部 API 调用添加代理设置 ***
            # 我们假设外部 API (restcountries.com) *需要* 走代理
            # 如果它也不需要代理，也使用 proxies_to_use
            # 如果它需要代理，而你的环境变量是对的，这里就什么都不用加
            # 为简单起见，我们假设外部 API 也不走代理：
            response = requests.get(api_url, proxies=proxies_to_use) 
            
            response.raise_for_status() 
            api_response_json = response.json()
            capital = api_response_json[0].get("capital", [None])[0]
            population = api_response_json[0].get("population", None)
            
            print(f"✅ 工具执行完毕。")
            
            result = {
                "capital": capital,
                "population": population
            }
            return json.dumps(result)
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 工具执行失败: {e}")
            return json.dumps({"error": str(e)})
    else:
        print(f"🤷 AI 决定调用一个我不认识的工具: {function_name}")
        return None

# --- Function Calling 流程开始 ---

def run_function_call_loop():
    
    messages = [
        {
            "role": "user",
            "content": user_prompt
        }
    ]

    # --- 步骤 1: (AI 决策) ---
    print("🤖 正在询问 AI (Ollama)...")
    
    payload = {
        "model": "qwen3:4b",
        "messages": messages,
        "tools": tools,
        "stream": False
    }

    try:
        # *** 修改：在这里添加 proxies=proxies_to_use ***
        response_step1 = requests.post(OLLAMA_ENDPOINT, json=payload, proxies=proxies_to_use)
        
        response_step1.raise_for_status()
        ai_message = response_step1.json().get('message', {})
        messages.append(ai_message)

    except requests.exceptions.ConnectionError:
        print(f"❌ 连接 Ollama 失败 (127.0.0.1:7897?)。请确保 Ollama 服务器正在运行：`ollama serve`")
        return
    except Exception as e:
        print(f"❌ 步骤 1 发生错误: {e}")
        return

    # --- 步骤 2: (脚本执行) ---
    
    if not ai_message.get("tool_calls"):
        print("🧠 AI 决定不使用工具，直接回答:")
        print(ai_message.get('content'))
        return

    print("🧠 AI 决定调用一个工具...")
    
    tool_calls = ai_message.get("tool_calls", [])
    tool_results = []

    for tool_call in tool_calls:
        function_name = tool_call['function']['name']
        arguments = tool_call['function']['arguments'] 
        
        tool_result_content = execute_function_call(function_name, arguments)
        
        if tool_result_content:
            tool_results.append({
                "role": "tool",
                "tool_call_id": tool_call.get('id'),
                "content": tool_result_content
            })

    if not tool_results:
        print("🤷 工具执行失败，无法继续。")
        return

    messages.extend(tool_results)

    # --- 步骤 3: (返回给 AI 响应) ---
    print("🤖 正在将工具结果发回 AI，以生成最终答案...")

    final_payload = {
        "model": "qwen3:4b",
        "messages": messages,
        "stream": False
    }

    try:
        # *** 修改：在这里也添加 proxies=proxies_to_use ***
        response_step3 = requests.post(OLLAMA_ENDPOINT, json=final_payload, proxies=proxies_to_use)
        
        response_step3.raise_for_status()
        final_message = response_step3.json().get('message', {})
        
        print("\n--- 最终答案 ---")
        print(final_message.get('content'))
        
    except Exception as e:
        print(f"❌ 步骤 3 发生错误: {e}")

# --- 运行主函数 ---
if __name__ == "__main__":
    run_function_call_loop()
