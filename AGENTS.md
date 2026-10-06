# agentbrain

仕事の文脈を AI に渡すためのフォルダ「agentbrain」の雛形と、それを作る・点検する手順を配る repo。配り方は 2 つあり、中身は同じ。

- **プラグイン**（`dist/agentbrain.plugin`）: スキルとして入れる
- **リモート MCP**（Worker `agentbrain-mcp`、`https://agentbrain.taskf.co.jp/mcp`、認証なし）: コネクタとして足す

紹介ページ `https://agentbrain.taskf.co.jp` も同じ Worker が出す（`worker/public/index.html`）。

**公開 repo。** 秘密の値、社内の情報、利用者や顧客の名前を commit しない（履歴にも残る）。

## 構成

| パス | 中身 |
|---|---|
| `skills/agentbrain-setup/SKILL.md` | **作る手順の正本。** 末尾の「雛形の中身」だけは生成物 |
| `skills/agentbrain-setup/template/` | **雛形の正本。** 利用者のフォルダに写される実ファイル |
| `skills/agentbrain-check/SKILL.md` | **点検する手順の正本** |
| `.claude-plugin/plugin.json` | プラグインの定義。配布のたびに `version` を上げる |
| `.claude-plugin/marketplace.json` | Claude Code から配布元として登録するための定義 |
| `worker/` | MCP サーバー（Cloudflare Worker、依存なし・ステートレス）。`src/content.gen.ts` は生成物 |
| `worker/public/index.html` | 紹介ページ（1 ファイル、ビルドなし）。フォルダの中身は `/api/template` から読むので、雛形を直せばページにも出る |
| `scripts/build.py` | 正本から生成物と `dist/agentbrain.plugin` を作る |

## 規約

- 雛形を直すのは `template/`、手順を直すのは 2 つの SKILL.md の本文だけ。README や Worker に中身の写しを手で書かない
- 生成物は 2 つで、どちらも `scripts/build.py` が作る。手で直さない
  - `agentbrain-setup/SKILL.md` 末尾の「雛形の中身」: スキルが自分の `template/` を読めない環境（権限で止まる場合）でも同じフォルダを書き出せるようにする写し
  - `worker/src/content.gen.ts`: MCP が返す手順と雛形。手順は SKILL.md の本文に、MCP 向けの読み替え（`build.py` の `MCP_PREAMBLE`）を前置きしたもの
- 正本を直したら `python3 scripts/build.py` を実行し、生成物も一緒に commit する（ずれは CI が止める）
- 雛形にファイルを足す・消すときは、雛形の `CLAUDE.md` の地図も合わせる
- 質問は雛形の `>` 行に書く。未回答の印は「（未記入）」、置き換える名前は `{{…}}`。点検の手順がこの 2 つを数える
- 雛形の `CLAUDE.md` は 100 行以内
- 生成されたフォルダは、プラグインや MCP が無くても動くように保つ（育て方は雛形の `CLAUDE.md` に書く）
- 雛形と手順の文章は日本語。プラグインの構成要素（フォルダ名・スキル名）と MCP のツール名は英小文字
- MCP サーバーはファイルを書かない。書くのはクライアント側なので、手順は「返した中身をそのまま書き出す」前提で書く
- `/mcp` は認証なしで公開している。返してよいのは、公開している手順と雛形だけ。利用者の入力を受け取るツールや、社内の情報を返すツールを足さない
- 紹介ページの文言は、手順や雛形の実際の動きと合わせる（頼み方の言葉、ファイル数、受け取らないもの）。変えたら両方を直す

## 確かめ方

```
python3 scripts/build.py --check        # 生成物が正本と一致しているか
claude plugin validate .                # ルートの CLAUDE.md への警告は開発用のものなので無視してよい
python3 scripts/build.py                # 生成物を更新して dist/agentbrain.plugin を作る
(cd worker && npx tsc --noEmit)         # Worker の型検査
```

配置の通し確認は、空のフォルダで次のどちらかを実行し、できたフォルダを `template/` と `diff -r` する（差は名前の置き換えだけになる）。

```
claude -p --plugin-dir <この repo> --permission-mode acceptEdits "agentbrain を作って。名前は「山田」。手順 2 まで"
claude -p --strict-mcp-config --mcp-config <MCP の URL を書いた json> --permission-mode acceptEdits "（同じ依頼）"
```

## 開発フロー（tskf `01-operations/playbooks/infra/dev-flow.md`）

- **git 方針**: `pr` — `tskf/<項目 id>` ブランチ → PR → CI が緑なら自分で squash merge（`gh pr checks <PR> --watch --fail-fast && gh pr merge <PR> --squash --delete-branch`）
- **CI / Deploy**: 公開 repo は tskf の再利用可能ワークフローを呼べないので、`.github/workflows/` に型を写した自己完結版を置いている
- **デプロイ**: main への merge で GitHub Actions `Deploy` が `worker/` を出す。手で出す予備は `cd worker && npm run deploy`。プラグイン（`dist/`）は commit せず、配るときに `build.py` で作る
- **本番デプロイは事前承認済み**（承認ゲートで止めるのは 外部送信・削除・課金・アプリの外部配信 だけ）
- 公開面は独自ホスト `agentbrain.taskf.co.jp`（`wrangler.jsonc` の `routes`）。`mcp.taskf.co.jp/agentbrain/<secret>`（ゲートウェイ経由、`MCP_PATH_SECRET` で内部認証）は、公開前に配った URL のために残している
