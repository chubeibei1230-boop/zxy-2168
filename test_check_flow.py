import requests
import json
import sqlite3
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8125"
DB_PATH = "luggage_tags.db"

def print_response(title, response):
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except:
        print(response.text)

def simulate_overtime(tag_code):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    past_time = (datetime.utcnow() - timedelta(hours=5)).isoformat()
    cursor.execute(
        "UPDATE luggage_tags SET issue_time = ?, expected_return_time = ? WHERE tag_code = ?",
        (past_time, (datetime.utcnow() - timedelta(hours=2)).isoformat(), tag_code)
    )
    cursor.execute(
        "UPDATE tag_issue_records SET issue_time = ?, expected_return_time = ? WHERE tag_code = ? AND status = '使用中'",
        (past_time, (datetime.utcnow() - timedelta(hours=2)).isoformat(), tag_code)
    )
    conn.commit()
    conn.close()
    print(f"[模拟] 已将 {tag_code} 的发放时间提前，模拟超时")

print("=" * 60)
print("超时归还与核对流程测试")
print("=" * 60)

print_response("1. 创建测试寄物牌 TAG-CHECK-001",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "TAG-CHECK-001",
        "area": "核对测试区",
        "group_name": "核对组",
        "retention_hours": 2,
        "responsible_person": "核对负责人"
    }))

print_response("2. 发放 TAG-CHECK-001",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "TAG-CHECK-001",
        "user_name": "超时用户",
        "user_contact": "13500000000"
    }))

simulate_overtime("TAG-CHECK-001")

print_response("3. 触发超时检测（访问任意接口会自动更新超时状态）",
    requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "TAG-CHECK-001"}))

print_response("4. 验证状态变为超时占用",
    requests.get(f"{BASE_URL}/api/tags", params={"status": "超时占用"}))

print_response("5. 尝试手动恢复为可用（应失败-需先核对）",
    requests.put(f"{BASE_URL}/api/tags/3/status", json={
        "status": "恢复可用"
    }))

print_response("6. 尝试再次发放（应失败-超时占用期间不能发放）",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "TAG-CHECK-001",
        "user_name": "另一个用户",
        "user_contact": "13400000000"
    }))

print_response("7. 归还超时的寄物牌（应变为待核对状态）",
    requests.post(f"{BASE_URL}/api/tags/TAG-CHECK-001/return", json={
        "return_note": "超时归还，有事耽误了"
    }))

print_response("8. 验证状态为待核对",
    requests.get(f"{BASE_URL}/api/tags", params={"status": "待核对"}))

print_response("9. 对待核对的寄物牌进行核对（闭环）",
    requests.post(f"{BASE_URL}/api/tags/TAG-CHECK-001/check", json={
        "overtime_description": "用户因临时有事未能及时归还，已电话沟通",
        "handling_conclusion": "已批评教育，下次注意，寄物牌恢复可用",
        "check_person": "管理员A",
        "is_closed": 1
    }))

print_response("10. 验证核对后状态变为恢复可用",
    requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "TAG-CHECK-001"}))

print_response("11. 查看核对记录",
    requests.get(f"{BASE_URL}/api/check-records"))

print_response("12. 统计数据 - 责任人闭环率",
    requests.get(f"{BASE_URL}/api/statistics"))

print_response("13. 待核对统计",
    requests.get(f"{BASE_URL}/api/statistics"))

print("\n" + "="*60)
print("超时归还与核对流程测试完成！")
print("="*60)
