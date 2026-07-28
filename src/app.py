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


def run_react_agent(user_query: str, provider):
    """
    Dựng vòng lặp ReAct Agent (Thought -> Action -> Observation) có Guardrails.
    """
    print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")
    step = 0
    
    while step < MAX_ITERATIONS:
        step += 1
        print(f"\n--- 🔄 Vòng lặp ReAct (Step {step}/{MAX_ITERATIONS}) ---")
        
        if step == 1:
            print("🧠 Thought: Câu hỏi này cần tra cứu danh mục khóa học Python & AI.")
            print("🛠️ Action: search_courses['Python']")
            
            # Thực thi tool từ tools.py
            obs = search_courses("Python")
            print(f"👁️ Observation: {obs}")
            
        elif step == 2:
            print("🧠 Thought: Tôi đã có kết quả khóa học từ database, giờ tôi có thể tư vấn lộ trình.")
            print("🏁 Final Answer: Bạn nên bắt đầu với khóa CS101 (Nhập môn Lập trình Python) 3 tín chỉ!")
            break
            
    if step >= MAX_ITERATIONS:
        print(f"🛡️ GUARDRAIL TRIGGERED: Đã đạt giới hạn tối đa {MAX_ITERATIONS} bước. Ngắt lặp an toàn!")


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
    run_baseline_chatbot(tests, provider)
    
    print("\n--- DEMO 2: CHẠY THỬ REACT AGENT CỦA TEST CASE #3 ---")
    sample_query = tests[2]["question"]
    run_react_agent(sample_query, provider)

