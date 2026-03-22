import sqlite3
import json
import logging
import os

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 数据库文件路径
DB_PATH = 'detection_records.db'

def init_db():
    """初始化数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 创建检测记录表
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS detection_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            img_name TEXT NOT NULL,
            detect_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            diseases TEXT,
            result_path TEXT,
            temp REAL,
            humidity REAL,
            rainfall REAL
        )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("数据库初始化成功")
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")

def save_record(username, img_name, detections, result_path):
    """保存检测记录"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 将检测结果转换为JSON字符串
        diseases_json = json.dumps(detections, ensure_ascii=False)
        
        cursor.execute('''
        INSERT INTO detection_records (username, img_name, diseases, result_path)
        VALUES (?, ?, ?, ?)
        ''', (username, img_name, diseases_json, result_path))
        
        # 获取最后插入的ID
        record_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        logger.info(f"保存检测记录成功: {img_name}，记录ID: {record_id}")
        return record_id
    except Exception as e:
        logger.error(f"保存检测记录失败: {str(e)}")
        return None

def get_history_records(username):
    """获取用户的检测历史记录"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, username, img_name, detect_time, diseases, result_path, temp, humidity, rainfall
        FROM detection_records
        WHERE username = ?
        ORDER BY detect_time DESC
        ''', (username,))
        
        records = []
        for row in cursor.fetchall():
            record = {
                "id": row[0],
                "username": row[1],
                "img_name": row[2],
                "detect_time": row[3],
                "diseases": json.loads(row[4]) if row[4] else [],
                "result_path": row[5],
                "temp": row[6],
                "humidity": row[7],
                "rainfall": row[8]
            }
            records.append(record)
        
        conn.close()
        return records
    except Exception as e:
        logger.error(f"获取检测历史记录失败: {str(e)}")
        return []

def get_all_records():
    """获取所有检测记录（管理员用）"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT id, username, img_name, detect_time, diseases, result_path
        FROM detection_records
        ORDER BY detect_time DESC
        ''')
        
        records = []
        for row in cursor.fetchall():
            record = {
                "id": row[0],
                "username": row[1],
                "img_name": row[2],
                "detect_time": row[3],
                "diseases": json.loads(row[4]) if row[4] else [],
                "result_path": row[5]
            }
            records.append(record)
        
        conn.close()
        return records
    except Exception as e:
        logger.error(f"获取所有检测记录失败: {str(e)}")
        return []

def add_env_data(record_id, temp, humidity, rainfall):
    """添加环境数据"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE detection_records
        SET temp = ?, humidity = ?, rainfall = ?
        WHERE id = ?
        ''', (temp, humidity, rainfall, record_id))
        
        conn.commit()
        conn.close()
        logger.info(f"添加环境数据成功: 记录ID={record_id}")
    except Exception as e:
        logger.error(f"添加环境数据失败: {str(e)}")

def delete_record(record_id):
    """删除检测记录"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 先获取记录信息，以便删除对应的图片文件
        cursor.execute('''
        SELECT result_path
        FROM detection_records
        WHERE id = ?
        ''', (record_id,))
        
        row = cursor.fetchone()
        result_path = row[0] if row else None
        
        # 删除记录
        cursor.execute('''
        DELETE FROM detection_records
        WHERE id = ?
        ''', (record_id,))
        
        conn.commit()
        conn.close()
        
        # 删除对应的结果图片
        if result_path:
            # 将相对路径转换为绝对路径
            if not os.path.isabs(result_path):
                abs_result_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), result_path)
            else:
                abs_result_path = result_path
            
            logger.info(f"尝试删除图片，相对路径: {result_path}, 绝对路径: {abs_result_path}")
            
            if os.path.exists(abs_result_path):
                try:
                    os.remove(abs_result_path)
                    logger.info(f"删除结果图片成功: {abs_result_path}")
                except Exception as e:
                    logger.error(f"删除结果图片失败: {str(e)}")
            else:
                logger.warning(f"结果图片不存在: {abs_result_path}")
        
        logger.info(f"删除检测记录成功: 记录ID={record_id}")
        return result_path
    except Exception as e:
        logger.error(f"删除检测记录失败: {str(e)}")
        return None

def delete_all_records(username=None):
    """删除所有检测记录（可选按用户删除）"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 先获取所有记录的 result_path，以便删除对应的图片文件
        if username:
            cursor.execute('''
            SELECT result_path
            FROM detection_records
            WHERE username = ?
            ''', (username,))
        else:
            cursor.execute('''
            SELECT result_path
            FROM detection_records
            ''')
        
        result_paths = [row[0] for row in cursor.fetchall() if row[0]]
        
        # 删除记录
        if username:
            cursor.execute('''
            DELETE FROM detection_records
            WHERE username = ?
            ''', (username,))
        else:
            cursor.execute('''
            DELETE FROM detection_records
            ''')
        
        conn.commit()
        conn.close()
        
        # 删除对应的结果图片
        for result_path in result_paths:
            # 将相对路径转换为绝对路径
            if not os.path.isabs(result_path):
                abs_result_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), result_path)
            else:
                abs_result_path = result_path
            
            logger.info(f"尝试删除图片，相对路径: {result_path}, 绝对路径: {abs_result_path}")
            
            if os.path.exists(abs_result_path):
                try:
                    os.remove(abs_result_path)
                    logger.info(f"删除结果图片成功: {abs_result_path}")
                except Exception as e:
                    logger.error(f"删除结果图片失败: {str(e)}")
            else:
                logger.warning(f"结果图片不存在: {abs_result_path}")
        
        logger.info(f"删除所有检测记录成功: 用户={username}")
        return result_paths
    except Exception as e:
        logger.error(f"删除所有检测记录失败: {str(e)}")
        return []
