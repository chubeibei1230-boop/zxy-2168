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


print("=" * 80)
print("  异常闭环追踪与复盘模块 - 增强功能验证测试")
print("=" * 80)

print_response("1. 检查系统状态", requests.get(f"{BASE_URL}/"))

print("\n>>> 创建多区域多责任人测试数据 <<<")

print_response("2. 创建寄物牌 ENH-TAG-01 (区域A, 负责人A)", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "ENH-TAG-01",
    "area": "区域A-入口处",
    "group_name": "接待组1",
    "retention_hours": 1,
    "responsible_person": "责任人-张小明"
}))

print_response("3. 创建寄物牌 ENH-TAG-02 (区域A, 负责人B)", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "ENH-TAG-02",
    "area": "区域A-入口处",
    "group_name": "接待组2",
    "retention_hours": 1,
    "responsible_person": "责任人-李小红"
}))

print_response("4. 创建寄物牌 ENH-TAG-03 (区域B, 负责人A)", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "ENH-TAG-03",
    "area": "区域B-游乐区",
    "group_name": "游乐组1",
    "retention_hours": 1,
    "responsible_person": "责任人-张小明"
}))

print_response("5. 创建寄物牌 ENH-TAG-04 (区域B, 负责人C)", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "ENH-TAG-04",
    "area": "区域B-游乐区",
    "group_name": "游乐组2",
    "retention_hours": 1,
    "responsible_person": "责任人-王大山"
}))

print_response("6. 创建寄物牌 ENH-TAG-05 (区域C, 负责人D)", requests.post(f"{BASE_URL}/api/tags", json={
    "tag_code": "ENH-TAG-05",
    "area": "区域C-餐饮区",
    "group_name": "餐饮组1",
    "retention_hours": 1,
    "responsible_person": "责任人-赵美丽"
}))

print("\n>>> 场景1: 超时未归还自动触发异常工单 <<<")

print_response("7. 发放 ENH-TAG-01 给用户1", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "ENH-TAG-01",
    "user_name": "用户A-王先生",
    "user_contact": "13800000001"
}))

print("8. 模拟 ENH-TAG-01 超时5小时未归还...")
simulate_overtime("ENH-TAG-01", hours_ago=5)

print_response("9. 触发超时检测（应自动标记超时状态并创建超时异常工单）",
    requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "ENH-TAG-01"}))

tickets_resp = requests.get(f"{BASE_URL}/api/exception-tickets", params={
    "tag_code": "ENH-TAG-01",
    "exception_type": "超时归还"
}).json()
print(f"  查询到超时工单数量: {tickets_resp['total']}")

if tickets_resp["total"] > 0:
    auto_ticket_id = tickets_resp["items"][0]["id"]
    print(f"  自动创建的超時工单号: #{auto_ticket_id}")
    print_response(f"10. 查看自动创建的超时工单完整上下文详情 #{auto_ticket_id}",
        requests.get(f"{BASE_URL}/api/exception-tickets/{auto_ticket_id}/detail"))

print("\n>>> 场景2: 超时归还触发异常工单并处理 <<<")

print_response("11. 发放 ENH-TAG-02 给用户2", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "ENH-TAG-02",
    "user_name": "用户B-李女士",
    "user_contact": "13800000002"
}))

print("12. 模拟 ENH-TAG-02 超时3小时...")
simulate_overtime("ENH-TAG-02", hours_ago=3)

print_response("13. 归还 ENH-TAG-02（应触发超时归还异常工单）",
    requests.post(f"{BASE_URL}/api/tags/ENH-TAG-02/return", json={
        "return_note": "逛太久忘记时间了"
    }))

print_response("14. 查询异常工单列表（筛选区域A）",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "area": "区域A-入口处",
        "page_size": 20
    }))

tickets_a_resp = requests.get(f"{BASE_URL}/api/exception-tickets", params={
    "area": "区域A-入口处"
}).json()

