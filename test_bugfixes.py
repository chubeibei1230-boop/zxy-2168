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

def simulate_past_records(tag_code, n_overtime, n_normal=0):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM luggage_tags WHERE tag_code = ?", (tag_code,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
    tag_id = row[0]

    base_time = datetime.utcnow() - timedelta(days=30)
    for i in range(n_overtime):
        issue_t = base_time + timedelta(days=i*3, hours=10)
        expected_t = issue_t + timedelta(hours=1)
        return_t = issue_t + timedelta(hours=5)
        cursor.execute("""
            INSERT INTO tag_issue_records (tag_id, tag_code, area, group_name, responsible_person,
            user_name, user_contact, issue_time, expected_return_time, actual_return_time,
            is_overtime, overtime_hours, status, return_note, created_at)
            VALUES (?, ?, '测试区', '连续测试组', '连续负责人',
            '用户', '111', ?, ?, ?, 1, 4, '已归还', '超时归还', ?)
        """, (tag_id, tag_code, issue_t.isoformat(), expected_t.isoformat(),
              return_t.isoformat(), return_t.isoformat()))

    for i in range(n_normal):
        issue_t = base_time + timedelta(days=n_overtime * 3 + i * 3, hours=10)
        expected_t = issue_t + timedelta(hours=24)
        return_t = issue_t + timedelta(hours=2)
        cursor.execute("""
            INSERT INTO tag_issue_records (tag_id, tag_code, area, group_name, responsible_person,
            user_name, user_contact, issue_time, expected_return_time, actual_return_time,
            is_overtime, overtime_hours, status, return_note, created_at)
            VALUES (?, ?, '测试区', '连续测试组', '连续负责人',
            '用户', '222', ?, ?, ?, 0, 0, '已归还', '正常归还', ?)
        """, (tag_id, tag_code, issue_t.isoformat(), expected_t.isoformat(),
              return_t.isoformat(), return_t.isoformat()))

    conn.commit()
    conn.close()

print("=" * 60)
print("Bug 修复验证测试")
print("=" * 60)

print_response("Bug 1 测试：重复核对验证 - 先创建并核对一次",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "BUG1-TAG",
        "area": "Bug修复区",
        "group_name": "Bug1组",
        "retention_hours": 1,
        "responsible_person": "Bug1负责人"
    }))

print_response("发放 BUG1-TAG",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "BUG1-TAG",
        "user_name": "用户1",
        "user_contact": "111"
    }))

simulate_overtime("BUG1-TAG")

print_response("触发超时检测", requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUG1-TAG"}))

print_response("归还超时牌变为待核对",
    requests.post(f"{BASE_URL}/api/tags/BUG1-TAG/return", json={"return_note": "超时"}))

print_response("第一次核对（应成功）",
    requests.post(f"{BASE_URL}/api/tags/BUG1-TAG/check", json={
        "overtime_description": "超时说明",
        "handling_conclusion": "处理完成",
        "check_person": "管理员",
        "is_closed": 1
    }))

print_response("第二次核对（应失败-重复核对）",
    requests.post(f"{BASE_URL}/api/tags/BUG1-TAG/check", json={
        "overtime_description": "再次核对",
        "handling_conclusion": "再处理",
        "check_person": "管理员",
        "is_closed": 1
    }))

print("\n" + "="*60)
print("Bug 2 测试：停用后误发放")
print("="*60)

print_response("创建 BUG2-TAG",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "BUG2-TAG",
        "area": "Bug修复区",
        "group_name": "Bug2组",
        "retention_hours": 24,
        "responsible_person": "Bug2负责人"
    }))

print_response("发放 BUG2-TAG",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "BUG2-TAG",
        "user_name": "用户A",
        "user_contact": "222"
    }))

print_response("正常归还",
    requests.post(f"{BASE_URL}/api/tags/BUG2-TAG/return", json={"return_note": "正常"}))

bug2_tag_id = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUG2-TAG"}).json()["items"][0]["id"]
print(f"BUG2-TAG ID: {bug2_tag_id}")

print_response("停用 BUG2-TAG",
    requests.put(f"{BASE_URL}/api/tags/{bug2_tag_id}/status", json={
        "status": "停用"
    }))

print_response("查看预警（应没有停用后误发放）",
    requests.get(f"{BASE_URL}/api/alerts"))

print("\n" + "="*60)
print("Bug 3 测试：分组回收偏慢包含超时占用")
print("="*60)

for i in range(1, 6):
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": f"BUG3-TAG-{i}",
        "area": "Bug修复区",
        "group_name": "Bug3组",
        "retention_hours": 1,
        "responsible_person": "Bug3负责人"
    })
print("已创建 5 个 Bug3 组寄物牌")

for i in range(1, 4):
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": f"BUG3-TAG-{i}",
        "user_name": f"用户{i}",
    })
print("已发放 3 个（应正常使用中）")

for i in [4, 5]:
    resp = requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": f"BUG3-TAG-{i}",
        "user_name": f"用户{i}",
    })
    simulate_overtime(f"BUG3-TAG-{i}")
print("已发放 2 个并模拟超时")

print_response("触发超时检测", requests.get(f"{BASE_URL}/api/tags", params={"group_name": "Bug3组"}))

print_response("查看分组预警（Bug3组 5/5 应报警）",
    requests.get(f"{BASE_URL}/api/alerts"))

print("\n" + "="*60)
print("Bug 4 测试：连续超时占用（真连续）")
print("="*60)

print_response("创建 BUG4-TAG（先造历史数据：3次连续超时 + 1次正常 + 2次连续超时",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "BUG4-TAG",
        "area": "Bug修复区",
        "group_name": "Bug4组",
        "retention_hours": 1,
        "responsible_person": "Bug4负责人"
    }))

simulate_past_records("BUG4-TAG", n_overtime=2, n_normal=0)
print("已插入 2 条历史超时记录（最近连续超时次数=2，应不报警（<3）")

print_response("发放 BUG4-TAG",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "BUG4-TAG",
        "user_name": "用户X"
    }))

simulate_overtime("BUG4-TAG")

print_response("归还并触发超时检测",
    requests.post(f"{BASE_URL}/api/tags/BUG4-TAG/return", json={"return_note": "超时"}))

bug4_tag_id = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUG4-TAG"}).json()["items"][0]["id"]

print_response("核对闭环",
    requests.post(f"{BASE_URL}/api/tags/BUG4-TAG/check", json={
        "overtime_description": "超时",
        "handling_conclusion": "OK",
        "check_person": "管理员",
        "is_closed": 1
    }))

print_response("查看预警（BUG4-TAG 最近连续超时=3 次，应报警）",
    requests.get(f"{BASE_URL}/api/alerts"))

print("\n" + "="*60)
print("所有 Bug 修复测试完成！")
print("="*60)
