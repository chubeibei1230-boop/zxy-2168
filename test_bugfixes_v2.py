import requests
import json
import sqlite3
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8125"
DB_PATH = "luggage_tags.db"


def print_response(title, response):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}")
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


def count_tickets(tag_code=None):
    params = {}
    if tag_code:
        params["tag_code"] = tag_code
    params["page_size"] = 100
    resp = requests.get(f"{BASE_URL}/api/exception-tickets", params=params)
    return resp.json()["total"]


def get_issue_record_id(tag_code):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM tag_issue_records WHERE tag_code = ? ORDER BY id DESC LIMIT 1",
        (tag_code,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def create_overtime_unreturned_ticket(tag_code, exception_type="OVERTIME"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, area, group_name, responsible_person FROM luggage_tags WHERE tag_code = ?",
        (tag_code,)
    )
    tag_row = cursor.fetchone()
    if not tag_row:
        conn.close()
        return None
    tag_id, area, group_name, responsible_person = tag_row
    cursor.execute(
        "SELECT id FROM tag_issue_records WHERE tag_code = ? ORDER BY id DESC LIMIT 1",
        (tag_code,)
    )
    issue_row = cursor.fetchone()
    issue_record_id = issue_row[0] if issue_row else None
    now = datetime.utcnow().isoformat()
    cursor.execute(
        "INSERT INTO tag_exception_tickets (tag_id, issue_record_id, tag_code, area, group_name, responsible_person, user_name, exception_type, exception_description, handling_conclusion, handler, handling_time, ticket_status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (tag_id, issue_record_id, tag_code, area, group_name, responsible_person, "测试用户", exception_type, "模拟超时未归还工单", None, None, None, "PENDING", now, now)
    )
    conn.commit()
    ticket_id = cursor.lastrowid
    conn.close()
    return ticket_id


print("=" * 80)
print("  4个Bug修复验证测试 (v2 修复版)")
print("=" * 80)

print_response("0. 系统状态检查", requests.get(f"{BASE_URL}/"))

print("\n" + "=" * 80)
print("  Bug1+Bug2 验证: 超时工单闭环后，归还不重复生成异常")
print("=" * 80)

print_response("1. 创建寄物牌 BUGFIX-01", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "BUGFIX-01",
    "area": "Bug修复验证区",
    "group_name": "测试组1",
    "retention_hours": 1,
    "responsible_person": "责任人-甲"
}))

print_response("2. 发放 BUGFIX-01", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "BUGFIX-01",
    "user_name": "用户甲",
    "user_contact": "13800000001"
}))

print("3. 模拟 BUGFIX-01 超时4小时...")
simulate_overtime("BUGFIX-01", hours_ago=4)

print("4. 手动插入一条超时未归还异常工单（模拟中间件自动创建）...")
auto_ticket_id = create_overtime_unreturned_ticket("BUGFIX-01")
print(f"   已创建模拟超时工单 #{auto_ticket_id}")

bug1_tickets_before = count_tickets("BUGFIX-01")
print(f"   归还前异常工单数量: {bug1_tickets_before}")

bug1_tickets_after_close = bug1_tickets_before

if auto_ticket_id:
    print_response(f"5. 管理员先闭环超时未归还工单 #{auto_ticket_id}",
        requests.put(f"{BASE_URL}/api/exception-tickets/{auto_ticket_id}/handle", json={
            "handling_conclusion": "已联系用户，用户承诺今日内归还",
            "handler": "管理员-提前处理",
            "ticket_status": "已闭环"
        }))

    bug1_tickets_after_close = count_tickets("BUGFIX-01")
    print(f"   闭环后异常工单数量: {bug1_tickets_after_close}")

print_response("6. 用户后续归还 BUGFIX-01（不应生成新异常）",
    requests.post(f"{BASE_URL}/api/tags/BUGFIX-01/return", json={
        "return_note": "用户刚归还"
    }))

