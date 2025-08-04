import pymysql
import time

# 数据库配置
DB_CONFIG = {
    "host": "little2net.i234.me",
    "user": "telebot",
    "password": "GB]RcWbK9EQOxcdv",
    "database": "telebot",
    "charset": "utf8mb4",
    
    "port":58736
}




BATCH_SIZE = 1000


def migrate_data():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()

    last_id = 317828  # 从 ID > 0 开始处理

    while True:
        print(f"🚚 Migrating batch where id > {last_id}")

        # 查询一批数据
        cursor.execute(f"""
            SELECT id, file_type, file_unique_id, file_id, bot, user_id, create_time
            FROM file_extension
            WHERE id > %s
            ORDER BY id
            LIMIT %s
        """, (last_id, BATCH_SIZE))

        rows = cursor.fetchall()
        if not rows:
            print("✅ Migration complete.")
            break

        # 插入新表（避免重复，自动跳过）
        for row in rows:
            id, file_type, file_unique_id, file_id, bot, user_id, create_time = row
            try:
                cursor.execute("""
                    INSERT IGNORE INTO file_extension_new (
                        id, file_type, file_unique_id, file_id, bot, user_id, create_time
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    id,
                    file_type,
                    file_unique_id,
                    file_id,
                    bot,
                    int(user_id) if user_id is not None else None,  # 转成 bigint
                    create_time
                ))
            except Exception as e:
                print(f"⚠️ Failed to insert id={id}: {e}")

        conn.commit()

        # 更新 last_id 为本批最大 id
        last_id = rows[-1][0]
        time.sleep(0.5)  # 可选：避免太快

    cursor.close()
    conn.close()

if __name__ == "__main__":
    migrate_data()
