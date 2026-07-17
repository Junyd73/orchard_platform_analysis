import sqlite3

def init_order_delivery_table():
    db_path = "orchard_platform.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 첨부 양식의 8개 컬럼 + 관리용 order_no 포함
    sql = """
    CREATE TABLE IF NOT EXISTS t_order_delivery (
        order_dlvry_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        order_no        TEXT NOT NULL,
        snd_name        TEXT, -- 보내는분
        snd_tel         TEXT, -- 보내는연락처
        snd_addr        TEXT, -- 보내는주소
        rcv_name        TEXT, -- 받는분
        rcv_tel         TEXT, -- 받는연락처
        rcv_addr        TEXT, -- 받는주소
        dlvry_qty       INTEGER DEFAULT 1, -- 1박스 1송장 원칙에 따라 무조건 1 저장
        dlvry_msg       TEXT,
        reg_dt          TEXT DEFAULT (datetime('now','localtime'))
    );
    """
    cursor.execute(sql)
    conn.commit()
    conn.close()
    print("✅ t_order_delivery 테이블 생성 완료")

if __name__ == "__main__":
    init_order_delivery_table()