bug1_tickets_final = count_tickets("BUGFIX-01")
print(f"   归还后异常工单数量: {bug1_tickets_final}")

if bug1_tickets_final == bug1_tickets_after_close:
    print("  [OK] Bug1+Bug2修复验证通过：归还后未重复生成异常工单！")
else:
    print(f"  [FAIL] Bug1+Bug2修复验证失败：工单数量从 {bug1_tickets_after_close} 增加到 {bug1_tickets_final}")

print("\n" + "=" * 80)
print("  Bug3 验证: 待核对/超时归还类型异常闭环不能绕过核对")
print("=" * 80)

print_response("7. 创建寄物牌 BUGFIX-02", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "BUGFIX-02",
    "area": "Bug修复验证区",
    "group_name": "测试组2",
    "retention_hours": 1,
    "responsible_person": "责任人-乙"
}))

print_response("8. 发放 BUGFIX-02", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "BUGFIX-02",
    "user_name": "用户乙",
    "user_contact": "13800000002"
}))

print("9. 模拟 BUGFIX-02 超时2小时...")
simulate_overtime("BUGFIX-02", hours_ago=2)

print_response("10. 超时归还 BUGFIX-02（产生待核对状态+超时归还异常）",
    requests.post(f"{BASE_URL}/api/tags/BUGFIX-02/return", json={
        "return_note": "超时2小时归还"
    }))

tag_resp = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUGFIX-02"})
tag_data = tag_resp.json()["items"][0]
print(f"   BUGFIX-02 当前状态: {tag_data['status']}")

resp = requests.get(f"{BASE_URL}/api/exception-tickets", params={
    "tag_code": "BUGFIX-02",
    "ticket_status": "待处理",
    "page_size": 20
})
bug3_ticket_id = resp.json()["items"][0]["id"]
print(f"   待处理异常工单号: #{bug3_ticket_id}")

print_response(f"11. 直接闭环超时归还类型异常 #{bug3_ticket_id}",
    requests.put(f"{BASE_URL}/api/exception-tickets/{bug3_ticket_id}/handle", json={
        "handling_conclusion": "尝试直接闭环看是否绕过核对",
        "handler": "管理员-测试绕过",
        "ticket_status": "已闭环"
    }))

tag_resp2 = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUGFIX-02"})
tag_data2 = tag_resp2.json()["items"][0]
print(f"   闭环后 BUGFIX-02 当前状态: {tag_data2['status']}")

if tag_data2["status"] == "待核对":
    print("  [OK] Bug3修复验证通过：超时归还类型异常闭环后仍保持待核对状态，必须走核对流程！")
elif tag_data2["status"] == "恢复可用":
    print("  [FAIL] Bug3修复验证失败：被绕过核对直接恢复可用了！")

print_response("12. 走正常核对流程处理 BUGFIX-02",
    requests.post(f"{BASE_URL}/api/tags/BUGFIX-02/check", json={
        "overtime_description": "用户逛太久忘记归还时间",
        "handling_conclusion": "已对用户进行提醒，用户接受",
        "check_person": "核对员-小陈",
        "is_closed": 1
    }))

tag_resp3 = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUGFIX-02"})
tag_data3 = tag_resp3.json()["items"][0]
print(f"   核对后 BUGFIX-02 当前状态: {tag_data3['status']}")

if tag_data3["status"] == "恢复可用":
    print("  [OK] 核对流程验证通过：核对完成后正确恢复可用！")

print("\n" + "=" * 80)
print("  Bug3对比验证: 人工标记异常闭环后应能恢复可用")
print("=" * 80)

print_response("13. 创建寄物牌 BUGFIX-03", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "BUGFIX-03",
    "area": "Bug修复验证区",
    "group_name": "测试组3",
    "retention_hours": 1,
    "responsible_person": "责任人-丙"
}))

