#!/usr/bin/env python3
"""雛形と手順から、配布物の生成部分を作る。

  python3 scripts/build.py          生成物を更新して dist/agentbrain.plugin を作る
  python3 scripts/build.py --check  生成物が正本と一致しているかだけ確かめる

正本は skills/agentbrain-setup/template/（雛形）と、2 つの SKILL.md の本文（手順）。
ここから次の 2 つを生成する。どちらも commit する。

  skills/agentbrain-setup/SKILL.md の「雛形の中身」
      スキルが自分の template/ を読めない環境があるので、同じ内容を本文の末尾にも載せる
  worker/src/content.gen.ts
      MCP サーバーが返す手順と雛形

日本語のファイル名を Windows でも読めるよう、zip には NFC・UTF-8 フラグ付きで格納する
（macOS の zip コマンドはフラグを立てないことがあるので使わない）。
"""
import json
import sys
import unicodedata
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SETUP_SKILL = ROOT / "skills/agentbrain-setup/SKILL.md"
CHECK_SKILL = ROOT / "skills/agentbrain-check/SKILL.md"
TEMPLATE = ROOT / "skills/agentbrain-setup/template"
WORKER_CONTENT = ROOT / "worker/src/content.gen.ts"
START, END = "<!-- template:start -->", "<!-- template:end -->"
EMBED_HEADING = "## 雛形の中身"
FENCE = "~~~~"
INCLUDE = [".claude-plugin/plugin.json", "skills", "README.md"]
SKIP_NAMES = {".DS_Store"}

MCP_PREAMBLE = """\
> この手順は MCP サーバー agentbrain-mcp から届いている。本文はプラグイン版のスキルと同じなので、次のように読み替える。
>
> - 「このスキルのベースディレクトリにある `template/`」と「雛形の中身」は、`agentbrain_template` ツールが返すファイルのこと。全ファイルを取得し、相対パスどおりに、中身を変えずに書き出す。
> - 「agentbrain-setup」「agentbrain-check」は、`agentbrain_guide` の `topic=setup` / `topic=check` のこと。
> - フォルダに書き込む手段が無い環境では、作業を始める前にそのことを伝え、フォルダを選べる環境（Claude デスクトップアプリの Cowork、Claude Code）で頼み直すよう案内する。
"""


def nfc(text):
    return unicodedata.normalize("NFC", text)


def template_files():
    """(相対パス, 中身) の一覧。地図（CLAUDE.md）を先頭に、残りはパス順。"""
    paths = [p for p in TEMPLATE.rglob("*") if p.is_file() and p.name not in SKIP_NAMES]
    paths.sort(key=lambda p: (p.parent != TEMPLATE, nfc(p.relative_to(TEMPLATE).as_posix())))
    files = []
    for path in paths:
        body = path.read_text(encoding="utf-8").rstrip("\n")
        if FENCE in body:
            sys.exit(f"{path} に {FENCE} が含まれていて囲めません")
        files.append((nfc(path.relative_to(TEMPLATE).as_posix()), body))
    return files


def synced_skill():
    block = "\n\n".join(f"### `{rel}`\n\n{FENCE}markdown\n{body}\n{FENCE}" for rel, body in template_files())
    head, rest = SETUP_SKILL.read_text(encoding="utf-8").split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{block}\n{END}{tail}"


def skill_body(path):
    """frontmatter と、SKILL.md に埋め込んだ雛形の写しを除いた本文。"""
    text = path.read_text(encoding="utf-8")
    body = text.split("---", 2)[2]
    return body.split(EMBED_HEADING, 1)[0].strip()


def worker_content():
    version = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
    guides = {
        "setup": f"{MCP_PREAMBLE}\n{skill_body(SETUP_SKILL)}\n",
        "check": f"{MCP_PREAMBLE}\n{skill_body(CHECK_SKILL)}\n",
    }
    files = [{"path": rel, "content": body + "\n"} for rel, body in template_files()]
    dump = lambda value: json.dumps(value, ensure_ascii=False, indent=2)
    return (
        "// scripts/build.py が生成する。手で直さない（正本は skills/ の SKILL.md と template/）\n"
        f"export const VERSION = {dump(version)};\n\n"
        f"export const GUIDES = {dump(guides)} as const;\n\n"
        f"export const TEMPLATE: readonly {{ path: string; content: string }}[] = {dump(files)};\n"
    )


def package_files():
    for entry in INCLUDE:
        path = ROOT / entry
        if path.is_file():
            yield path
        else:
            yield from sorted(p for p in path.rglob("*") if p.is_file() and p.name not in SKIP_NAMES)


def main():
    generated = {SETUP_SKILL: synced_skill()}
    if "--check" in sys.argv:
        generated[WORKER_CONTENT] = worker_content()
        stale = [p for p, text in generated.items() if not p.exists() or p.read_text(encoding="utf-8") != text]
        if stale:
            names = ", ".join(str(p.relative_to(ROOT)) for p in stale)
            sys.exit(f"生成物が正本とずれています: {names}\npython3 scripts/build.py を実行してください")
        print("生成物は正本と一致しています")
        return
    SETUP_SKILL.write_text(generated[SETUP_SKILL], encoding="utf-8")
    # SKILL.md を更新してから、その本文をもとに Worker 用の中身を作る
    WORKER_CONTENT.write_text(worker_content(), encoding="utf-8")

    name = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))["name"]
    out = ROOT / "dist" / f"{name}.plugin"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in package_files():
            zf.write(path, nfc(path.relative_to(ROOT).as_posix()))
    print(f"{out.relative_to(ROOT)}  ({len(zipfile.ZipFile(out).namelist())} files)")


if __name__ == "__main__":
    main()
