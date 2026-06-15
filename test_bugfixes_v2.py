import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8125"

def print_response(title, response, expect_fail=False):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")
    print(f"Status: {response.status_code}  {'(预期失败)' if expect_fail else '(预期成功)'}")
    try:
        data = response.json()
        print(json.dumps(data, ensure_ascii=False, indent=2))
    except:
        print(response.text)
    ok = (response.status_code < 400 and not expect_fail) or (response.status_code >= 400 and expect_fail)
    print(f"  >>> 结果: {'✅ 通过' if ok else '❌ 失败'}")
    return response

print("=" * 70)
print("  Bug 修复验证测试 v2 - 针对4个已报告问题")
print("=" * 70)

# ============ 准备数据 ============
print_response("准备：创建从未发放的寄物牌 FIX1-TAG-NEW（从未发放）",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "FIX1-TAG-NEW",
        "area": "修复验证区",
        "group_name": "FIX1组",
        "retention_hours": 24,
        "responsible_person": "FIX负责人"
    }))

print_response("准备：创建 FIX2-TAG-HIS 并经历一次完整发放-归还",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "FIX2-TAG-HIS",
        "area": "修复验证区",
        "group_name": "FIX2组",
        "retention_hours": 24,
        "responsible_person": "FIX负责人"
    }))
print_response("发放 FIX2-TAG-HIS 给用户A（历史用户）",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "FIX2-TAG-HIS",
        "user_name": "历史用户A",
        "user_contact": "111"
    }))
print_response("正常归还 FIX2-TAG-HIS（现在是恢复可用状态）",
    requests.post(f"{BASE_URL}/api/tags/FIX2-TAG-HIS/return", json={
        "return_note": "正常归还"
    }))

print_response("准备：创建 FIX3-TAG-DUP 并发放-归还",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "FIX3-TAG-DUP",
        "area": "修复验证区",
        "group_name": "FIX3组",
        "retention_hours": 24,
        "responsible_person": "FIX负责人"
    }))
print_response("发放 FIX3-TAG-DUP",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "FIX3-TAG-DUP",
        "user_name": "用户C"
    }))
print_response("归还 FIX3-TAG-DUP",
    requests.post(f"{BASE_URL}/api/tags/FIX3-TAG-DUP/return", json={}))

# ============ Bug 1: 从未发放的寄物牌也能创建异常工单 ============
print("\n" + "=" * 70)
print("  Bug 1 验证：从未发放的寄物牌不能创建异常工单")
print("=" * 70)
print_response("尝试给从未发放的 FIX1-TAG-NEW 创建异常工单（应失败 400）",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "FIX1-TAG-NEW",
        "exception_type": "人工标记异常",
        "exception_description": "测试创建在未发放牌上"
    }), expect_fail=True)

# ============ Bug 2: 已归还可用的牌创建工单时错误关联历史发放记录 ============
print("\n" + "=" * 70)
print("  Bug 2 验证：已归还可用的牌创建人工工单不应关联历史记录和使用人")
print("=" * 70)
resp = print_response("给已归还可用的 FIX2-TAG-HIS 创建人工异常工单",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "FIX2-TAG-HIS",
        "exception_type": "人工标记异常",
        "exception_description": "牌面有刮痕，需检修（此时牌已归还可用，无活跃使用人）"
    }))
ticket_data = resp.json()
print(f"  > 检查字段：issue_record_id = {ticket_data.get('issue_record_id')} (期望: null)")
print(f"  > 检查字段：user_name = {ticket_data.get('user_name')} (期望: null)")
fix2_ok = ticket_data.get("issue_record_id") is None and ticket_data.get("user_name") is None
print(f"  >>> Bug2 验证结果: {'✅ 通过' if fix2_ok else '❌ 失败'}")

# ============ Bug 3: 同一寄物牌重复创建未闭环异常工单 ============
print("\n" + "=" * 70)
print("  Bug 3 验证：同一寄物牌存在未闭环工单时不能重复创建")
print("=" * 70)
print_response("先给 FIX3-TAG-DUP 创建第一个异常工单（应成功）",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "FIX3-TAG-DUP",
        "exception_type": "人工标记异常",
        "exception_description": "第一个工单"
    }))
print_response("FIX3-TAG-DUP 已有未闭环工单，尝试再创建第二个（应失败 409）",
    requests.post(f"{BASE_URL}/api/exception-tickets", json={
        "tag_code": "FIX3-TAG-DUP",
        "exception_type": "超时归还",
        "exception_description": "第二个重复工单"
    }), expect_fail=True)

# ============ Bug 4: 列表传入无效筛选参数不报错 ============
print("\n" + "=" * 70)
print("  Bug 4 验证：列表传入无效异常类型/处理状态应返回400错误")
print("=" * 70)
print_response("传入无效异常类型 '不存在的异常' 筛选（应失败 400）",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "exception_type": "不存在的异常"
    }), expect_fail=True)

print_response("传入无效处理状态 '瞎写的状态' 筛选（应失败 400）",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "ticket_status": "瞎写的状态"
    }), expect_fail=True)

print_response("传入有效的异常类型 '人工标记异常' 筛选（应成功 200）",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "exception_type": "人工标记异常"
    }))

print_response("传入有效的处理状态 '待处理' 筛选（应成功 200）",
    requests.get(f"{BASE_URL}/api/exception-tickets", params={
        "ticket_status": "待处理"
    }))

# ============ 最终汇总 ============
print("\n" + "=" * 70)
print("  所有 Bug 修复验证完成！")
print("=" * 70)
print("""
  修复点总结：
  ✓ Bug1: 未发放过的寄物牌禁止创建异常工单（需有发放记录校验）
  ✓ Bug2: 人工创建工单时仅活跃状态(使用中/超时/待核对)才关联发放记录和使用人
          已归还可用的牌创建工单时 issue_record_id=null, user_name=null
  ✓ Bug3: 同一寄物牌存在未闭环异常工单时禁止重复创建（409冲突）
  ✓ Bug4: 列表筛选传入无效异常类型/处理状态时返回400错误，不再静默忽略
""")