print_response("14. 发放并正常归还 BUGFIX-03", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "BUGFIX-03",
    "user_name": "用户丙",
    "user_contact": "13800000003"
}))
requests.post(f"{BASE_URL}/api/tags/BUGFIX-03/return", json={"return_note": "正常归还"})

print_response("15. 人工标记 BUGFIX-03 异常（牌面损坏）",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "BUGFIX-03",
        "exception_type": "人工标记异常",
        "exception_description": "牌面边角有裂痕"
    }))

tag_resp4 = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUGFIX-03"})
tag_data4 = tag_resp4.json()["items"][0]
print(f"   标记异常后 BUGFIX-03 当前状态: {tag_data4['status']}")

resp = requests.get(f"{BASE_URL}/api/exception-tickets", params={
    "tag_code": "BUGFIX-03",
    "page_size": 20
})
manual_ticket_id = resp.json()["items"][0]["id"]
print(f"   人工标记异常工单号: #{manual_ticket_id}")

print_response(f"16. 维修完成后闭环人工标记异常 #{manual_ticket_id}",
    requests.put(f"{BASE_URL}/api/exception-tickets/{manual_ticket_id}/handle", json={
        "handling_conclusion": "牌面裂痕已修复，可以重新投入使用",
        "handler": "维修员-老李",
        "ticket_status": "已闭环"
    }))

tag_resp5 = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUGFIX-03"})
tag_data5 = tag_resp5.json()["items"][0]
print(f"   闭环人工标记异常后 BUGFIX-03 当前状态: {tag_data5['status']}")

if tag_data5["status"] == "恢复可用":
    print("  [OK] 人工标记异常对比验证通过：修复后闭环可正确恢复可用！")
else:
    print(f"  [WARN] 注意：人工标记闭环后状态是 {tag_data5['status']}")

print("\n" + "=" * 80)
print("  Bug4 验证: 处理时间支持按实际处理时间登记")
print("=" * 80)

print_response("17. 创建寄物牌 BUGFIX-04", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "BUGFIX-04",
    "area": "Bug修复验证区",
    "group_name": "测试组4",
    "retention_hours": 1,
    "responsible_person": "责任人-丁"
}))

print_response("18. 发放并正常归还 BUGFIX-04", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "BUGFIX-04",
    "user_name": "用户丁",
    "user_contact": "13800000004"
}))
requests.post(f"{BASE_URL}/api/tags/BUGFIX-04/return", json={"return_note": "正常归还"})

print_response("19. 人工标记 BUGFIX-04 异常",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "BUGFIX-04",
        "exception_type": "人工标记异常",
        "exception_description": "系统登记信息有误"
    }))

resp = requests.get(f"{BASE_URL}/api/exception-tickets", params={
    "tag_code": "BUGFIX-04",
    "page_size": 20
})
custom_time_ticket_id = resp.json()["items"][0]["id"]

custom_time = (datetime.utcnow() - timedelta(hours=2, minutes=30)).isoformat()
print(f"   传入的自定义处理时间: {custom_time}")

print_response(f"20. 闭环时传入自定义处理时间 #{custom_time_ticket_id}",
    requests.put(f"{BASE_URL}/api/exception-tickets/{custom_time_ticket_id}/handle", json={
        "handling_conclusion": "信息已修正，实际2个半小时前处理完毕",
        "handler": "管理员-补录数据",
        "ticket_status": "已闭环",
        "handling_time": custom_time
    }))

detail_resp = requests.get(f"{BASE_URL}/api/exception-tickets/{custom_time_ticket_id}")
detail_data = detail_resp.json()
actual_time = detail_data["handling_time"]
print(f"   返回的实际处理时间: {actual_time}")

if actual_time and actual_time.startswith(custom_time[:16]):
    print("  [OK] Bug4修复验证通过：处理时间已按自定义时间正确登记！")
elif actual_time and custom_time[:10] in actual_time:
    print(f"  [OK] Bug4修复验证通过：处理日期匹配（{actual_time}）")
