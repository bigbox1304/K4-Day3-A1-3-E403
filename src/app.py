"""
🚀 CORE AGENT APP (Dành cho Role 4: Core Agent Developer)
File chính ghép nối tất cả các thành phần: Tools + Prompts + Test Cases + Multi-Provider.
"""

import json
import os
import sys
from dotenv import load_dotenv

# Đảm bảo import các module cùng thư mục src/ hoạt động mượt mà
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import các thành phần từ file của Role 2, Role 3 & Multi-Provider Adapter
from tools import (
    AVAILABLE_TOOLS,
    search_courses,
    get_course_details,
    get_student_progress,
    check_prerequisites,
    check_schedule_conflicts,
)
from prompts import CHATBOT_BASELINE_PROMPT, REACT_SYSTEM_PROMPT, MAX_ITERATIONS
from providers import get_llm_provider

load_dotenv()

def load_test_cases():
    """Đọc bộ test cases từ config/test_cases.json của Role 1"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")
    
    # Fallback kiểm tra nếu file ở thư mục hiện tại
    if not os.path.exists(config_path):
        config_path = "test_cases.json"
        
    with open(config_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def run_baseline_chatbot(target, provider):
    """
    Dựng Chatbot gốc (Baseline) không có công cụ.
    - Nối với `prompts.py` qua `CHATBOT_BASELINE_PROMPT`
    - Nối với `tools.py` (Khai báo trạng thái 0 Tool Calls, hiển thị danh sách công cụ có sẵn từ tools.py nhưng không kích hoạt)
    - Chạy mượt mà với bộ `config/test_cases.json` (dạng list, dict hoặc query string)
    """
    available_tools_list = list(AVAILABLE_TOOLS.keys())
    print("\n==================================================")
    print("💬 [CHATBOT BASELINE] KHỞI CHẠY CHẾ ĐỘ BASELINE THUẦN LLM")
    print(f"⚙️ System Prompt (từ prompts.py):\n{CHATBOT_BASELINE_PROMPT.strip()}")
    print(f"🛠️ Tool Status (từ tools.py): 0 Tool Calls (Có {len(available_tools_list)} tools sẵn có: {', '.join(available_tools_list)} - Không được phép gọi ở Baseline)")
    print("==================================================\n")

    # Nếu truyền vào danh sách toàn bộ test cases từ config/test_cases.json
    if isinstance(target, list):
        print(f"🚀 [CONFIG/TEST_CASES.JSON] Đang thực thi toàn bộ {len(target)} Test Cases:\n")
        for idx, item in enumerate(target, 1):
            if isinstance(item, dict):
                qid = item.get("id", idx)
                category = item.get("category", "N/A")
                question = item.get("question", "")
                expected = item.get("expected_behavior", "")
            else:
                qid = idx
                category = "General"
                question = str(item)
                expected = ""

            print(f"--------------------------------------------------")
            print(f"📌 [Test Case #{qid}] - Phân loại: {category}")
            print(f"❓ Câu hỏi: {question}")
            if expected:
                print(f"🎯 Hành vi kỳ vọng: {expected}")
            
            response = provider.generate(question, system_prompt=CHATBOT_BASELINE_PROMPT)
            print(f"🤖 Chatbot Baseline trả lời:\n{response}\n")

    # Nếu truyền vào 1 dict của 1 test case cụ thể
    elif isinstance(target, dict):
        qid = target.get("id", 1)
        category = target.get("category", "N/A")
        question = target.get("question", "")
        expected = target.get("expected_behavior", "")

        print(f"📌 [Test Case #{qid}] - Phân loại: {category}")
        print(f"❓ Câu hỏi: {question}")
        if expected:
            print(f"🎯 Hành vi kỳ vọng: {expected}")
        
        response = provider.generate(question, system_prompt=CHATBOT_BASELINE_PROMPT)
        print(f"🤖 Chatbot Baseline trả lời:\n{response}\n")

    # Nếu truyền vào chuỗi câu hỏi (str)
    else:
        question = str(target)
        print(f"❓ Câu hỏi: {question}")
        response = provider.generate(question, system_prompt=CHATBOT_BASELINE_PROMPT)
        print(f"🤖 Chatbot Baseline trả lời:\n{response}\n")


def run_react_agent(user_query, provider):
    """
    Dựng vòng lặp ReAct Agent (Thought -> Action -> Observation) có Guardrails.
    Nối với `prompts.py` (REACT_SYSTEM_PROMPT, MAX_ITERATIONS, SAFE_FALLBACK_MESSAGE)
    Nối với `tools.py` (AVAILABLE_TOOLS)
    Chạy mượt mà với bộ `config/test_cases.json` (dạng list, dict hoặc query string)
    """
    import re
    from prompts import SAFE_FALLBACK_MESSAGE

    def _execute_single(target_query, category="General", qid="1", expected=""):
        print(f"\n==================================================")
        print(f"🤖 [REACT AGENT] - Test Case #{qid} (Phân loại: {category})")
        print(f"❓ Câu hỏi: {target_query}")
        if expected:
            print(f"🎯 Hành vi kỳ vọng: {expected}")
        print("==================================================")

        history = f"Question: {target_query}"
        step = 0
        final_answered = False

        while step < MAX_ITERATIONS:
            step += 1
            print(f"\n--- 🔄 Vòng lặp ReAct (Step {step}/{MAX_ITERATIONS}) ---")
            
            response = provider.generate(history, system_prompt=REACT_SYSTEM_PROMPT)
            print(f"🤖 Agent Response:\n{response}")

            if "Final Answer:" in response:
                final_answered = True
                break

            action_match = re.search(r"Action:\s*([a-zA-Z0-9_]+)\s*([\[\(\{].*?[\}\)\]])", response, re.DOTALL)
            if not action_match:
                action_match = re.search(r"Action:\s*([a-zA-Z0-9_]+)", response)
                tool_name = action_match.group(1).strip() if action_match else None
                raw_args = ""
            else:
                tool_name = action_match.group(1).strip()
                raw_args = action_match.group(2).strip()

            if tool_name:
                if tool_name in AVAILABLE_TOOLS:
                    tool_func = AVAILABLE_TOOLS[tool_name]
                    parsed = None
                    if raw_args:
                        try:
                            parsed = json.loads(raw_args)
                        except Exception:
                            inner = raw_args.strip("[](){}")
                            try:
                                parsed = json.loads(inner)
                            except Exception:
                                parsed = inner.strip("'\"")

                    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], (dict, str)):
                        parsed = parsed[0]

                    try:
                        if isinstance(parsed, dict):
                            obs = tool_func(**parsed)
                        elif isinstance(parsed, list):
                            obs = tool_func(parsed)
                        elif isinstance(parsed, str) and parsed:
                            obs = tool_func(parsed)
                        elif parsed is None:
                            obs = tool_func()
                        else:
                            obs = tool_func(parsed)
                    except Exception as e:
                        obs = json.dumps({"ok": False, "error": f"Lỗi tham số khi gọi tool '{tool_name}': {str(e)}"}, ensure_ascii=False)
                else:
                    obs = json.dumps({
                        "ok": False,
                        "error": f"Tool '{tool_name}' không tồn tại.",
                        "available_tools": list(AVAILABLE_TOOLS.keys())
                    }, ensure_ascii=False)

                print(f"👁️ Observation: {obs}")
                history += f"\n{response}\nObservation: {obs}\n"
            else:
                history += f"\n{response}\n"

        if not final_answered:
            print(f"\n🛡️ GUARDRAIL TRIGGERED: Đã đạt giới hạn tối đa {MAX_ITERATIONS} bước. Ngắt lặp an toàn!")
            print(f"🏁 Final Answer: {SAFE_FALLBACK_MESSAGE}")

    if isinstance(user_query, list):
        print(f"🚀 [CONFIG/TEST_CASES.JSON] Đang thực thi ReAct Agent trên toàn bộ {len(user_query)} Test Cases:\n")
        for idx, item in enumerate(user_query, 1):
            if isinstance(item, dict):
                _execute_single(
                    target_query=item.get("question", ""),
                    category=item.get("category", "N/A"),
                    qid=item.get("id", idx),
                    expected=item.get("expected_behavior", "")
                )
            else:
                _execute_single(target_query=str(item), qid=idx)
    elif isinstance(user_query, dict):
        _execute_single(
            target_query=user_query.get("question", ""),
            category=user_query.get("category", "N/A"),
            qid=user_query.get("id", 1),
            expected=user_query.get("expected_behavior", "")
        )
    else:
        _execute_single(target_query=str(user_query))


if __name__ == "__main__":
    print("==================================================")
    print("🏫 ĐẠI HỌC VINUNI - BÀI LAB 3: CHATBOT VS REACT AGENT")
    print("==================================================")
    
    # Khởi tạo Multi-Provider LLM Adapter (Đọc từ biến môi trường LLM_PROVIDER)
    provider = get_llm_provider()
    model_name = getattr(provider, "model_name", "Offline Mock Mode")
    print(f"🔌 LLM Provider đang hoạt động: {provider.__class__.__name__} (Model: {model_name})")
    
    tests = load_test_cases()
    print(f"✅ Đã tải thành công {len(tests)} Test Cases từ config/test_cases.json\n")
    
    print("--- DEMO 1: CHẠY BỘ TEST_CASES.JSON TRÊN CHATBOT BASELINE ---")
    #run_baseline_chatbot(tests, provider)
    
    print("\n--- DEMO 2: CHẠY THỬ REACT AGENT CỦA TEST CASE #3 ---")
    sample_query = tests[2]["question"]
    run_react_agent(sample_query, provider)

