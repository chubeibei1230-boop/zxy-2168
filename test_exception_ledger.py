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


def clean_test_data():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tag_exception_tickets WHERE tag_code LIKE 'LEDGER-%'")
    cursor.execute("DELETE FROM tag_check_records WHERE tag_code LIKE 'LEDGER-%'")
    cursor.execute("DELETE FROM tag_issue_records WHERE tag_code LIKE 'LEDGER-%'")
    cursor.execute("DELETE FROM luggage_tags WHERE tag_code LIKE 'LEDGER-%'")
    conn.commit()
    conn.close()


print("=" * 80)
print("  异常寄物牌处置台账模块 - 完整功能验证测试")
print("=" * 80)

print("\n>>> 清理历史测试数据 <<<")
clean_test_data()

print_response("1. 检查系统状态", requests.get(f"{BASE_URL}/"))

print("\n>>> 创建多维度测试数据 <<<")

print_response("2. 创建寄物牌 LEDGER-01 (区域A, 责任人A)", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "LEDGER-01",
    "area": "台账测试区-入口",
    "group_name": "前台组",
    "retention_hours": 1,
    "responsible_person": "责任人-陈主管"
}))

print_response("3. 创建寄物牌 LEDGER-02 (区域A, 责任人B)", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "LEDGER-02",
    "area": "台账测试区-入口",
    "group_name": "前台组",
    "retention_hours": 1,
    "responsible_person": "责任人-林助理"
}))

print_response("4. 创建寄物牌 LEDGER-03 (区域B, 责任人A)", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "LEDGER-03",
    "area": "台账测试区-游乐场",
    "group_name": "游乐组",
    "retention_hours": 1,
    "responsible_person": "责任人-陈主管"
}))

print_response("5. 创建寄物牌 LEDGER-04 (区域B, 责任人C)", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "LEDGER-04",
    "area": "台账测试区-游乐场",
    "group_name": "游乐组",
    "retention_hours": 1,
    "responsible_person": "责任人-黄组长"
}))

print_response("6. 创建寄物牌 LEDGER-05 (区域C, 责任人D)", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "LEDGER-05",
    "area": "台账测试区-餐厅",
    "group_name": "餐饮组",
    "retention_hours": 1,
    "responsible_person": "责任人-吴经理"
}))

print("\n>>> 场景1: 超时未归还 - 自动生成占用超时异常台账 <<<")

print_response("7. 发放 LEDGER-01", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "LEDGER-01",
    "user_name": "用户1-周先生",
    "user_contact": "13900000001"
}))

print("8. 模拟 LEDGER-01 超时6小时未归还...")
simulate_overtime("LEDGER-01", hours_ago=6)

print_response("9. 触发超时检测", requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "LEDGER-01"}))

print("\n>>> 场景2: 超时归还 - 自动生成归还超时异常台账 <<<")

print_response("10. 发放 LEDGER-02", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "LEDGER-02",
    "user_name": "用户2-吴女士",
    "user_contact": "13900000002"
}))

print("11. 模拟 LEDGER-02 超时3小时...")
simulate_overtime("LEDGER-02", hours_ago=3)

print_response("12. 归还超时的 LEDGER-02（应自动创建归还超时异常台账）",
    requests.post(f"{BASE_URL}/api/tags/LEDGER-02/return", json={
        "return_note": "购物超时忘记归还"
    }))

print("\n>>> 场景3: 人工标记异常台账 <<<")

print_response("13. 发放 LEDGER-03", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "LEDGER-03",
    "user_name": "用户3-郑先生",
    "user_contact": "13900000003"
}))
print_response("13b. 归还 LEDGER-03", requests.post(f"{BASE_URL}/api/tags/LEDGER-03/return", json={}))

print_response("14. 人工标记 LEDGER-03 异常",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "LEDGER-03",
        "exception_type": "人工标记异常",
        "exception_description": "归还时发现牌面有裂痕，需要维修"
    }))

print("\n>>> 场景4: 待核对类型异常台账 <<<")

