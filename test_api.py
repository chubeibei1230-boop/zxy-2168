import requests
import json

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

print_response("1. 系统根接口", requests.get(f"{BASE_URL}/"))

print_response("2. 获取状态选项", requests.get(f"{BASE_URL}/api/status-options"))

tag_data = {
    "tag_code": "TAG-001",
    "area": "A区",
    "group_name": "标准组",
    "retention_hours": 24,
    "responsible_person": "张三"
}
print_response("3. 创建寄物牌 TAG-001", requests.post(f"{BASE_URL}/api/tags", json=tag_data))

tag_data2 = {
    "tag_code": "TAG-002",
    "area": "A区",
    "group_name": "标准组",
    "retention_hours": 2,
    "responsible_person": "张三"
}
print_response("4. 创建寄物牌 TAG-002", requests.post(f"{BASE_URL}/api/tags", json=tag_data2))

tag_data3 = {
    "tag_code": "TAG-003",
    "area": "B区",
    "group_name": "VIP组",
    "retention_hours": 48,
    "responsible_person": "李四"
}
print_response("5. 创建寄物牌 TAG-003", requests.post(f"{BASE_URL}/api/tags", json=tag_data3))

print_response("6. 获取寄物牌列表", requests.get(f"{BASE_URL}/api/tags"))

issue_data = {
    "tag_code": "TAG-001",
    "user_name": "王小明",
    "user_contact": "13800138000"
}
print_response("7. 发放寄物牌 TAG-001", requests.post(f"{BASE_URL}/api/tags/issue", json=issue_data))

print_response("8. 再次发放 TAG-001（应该失败-使用中）", requests.post(f"{BASE_URL}/api/tags/issue", json=issue_data))

issue_data2 = {
    "area": "B区",
    "user_name": "赵小红",
    "user_contact": "13900139000"
}
print_response("9. 按区域发放 B 区寄物牌", requests.post(f"{BASE_URL}/api/tags/issue", json=issue_data2))

return_data = {
    "return_note": "正常归还"
}
print_response("10. 归还 TAG-001", requests.post(f"{BASE_URL}/api/tags/TAG-001/return", json=return_data))

print_response("11. 查看寄物牌列表（筛选状态=恢复可用）", 
    requests.get(f"{BASE_URL}/api/tags", params={"status": "恢复可用"}))

print_response("12. 获取发放记录列表", requests.get(f"{BASE_URL}/api/issue-records"))

print_response("13. 统计数据", requests.get(f"{BASE_URL}/api/statistics"))

print_response("14. 自动预警", requests.get(f"{BASE_URL}/api/alerts"))

print("\n" + "="*60)
print("测试完成！")
print("="*60)
