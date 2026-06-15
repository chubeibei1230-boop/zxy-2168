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
print("  异常闭环追踪与复盘 - 核心功能快速验证")
print("=" * 70)

print_response("1. 系统状态检查", requests.get(f"{BASE_URL}/"))

print_response("2. 创建测试寄物牌", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "QUICK-TEST-001",
    "area": "测试区域-快速验证区",
    "group_name": "验证组",
    "retention_hours": 1,
    "responsible_person": "验证负责人-王测试"
}))

print_response("3. 发放寄物牌", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "QUICK-TEST-001",
    "user_name": "测试用户",
    "user_contact": "13900000000"
}))

print("4. 模拟超时3小时...")
simulate_overtime("QUICK-TEST-001", hours_ago=3)

print_response("5. 触发超时检测，自动创建超时异常工单",
    requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "QUICK-TEST-001"}))

resp = requests.get(f"{BASE_URL}/api/exception-tickets", params={"tag_code": "QUICK-TEST-001"})
data = resp.json()
print(f"  当前异常工单数量: {data['total']}")

if data['total'] == 0:
    print_response("5b. 主动归还超时牌触发创建工单",
        requests.post(f"{BASE_URL}/api/tags/QUICK-TEST-001/return", json={
            "return_note": "超时归还"
        }))
    resp = requests.get(f"{BASE_URL}/api/exception-tickets", params={"tag_code": "QUICK-TEST-001"})
    data = resp.json()
    print(f"  归还后异常工单数量: {data['total']}")

ticket_id = data['items'][0]['id'] if data['items'] else None
print(f"  获取工单号: #{ticket_id}")

if ticket_id:
    print_response(f"6. 查询异常工单完整上下文详情 #{ticket_id}",
        requests.get(f"{BASE_URL}/api/exception-tickets/{ticket_id}/detail"))

    print_response(f"7. 处理工单 - 设为处理中 #{ticket_id}",
        requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id}/handle", json={
            "handling_conclusion": "已联系用户，正在核实中",
            "handler": "管理员-测试",
            "ticket_status": "处理中"
        }))

    print_response(f"8. 再次查看详情(处理中状态) #{ticket_id}",
        requests.get(f"{BASE_URL}/api/exception-tickets/{ticket_id}/detail"))

    print_response(f"9. 闭环工单 #{ticket_id}",
        requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id}/handle", json={
            "handling_conclusion": "用户已归还，已完成复盘记录",
            "handler": "管理员-测试",
            "ticket_status": "已闭环"
        }))

    print_response(f"10. 闭环后查看详情(can_handle应为false) #{ticket_id}",
        requests.get(f"{BASE_URL}/api/exception-tickets/{ticket_id}/detail"))

    print_response(f"11. 尝试重复闭环(应失败) #{ticket_id}",
        requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id}/handle", json={
            "handling_conclusion": "重复处理",
            "handler": "管理员-测试"
        }))

print_response("12. 查询详细异常统计",
    requests.get(f"{BASE_URL}/api/exception-statistics"))

print("\n" + "=" * 70)
print("  核心功能快速验证完成！")
print("=" * 70)
