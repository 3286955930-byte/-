#!/usr/bin/env python3
"""
测试批量图片检测功能
"""
import os
import sys

# 添加APP目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'APP'))

from detection import batch_detect_images

def main():
    # 测试参数
    input_folder = os.path.join(os.path.dirname(__file__), 'test_images')
    output_folder = os.path.join(os.path.dirname(__file__), 'output')
    
    # 确保测试文件夹存在
    if not os.path.exists(input_folder):
        os.makedirs(input_folder)
        print(f"创建测试文件夹: {input_folder}")
        print("请在该文件夹中添加测试图片")
        return
    
    # 执行批量检测
    print(f"开始批量检测，输入文件夹: {input_folder}")
    print(f"输出文件夹: {output_folder}")
    
    result = batch_detect_images(input_folder, output_folder)
    
    print("\n测试完成！")
    print(f"检测结果: {result}")

if __name__ == "__main__":
    main()