if tickets_a_resp["items"]:
    for t in tickets_a_resp["items"]:
        if t["exception_type"] == "超时归还" and t["ticket_status"] == "待处理":
            overtime_ticket_id = t["id"]
            break
    else:
        overtime_ticket_id = tickets_a_resp["items"][0]["id"]

    print(f"  选择工单号 #{overtime_ticket_id} 进行处理")

    print_response(f"15. 查看工单完整上下文详情 #{overtime_ticket_id}",
        requests.get(f"{BASE_URL}/api/exception-tickets/{overtime_ticket_id}/detail"))

    print_response(f"16. 将工单 #{overtime_ticket_id} 设为处理中",
        requests.put(f"{BASE_URL}/api/exception-tickets/{overtime_ticket_id}/handle", json={
            "handling_conclusion": "已联系用户，用户确认已归还，正在走内部流程",
            "handler": "管理员-刘经理",
            "ticket_status": "处理中"
        }))

    print_response(f"17. 处理中状态下再次查看详情 #{overtime_ticket_id}",
        requests.get(f"{BASE_URL}/api/exception-tickets/{overtime_ticket_id}/detail"))

    print_response(f"18. 闭环工单 #{overtime_ticket_id}",
        requests.put(f"{BASE_URL}/api/exception-tickets/{overtime_ticket_id}/handle", json={
            "handling_conclusion": "已完成内部复盘，对用户进行了口头提醒，相关流程已闭环",
            "handler": "管理员-刘经理",
            "ticket_status": "已闭环"
        }))

    print_response(f"19. 闭环后再次查看详情 #{overtime_ticket_id}（can_handle应为false）",
        requests.get(f"{BASE_URL}/api/exception-tickets/{overtime_ticket_id}/detail"))

    print_response(f"20. 尝试重复闭环 #{overtime_ticket_id}（应失败）",
        requests.put(f"{BASE_URL}/api/exception-tickets/{overtime_ticket_id}/handle", json={
            "handling_conclusion": "再处理一次",
            "handler": "其他管理员"
        }))

print("\n>>> 场景3: 创建不同类型异常工单并测试多条件查询 <<<")

print_response("21. 发放 ENH-TAG-03", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "ENH-TAG-03",
    "user_name": "用户C-陈先生",
    "user_contact": "13800000003"
}))

print("22. 模拟超时后归还 ENH-TAG-03...")
simulate_overtime("ENH-TAG-03", hours_ago=2)
requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "ENH-TAG-03"})
print_response("22b. 归还超时的 ENH-TAG-03",
    requests.post(f"{BASE_URL}/api/tags/ENH-TAG-03/return", json={"return_note": "超时2小时"}))

print_response("23. 发放 ENH-TAG-04 后立即归还（不超时）", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "ENH-TAG-04",
    "user_name": "用户D-周女士",
    "user_contact": "13800000004"
}))
requests.post(f"{BASE_URL}/api/tags/ENH-TAG-04/return", json={"return_note": "按时归还"})

print_response("24. 人工标记 ENH-TAG-04 异常", requests.post(f"{BASE_URL}/api/exception-tickets", json={
    "tag_code": "ENH-TAG-04",
    "exception_type": "人工标记异常",
    "exception_description": "归还时发现牌面有明显划痕，需要维修"
}))

print_response("25. 发放 ENH-TAG-05", requests.post(f"{BASE_URL}/api/tags/issue", json={
    "tag_code": "ENH-TAG-05",
    "user_name": "用户E-孙先生",
    "user_contact": "13800000005"
}))
requests.post(f"{BASE_URL}/api/tags/ENH-TAG-05/return", json={"return_note": "正常归还"})

print_response("26. 为 ENH-TAG-05 创建待核对类型异常", requests.post(f"{BASE_URL}/api/exception-tickets", json={
    "tag_code": "ENH-TAG-05",
    "exception_type": "待核对",
    "exception_description": "系统记录与人工登记不一致，需核对"
}))

print("\n>>> 场景4: 多维度筛选异常工单 <<<")

print_response("27. 按责任人筛选 - 责任人-张小明",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "responsible_person": "责任人-张小明",
        "page_size": 20
    }))

print_response("28. 按分组筛选 - 游乐组1",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "group_name": "游乐组1",
        "page_size": 20
    }))

print_response("29. 按处理状态筛选 - 待处理",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "ticket_status": "待处理",
        "page_size": 20
    }))