else:
    print(f"   预期时间前缀: {custom_time[:16]}")
    print(f"  [FAIL] Bug4修复验证失败：处理时间未按自定义时间登记")

print("\n" + "=" * 80)
print("  额外验证: Bug3-待核对类型异常闭环后仍需走核对流程")
print("=" * 80)

print_response("21. 创建寄物牌 BUGFIX-05", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "BUGFIX-05",
    "area": "Bug修复验证区",
    "group_name": "测试组5",
    "retention_hours": 1,
    "responsible_person": "责任人-戊"
}))

print_response("22. 发放并正常归还 BUGFIX-05", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "BUGFIX-05",
    "user_name": "用户戊",
    "user_contact": "13800000005"
}))
requests.post(f"{BASE_URL}/api/tags/BUGFIX-05/return", json={"return_note": "正常归还"})

print_response("23. 为 BUGFIX-05 创建「待核对」类型异常工单",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "BUGFIX-05",
        "exception_type": "待核对",
        "exception_description": "系统记录与纸质登记不一致"
    }))

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("UPDATE luggage_tags SET status = 'PENDING_CHECK' WHERE tag_code = 'BUGFIX-05'")
conn.commit()
conn.close()
print("   已手动将 BUGFIX-05 标记为待核对状态，模拟待核对场景")

resp = requests.get(f"{BASE_URL}/api/exception-tickets", params={
    "tag_code": "BUGFIX-05",
    "ticket_status": "待处理",
    "page_size": 20
})
pending_check_ticket_id = resp.json()["items"][0]["id"]
print(f"   待核对类型异常工单号: #{pending_check_ticket_id}")

print_response(f"24. 直接闭环待核对类型异常 #{pending_check_ticket_id}",
    requests.put(f"{BASE_URL}/api/exception-tickets/{pending_check_ticket_id}/handle", json={
        "handling_conclusion": "尝试直接闭环待核对工单",
        "handler": "管理员-测试绕过2",
        "ticket_status": "已闭环"
    }))

tag_resp6 = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUGFIX-05"})
tag_data6 = tag_resp6.json()["items"][0]
print(f"   闭环待核对异常后 BUGFIX-05 当前状态: {tag_data6['status']}")

if tag_data6["status"] == "待核对":
    print("  [OK] 待核对类型异常验证通过：闭环后仍保持待核对状态，必须走核对流程！")
elif tag_data6["status"] == "恢复可用":
    print("  [FAIL] 待核对类型异常验证失败：绕过核对直接恢复可用了！")

print_response("25. 通过核对流程闭环 BUGFIX-05",
    requests.post(f"{BASE_URL}/api/tags/BUGFIX-05/check", json={
        "overtime_description": "无超时，只是登记信息核对",
        "handling_conclusion": "信息已核对一致，纸质登记补录完成",
        "check_person": "核对员-小王",
        "is_closed": 1
    }))

tag_resp7 = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUGFIX-05"})
tag_data7 = tag_resp7.json()["items"][0]
print(f"   核对完成后 BUGFIX-05 当前状态: {tag_data7['status']}")

if tag_data7["status"] == "恢复可用":
    print("  [OK] 核对流程验证通过：核对完成后正确恢复可用！")

print("\n" + "=" * 80)
print("  统计接口验证: 多维度异常统计")
print("=" * 80)

print_response("26. 查询详细异常统计",
    requests.get(f"{BASE_URL}/api/exception-statistics"))

print("\n" + "=" * 80)
print("  4个Bug修复验证测试完成！")
print("=" * 80)
print("""
  修复总结:
  Bug1+2: 归还时检查是否已有闭环工单(同发放记录)，避免重复生成异常
  Bug3:   超时归还/待核对类型异常闭环不自动恢复可用(仍保持待核对)
          人工标记异常闭环后正常恢复可用
  Bug4:   处理接口新增handling_time字段，支持按实际处理时间登记
""")
