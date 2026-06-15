import requests
import json
import sqlite3
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8125"
DB_PATH = "luggage_tags.db"


def pr(title, response):
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


def clean():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ticket_handle_records")
    cursor.execute("DELETE FROM tag_exception_tickets WHERE tag_code LIKE 'BUG-%'")
    cursor.execute("DELETE FROM tag_check_records WHERE tag_code LIKE 'BUG-%'")
    cursor.execute("DELETE FROM tag_issue_records WHERE tag_code LIKE 'BUG-%'")
    cursor.execute("DELETE FROM luggage_tags WHERE tag_code LIKE 'BUG-%'")
    conn.commit()
    conn.close()


print("=" * 80)
print("  异常寄物牌处置台账 - Bug修复验证测试")
print("=" * 80)

clean()

# ============================================================
# Bug1: 超时异常先完成核对后，异常台账会自动闭环，管理端再做处置登记会失败
# 预期修复：核对闭环后，关联异常工单仅更新为"处理中"，不自动闭环
# 管理端可以继续做处置登记（处理中→已闭环）
# ============================================================
print("\n" + "=" * 80)
print("  Bug1: 超时异常先核对闭环后，管理端仍可做处置登记")
print("=" * 80)

pr("1. 创建寄物牌 BUG-01", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "BUG-01", "area": "Bug测试区", "group_name": "测试组",
    "retention_hours": 1, "responsible_person": "测试责任人"
}))

pr("2. 发放 BUG-01", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "BUG-01", "user_name": "用户1", "user_contact": "13800000001"
}))

print("3. 模拟超时...")
simulate_overtime("BUG-01", hours_ago=6)

pr("4. 触发超时检测", requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUG-01"}))

pr("5. 归还超时的 BUG-01", requests.post(f"{BASE_URL}/api/tags/BUG-01/return", json={
    "return_note": "超时归还"
}))

pr("6. 核对并闭环", requests.post(f"{BASE_URL}/api/tags/BUG-01/check", json={
    "overtime_description": "用户逛街忘记归还",
    "handling_conclusion": "已口头警告",
    "check_person": "核对人-小张",
    "is_closed": 1
}))

ledgers = requests.get(f"{BASE_URL}/api/exception-ledgers", params={
    "tag_code": "BUG-01", "page_size": 10
}).json()

bug1_pass = True
if ledgers["items"]:
    ticket = ledgers["items"][0]
    ticket_id = ticket["id"]
    status = ticket["ticket_status"]
    print(f"\n  Bug1验证: 核对闭环后工单状态 = {status}")
    if status == "已闭环":
        print("  ✗ Bug1未修复！核对闭环后工单被自动闭环了")
        bug1_pass = False
    elif status == "处理中":
        print("  ✓ Bug1已修复！核对闭环后工单状态为处理中，管理端可继续处置")
    else:
        print(f"  ? Bug1状态异常: {status}")
        bug1_pass = False

    pr("7. 管理端处置登记 - 将处理中的工单闭环",
        requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id}/handle", json={
            "handling_conclusion": "管理端完成异常处置闭环",
            "handler": "管理员-王经理",
            "ticket_status": "已闭环"
        }))
else:
    print("  ✗ 未找到异常工单")
    bug1_pass = False

# ============================================================
# Bug2: 异常处置进度不保留历史过程，处理中的处理人/结论会被已闭环覆盖
# 预期修复：每次处置操作都写入ticket_handle_records，详情中展示完整历史
# ============================================================
print("\n" + "=" * 80)
print("  Bug2: 处置进度保留完整历史过程")
print("=" * 80)

pr("8. 创建寄物牌 BUG-02", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "BUG-02", "area": "Bug测试区", "group_name": "测试组",
    "retention_hours": 1, "responsible_person": "测试责任人"
}))

pr("9. 发放后归还(超时)", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "BUG-02", "user_name": "用户2", "user_contact": "13800000002"
}))

simulate_overtime("BUG-02", hours_ago=3)

pr("10. 归还", requests.post(f"{BASE_URL}/api/tags/BUG-02/return", json={
    "return_note": "超时归还"
}))

ledgers2 = requests.get(f"{BASE_URL}/api/exception-ledgers", params={
    "tag_code": "BUG-02", "page_size": 10
}).json()

