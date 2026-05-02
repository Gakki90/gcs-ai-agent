from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/patch-open-autoglm.py <Open-AutoGLM directory>")
        return 2

    root = Path(sys.argv[1])
    prompt_file = root / "phone_agent" / "config" / "prompts_zh.py"
    if not prompt_file.exists():
        print(f"Open-AutoGLM prompt file not found: {prompt_file}")
        return 1

    content = prompt_file.read_text(encoding="utf-8")
    old = 'formatted_date = today.strftime("%Y年%m月%d日") + " " + weekday'
    new = 'formatted_date = f"{today.year}年{today.month:02d}月{today.day:02d}日 " + weekday'
    if old not in content:
        if new in content:
            print("Open-AutoGLM Windows date patch already applied.")
            return 0
        print("Open-AutoGLM prompt date line did not match expected content.")
        return 1

    prompt_file.write_text(content.replace(old, new), encoding="utf-8")
    print("Applied Open-AutoGLM Windows date patch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
