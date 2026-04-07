#!/usr/bin/env python3

import sys
import yaml
import json
import os

def load_yaml(file_path):
    if not file_path:
        print("Error: File path is empty", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found", file=sys.stderr)
        sys.exit(1)
    
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
    expression = expression.strip("'\"")
    
    if expression == 'keys | .[]':
        if isinstance(data, dict):
            return list(data.keys())
        else:
            return []
    
    if expression.startswith('.'):
        key = expression[1:]
        try:
            return data[key]
        except (KeyError, TypeError):
            return None
    else:
        return data

def main():
    if len(sys.argv) < 2:
        print("Usage: yq <expression> <file>")
        print("   or: yq eval <expression> <file>")
        sys.exit(1)
    
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
    
    if not file_path:
        print("Error: File path is empty", file=sys.stderr)
        sys.exit(1)
    
    data = load_yaml(file_path)
    
    expression_clean = expression.strip("'\"")
    
    if expression_clean == '.':
        print("Valid YAML file")
        sys.exit(0)
    else:
        value = get_value(data, expression)
        if value is not None:
            if expression_clean == 'keys | .[]':
                if isinstance(value, list):
                    for key in value:
                        print(key)
            elif isinstance(value, (dict, list)):
                print(json.dumps(value, indent=2))
            else:
                print(value)
        else:
            print("")
            sys.exit(1)

if __name__ == '__main__':
    main()
