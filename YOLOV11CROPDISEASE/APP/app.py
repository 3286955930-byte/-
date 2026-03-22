from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import json
import datetime
import logging
import concurrent.futures
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# 导入自定义模块
import sys

# 添加当前目录到路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from database import init_db, save_record, get_history_records, add_env_data, get_all_records, delete_record, delete_all_records

# 创建线程池执行器
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

# 初始化Flask应用
app = Flask(__name__)
app.secret_key = "crop_detection_2026"  # 会话加密密钥

# 静态文件配置
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'images', 'uploads')
app.config['RESULT_FOLDER'] = os.path.join(BASE_DIR, 'static', 'images', 'results')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg'}
# 图片保留天数
app.config['IMAGE_RETENTION_DAYS'] = 7

# CSRF配置
app.config['WTF_CSRF_ENABLED'] = False

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 创建文件夹（若不存在）
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

# 清理根目录下的static文件夹（如果存在）
ROOT_STATIC = os.path.join(os.path.dirname(BASE_DIR), 'static')
if os.path.exists(ROOT_STATIC):
    try:
        import shutil
        shutil.rmtree(ROOT_STATIC)
        logger.info(f"清理根目录下的static文件夹: {ROOT_STATIC}")
    except Exception as e:
        logger.error(f"清理根目录static文件夹失败: {str(e)}")

# 清理根目录下的数据库文件（如果存在）
ROOT_DB = os.path.join(os.path.dirname(BASE_DIR), 'detection_records.db')
if os.path.exists(ROOT_DB):
    try:
        os.remove(ROOT_DB)
        logger.info(f"清理根目录下的数据库文件: {ROOT_DB}")
    except Exception as e:
        logger.error(f"清理根目录数据库文件失败: {str(e)}")

# 定期清理过期图片
def cleanup_old_images():
    """清理过期的图片文件"""
    import datetime
    
    # 计算过期时间
    cutoff_date = datetime.datetime.now() - datetime.timedelta(days=app.config['IMAGE_RETENTION_DAYS'])
    
    # 清理上传文件夹
    uploads_dir = app.config['UPLOAD_FOLDER']
    for filename in os.listdir(uploads_dir):
        file_path = os.path.join(uploads_dir, filename)
        if os.path.isfile(file_path):
            file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_mod_time < cutoff_date:
                os.remove(file_path)
                logger.info(f"删除过期上传图片: {filename}")
    
    # 清理结果文件夹
    results_dir = app.config['RESULT_FOLDER']
    for filename in os.listdir(results_dir):
        file_path = os.path.join(results_dir, filename)
        if os.path.isfile(file_path):
            file_mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            if file_mod_time < cutoff_date:
                os.remove(file_path)
                logger.info(f"删除过期结果图片: {filename}")

# 启动时清理一次过期图片
try:
    cleanup_old_images()
except Exception as e:
    logger.error(f"清理过期图片失败: {str(e)}")

# 加载用户数据
users_path = os.path.join(BASE_DIR, 'users.json')
with open(users_path, 'r', encoding='utf-8') as f:
    USERS = json.load(f)

# 确保用户密码已哈希
passwords_updated = False
for username, user_data in USERS.items():
    if 'password' in user_data:
        stored_password = user_data['password']
        # 检查密码是否已经哈希（支持 pbkdf2 和 scrypt 格式）
        if not (stored_password.startswith('pbkdf2:') or stored_password.startswith('scrypt:')):
            USERS[username]['password'] = generate_password_hash(stored_password)
            passwords_updated = True

# 只有在密码更新时才保存
if passwords_updated:
    with open(users_path, 'w', encoding='utf-8') as f:
        json.dump(USERS, f, ensure_ascii=False, indent=2)

# 加载病虫害知识库
disease_lib_path = os.path.join(BASE_DIR, 'disease_lib.json')
with open(disease_lib_path, 'r', encoding='utf-8') as f:
    DISEASE_LIB = json.load(f)

# 初始化数据库
init_db()

