"""
Tool registry cho đề tài 7: Trợ Lý Tư Vấn Khóa Học Sinh Viên.

Các tool chỉ cung cấp dữ liệu/kiểm tra deterministic. Việc tổng hợp bằng chứng và
đưa ra lời khuyên cuối cùng thuộc trách nhiệm của ReAct Agent.
"""

import json
import unicodedata
from functools import wraps
from typing import Any, Callable


COURSE_CATALOG: dict[str, dict[str, Any]] = {
    "CS101": {
        "name": "Nhập môn Lập trình Python",
        "department": "Khoa học máy tính",
        "credits": 3,
        "level": "cơ bản",
        "topics": ["python", "lập trình", "tư duy thuật toán"],
        "prerequisites": [],
        "schedule": [{"day": "Thứ 2", "start": "08:00", "end": "10:00"}],
        "seats_available": 12,
    },
    "CS201": {
        "name": "Cấu trúc Dữ liệu và Giải thuật",
        "department": "Khoa học máy tính",
        "credits": 4,
        "level": "trung cấp",
        "topics": ["cấu trúc dữ liệu", "giải thuật", "python"],
        "prerequisites": ["CS101"],
        "schedule": [{"day": "Thứ 3", "start": "13:00", "end": "15:30"}],
        "seats_available": 5,
    },
    "AI301": {
        "name": "Nhập môn Trí tuệ Nhân tạo",
        "department": "Khoa học máy tính",
        "credits": 3,
        "level": "nâng cao",
        "topics": ["ai", "trí tuệ nhân tạo", "machine learning", "python"],
        "prerequisites": ["CS101", "MATH201"],
        "schedule": [{"day": "Thứ 4", "start": "09:00", "end": "11:00"}],
        "seats_available": 8,
    },
    "DS210": {
        "name": "Phân tích Dữ liệu",
        "department": "Khoa học dữ liệu",
        "credits": 3,
        "level": "trung cấp",
        "topics": ["dữ liệu", "python", "thống kê", "trực quan hóa"],
        "prerequisites": ["CS101", "MATH101"],
        "schedule": [{"day": "Thứ 3", "start": "14:30", "end": "16:30"}],
        "seats_available": 0,
    },
    "MATH101": {
        "name": "Toán Rời rạc",
        "department": "Toán",
        "credits": 3,
        "level": "cơ bản",
        "topics": ["logic", "tổ hợp", "đồ thị", "toán"],
        "prerequisites": [],
        "schedule": [{"day": "Thứ 5", "start": "08:00", "end": "10:00"}],
        "seats_available": 20,
    },
    "MATH201": {
        "name": "Xác suất và Thống kê",
        "department": "Toán",
        "credits": 3,
        "level": "trung cấp",
        "topics": ["xác suất", "thống kê", "dữ liệu", "toán"],
        "prerequisites": ["MATH101"],
        "schedule": [{"day": "Thứ 4", "start": "10:30", "end": "12:30"}],
        "seats_available": 14,
    },
    "BUS220": {
        "name": "Quản trị Dự án",
        "department": "Kinh doanh",
        "credits": 3,
        "level": "trung cấp",
        "topics": ["quản trị", "dự án", "kỹ năng mềm"],
        "prerequisites": [],
        "schedule": [{"day": "Thứ 6", "start": "13:00", "end": "15:00"}],
        "seats_available": 9,
    },
}


STUDENT_RECORDS: dict[str, dict[str, Any]] = {
    "SV001": {
        "major": "Khoa học máy tính",
        "completed_courses": ["CS101", "MATH101"],
        "current_courses": ["CS201"],
        "max_semester_credits": 18,
    },
    "SV002": {
        "major": "Khoa học dữ liệu",
        "completed_courses": ["CS101", "MATH101", "MATH201"],
        "current_courses": [],
        "max_semester_credits": 15,
    },
}


def _json_result(*, ok: bool, **payload: Any) -> str:
    """Chuẩn hóa mọi Observation thành JSON UTF-8 để Agent dễ phân tích."""
    return json.dumps({"ok": ok, **payload}, ensure_ascii=False, sort_keys=True)