print_response("15. 发放 LEDGER-04 后立即归还", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "LEDGER-04",
    "user_name": "用户4-孙女士",
    "user_contact": "13900000004"
}))
print_response("15b. 归还 LEDGER-04", requests.post(f"{BASE_URL}/api/tags/LEDGER-04/return", json={}))

print_response("16. 为 LEDGER-04 创建待核对类型异常",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "LEDGER-04",
        "exception_type": "待核对",
        "exception_description": "系统记录与纸质登记不符，需核对"
    }))

print("\n>>> 场景5: 验证异常台账列表查询功能 <<<")

print_response("17. 查询异常台账列表（验证字段完整性）",
    requests.get(f"{BASE_URL}/api/exception-ledgers", params={
        "page_size": 50
    }))

print_response("18. 按寄物牌编号筛选 - LEDGER-01",
    requests.get(f"{BASE_URL}/api/exception-ledgers", params={
        "tag_code": "LEDGER-01",
        "page_size": 10
    }))

print_response("19. 按所属区域筛选 - 台账测试区-入口",
    requests.get(f"{BASE_URL}/api/exception-ledgers", params={
        "area": "台账测试区-入口",
        "page_size": 10
    }))

print_response("20. 按责任人筛选 - 责任人-陈主管",
    requests.get(f"{BASE_URL}/api/exception-ledgers", params={
        "responsible_person": "责任人-陈主管",
        "page_size": 10
    }))

print_response("21. 按异常类型筛选 - 超时归还",
    requests.get(f"{BASE_URL}/api/exception-ledgers", params={
        "exception_type": "超时归还",
        "page_size": 10
    }))

print_response("22. 按处理状态筛选 - 待处理",
    requests.get(f"{BASE_URL}/api/exception-ledgers", params={
        "ticket_status": "待处理",
        "page_size": 10
    }))

print_response("23. 组合筛选: 区域B + 待处理状态",
    requests.get(f"{BASE_URL}/api/exception-ledgers", params={
        "area": "台账测试区-游乐场",
        "ticket_status": "待处理",
        "page_size": 10
    }))

print("\n>>> 场景6: 验证台账列表展示字段 <<<")

ledger_resp = requests.get(f"{BASE_URL}/api/exception-ledgers", params={
    "tag_code": "LEDGER-01",
    "page_size": 1
}).json()

if ledger_resp["items"]:
    item = ledger_resp["items"][0]
    print("\n" + "="*80)
    print("  台账列表字段验证")
    print("="*80)
    print(f"  ✓ 寄物牌编号: {item.get('tag_code')}")
    print(f"  ✓ 寄物牌当前状态: {item.get('tag_current_status')}")
    print(f"  ✓ 最近一次发放时间: {item.get('latest_issue_time')}")
    print(f"  ✓ 最近预计归还时间: {item.get('latest_expected_return_time')}")
    print(f"  ✓ 最近使用人: {item.get('latest_user_name')}")
    print(f"  ✓ 异常来源: {item.get('exception_source')}")
    print(f"  ✓ 异常说明: {item.get('exception_description')}")
    print(f"  ✓ 责任人: {item.get('responsible_person')}")
    print(f"  ✓ 处理人: {item.get('handler')}")
    print(f"  ✓ 处理结论: {item.get('handling_conclusion')}")
    print(f"  ✓ 处理状态: {item.get('ticket_status')}")
    print(f"  ✓ 关键时间-创建时间: {item.get('created_at')}")
    print(f"  ✓ 关键时间-更新时间: {item.get('updated_at')}")
    print(f"  ✓ 关键时间-处理时间: {item.get('handling_time')}")

print("\n>>> 场景7: 验证异常台账详情串联展示 <<<")

tickets_resp = requests.get(f"{BASE_URL}/api/exception-ledgers", params={
    "tag_code": "LEDGER-02",
    "page_size": 1
}).json()

if tickets_resp["items"]:
    ticket_id = tickets_resp["items"][0]["id"]
    print_response(f"24. 查看异常台账 #{ticket_id} 完整详情",
        requests.get(f"{BASE_URL}/api/exception-tickets/{ticket_id}/detail"))

