"""Core app của Role 4: ghép provider, prompt, tool và ReAct loop."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

from dotenv import load_dotenv

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from prompts import (  # noqa: E402
    CHATBOT_BASELINE_PROMPT,
    MAX_ITERATIONS,
    REACT_SYSTEM_PROMPT,
    SAFE_FALLBACK_MESSAGE,
)
from providers import get_llm_provider  # noqa: E402
from tools import AVAILABLE_TOOLS  # noqa: E402

load_dotenv(os.path.join(PROJECT_DIR, ".env"))

FINAL_PATTERN = re.compile(r"Final Answer:\s*(.+)", re.IGNORECASE | re.DOTALL)
ACTION_PATTERN = re.compile(
    r"Action:\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(\[[\s\S]*\]|\{[\s\S]*\}|\([\s\S]*\))?\s*$",
    re.IGNORECASE,
)
PROVIDER_ERROR_PATTERN = re.compile(
    r"^\[(?:Gemini|OpenAI|Anthropic|OpenRouter)(?: API)? (?:Error|Exception)(?: [^]]+)?\]:",
    re.IGNORECASE,
)


def load_test_cases() -> list[dict[str, Any]]:
    """Đọc và kiểm tra tối thiểu bộ test case của Role 1."""
    config_path = os.path.join(PROJECT_DIR, "config", "test_cases.json")
    with open(config_path, "r", encoding="utf-8-sig") as file:
        test_cases = json.load(file)
    if not isinstance(test_cases, list):
        raise ValueError("config/test_cases.json phải chứa một JSON array")
    return test_cases


def _normalise_cases(target: Any) -> list[dict[str, Any]]:
    """Chuẩn hóa str/dict/list về cùng một cấu trúc để hai chế độ dùng chung."""
    items = target if isinstance(target, list) else [target]
    cases: list[dict[str, Any]] = []
    for index, item in enumerate(items, 1):
        if isinstance(item, dict):
            cases.append(
                {
                    "id": item.get("id", index),
                    "category": item.get("category", "General"),
                    "question": str(item.get("question", "")).strip(),
                    "expected_behavior": item.get("expected_behavior", ""),
                }
            )
        else:
            cases.append(
                {
                    "id": index,
                    "category": "General",
                    "question": str(item).strip(),
                    "expected_behavior": "",
                }
            )
    return cases


def _provider_error(response: Any) -> str | None:
    """Nhận diện lỗi adapter để không đưa lỗi hạ tầng vào ReAct history."""
    if not isinstance(response, str) or not response.strip():
        return "Provider không trả về nội dung."
    text = response.strip()
    return text if PROVIDER_ERROR_PATTERN.match(text) else None


def _parse_action(response: str) -> tuple[str | None, Any, str | None]:
    """Parse một Action; lỗi cú pháp được trả thành dữ liệu recovery, không raise."""
    match = ACTION_PATTERN.search(response.strip())
    if not match:
        return None, None, "Phản hồi phải chứa 'Action:' hoặc 'Final Answer:'."

    tool_name = match.group(1)
    raw_args = (match.group(2) or "").strip()
    if not raw_args:
        return tool_name, None, "Action thiếu đối số JSON."

    candidate = raw_args
    if candidate.startswith("(") and candidate.endswith(")"):
        candidate = candidate[1:-1].strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return tool_name, None, f"Đối số Action không phải JSON hợp lệ: {exc.msg}."

    # Prompt chuẩn dùng tool[{...}], nên bỏ đúng một lớp list bao ngoài.
    if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
        parsed = parsed[0]
    return tool_name, parsed, None


def _execute_tool(tool_name: str, arguments: Any) -> str:
    """Thực thi đúng một tool và luôn trả đúng một Observation dạng chuỗi."""
    tool = AVAILABLE_TOOLS.get(tool_name)
    if tool is None:
        return json.dumps(
            {
                "ok": False,
                "error": f"Tool '{tool_name}' không tồn tại.",
                "available_tools": sorted(AVAILABLE_TOOLS),
                "recoverable": True,
            },
            ensure_ascii=False,
        )
    try:
        if isinstance(arguments, dict):
            return tool(**arguments)
        if isinstance(arguments, list):
            return tool(arguments)
        if arguments is None:
            return tool()
        return tool(arguments)
    except Exception as exc:
        return json.dumps(
            {
                "ok": False,
                "error": f"Tham số không phù hợp với tool '{tool_name}': {exc}",
                "recoverable": True,
            },
            ensure_ascii=False,
        )


def run_baseline_chatbot(target: Any, provider: Any) -> list[dict[str, Any]]:
    """Chạy đúng một LLM call và không gọi tool cho mỗi test case."""
    results: list[dict[str, Any]] = []
    print("\n💬 [CHATBOT BASELINE] 1 LLM call/case, 0 tool calls")
    for case in _normalise_cases(target):
        print(f"\n📌 Test Case #{case['id']} — {case['category']}")
        print(f"❓ {case['question']}")
        response = provider.generate(
            case["question"], system_prompt=CHATBOT_BASELINE_PROMPT
        )
        error = _provider_error(response)
        answer = error or response.strip()
        status = "provider_error" if error else "completed"
        print(f"🤖 {answer}")
        results.append({**case, "status": status, "answer": answer, "tool_calls": 0})
    return results


def _run_react_case(case: dict[str, Any], provider: Any) -> dict[str, Any]:
    """Chạy state machine ReAct V2 cho một câu hỏi."""
    print(f"\n🤖 [REACT AGENT] Test Case #{case['id']} — {case['category']}")
    print(f"❓ {case['question']}")
    history = f"Question: {case['question']}"
    trace: list[dict[str, Any]] = []
    seen_actions: set[str] = set()

    for step in range(1, MAX_ITERATIONS + 1):
        print(f"\n--- Step {step}/{MAX_ITERATIONS} ---")
        response = provider.generate(history, system_prompt=REACT_SYSTEM_PROMPT)
        error = _provider_error(response)
        if error:
            answer = f"Không thể kết nối dịch vụ AI. Chi tiết: {error}"
            print(f"⚠️ {answer}")
            return {**case, "status": "provider_error", "answer": answer, "trace": trace}

        response = response.strip()
        final_match = FINAL_PATTERN.search(response)
        if final_match:
            raw_answer = final_match.group(1).strip()
            answer = re.sub(
                r"^(?:Final\s*Answer:\s*)+", "", raw_answer, flags=re.IGNORECASE
            ).strip()
            thought_part = response[:final_match.start()].strip()
            if thought_part:
                print(thought_part)
            trace.append({"step": step, "response": response, "type": "final"})
            print(f"🏁 Final Answer: {answer}")
            return {**case, "status": "completed", "answer": answer, "trace": trace}

        print(response)

        tool_name, arguments, parse_error = _parse_action(response)
        if parse_error:
            observation = json.dumps(
                {"ok": False, "error": parse_error, "recoverable": True},
                ensure_ascii=False,
            )
        else:
            action_key = json.dumps(
                [tool_name, arguments], ensure_ascii=False, sort_keys=True
            )
            if action_key in seen_actions:
                observation = json.dumps(
                    {
                        "ok": False,
                        "error": "Action này đã được gọi với cùng tham số.",
                        "recoverable": True,
                    },
                    ensure_ascii=False,
                )
            else:
                seen_actions.add(action_key)
                observation = _execute_tool(tool_name or "", arguments)

        # Một lượt không-final luôn sinh đúng một Observation và đưa lại vào prompt.
        print(f"👁️ Observation: {observation}")
        trace.append(
            {
                "step": step,
                "response": response,
                "tool": tool_name,
                "arguments": arguments,
                "observation": observation,
            }
        )
        history += f"\n{response}\nObservation: {observation}"

    print(f"🛡️ Guardrail MAX_ITERATIONS={MAX_ITERATIONS} đã dừng vòng lặp.")
    print(f"🏁 Final Answer: {SAFE_FALLBACK_MESSAGE}")
    return {
        **case,
        "status": "guardrail",
        "answer": SAFE_FALLBACK_MESSAGE,
        "trace": trace,
    }


def run_react_agent(user_query: Any, provider: Any) -> Any:
    """Chạy ReAct cho str/dict/list và trả kết quả để UI/module khác sử dụng."""
    cases = _normalise_cases(user_query)
    results = [_run_react_case(case, provider) for case in cases]
    return results if isinstance(user_query, list) else results[0]


def _select_cases(cases: list[dict[str, Any]], case_id: int | None) -> Any:
    if case_id is None:
        return cases
    for case in cases:
        if case.get("id") == case_id:
            return case
    raise ValueError(f"Không tìm thấy test case #{case_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chatbot baseline và ReAct Agent")
    parser.add_argument("--mode", choices=("baseline", "react", "both"), default="react")
    parser.add_argument("--case", type=int, help="ID test case; bỏ trống để chạy cả bộ")
    parser.add_argument("--query", help="Chạy trực tiếp một câu hỏi thay cho test case")
    args = parser.parse_args()

    provider = get_llm_provider()
    model = getattr(provider, "model_name", "offline mock")
    print("🏫 LAB 3 — CHATBOT VS REACT AGENT")
    print(f"🔌 Provider: {provider.__class__.__name__} ({model})")

    target = args.query if args.query is not None else _select_cases(load_test_cases(), args.case)
    if args.mode in ("baseline", "both"):
        run_baseline_chatbot(target, provider)
    if args.mode in ("react", "both"):
        run_react_agent(target, provider)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
