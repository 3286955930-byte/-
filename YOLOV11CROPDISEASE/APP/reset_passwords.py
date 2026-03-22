import os
import json
from werkzeug.security import generate_password_hash

# 获取当前文件所在目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 用户账号和密码
users = {
    "admin": {
        "password": "123456",
        "role": "admin"
    },
    "农技员1": {
        "password": "nongji123",
        "role": "technician"
    },
    "农户1": {
        "password": "nonghu123",
        "role": "user"
    },
    "test": {
        "password": "123456",
        "role": "user"
    }
}

# 生成哈希密码
for username, user_data in users.items():
    users[username]['password'] = generate_password_hash(user_data['password'])

# 保存到文件
users_path = os.path.join(BASE_DIR, 'users.json')
with open(users_path, 'w', encoding='utf-8') as f:
    json.dump(users, f, ensure_ascii=False, indent=2)

print("密码重置成功！")
print("新的用户数据:")
print(json.dumps(users, ensure_ascii=False, indent=2))