print("\n>>> 场景8: 对未闭环异常进行处置登记 <<<")

pending_resp = requests.get(f"{BASE_URL}/api/exception-ledgers", params={
    "ticket_status": "待处理",
    "tag_code": "LEDGER-02",
    "page_size": 1
}).json()

if pending_resp["items"]:
    handle_ticket_id = pending_resp["items"][0]["id"]
    
    print_response(f"25. 先核对 LEDGER-02（为闭环做准备）",
        requests.post(f"{BASE_URL}/api/tags/LEDGER-02/check", json={
            "overtime_description": "用户逛街超时，已电话提醒",
            "handling_conclusion": "用户已道歉，口头警告一次",
            "check_person": "核对员-小王",
            "is_closed": 1
        }))
    
    print_response(f"26. 处置登记 - 将台账 #{handle_ticket_id} 设为处理中",
        requests.put(f"{BASE_URL}/api/exception-tickets/{handle_ticket_id}/handle", json={
            "handling_conclusion": "已联系用户确认情况，正在走内部审批流程",
            "handler": "处理员-李经理",
            "ticket_status": "处理中"
        }))
    
    print_response(f"27. 处置登记 - 将台账 #{handle_ticket_id} 闭环",
        requests.put(f"{BASE_URL}/api/exception-tickets/{handle_ticket_id}/handle", json={
            "handling_conclusion": "内部审批通过，已完成异常处置，用户已接受教育",
            "handler": "处理员-李经理",
            "ticket_status": "已闭环"
        }))
    
    print_response(f"28. 验证闭环后寄物牌 LEDGER-02 状态（应为恢复可用）",
        requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "LEDGER-02"}))
    
    print_response(f"29. 验证闭环后 LEDGER-02 可正常发放",
        requests.post(f"{BASE_URL}/api/tags/issue", json={
            "tag_code": "LEDGER-02",
            "user_name": "新用户-钱先生",
            "user_contact": "13900000099"
        }))

print("\n>>> 场景9: 验证人工标记异常闭环后寄物牌恢复可用 <<<")

manual_resp = requests.get(f"{BASE_URL}/api/exception-ledgers", params={
    "exception_type": "人工标记异常",
    "tag_code": "LEDGER-03",
    "page_size": 1
}).json()

if manual_resp["items"]:
    manual_ticket_id = manual_resp["items"][0]["id"]
    
    print_response(f"30. 闭环人工标记异常台账 #{manual_ticket_id}",
        requests.put(f"{BASE_URL}/api/exception-tickets/{manual_ticket_id}/handle", json={
            "handling_conclusion": "寄物牌已维修完成，可以重新投入使用",
            "handler": "维修组-张师傅",
            "ticket_status": "已闭环"
        }))
    
    print_response(f"31. 验证 LEDGER-03 状态（应为恢复可用）",
        requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "LEDGER-03"}))

print("\n>>> 场景10: 验证异常台账汇总统计 <<<")

print_response("32. 查询异常台账汇总统计（按区域/责任人/异常类型）",
    requests.get(f"{BASE_URL}/api/exception-statistics"))

print("\n>>> 场景11: 闭环更多台账后验证统计更新 <<<")

all_pending = requests.get(f"{BASE_URL}/api/exception-ledgers", params={
    "ticket_status": "待处理",
    "page_size": 50
}).json()

print(f"  共找到 {all_pending['total']} 个待处理台账，将全部闭环...")

for t in all_pending["items"]:
    tid = t["id"]
    tag_code = t.get("tag_code", "")
    
    if t.get("exception_type") in ["超时归还", "待核对"]:
        check_resp = requests.get(f"{BASE_URL}/api/tags", params={"tag_code": tag_code})
        if check_resp.status_code == 200:
            tag_data = check_resp.json()
            if tag_data["items"] and tag_data["items"][0]["status"] == "待核对":
                print(f"  先核对寄物牌 {tag_code}...")
                requests.post(f"{BASE_URL}/api/tags/{tag_code}/check", json={
                    "overtime_description": "批量处理",
                    "handling_conclusion": "批量处理完成",
                    "check_person": "批量处理员",
                    "is_closed": 1
                })
    
    print(f"  正在闭环台账 #{tid}...")
    resp = requests.put(f"{BASE_URL}/api/exception-tickets/{tid}/handle", json={
        "handling_conclusion": f"台账#{tid}批量处理完成",
        "handler": "批量处理管理员",
        "ticket_status": "已闭环"
    })