bug2_pass = False
if ledgers2["items"]:
    ticket_id2 = ledgers2["items"][0]["id"]

    pr("11. 第一次处置: 待处理 → 处理中",
        requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id2}/handle", json={
            "handling_conclusion": "正在联系用户确认情况",
            "handler": "处理员-小李",
            "ticket_status": "处理中"
        }))

    pr("12. 核对闭环", requests.post(f"{BASE_URL}/api/tags/BUG-02/check", json={
        "overtime_description": "用户确认超时",
        "handling_conclusion": "已处理",
        "check_person": "核对人-小张",
        "is_closed": 1
    }))

    pr("13. 第二次处置: 处理中 → 已闭环",
        requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id2}/handle", json={
            "handling_conclusion": "管理端审批完成，异常闭环",
            "handler": "管理员-赵总",
            "ticket_status": "已闭环"
        }))

    detail = requests.get(f"{BASE_URL}/api/exception-tickets/{ticket_id2}/detail").json()

    print(f"\n  Bug2验证: 处置进度历史记录")
    handle_records = detail.get("handle_records", [])
    if len(handle_records) >= 2:
        for i, hr in enumerate(handle_records):
            print(f"    记录{i+1}: {hr['from_status']} → {hr['to_status']}, "
                  f"处理人={hr['handler']}, 结论={hr['handling_conclusion']}")

        first_handler = handle_records[0]["handler"]
        first_conclusion = handle_records[0]["handling_conclusion"]
        second_handler = handle_records[1]["handler"]
        second_conclusion = handle_records[1]["handling_conclusion"]

        if first_handler != second_handler or first_conclusion != second_conclusion:
            print("  ✓ Bug2已修复！不同处置阶段的处理人/结论被独立保留")
            bug2_pass = True
        else:
            print("  ✗ Bug2未修复！处理人/结论被覆盖了")
    else:
        print(f"  ✗ Bug2未修复！历史记录数量不正确: {len(handle_records)}")

    print(f"\n  Bug2验证: 处置进度展示")
    for i, p in enumerate(detail.get("processing_progress", [])):
        print(f"    阶段{i+1}: 状态={p['status']}, 处理人={p['handler']}, 结论={p['handling_conclusion']}")
else:
    print("  ✗ 未找到异常工单")

# ============================================================
# Bug3: 待核对异常可以不做核对直接闭环，导致核对流程被绕过
# 预期修复：超时归还/待核对类型工单闭环前，必须先完成核对且核对闭环
# ============================================================
print("\n" + "=" * 80)
print("  Bug3: 待核对异常不能绕过核对直接闭环")
print("=" * 80)

pr("14. 创建寄物牌 BUG-03", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "BUG-03", "area": "Bug测试区", "group_name": "测试组",
    "retention_hours": 1, "responsible_person": "测试责任人"
}))

pr("15. 发放后超时归还", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "BUG-03", "user_name": "用户3", "user_contact": "13800000003"
}))

simulate_overtime("BUG-03", hours_ago=4)

pr("16. 归还", requests.post(f"{BASE_URL}/api/tags/BUG-03/return", json={
    "return_note": "超时归还"
}))

ledgers3 = requests.get(f"{BASE_URL}/api/exception-ledgers", params={
    "tag_code": "BUG-03", "page_size": 10
}).json()

bug3_pass = False
if ledgers3["items"]:
    ticket_id3 = ledgers3["items"][0]["id"]

    resp_direct_close = requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id3}/handle", json={
        "handling_conclusion": "试图直接闭环",
        "handler": "违规操作员",
        "ticket_status": "已闭环"
    })

    print(f"\n  Bug3验证: 未核对直接闭环")
    if resp_direct_close.status_code == 409:
        error_data = resp_direct_close.json()
        print(f"  ✓ Bug3已修复！未核对直接闭环被拦截: {error_data.get('detail', {}).get('message', '')}")
        bug3_pass = True
    else:
        print(f"  ✗ Bug3未修复！未核对直接闭环成功了 (status={resp_direct_close.status_code})")

    pr("17. 核对但未闭环", requests.post(f"{BASE_URL}/api/tags/BUG-03/check", json={
        "overtime_description": "用户迟到",
        "handling_conclusion": "需要进一步跟进",
        "check_person": "核对人-小陈",
        "is_closed": 0
    }))

    resp_close_after_unclosed_check = requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id3}/handle", json={
        "handling_conclusion": "核对未闭环就试图闭环异常工单",
        "handler": "违规操作员",
        "ticket_status": "已闭环"
    })

    print(f"\n  Bug3验证: 核对未闭环时直接闭环异常工单")
    if resp_close_after_unclosed_check.status_code == 409:
        print("  ✓ Bug3已修复！核对未闭环时闭环异常工单被拦截")
    else:
        print(f"  ✗ Bug3未修复！核对未闭环时闭环成功了 (status={resp_close_after_unclosed_check.status_code})")

    pr("18. 核对闭环", requests.post(f"{BASE_URL}/api/tags/BUG-03/check", json={
        "overtime_description": "用户迟到(补充核对)",
        "handling_conclusion": "已闭环",
        "check_person": "核对人-小陈",
        "is_closed": 1
    }))

    pr("19. 核对闭环后，管理端可闭环异常工单",
        requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id3}/handle", json={
            "handling_conclusion": "核对已完成，管理端闭环",
            "handler": "管理员-王经理",
            "ticket_status": "已闭环"
        }))
