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

print_response("1. 创建 TAG-004（保留时长1小时，用于测试超时）",
    requests.post(f"{BASE_URL}/api/tags", json={
        "tag_code": "TAG-004",
        "area": "C区",
        "group_name": "测试组",
        "retention_hours": 1,
        "responsible_person": "王五"
    }))

print_response("2. 发放 TAG-004",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "TAG-004",
        "user_name": "测试用户",
        "user_contact": "13000130000"
    }))

print_response("3. 模拟超时后归还 TAG-004（通过直接修改数据库方式验证，先看看当前状态）",
    requests.get(f"{BASE_URL}/api/tags", params={"tag_code": "TAG-004"}) if False else requests.get(f"{BASE_URL}/api/tags/4")
)

print_response("4. 手动归还 TAG-004（当前未超时，应该直接恢复可用）",
    requests.post(f"{BASE_URL}/api/tags/TAG-004/return", json={
        "return_note": "测试归还"
    }))

print_response("5. 查看 TAG-004 当前状态",
    requests.get(f"{BASE_URL}/api/tags/4")
)

print_response("6. 再次发放 TAG-004",
    requests.post(f"{BASE_URL}/api/tags/issue", json={
        "tag_code": "TAG-004",
        "user_name": "测试用户2",
        "user_contact": "13100131000"
    }))

print_response("7. 测试多条件筛选 - 按区域+状态",
    requests.get(f"{BASE_URL}/api/tags", params={
        "area": "A区",
        "status": "使用中"
    })
)

print_response("8. 测试多条件筛选 - 按责任人",
    requests.get(f"{BASE_URL}/api/tags", params={
        "responsible_person": "张三"
    })
)

print_response("9. 测试发放记录筛选 - 按是否超时",
    requests.get(f"{BASE_URL}/api/issue-records", params={
        "is_overtime": 0
    })
)

print_response("10. 测试停用寄物牌（需要先实现状态修改接口）",
    requests.put(f"{BASE_URL}/api/tags/4", json={
        "responsible_person": "王五"
    })
)

print("\n" + "="*60)
print("扩展测试完成！")
print("="*60)