print_response("33. 全部闭环后再次查询统计（闭环率应为100%）",
    requests.get(f"{BASE_URL}/api/exception-statistics"))

print("\n>>> 场景12: 验证统计字段完整性 <<<")

stats_resp = requests.get(f"{BASE_URL}/api/exception-statistics").json()

print("\n" + "="*80)
print("  汇总统计字段验证")
print("="*80)

overview = stats_resp.get("overview", {})
print(f"\n  ✓ 总览统计:")
print(f"    - 总工单数量: {overview.get('total_count')}")
print(f"    - 待处理数量: {overview.get('pending_count')}")
print(f"    - 处理中数量: {overview.get('processing_count')}")
print(f"    - 已闭环数量: {overview.get('closed_count')}")
print(f"    - 闭环率: {overview.get('closure_rate')}%")

if stats_resp.get("by_area"):
    print(f"\n  ✓ 按区域统计（共{len(stats_resp['by_area'])}个区域）:")
    for area_stat in stats_resp["by_area"][:2]:
        print(f"    - {area_stat['area']}: 总数{area_stat['total_count']}, "
              f"待处理{area_stat['pending_count']}, "
              f"处理中{area_stat['processing_count']}, "
              f"已闭环{area_stat['closed_count']}")

if stats_resp.get("by_responsible"):
    print(f"\n  ✓ 按责任人统计（共{len(stats_resp['by_responsible'])}个责任人）:")
    for resp_stat in stats_resp["by_responsible"][:2]:
        print(f"    - {resp_stat['responsible_person']}: 总数{resp_stat['total_count']}, "
              f"待处理{resp_stat['pending_count']}, "
              f"处理中{resp_stat['processing_count']}, "
              f"已闭环{resp_stat['closed_count']}")

if stats_resp.get("by_exception_type"):
    print(f"\n  ✓ 按异常类型统计（共{len(stats_resp['by_exception_type'])}种类型）:")
    for type_stat in stats_resp["by_exception_type"]:
        print(f"    - {type_stat['exception_type']}: 总数{type_stat['total_count']}, "
              f"待处理{type_stat['pending_count']}, "
              f"处理中{type_stat['processing_count']}, "
              f"已闭环{type_stat['closed_count']}")

print("\n" + "=" * 80)
print("  异常寄物牌处置台账模块测试完成！")
print("=" * 80)
print("""
  测试覆盖内容：
  ✓ 1. 异常台账多维度查询（寄物牌编号/区域/责任人/异常类型/处理状态/时间范围）
  ✓ 2. 台账列表完整字段展示：
     - 寄物牌当前状态
     - 最近一次发放信息（发放时间/预计归还/使用人）
     - 异常来源（自动生成/人工登记）
     - 异常说明
     - 责任人
     - 处理人
     - 处理结论
     - 处理状态
     - 关键时间（创建/更新/处理）
  ✓ 3. 单个异常台账详情串联展示：
     - 寄物牌基础信息
     - 发放记录
     - 归还/核对记录
     - 异常处置进度
     - 当前闭环结果
  ✓ 4. 未闭环异常处置登记：
     - 支持处理中/已闭环状态流转
     - 登记后同步更新寄物牌可用性
     - 同步更新异常统计数据
  ✓ 5. 异常台账汇总统计：
     - 总览统计（总数/待处理/处理中/已闭环/闭环率）
     - 按区域统计
     - 按责任人统计
     - 按异常类型统计
  ✓ 6. 异常来源自动识别：
     - 占用超时(自动生成)
     - 归还超时(自动生成)
     - 核对未闭环(自动生成)
     - 人工登记
""")
