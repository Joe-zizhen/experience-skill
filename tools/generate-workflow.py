#!/usr/bin/env python3
"""生成唯一运行时契约 contracts/workflow.json。"""
import argparse
import os
import sys

from workflow_contract import ContractError, WORKFLOW_REL, check_generated, generated_bytes, write_bytes_atomic


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = os.path.abspath(args.root)
    if args.check:
        errors = check_generated(root)
        if errors:
            for error in errors:
                print("ERROR: " + error)
            return 1
        print("WORKFLOW CONTRACT OK")
        return 0
    try:
        data = generated_bytes(root)
        path = os.path.join(root, WORKFLOW_REL.replace("/", os.sep))
        write_bytes_atomic(path, data)
    except (ContractError, OSError, ValueError, KeyError, TypeError) as exc:
        print("ERROR: " + str(exc))
        return 1
    print("GENERATED " + WORKFLOW_REL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