def _normalize_text(value: str) -> str:
    """Chuẩn hóa chữ thường và dấu tiếng Việt phục vụ tìm kiếm mềm."""
    normalized = unicodedata.normalize("NFD", value.strip().lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _normalize_course_codes(course_codes: list[str]) -> list[str]:
    return list(dict.fromkeys(str(code).strip().upper() for code in course_codes if str(code).strip()))


def _safe_tool(func: Callable[..., str]) -> Callable[..., str]:
    """Biến mọi exception ngoài dự kiến thành Observation JSON an toàn.

    Validation nghiệp vụ vẫn nằm trong từng tool để trả lỗi cụ thể. Lớp bảo vệ
    cuối này ngăn lỗi dữ liệu/code làm dừng ReAct loop và không làm lộ chi tiết
    exception nội bộ cho người dùng.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> str:
        try:
            return func(*args, **kwargs)
        except Exception:
            return _json_result(
                ok=False,
                error=f"Tool '{func.__name__}' không thể xử lý yêu cầu an toàn",
                recoverable=False,
            )

    return wrapper


@_safe_tool
def search_courses(keyword: str, department: str = "", level: str = "") -> str:
    """Tìm khóa học theo từ khóa và bộ lọc tùy chọn.

    Args:
        keyword: Chủ đề, kỹ năng, tên hoặc mã khóa học; không được để trống.
        department: Tên khoa cần lọc; để trống nếu không giới hạn.
        level: Một trong ``cơ bản``, ``trung cấp``, ``nâng cao``; để trống nếu
            không giới hạn.

    Returns:
        Chuỗi JSON gồm ``ok`` và ``courses``. Mỗi kết quả chứa mã, tên, khoa,
        trình độ, số tín chỉ và số chỗ trống. Lỗi đầu vào được trả về với
        ``ok=false`` thay vì phát sinh exception.

    Side effects:
        Không có; đây là tool tra cứu read-only.
    """
    if not isinstance(keyword, str) or not keyword.strip():
        return _json_result(ok=False, error="keyword phải là chuỗi không rỗng")
    if not isinstance(department, str) or not isinstance(level, str):
        return _json_result(ok=False, error="department và level phải là chuỗi")

    valid_levels = {"", "co ban", "trung cap", "nang cao"}
    normalized_level = _normalize_text(level)
    if normalized_level not in valid_levels:
        return _json_result(
            ok=False,
            error="level không hợp lệ",
            valid_levels=["cơ bản", "trung cấp", "nâng cao"],
        )

    query = _normalize_text(keyword)
    department_filter = _normalize_text(department)
    matches = []
    for code, course in COURSE_CATALOG.items():
        searchable = " ".join([code, course["name"], course["department"], *course["topics"]])
        if query not in _normalize_text(searchable):
            continue
        if department_filter and department_filter not in _normalize_text(course["department"]):
            continue
        if normalized_level and normalized_level != _normalize_text(course["level"]):
            continue
        matches.append(
            {
                "code": code,
                "name": course["name"],
                "department": course["department"],
                "level": course["level"],
                "credits": course["credits"],
                "seats_available": course["seats_available"],
            }
        )

    return _json_result(ok=True, count=len(matches), courses=matches)


@_safe_tool
def get_course_details(course_code: str) -> str:
    """Lấy dữ liệu đầy đủ của một khóa học từ mã khóa học.

    Args:
        course_code: Mã khóa học, ví dụ ``CS201``; không phân biệt hoa thường.

    Returns:
        Chuỗi JSON chứa thông tin học phần, tiên quyết, lịch và số chỗ trống;
        hoặc ``ok=false`` cùng danh sách mã hợp lệ nếu không tìm thấy.

    Side effects:
        Không có; tool không thực hiện đăng ký học.
    """
    if not isinstance(course_code, str) or not course_code.strip():
        return _json_result(ok=False, error="course_code phải là chuỗi không rỗng")

    code = course_code.strip().upper()
    course = COURSE_CATALOG.get(code)
    if course is None:
        return _json_result(
            ok=False,
            error=f"Không tìm thấy khóa học '{code}'",
            available_codes=sorted(COURSE_CATALOG),
        )
    return _json_result(ok=True, course={"code": code, **course})


@_safe_tool
def get_student_progress(student_id: str) -> str:
    """Tra cứu tiến độ học tập tối thiểu cần cho việc tư vấn cá nhân hóa.

    Args:
        student_id: Mã sinh viên được phép tra cứu, ví dụ ``SV001``.

    Returns:
        Chuỗi JSON chứa ngành, các môn đã/đang học và giới hạn tín chỉ. Không
        trả về tên, email, điểm số hoặc dữ liệu cá nhân không cần thiết.

    Side effects:
        Không có; tool read-only. Trong hệ thống thật cần xác thực người dùng.
    """
    if not isinstance(student_id, str) or not student_id.strip():
        return _json_result(ok=False, error="student_id phải là chuỗi không rỗng")

    student_key = student_id.strip().upper()
    record = STUDENT_RECORDS.get(student_key)
    if record is None:
        return _json_result(ok=False, error=f"Không tìm thấy hoặc không được phép truy cập '{student_key}'")
    return _json_result(ok=True, student_id=student_key, progress=record)


@_safe_tool
def check_prerequisites(course_code: str, completed_courses: list[str]) -> str:
    """Kiểm tra sinh viên đã đáp ứng môn tiên quyết hay chưa.

    Args:
        course_code: Mã khóa học dự định đăng ký.
        completed_courses: Danh sách mã các khóa học đã hoàn thành.

    Returns:
        Chuỗi JSON gồm ``eligible``, ``required`` và ``missing``. Mã môn không
        tồn tại hoặc kiểu tham số sai được trả về dưới dạng lỗi an toàn.

    Side effects:
        Không có; kết quả chỉ hỗ trợ tư vấn, không thay thế phê duyệt học vụ.
    """
    if not isinstance(course_code, str) or not course_code.strip():
        return _json_result(ok=False, error="course_code phải là chuỗi không rỗng")
    if not isinstance(completed_courses, list) or not all(isinstance(code, str) for code in completed_courses):
        return _json_result(ok=False, error="completed_courses phải là danh sách chuỗi")

    code = course_code.strip().upper()
    course = COURSE_CATALOG.get(code)
    if course is None:
        return _json_result(ok=False, error=f"Không tìm thấy khóa học '{code}'")

    completed = set(_normalize_course_codes(completed_courses))
    required = course["prerequisites"]
    missing = [prerequisite for prerequisite in required if prerequisite not in completed]
    return _json_result(
        ok=True,
        course_code=code,
        eligible=not missing,
        required=required,
        missing=missing,
    )


@_safe_tool
def check_schedule_conflicts(course_codes: list[str]) -> str:
    """Phát hiện lịch học chồng lấn giữa nhiều khóa học.

    Args:
        course_codes: Danh sách ít nhất hai mã khóa học cần so sánh.

    Returns:
        Chuỗi JSON gồm ``has_conflict`` và từng cặp lịch bị chồng lấn. Nếu có
        mã lạ, tool trả về ``ok=false`` và không suy đoán lịch.

    Side effects:
        Không có; tool read-only.
    """
    if not isinstance(course_codes, list) or not all(isinstance(code, str) for code in course_codes):
        return _json_result(ok=False, error="course_codes phải là danh sách chuỗi")

    codes = _normalize_course_codes(course_codes)
    if len(codes) < 2:
        return _json_result(ok=False, error="Cần ít nhất hai mã khóa học để kiểm tra xung đột")

    unknown = [code for code in codes if code not in COURSE_CATALOG]
    if unknown:
        return _json_result(ok=False, error="Có mã khóa học không tồn tại", unknown_codes=unknown)

    conflicts = []
    for index, first_code in enumerate(codes):
        for second_code in codes[index + 1 :]:
            for first_slot in COURSE_CATALOG[first_code]["schedule"]:
                for second_slot in COURSE_CATALOG[second_code]["schedule"]:
                    overlaps = (
                        first_slot["day"] == second_slot["day"]
                        and first_slot["start"] < second_slot["end"]
                        and second_slot["start"] < first_slot["end"]
                    )
                    if overlaps:
                        conflicts.append(
                            {
                                "course_1": first_code,
                                "course_2": second_code,
                                "day": first_slot["day"],
                                "time_1": f"{first_slot['start']}-{first_slot['end']}",
                                "time_2": f"{second_slot['start']}-{second_slot['end']}",
                            }
                        )

    return _json_result(ok=True, checked_courses=codes, has_conflict=bool(conflicts), conflicts=conflicts)


AVAILABLE_TOOLS = {
    "search_courses": search_courses,
    "get_course_details": get_course_details,
    "get_student_progress": get_student_progress,
    "check_prerequisites": check_prerequisites,
    "check_schedule_conflicts": check_schedule_conflicts,
}


TOOL_SCHEMAS = {
    "search_courses": {
        "name": "search_courses",
        "description": "Tìm các khóa học phù hợp theo chủ đề, khoa và trình độ.",
        "use_when": "Cần khám phá khóa học theo tên, mã, chủ đề, khoa hoặc trình độ.",
        "do_not_use_when": "Đã có mã môn và cần lịch, tiên quyết hoặc thông tin đầy đủ.",
        "input_schema": {
            "keyword": {"type": "str", "required": True},
            "department": {"type": "str", "required": False, "default": ""},
            "level": {"type": "str", "required": False, "default": ""},
        },
        "output_schema": "JSON string: {ok, count, courses[]}; mỗi course có code, name, department, level, credits, seats_available.",
        "error_semantics": "Trả JSON ok=false nếu keyword rỗng, sai kiểu hoặc level không hợp lệ; không raise lỗi nghiệp vụ.",
        "side_effect": "none (read-only)",
        "example": {"input": {"keyword": "python", "department": "Khoa học máy tính", "level": ""}, "output_contains": {"ok": True, "courses": [{"code": "CS101"}]}},
        "safety": "Không đăng ký môn và không trả hồ sơ sinh viên.",
    },
    "get_course_details": {
        "name": "get_course_details",
        "description": "Lấy thông tin đầy đủ và số chỗ còn lại của một khóa học.",
        "use_when": "Đã biết chính xác mã môn và cần dữ liệu chi tiết.",
        "do_not_use_when": "Chưa biết mã môn; hãy dùng search_courses trước.",
        "input_schema": {"course_code": {"type": "str", "required": True}},
        "output_schema": "JSON string: {ok, course}; course gồm code, name, department, credits, level, topics, prerequisites, schedule, seats_available.",
        "error_semantics": "Trả JSON ok=false và available_codes khi mã không tồn tại; không suy đoán môn gần giống.",
        "side_effect": "none (read-only)",
        "example": {"input": {"course_code": "CS201"}, "output_contains": {"ok": True, "course": {"code": "CS201"}}},
        "safety": "Số chỗ chỉ phản ánh catalog mẫu và không phải xác nhận đăng ký.",
    },
    "get_student_progress": {
        "name": "get_student_progress",
        "description": "Lấy tiến độ tối thiểu để tư vấn cá nhân hóa cho sinh viên.",
        "use_when": "Cần kiểm tra các môn đã/đang học và giới hạn tín chỉ của chính sinh viên được phép tra cứu.",
        "do_not_use_when": "Câu hỏi chỉ cần kiến thức chung hoặc người dùng chưa cung cấp mã sinh viên hợp lệ.",
        "input_schema": {"student_id": {"type": "str", "required": True}},
        "output_schema": "JSON string: {ok, student_id, progress}; progress chỉ gồm major, completed_courses, current_courses, max_semester_credits.",
        "error_semantics": "Trả JSON ok=false cho mã rỗng, sai kiểu, không tồn tại hoặc không được phép.",
        "side_effect": "none (read-only)",
        "example": {"input": {"student_id": "SV001"}, "output_contains": {"ok": True, "student_id": "SV001"}},
        "safety": "Giảm thiểu dữ liệu: không trả tên, email, GPA hoặc điểm số; hệ thống thật phải xác thực.",
    },
    "check_prerequisites": {
        "name": "check_prerequisites",
        "description": "Kiểm tra điều kiện tiên quyết trước khi đề xuất đăng ký.",
        "use_when": "Đã có mã môn mục tiêu và danh sách môn hoàn thành đáng tin cậy.",
        "do_not_use_when": "Chưa lấy tiến độ sinh viên hoặc cần kiểm tra xung đột lịch.",
        "input_schema": {"course_code": {"type": "str", "required": True}, "completed_courses": {"type": "list[str]", "required": True}},
        "output_schema": "JSON string: {ok, course_code, eligible, required, missing}.",
        "error_semantics": "Trả JSON ok=false nếu mã môn, danh sách hoặc phần tử trong danh sách không hợp lệ.",
        "side_effect": "none (read-only)",
        "example": {"input": {"course_code": "AI301", "completed_courses": ["CS101"]}, "output_contains": {"ok": True, "eligible": False, "missing": ["MATH201"]}},
        "safety": "Kết quả chỉ hỗ trợ tư vấn và không thay thế phê duyệt học vụ.",
    },
    "check_schedule_conflicts": {
        "name": "check_schedule_conflicts",
        "description": "Kiểm tra xung đột lịch giữa các khóa học dự kiến.",
        "use_when": "Cần so sánh lịch của ít nhất hai mã môn đã biết.",
        "do_not_use_when": "Chỉ có một môn hoặc cần tìm môn theo chủ đề.",
        "input_schema": {"course_codes": {"type": "list[str]", "required": True, "min_items": 2}},
        "output_schema": "JSON string: {ok, checked_courses, has_conflict, conflicts[]}.",
        "error_semantics": "Trả JSON ok=false nếu sai kiểu, ít hơn hai mã hoặc có mã không tồn tại.",
        "side_effect": "none (read-only)",
        "example": {"input": {"course_codes": ["CS201", "DS210"]}, "output_contains": {"ok": True, "has_conflict": True}},
        "safety": "Chỉ so sánh catalog mẫu; không thay đổi thời khóa biểu hay đăng ký môn.",
    },
}
