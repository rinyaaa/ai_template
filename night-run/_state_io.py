"""night_runner.py と update_step.py が共有する、状態ファイルへのアトミック書き込み。
2つの独立したスクリプト(前者はオーケストレーター本体、後者はタスク実行中のClaudeが
呼ぶ最小ツール)に同じ書き込みロジックを重複させない(コードレビューで指摘された重複)。
"""
import json
import os
import tempfile


def atomic_write_json(path, data):
    dir_name = os.path.dirname(os.path.abspath(path))
    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, suffix=".tmp") as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, path)  # アトミックな置き換え
