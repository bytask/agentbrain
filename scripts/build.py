#!/usr/bin/env python3
"""雛形を SKILL.md に写し、dist/agentbrain.plugin を作る。

  python3 scripts/build.py          写しを更新して配布物を作る
  python3 scripts/build.py --check  写しが雛形と一致しているかだけ確かめる

スキルが自分の template/ を読めない環境があるので、同じ内容を SKILL.md の末尾にも載せる。
正本は template/ で、SKILL.md の「雛形の中身」はここで生成する。

日本語のファイル名を Windows でも読めるよう、zip には NFC・UTF-8 フラグ付きで格納する
（macOS の zip コマンドはフラグを立てないことがあるので使わない）。
"""
import json
import sys
import unicodedata
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills/agentbrain-setup/SKILL.md"
TEMPLATE = ROOT / "skills/agentbrain-setup/template"
START, END = "<!-- template:start -->", "<!-- template:end -->"
FENCE = "~~~~"
INCLUDE = [".claude-plugin/plugin.json", "skills", "README.md"]
SKIP_NAMES = {".DS_Store"}


def nfc(text):
    return unicodedata.normalize("NFC", text)


def template_files():
    paths = [p for p in TEMPLATE.rglob("*") if p.is_file() and p.name not in SKIP_NAMES]
    # 地図（CLAUDE.md）を先頭に、残りはパス順
    return sorted(paths, key=lambda p: (p.parent != TEMPLATE, nfc(p.relative_to(TEMPLATE).as_posix())))


def render_block():
    parts = []
    for path in template_files():
        body = path.read_text(encoding="utf-8").rstrip("\n")
        if FENCE in body:
            sys.exit(f"{path} に {FENCE} が含まれていて囲めません")
        rel = nfc(path.relative_to(TEMPLATE).as_posix())
        parts.append(f"### `{rel}`\n\n{FENCE}markdown\n{body}\n{FENCE}")
    return "\n\n".join(parts)


def synced_skill():
    text = SKILL.read_text(encoding="utf-8")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{render_block()}\n{END}{tail}"


def package_files():
    for entry in INCLUDE:
        path = ROOT / entry
        if path.is_file():
            yield path
        else:
            yield from sorted(p for p in path.rglob("*") if p.is_file() and p.name not in SKIP_NAMES)


def main():
    wanted = synced_skill()
    if "--check" in sys.argv:
        if SKILL.read_text(encoding="utf-8") != wanted:
            sys.exit("SKILL.md の「雛形の中身」が template/ とずれています。python3 scripts/build.py を実行してください")
        print("SKILL.md は template/ と一致しています")
        return
    SKILL.write_text(wanted, encoding="utf-8")

    name = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["name"]
    out = ROOT / "dist" / f"{name}.plugin"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in package_files():
            zf.write(path, nfc(path.relative_to(ROOT).as_posix()))
    print(f"{out.relative_to(ROOT)}  ({len(zipfile.ZipFile(out).namelist())} files)")


if __name__ == "__main__":
    main()
