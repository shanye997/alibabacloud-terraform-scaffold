#!/usr/bin/env python3

import sys
import yaml
import json
import argparse
import os

def load_yaml(file_path):
    """加载 YAML 文件"""
    # 检查文件路径是否为空
    if not file_path:
        print("Error: File path is empty", file=sys.stderr)
        sys.exit(1)
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found", file=sys.stderr)
        sys.exit(1)
    
    # 检查是否为文件（而不是目录）
    if not os.path.isfile(file_path):
        print(f"Error: '{file_path}' is not a file", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML format in '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"Error: Permission denied when reading '{file_path}'", file=sys.stderr)
        sys.exit(1)

def get_value(data, expression):
    """根据表达式获取值"""
    # 移除表达式两端的引号（单引号或双引号）
    expression = expression.strip("'\"")
    
    # 处理 keys | .[] 表达式，获取所有键
    if expression == 'keys | .[]':
        if isinstance(data, dict):
            return list(data.keys())
        else:
            return []
    
    # 处理简单的点符号表达式，如 '.oss_bucket'
    if expression.startswith('.'):
        key = expression[1:]  # 去掉开头的点
        try:
            return data[key]
        except (KeyError, TypeError):
            return None
    else:
        # 直接返回整个数据
        return data

def main():
    # 手动解析参数以兼容 yq 的调用方式
    if len(sys.argv) < 2:
        print("Usage: yq <expression> <file>")
        print("   or: yq eval <expression> <file>")
        sys.exit(1)
    
    # 检查是否是 eval 命令
    if sys.argv[1] == 'eval':
        if len(sys.argv) < 3:
            print("Error: Expression required for eval command")
            sys.exit(1)
        
        expression = sys.argv[2]
        if len(sys.argv) >= 4:
            file_path = sys.argv[3]
        else:
            print("Error: File argument required")
            sys.exit(1)
    else:
        expression = sys.argv[1]
        if len(sys.argv) >= 3:
            file_path = sys.argv[2]
        else:
            print("Error: File argument required")
            sys.exit(1)
    
    # 检查文件路径
    if not file_path:
        print("Error: File path is empty", file=sys.stderr)
        sys.exit(1)
    
    # 加载 YAML 文件
    data = load_yaml(file_path)
    
    # 处理表达式
    expression_clean = expression.strip("'\"")
    
    if expression_clean == '.':
        # 验证整个文件
        print("Valid YAML file")
        sys.exit(0)
    else:
        # 获取特定值
        value = get_value(data, expression)
        if value is not None:
            # 处理 keys | .[] 表达式，输出每个键一行
            if expression_clean == 'keys | .[]':
                if isinstance(value, list):
                    for key in value:
                        print(key)
                else:
                    # 如果没有键，不输出任何内容（与 yq 行为一致）
                    pass
            elif isinstance(value, (dict, list)):
                print(json.dumps(value, indent=2))
            else:
                # 字符串值直接输出，不包含引号（与 yq 行为一致）
                print(value)
        else:
            # 当值为 None 时，输出空字符串（与 yq 行为一致）
            # 这样 shell 中的 [ -n "$VALUE" ] 检查会失败
            print("")
            sys.exit(1)

if __name__ == '__main__':
    main()