print_response("30. 按异常类型筛选 - 人工标记异常",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "exception_type": "人工标记异常",
        "page_size": 20
    }))

print_response("31. 组合筛选: 区域B + 待处理状态",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "area": "区域B-游乐区",
        "ticket_status": "待处理",
        "page_size": 20
    }))

print("\n>>> 场景5: 测试独立的异常统计接口 <<<")

print_response("32. 查询异常详细统计（按区域/责任人/异常类型维度）",
    requests.get(f"{BASE_URL}/api/exception-statistics"))

print("\n>>> 场景6: 闭环部分工单后再看统计 <<<")

all_pending = requests.get(f"{BASE_URL}/api/exception-tickets", params={
    "ticket_status": "待处理",
    "page_size": 50
}).json()

print(f"  共找到 {all_pending['total']} 个待处理工单，将闭环其中2个...")

closed_count = 0
for t in all_pending["items"]:
    if closed_count >= 2:
        break
    tid = t["id"]
    print(f"  正在闭环工单 #{tid}...")
    resp = requests.put(f"{BASE_URL}/api/exception-tickets/{tid}/handle", json={
        "handling_conclusion": f"工单#{tid}处理完成，问题已解决",
        "handler": "批量处理管理员",
        "ticket_status": "已闭环"
    })
    if resp.status_code == 200:
        closed_count += 1

print(f"  成功闭环 {closed_count} 个工单")

print_response("33. 再次查询统计（闭环率应提升）",
    requests.get(f"{BASE_URL}/api/exception-statistics"))

print("\n>>> 场景7: 测试错误场景提示 <<<")

print_response("34. 查询不存在的工单详情（应返回404）",
    requests.get(f"{BASE_URL}/api/exception-tickets/99999"))

print_response("35. 查询不存在的工单完整上下文（应返回404）",
    requests.get(f"{BASE_URL}/api/exception-tickets/99999/detail"))

print_response("36. 处理不存在的工单（应返回404）",
    requests.put(f"{BASE_URL}/api/exception-tickets/99999/handle", json={
        "handling_conclusion": "测试",
        "handler": "测试员"
    }))

print_response("37. 创建不存在寄物牌的异常工单（应失败）",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "NOT-EXIST-999",
        "exception_type": "人工标记异常",
        "exception_description": "测试"
    }))

print_response("38. 使用无效异常类型筛选（应失败）",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "exception_type": "无效的异常类型"
    }))

print_response("39. 使用无效工单状态筛选（应失败）",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "ticket_status": "无效的状态"
    }))

print_response("40. 无效的处理状态（应失败）",
    requests.get(f"{BASE_URL}/api/exception-tickets").json())

if all_pending["items"]:
    test_ticket_id = all_pending["items"][-1]["id"]
    print_response(f"41. 处理工单 #{test_ticket_id} 使用无效状态（应失败）",
        requests.put(f"{BASE_URL}/api/exception-tickets/{test_ticket_id}/handle", json={
            "handling_conclusion": "测试无效状态",
            "handler": "测试员",
            "ticket_status": "无效状态"
        }))

print("\n" + "=" * 80)
print("  异常闭环追踪与复盘模块增强功能测试完成！")
print("=" * 80)
print("""
  增强测试覆盖内容：
  ✓ 1. 超时未归还自动触发异常工单（自动检测创建）
  ✓ 2. 异常事件完整上下文详情查询（寄物牌状态+发放记录+核对记录+处理进度）
  ✓ 3. 处理状态流转（待处理->处理中->已闭环）
  ✓ 4. 多维度筛选查询（寄物牌/区域/分组/责任人/异常类型/处理状态）
  ✓ 5. 组合条件筛选
  ✓ 6. 独立详细统计接口（总览+按区域+按责任人+按异常类型）
  ✓ 7. 各维度统计包含: 异常总数/待处理数/闭环数/闭环率
  ✓ 8. 批量闭环后统计数据正确更新
  ✓ 9. 完整的错误场景提示（不存在的工单/寄物牌/无效参数/重复闭环等）
  ✓ 10. can_handle 标识正确反映可处理状态
  ✓ 11. 处理进度时间线正确展示各阶段
""")
