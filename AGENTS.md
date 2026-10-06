# agentbrain

仕事の文脈を AI に渡すためのフォルダ「agentbrain」の雛形と、それを作る・点検するスキルを、1 つのプラグインとして配る repo。

## 構成

| パス | 中身 |
|---|---|
| `.claude-plugin/plugin.json` | プラグインの定義。配布のたびに `version` を上げる |
| `.claude-plugin/marketplace.json` | Claude Code から配布元として登録するための定義 |
| `skills/agentbrain-setup/` | 作ってインタビューで埋めるスキル |
| `skills/agentbrain-setup/template/` | **雛形の正本。** 利用者のフォルダに写される実ファイル |
| `skills/agentbrain-check/` | 点検するスキル |
| `scripts/build.py` | `dist/agentbrain.plugin` を作る |

## 規約

- 雛形を直すのは `skills/agentbrain-setup/template/` だけ。README に中身の写しを書かない
- `agentbrain-setup/SKILL.md` 末尾の「雛形の中身」は `scripts/build.py` が `template/` から生成する。手で直さない。スキルが自分の `template/` を読めない環境（権限で止まる場合）でも、同じフォルダを書き出せるようにするための写し
- 雛形を直したら `python3 scripts/build.py` を実行し、更新された SKILL.md も一緒に commit する
- 雛形にファイルを足す・消すときは、雛形の `CLAUDE.md` の地図も合わせる
- 質問は雛形の `>` 行に書く。未回答の印は「（未記入）」、置き換える名前は `{{…}}`。点検スキルがこの 2 つを数える
- 雛形の `CLAUDE.md` は 100 行以内
- 生成されたフォルダは、プラグインが無くても動くように保つ（育て方は雛形の `CLAUDE.md` に書く）
- 雛形とスキルの文章は日本語。プラグインの構成要素（フォルダ名・スキル名）は英小文字とハイフン

## 確かめ方

```
python3 scripts/build.py --check   # SKILL.md の写しが template/ と一致しているか
claude plugin validate .           # ルートの CLAUDE.md への警告は開発用のものなので無視してよい
python3 scripts/build.py           # 写しを更新して dist/agentbrain.plugin を作る
```

配置の通し確認は、空のフォルダで `claude -p --plugin-dir <この repo> "agentbrain を作って。名前は「山田」。手順 2 まで"` を実行し、できたフォルダを `template/` と `diff -r` する。

## git

main に直接 commit する。配布物（`dist/`）は commit しない。
