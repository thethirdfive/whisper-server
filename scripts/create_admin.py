"""首次启动时创建管理员账号 - 幂等

从环境变量读取 ADMIN_* 配置，如果数据库里没有该用户就插入。
密码已经是 bcrypt 哈希，直接存。
"""
import os
import sys
from datetime import datetime

# 让本脚本能被 docker exec 直接调用
sys.path.insert(0, "/app")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import User


def main() -> None:
    db_url = os.getenv("DATABASE_URL", "sqlite:////data/whisper/db/whisper.db")
    username = os.getenv("ADMIN_USERNAME", "ethan").strip()
    email = os.getenv("ADMIN_EMAIL", "").strip() or None
    display_name = os.getenv("ADMIN_DISPLAY_NAME", username).strip()
    password_hash = os.getenv("ADMIN_PASSWORD_BCRYPT", "").strip()

    if not password_hash:
        print("❌ ADMIN_PASSWORD_BCRYPT 未设置，跳过管理员创建")
        return

    if not password_hash.startswith("$2"):
        print("❌ ADMIN_PASSWORD_BCRYPT 看起来不是 bcrypt 哈希（应以 $2b$ 开头）")
        print("   生成方式：python -c 'import bcrypt; print(bcrypt.hashpw(b\"你的密码\", bcrypt.gensalt(12)).decode())'")
        sys.exit(1)

    engine = create_engine(db_url)

    with Session(engine) as session:
        existing = session.execute(
            select(User).where(User.username == username)
        ).scalar_one_or_none()

        if existing:
            print(f"✓ 管理员 {username} 已存在，跳过创建")
            # 但如果 role 不是 admin，自动提升
            if existing.role != "admin":
                existing.role = "admin"
                session.commit()
                print(f"  → 已提升角色为 admin")
            return

        user = User(
            username=username,
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            role="admin",
            locale=os.getenv("APP_DEFAULT_LOCALE", "zh-CN"),
            created_at=datetime.utcnow(),
        )
        session.add(user)
        session.commit()
        print(f"✅ 已创建管理员账号：{username} (id={user.id})")


if __name__ == "__main__":
    main()
