import requests
import json
from datetime import datetime, timedelta

BASE_URL = "http://localhost:8125"

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

print("=" * 60)
print("完整业务流程测试")
print("=" * 60)

print_response("1. 创建测试寄物牌 TAG-TEST-001",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "TAG-TEST-001",
        "area": "测试区",
        "group_name": "流程测试组",
        "retention_hours": 24,
        "responsible_person": "测试负责人"
    }))

print_response("2. 发放 TAG-TEST-001",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "TAG-TEST-001",
        "user_name": "流程测试用户",
        "user_contact": "13800000000"
    }))

print_response("3. 再次发放（应失败-使用中冲突）",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "TAG-TEST-001",
        "user_name": "另一个用户",
        "user_contact": "13900000000"
    }))

print_response("4. 正常归还 TAG-TEST-001",
    requests.post(f"{BASE_URL}/api/tags/TAG-TEST-001/return", json={
        "return_note": "按时归还，一切正常"
    }))

print_response("5. 验证状态为恢复可用",
    requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "TAG-TEST-001"}))

print_response("6. 手动设置为停用状态",
    requests.put(f"{BASE_URL}/api/tags/5/status", json={
        "status": "停用",
        "note": "测试停用"
    }))

print_response("7. 停用状态下尝试发放（应失败）",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "TAG-TEST-001",
        "user_name": "测试用户",
        "user_contact": "13700000000"
    }))

print_response("8. 从停用恢复为待发放",
    requests.put(f"{BASE_URL}/api/tags/5/status", json={
        "status": "待发放"
    }))

print_response("9. 测试超时归还场景 - 先发放一个短时长的",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "TAG-TEST-002",
        "area": "测试区",
        "group_name": "超时测试组",
        "retention_hours": 1,
        "responsible_person": "超时负责人"
    }))

print_response("10. 发放 TAG-TEST-002",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "TAG-TEST-002",
        "user_name": "超时测试用户",
        "user_contact": "13600000000"
    }))

print("\n" + "="*60)
print("提示：超时场景需要修改数据库模拟时间流逝，")
print("或者等待1小时后自动变为超时占用。")
print("下面测试核对记录和统计功能")
print("="*60)

print_response("11. 查询发放记录",
    requests.get(f"{BASE_URL}/api/issue-records"))

print_response("12. 统计数据",
    requests.get(f"{BASE_URL}/api/statistics"))

print_response("13. 自动预警",
    requests.get(f"{BASE_URL}/api/alerts"))

print_response("14. 多条件筛选测试 - 按区域和责任人",
    requests.get(f"{BASE_URL}/api/tags", params={
        "area": "测试区",
        "responsible_person": "测试负责人"
    }))

print("\n" + "="*60)
print("完整流程测试完成！")
print("="*60)
