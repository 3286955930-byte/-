import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== 测试分类功能 ===")

# 导入检测模块
try:
    from detection import detect_image_yolov11
    print("✓ 成功导入检测模块")
except Exception as e:
    print(f"✗ 导入检测模块失败: {e}")
    sys.exit(1)

# 找一个测试图片
import glob
test_images = glob.glob('static/images/uploads/*.JPG')

if test_images:
    test_image = test_images[0]
    output_path = 'static/images/results/test_classification_result.jpg'
    
    print(f"测试图片: {test_image}")
    print(f"输出路径: {output_path}")
    
    # 执行分类
    print("开始分类...")
    try:
        result = detect_image_yolov11(test_image, output_path)
        
        print("\n分类结果:")
        print(f"状态: {result['status']}")
        print(f"消息: {result['message']}")
        print(f"检测到的目标: {len(result['detections'])}")
        
        for i, det in enumerate(result['detections']):
            print(f"\n目标 {i+1}:")
            print(f"  类别: {det['class']}")
            print(f"  置信度: {det['confidence']:.2f}")
            print(f"  病害等级: {det['level']}")
    except Exception as e:
        print(f"✗ 分类过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
else:
    print("没有找到测试图片，请先上传一些图片到 static/images/uploads/ 目录")
