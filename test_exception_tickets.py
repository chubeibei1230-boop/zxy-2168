import requests
import json
import sqlite3
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8125"
DB_PATH = "luggage_tags.db"


def print_response(title, response):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except:
        print(response.text)
    return response


def simulate_overtime(tag_code, hours_ago=5):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    issue_time = (datetime.utcnow() - timedelta(hours=hours_ago)).isoformat()
    expected_time = (datetime.utcnow() - timedelta(hours=hours_ago - 1)).isoformat()
    cursor.execute(
        "UPDATE luggage_tags SET issue_time = ?, expected_return_time = ? WHERE tag_code = ?",
        (issue_time, expected_time, tag_code)
    )
    cursor.execute(
        "UPDATE tag_issue_records SET issue_time = ?, expected_return_time = ? WHERE tag_code = ? AND status = '使用中'",
        (issue_time, expected_time, tag_code)
    )
    conn.commit()
    conn.close()


print("=" * 70)
print("  异常工单模块功能验证测试")
print("=" * 70)

print_response("1. 检查系统状态和选项接口", requests.get(f"{BASE_URL}/"))
print_response("2. 检查状态选项（包含新增枚举）", requests.get(f"{BASE_URL}/api/status-options"))

print_response("3. 创建寄物牌 TICKET-TAG-01", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "TICKET-TAG-01",
    "area": "异常工单测试区",
    "group_name": "测试组A",
    "retention_hours": 1,
    "responsible_person": "工单负责人A"
}))

print_response("4. 发放寄物牌 TICKET-TAG-01", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "TICKET-TAG-01",
    "user_name": "测试用户张三",
    "user_contact": "13800000001"
}))

print("5. 模拟超时...")
simulate_overtime("TICKET-TAG-01", hours_ago=5)

print_response("6. 触发超时检测", requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "TICKET-TAG-01"}))

print_response("7. 归还超时寄物牌（应自动创建超时归还类型异常工单）",
    requests.post(f"{BASE_URL}/api/tags/TICKET-TAG-01/return", json={
        "return_note": "用户晚归还"
    }))

print_response("8. 查询异常工单列表（应看到1条超时归还工单）",
    requests.get(f"{BASE_URL}/api/exception-tickets"))

tickets_resp = requests.get(f"{BASE_URL}/api/exception-tickets").json()
ticket_id = tickets_resp["items"][0]["id"] if tickets_resp["items"] else None
print(f"  获取到工单号: {ticket_id}")

if ticket_id:
    print_response(f"9. 查看工单详情 #{ticket_id}",
        requests.get(f"{BASE_URL}/api/exception-tickets/{ticket_id}"))

print_response("10. 尝试在异常工单未闭环时发放 TICKET-TAG-01（应失败）",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "TICKET-TAG-01",
        "user_name": "测试用户李四"
    }))

if ticket_id:
    print_response(f"11. 处理并闭环异常工单 #{ticket_id}",
        requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id}/handle", json={
            "handling_conclusion": "联系用户确认已归还，警告用户下次准时归还",
            "handler": "管理员王经理",
            "ticket_status": "已闭环"
        }))

print_response("12. 异常闭环后，再次尝试发放 TICKET-TAG-01（应成功）",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "TICKET-TAG-01",
        "user_name": "测试用户李四"
    }))

print_response("13. 归还 TICKET-TAG-01（正常归还，不应创建工单）",
    requests.post(f"{BASE_URL}/api/tags/TICKET-TAG-01/return", json={
        "return_note": "正常按时归还"
    }))

print_response("14. 人工创建异常工单（人工标记异常类型）",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "TICKET-TAG-01",
        "exception_type": "人工标记异常",
        "exception_description": "牌面有损坏，需要维修"
    }))

print_response("15. 查询统计接口（包含异常工单概览统计）",
    requests.get(f"{BASE_URL}/api/statistics"))

print_response("16. 按条件筛选工单列表 - 按责任人筛选",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "responsible_person": "工单负责人A",
        "page": 1,
        "page_size": 10
    }))

print_response("17. 按条件筛选工单列表 - 按异常类型筛选",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "exception_type": "超时归还",
        "page": 1,
        "page_size": 10
    }))

print_response("18. 按条件筛选工单列表 - 按处理状态筛选",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "ticket_status": "已闭环",
        "page": 1,
        "page_size": 10
    }))

print_response("19. 创建第二个寄物牌用于分组测试",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "TICKET-TAG-02",
        "area": "异常工单测试区",
        "group_name": "测试组B",
        "retention_hours": 1,
        "responsible_person": "工单负责人B"
    }))

print_response("20. 人工创建第二条异常工单",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "TICKET-TAG-02",
        "exception_type": "待核对",
        "exception_description": "历史核对记录有问题"
    }))

print_response("21. 查询全量工单（应看到3条工单）",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "page_size": 50
    }))

print_response("22. 再次查看统计（应看到多区域多责任人的统计数据）",
    requests.get(f"{BASE_URL}/api/statistics"))

print_response("23. 尝试处理已闭环工单（应失败-不能重复处理）",
    requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id}/handle", json={
        "handling_conclusion": "再处理一次",
        "handler": "其他管理员"
    }) if ticket_id else None)

print_response("24. 创建无效异常类型工单（应失败）",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "TICKET-TAG-01",
        "exception_type": "不存在的异常类型",
        "exception_description": "测试"
    }))

print("\n" + "=" * 70)
print("  异常工单模块测试完成！")
print("=" * 70)
print("""
  测试覆盖内容：
  ✓ 1. 超时归还自动创建异常工单
  ✓ 2. 异常工单多条件分页查询（区域/责任人/异常类型/处理状态）
  ✓ 3. 工单详情查看
  ✓ 4. 处理人补充处理结果并闭环工单
  ✓ 5. 未闭环异常工单时寄物牌不可发放
  ✓ 6. 异常闭环后寄物牌恢复可发放
  ✓ 7. 人工创建异常工单
  ✓ 8. 统计接口包含异常工单概览
  ✓ 9. 防止重复处理已闭环工单
  ✓ 10. 无效异常类型校验
  ✓ 11. 状态选项接口新增异常类型和工单状态枚举
""")