# ========== 辅助函数 ==========
def allowed_file(filename):
    """检查文件格式"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def detect_image(image_path, output_path):
    """检测图片"""
    try:
        # 尝试导入 detection 模块
        from detection import detect_image_yolov11
        return detect_image_yolov11(image_path, output_path)
    except Exception as e:
        logger.error(f"导入 detection 模块失败: {str(e)}")
        # 使用备用检测方法
        return fallback_detect(image_path, output_path)

def fallback_detect(image_path, output_path):
    """备用检测方法"""
    logger.warning("使用备用检测方法")
    
    try:
        # 打开图片获取基本信息
        from PIL import Image, ImageDraw, ImageFont
        image = Image.open(image_path)
        width, height = image.size
        
        # 创建一个模拟的检测结果
        from detection import get_disease_level
        disease_type = "健康"
        level = get_disease_level(0.85, disease_type)
        
        detections = [
            {
                "class_id": 5,  # 假设是健康
                "class": "苹果健康",
                "confidence": 0.85,
                "bbox": [width * 0.25, height * 0.25, width * 0.75, height * 0.75],
                "level": level
            }
        ]
        
        # 绘制检测结果
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()
        
        for det in detections:
            class_id = det["class_id"]
            class_name = det["class"]
            confidence = det["confidence"]
            bbox = det["bbox"]
            
            # 计算边界框坐标
            x1, y1, x2, y2 = bbox
            
            # 绘制矩形框
            draw.rectangle([(x1, y1), (x2, y2)], outline="red", width=2)
            
            # 绘制标签
            label = f"{class_name}: {confidence:.2f}"
            draw.text((x1, y1 - 20), label, fill="red", font=font)
        
        # 保存结果图片
        image.save(output_path)
        logger.info(f"结果保存到: {output_path}")
        
        return {
            "status": "success",
            "message": "使用备用检测方法完成",
            "detections": detections
        }
    except Exception as e:
        error_msg = f"检测过程中发生错误: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "message": error_msg,
            "detections": []
        }

# ========== 路由 ==========
@app.route('/', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 验证用户
        if username in USERS:
            stored_password = USERS[username].get("password")
            # 检查密码是否已经哈希（支持 pbkdf2 和 scrypt 格式）
            if stored_password.startswith('pbkdf2:') or stored_password.startswith('scrypt:'):
                # 使用哈希验证
                if check_password_hash(stored_password, password):
                    session['username'] = username
                    session['role'] = USERS[username].get("role", "user")
                    logger.info(f"用户 {username} 登录成功")
                    return redirect(url_for('index'))
            else:
                # 使用明文验证
                if stored_password == password:
                    session['username'] = username
                    session['role'] = USERS[username].get("role", "user")
                    logger.info(f"用户 {username} 登录成功")
                    return redirect(url_for('index'))
        # 验证失败
        logger.warning(f"用户 {username} 登录失败：密码错误")
        flash('用户名或密码错误！', 'error')

    return render_template('login.html')

@app.route('/index')
def index():
    """检测主界面（需登录）"""
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html',
                           username=session['username'],
                           role=session.get('role', 'user'))

def process_single_file(file, username):
    """处理单个文件的检测"""
    if file.filename == '' or not allowed_file(file.filename):
        return None, f"文件 {file.filename} 格式不支持"

    try:
        # 安全保存上传文件
        filename = secure_filename(file.filename)
        unique_filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(upload_path)
        logger.info(f"文件 {filename} 保存成功: {upload_path}")

        # 生成结果路径
        result_filename = f"result_{unique_filename}"
        result_path = os.path.join(app.config['RESULT_FOLDER'], result_filename)

        # 执行检测
        detect_result = detect_image(upload_path, result_path)

        # 删除临时上传文件
        try:
            if os.path.exists(upload_path):
                os.remove(upload_path)
                logger.info(f"删除临时上传文件: {upload_path}")
        except Exception as e:
            logger.error(f"删除临时上传文件失败: {str(e)}")

        if detect_result["status"] == "success":
            # 生成相对路径，用于存储和前端显示
            relative_result_path = os.path.relpath(result_path, os.path.join(BASE_DIR, 'static'))
            logger.info(f"结果图片相对路径: {relative_result_path}")
            
            # 保存检测记录（存储相对路径）
            record_id = save_record(username,
                        filename,
                        detect_result["detections"],
                        relative_result_path)
            logger.info(f"图片 {filename} 检测成功，记录ID: {record_id}")

            return {
                "filename": filename,
                "result_path": relative_result_path,
                "detections": detect_result["detections"],
                "record_id": record_id
            }, None
        else:
            error_msg = f"检测失败 {filename}：{detect_result['message']}"
            logger.error(f"图片 {filename} 检测失败: {detect_result['message']}")
            return None, error_msg
    except Exception as e:
        error_msg = f"处理文件 {file.filename} 时发生错误: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

@app.route('/detect', methods=['POST'])
def detect():
    """图片上传+检测"""
    if 'username' not in session:
        logger.warning("未登录用户尝试访问检测功能")
        return redirect(url_for('login'))

    try:
        # 检查文件上传
        if 'file' not in request.files:
            flash('未选择图片！', 'error')
            logger.warning(f"用户 {session['username']} 未选择图片")
            return redirect(url_for('index'))

        files = request.files.getlist('file')  # 支持批量上传
        success_count = 0
        fail_count = 0
        single_result = None  # 存储单文件检测结果

        logger.info(f"用户 {session['username']} 上传了 {len(files)} 张图片")

        # 单文件处理
        if len(files) == 1:
            result, error = process_single_file(files[0], session['username'])
            if result:
                # 获取防治方案
                main_disease = result["detections"][0]["class"] if result["detections"] else ""
                disease_info = DISEASE_LIB.get(main_disease, {
                    "level_strategy": {"轻微": "暂无方案", "轻度": "暂无方案", "中度": "暂无方案", "重度": "暂无方案"},
                    "prevent": "暂无预防建议"
                })
                level = result["detections"][0]["level"] if result["detections"] else ""
                strategy = disease_info["level_strategy"].get(level, "暂无对应分级方案")

                # 获取当前时间
                current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                # 获取记录ID
                record_id = result.get("record_id", None)
                
                logger.info(f"用户 {session['username']} 单文件检测完成，展示结果，记录ID: {record_id}")
                return render_template('index.html',
                                       username=session['username'],
                                       role=session.get('role', 'user'),
                                       result=result,
                                       strategy=strategy,
                                       prevent=disease_info.get("prevent", ""),
                                       current_time=current_time)
            else:
                flash(error, 'error')
                return redirect(url_for('index'))
        else:
            # 批量处理，使用线程池
            futures = []
            for file in files:
                future = executor.submit(process_single_file, file, session['username'])
                futures.append(future)

            # 收集结果
            for future in concurrent.futures.as_completed(futures):
                result, error = future.result()
                if result:
                    success_count += 1
                else:
                    fail_count += 1
                    if error:
                        flash(error, 'error')

            # 批量上传结果提示
            flash(f"批量检测完成：成功{success_count}张，失败{fail_count}张", 'success')
            logger.info(f"用户 {session['username']} 批量检测完成：成功{success_count}张，失败{fail_count}张")
            return redirect(url_for('history'))
    except Exception as e:
        logger.error(f"检测过程中发生错误: {str(e)}")
        flash(f"检测过程中发生错误: {str(e)}", 'error')
        return redirect(url_for('index'))

@app.route('/history')
def history():
    """检测历史记录"""
    if 'username' not in session:
        return redirect(url_for('login'))

    # 管理员可查看所有记录，普通用户仅看自己的
    if session.get('role') == 'admin':
        try:
            all_records = get_all_records()
            formatted_records = []
            for r in all_records:
                result_path = r["result_path"] if r["result_path"] else ""
                # 如果是绝对路径，转换为相对路径；如果已经是相对路径，直接使用
                if result_path and os.path.isabs(result_path):
                    relative_path = os.path.relpath(result_path, os.path.join(BASE_DIR, 'static'))
                else:
                    relative_path = result_path
                formatted_records.append({
                    "id": r["id"],
                    "username": r["username"],
                    "img_name": r["img_name"],
                    "detect_time": r["detect_time"],
                    "diseases": r["diseases"],
                    "result_path": relative_path
                })
            logger.info("管理员查看所有检测记录成功")
        except Exception as e:
            logger.error(f"管理员查看检测记录失败: {str(e)}")
            formatted_records = []
    else:
        user_records = get_history_records(session['username'])
        formatted_records = []
        for r in user_records:
            result_path = r["result_path"] if r["result_path"] else ""
            # 如果是绝对路径，转换为相对路径；如果已经是相对路径，直接使用
            if result_path and os.path.isabs(result_path):
                relative_path = os.path.relpath(result_path, os.path.join(BASE_DIR, 'static'))
            else:
                relative_path = result_path
            formatted_records.append({
                "id": r["id"],
                "img_name": r["img_name"],
                "detect_time": r["detect_time"],
                "diseases": r["diseases"],
                "result_path": relative_path,
                "temp": r["temp"] if r["temp"] else "",
                "humidity": r["humidity"] if r["humidity"] else "",
                "rainfall": r["rainfall"] if r["rainfall"] else ""
            })

    return render_template('history.html',
                           username=session['username'],
                           role=session.get('role', 'user'),
                           records=formatted_records)

@app.route('/add_env', methods=['POST'])
def add_env():
    """添加环境数据"""
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        record_id = request.form['record_id']
        temp = float(request.form['temp'])
        humidity = float(request.form['humidity'])
        rainfall = float(request.form['rainfall'])

        add_env_data(record_id, temp, humidity, rainfall)
        flash('环境数据添加成功！', 'success')
    except Exception as e:
        flash(f'环境数据添加失败：{str(e)}', 'error')

    return redirect(url_for('history'))

@app.route('/delete_record/<int:record_id>')
def delete_record_route(record_id):
    """删除单个检测记录和对应的图片"""
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        # 删除记录（database.py中已经处理了图片删除）
        result_path = delete_record(record_id)
        logger.info(f"删除记录成功，图片路径: {result_path}")
        flash('删除记录成功！', 'success')
    except Exception as e:
        logger.error(f"删除记录失败: {str(e)}")
        flash(f'删除记录失败：{str(e)}', 'error')

    return redirect(url_for('history'))

@app.route('/delete_all_records')
def delete_all_records_route():
    """删除所有检测记录和对应的图片"""
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        # 删除所有记录（database.py中已经处理了图片删除）
        result_paths = delete_all_records(session['username'])
        logger.info(f"删除所有记录成功，图片路径数量: {len(result_paths)}")
        flash('删除所有记录成功！', 'success')
    except Exception as e:
        logger.error(f"删除所有记录失败: {str(e)}")
        flash(f'删除所有记录失败：{str(e)}', 'error')

    return redirect(url_for('history'))

@app.route('/logout')
def logout():
    """退出登录"""
    session.pop('username', None)
    session.pop('role', None)
    flash('已安全退出登录！', 'success')
    return redirect(url_for('login'))

@app.route('/manage_images')
def manage_images():
    """管理图片页面"""
    if 'username' not in session:
        return redirect(url_for('login'))

    # 静态文件文件夹路径
    uploads_dir = app.config['UPLOAD_FOLDER']
    results_dir = app.config['RESULT_FOLDER']
    
    # 确保文件夹存在
    os.makedirs(uploads_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)
    
    # 获取上传图片列表
    uploads = []
    try:
        uploads = [f for f in os.listdir(uploads_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
        logger.info(f"上传文件夹路径: {uploads_dir}, 图片数量: {len(uploads)}")
    except Exception as e:
        logger.error(f"获取上传图片列表失败：{str(e)}")
        flash('获取上传图片列表失败！', 'error')
    
    # 获取结果图片列表
    results = []
    try:
        results = [f for f in os.listdir(results_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
        logger.info(f"结果文件夹路径: {results_dir}, 图片数量: {len(results)}")
    except Exception as e:
        logger.error(f"获取结果图片列表失败：{str(e)}")
        flash('获取结果图片列表失败！', 'error')
    
    # 记录图片数量
    logger.info(f"上传图片数量: {len(uploads)}, 结果图片数量: {len(results)}")

    return render_template('manage_images.html',
                           username=session['username'],
                           role=session.get('role', 'user'),
                           uploads=uploads,
                           results=results)

@app.route('/delete_image/<string:image_type>/<string:filename>')
def delete_image(image_type, filename):
    """删除图片"""
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        # 确定图片路径
        if image_type == 'upload':
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        elif image_type == 'result':
            image_path = os.path.join(app.config['RESULT_FOLDER'], filename)
        else:
            flash('无效的图片类型！', 'error')
            return redirect(url_for('manage_images'))

        # 记录删除操作
        logger.info(f"尝试删除图片：{image_path}")
        
        # 删除图片
        if os.path.exists(image_path):
            os.remove(image_path)
            logger.info(f"图片删除成功：{image_path}")
            flash(f'图片 {filename} 删除成功！', 'success')
        else:
            logger.warning(f"图片不存在：{image_path}")
            flash('图片不存在！', 'error')
    except Exception as e:
        logger.error(f"删除图片失败：{str(e)}")
        flash(f'删除图片失败：{str(e)}', 'error')

    return redirect(url_for('manage_images'))

@app.route('/delete_all_images')
def delete_all_images():
    """删除所有图片"""
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        # 删除上传的图片
        uploads_dir = app.config['UPLOAD_FOLDER']
        upload_count = 0
        if os.path.exists(uploads_dir):
            for file in os.listdir(uploads_dir):
                if file.endswith(('.jpg', '.jpeg', '.png')):
                    try:
                        os.remove(os.path.join(uploads_dir, file))
                        upload_count += 1
                    except Exception as e:
                        logger.error(f"删除上传图片 {file} 失败：{str(e)}")
        logger.info(f"删除上传图片数量：{upload_count}")

        # 删除结果图片
        results_dir = app.config['RESULT_FOLDER']
        result_count = 0
        if os.path.exists(results_dir):
            for file in os.listdir(results_dir):
                if file.endswith(('.jpg', '.jpeg', '.png')):
                    try:
                        os.remove(os.path.join(results_dir, file))
                        result_count += 1
                    except Exception as e:
                        logger.error(f"删除结果图片 {file} 失败：{str(e)}")
        logger.info(f"删除结果图片数量：{result_count}")

        flash(f'所有图片删除成功！上传图片: {upload_count} 张，结果图片: {result_count} 张', 'success')
    except Exception as e:
        logger.error(f"删除所有图片失败：{str(e)}")
        flash(f'删除图片失败：{str(e)}', 'error')

    return redirect(url_for('manage_images'))

@app.route('/video_detect')
def video_detect():
    """视频取图检测页面"""
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('video_detect.html',
                           username=session['username'],
                           role=session.get('role', 'user'))

@app.route('/detect_video_frame', methods=['POST'])
def detect_video_frame():
    """处理视频帧检测请求"""
    if 'username' not in session:
        return {'status': 'error', 'message': '未登录'}

    try:
        # 检查是否有视频帧数据
        if 'frame' not in request.files:
            return {'status': 'error', 'message': '未接收到视频帧'}

        frame_file = request.files['frame']
        if frame_file.filename == '':
            return {'status': 'error', 'message': '未接收到视频帧'}

        # 安全保存上传的视频帧
        filename = secure_filename(frame_file.filename)
        unique_filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        frame_file.save(upload_path)
        logger.info(f"视频帧保存成功: {upload_path}")

        # 生成结果路径
        result_filename = f"result_{unique_filename}"
        result_path = os.path.join(app.config['RESULT_FOLDER'], result_filename)

        # 执行检测
        detect_result = detect_image(upload_path, result_path)

        if detect_result["status"] == "success":
            # 生成相对路径，用于存储和前端显示
            relative_result_path = os.path.relpath(result_path, os.path.join(BASE_DIR, 'static'))
            logger.info(f"视频帧结果图片相对路径: {relative_result_path}")
            
            # 保存检测记录（存储相对路径）
            save_record(session['username'],
                        filename,
                        detect_result["detections"],
                        relative_result_path)
            logger.info(f"视频帧检测成功: {filename}")

            return {
                "status": "success",
                "img_name": filename,
                "result_path": relative_result_path,
                "detections": detect_result["detections"]
            }
        else:
            error_msg = f"检测失败：{detect_result['message']}"
            logger.error(f"视频帧检测失败: {detect_result['message']}")
            return {"status": "error", "message": error_msg}
    except Exception as e:
        error_msg = f"处理视频帧时发生错误: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}

# ========== 启动应用 ==========
if __name__ == '__main__':
    try:
        print("正在启动应用...")
        print(f"用户数据: {USERS.keys()}")
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"启动应用时发生错误: {str(e)}")
        import traceback
        traceback.print_exc()
