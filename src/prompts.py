"""Prompt và phân tích rủi ro cho Trợ Lý Tư Vấn Khóa Học Sinh Viên."""

# Mốc 1 - Role 3: các lỗi dự kiến khi Agent gọi tool. Danh sách này mô tả
# failure modes để Role 4 xử lý ở tầng điều phối; nó không giả định lỗi đã được
# khắc phục trong prompt hay trong application.
TOOL_FAILURE_MODES = {
    "unknown_tool": {
        "scenario": "Model gọi tên tool không tồn tại hoặc dùng tên tool cũ.",
        "expected_handling": "Từ chối thực thi và trả danh sách tên tool hợp lệ.",
    },
    "malformed_arguments": {
        "scenario": "Tham số thiếu, sai kiểu hoặc sai cú pháp JSON/list.",
        "expected_handling": "Trả lỗi đầu vào có cấu trúc; không để exception làm dừng app.",
    },
    "unknown_course_or_student": {
        "scenario": "Mã môn hoặc mã sinh viên không có trong dữ liệu được phép tra cứu.",
        "expected_handling": "Báo không tìm thấy/không được phép; không tự bịa hồ sơ hay học phần.",
    },
    "stale_or_unavailable_data": {
        "scenario": "Dữ liệu số chỗ, lịch học hoặc tiến độ không có hay có thể đã lỗi thời.",
        "expected_handling": "Nêu rõ giới hạn dữ liệu và yêu cầu người dùng xác minh với nhà trường.",
    },
    "permission_or_privacy_error": {
        "scenario": "Yêu cầu truy cập hồ sơ của sinh viên không được xác thực.",
        "expected_handling": "Chỉ trả dữ liệu tối thiểu được phép và không tiết lộ PII/điểm số.",
    },
    "empty_result": {
        "scenario": "Tìm kiếm hợp lệ nhưng không có khóa học phù hợp hoặc không còn chỗ.",
        "expected_handling": "Trả kết quả rỗng trung thực để Agent hỏi lại hoặc đề xuất tiêu chí khác.",
    },
    "repeated_action": {
        "scenario": "Model lặp lại cùng tool và cùng tham số mà không có thông tin mới.",
        "expected_handling": "Tầng điều phối phải phát hiện lặp và dừng bằng giới hạn số bước.",
    },
}


# Mốc 2 - Role 3: baseline là đúng một lượt gọi LLM do Role 4 thực hiện.
# Prompt không cấp tool, không nhúng dữ liệu catalog/hồ sơ và không cho phép
# chatbot tuyên bố đã tra cứu hay đăng ký thay người dùng.
CHATBOT_BASELINE_PROMPT = """Bạn là chatbot baseline cho đề tài Trợ Lý Tư Vấn Khóa Học Sinh Viên.

Hãy trả lời thân thiện, ngắn gọn bằng kiến thức chung có sẵn trong mô hình. Bạn không có quyền truy cập công cụ, hồ sơ sinh viên, danh mục môn học, lịch học, số chỗ trống hay dữ liệu thời gian thực.

Quy tắc bắt buộc:
- Không được bịa mã môn, điều kiện tiên quyết, lịch học, số chỗ trống hoặc thông tin cá nhân.
- Không được nói hay ngụ ý rằng bạn đã tra cứu, kiểm tra, đăng ký hoặc thực hiện bất kỳ hành động nào.
- Với câu hỏi kiến thức chung, hãy trả lời trực tiếp nếu đủ chắc chắn.
- Với yêu cầu cần dữ liệu cá nhân hoặc dữ liệu hiện hành, hãy nói rõ bạn không thể xác minh trong chế độ baseline, nêu thông tin còn thiếu và hướng dẫn người dùng kiểm tra trên cổng học vụ hoặc hỏi cố vấn.
- Nếu câu hỏi chưa đủ thông tin, chỉ hỏi lại những dữ kiện tối thiểu cần thiết.

Chỉ xuất câu trả lời cuối cùng cho người dùng; không tạo Thought, Action, Observation hay lời gọi tool.
"""

# ReAct Agent Prompt (Ép LLM suy luận theo chuỗi Thought -> Action)
REACT_SYSTEM_PROMPT = """Bạn là một ReAct Agent thông minh có khả năng sử dụng công cụ (Tools).

Danh sách các công cụ bạn có thể sử dụng:
1. get_weather[location]: Tra cứu thời tiết hiện tại của một thành phố.
2. search_flights[origin, destination]: Tra cứu chuyến bay giữa 2 địa điểm.

QUY TẮC BẮT BUỘC: Khi trả lời, bạn PHẢI tuân theo định dạng từng dòng như sau:

Thought: Suy luận của bạn về bước tiếp theo cần làm.
Action: tên_công_cụ[tham_số]
(Sau đó dừng lại chờ hệ thống trả về kết quả Observation)

Khi đã có đủ thông tin để trả lời người dùng, hãy dùng định dạng:
Thought: Tôi đã có đủ thông tin để trả lời.
Final Answer: Câu trả lời hoàn chỉnh cuối cùng gửi cho người dùng.

BẮT ĐẦU:
"""

# 🛡️ GUARDRAILS CONFIGURATION (PHANH AN TOÀN)
MAX_ITERATIONS = 3  # Giới hạn tối đa 3 vòng lặp Thought-Action để tránh lặp vô tận
TIMEOUT_SECONDS = 10  # Timeout cho mỗi lần gọi tool