else:
    print("  ✗ 未找到异常工单")

# ============================================================
# Bug4: 人工异常未闭环时，寄物牌列表/台账还是显示恢复可用，但是实际发放会被拦截
# 预期修复：创建人工标记异常时，寄物牌状态同步设为停用
# 闭环后恢复可用
# ============================================================
print("\n" + "=" * 80)
print("  Bug4: 人工标记异常未闭环时，寄物牌状态应同步为停用")
print("=" * 80)

pr("20. 创建寄物牌 BUG-04", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "BUG-04", "area": "Bug测试区", "group_name": "测试组",
    "retention_hours": 1, "responsible_person": "测试责任人"
}))

pr("21. 发放后归还(正常)", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "BUG-04", "user_name": "用户4", "user_contact": "13800000004"
}))

pr("22. 正常归还", requests.post(f"{BASE_URL}/api/tags/BUG-04/return", json={
    "return_note": "正常归还"
}))

tag_before = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUG-04"}).json()
print(f"\n  人工标记异常前，寄物牌状态: {tag_before['items'][0]['status']}")

pr("23. 人工标记异常", requests.post(f"{BASE_URL}/api/exception-tickets", json={
    "tag_code": "BUG-04",
    "exception_type": "人工标记异常",
    "exception_description": "寄物牌有裂痕需维修"
}))

tag_after = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUG-04"}).json()
tag_status_after = tag_after['items'][0]['status']
print(f"\n  Bug4验证: 人工标记异常后，寄物牌状态: {tag_status_after}")

bug4_pass = False
if tag_status_after == "停用":
    print("  ✓ Bug4已修复！人工标记异常后寄物牌状态同步为停用")
    bug4_pass = True
else:
    print(f"  ✗ Bug4未修复！状态为 {tag_status_after}，应该为停用")

pr("24. 尝试发放停用的寄物牌", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "BUG-04", "user_name": "新用户", "user_contact": "13800000099"
}))

ledgers4 = requests.get(f"{BASE_URL}/api/exception-ledgers", params={
    "tag_code": "BUG-04", "page_size": 10
}).json()

if ledgers4["items"]:
    ticket_id4 = ledgers4["items"][0]["id"]

    pr("25. 闭环人工标记异常", requests.put(f"{BASE_URL}/api/exception-tickets/{ticket_id4}/handle", json={
        "handling_conclusion": "寄物牌已维修完成",
        "handler": "维修组-张师傅",
        "ticket_status": "已闭环"
    }))

    tag_final = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "BUG-04"}).json()
    final_status = tag_final['items'][0]['status']
    print(f"\n  Bug4验证: 闭环后寄物牌状态: {final_status}")
    if final_status == "恢复可用":
        print("  ✓ Bug4已修复！闭环后寄物牌恢复可用")
    else:
        print(f"  ✗ Bug4闭环后状态异常: {final_status}")

    pr("26. 闭环后可正常发放", requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "BUG-04", "user_name": "新用户-钱先生", "user_contact": "13800000099"
    }))

# ============================================================
# 汇总
# ============================================================
print("\n" + "=" * 80)
print("  Bug修复验证结果汇总")
print("=" * 80)
results = {
    "Bug1: 核对闭环后管理端仍可处置登记": bug1_pass,
    "Bug2: 处置进度保留完整历史过程": bug2_pass,
    "Bug3: 待核对异常不能绕过核对直接闭环": bug3_pass,
    "Bug4: 人工标记异常后寄物牌同步停用": bug4_pass,
}

all_pass = True
for desc, passed in results.items():
    status = "✓ 已修复" if passed else "✗ 未修复"
    print(f"  {status} - {desc}")
    if not passed:
        all_pass = False

print(f"\n  总体结果: {'全部通过 ✓' if all_pass else '存在未修复项 ✗'}")
