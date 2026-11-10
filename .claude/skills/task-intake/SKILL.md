---
name: task-intake
description: 「issueを起票して」「issueを切りたい」「タスクを追加して」「計画を立てて」「設計して」「着手前にスコープを固めたい」「次なにやる？」で発動。ヒアリングでスコープ・受け入れ条件を固め、Work Item（docs/work-items/）と必要ならGitHub Issueにする。
---

# タスクの整理（Work Item / Issue）

着手前に曖昧さを削る。特に `night-run` に渡すタスクは、AIが夜中に自分で判断する余地を減らしておく。判断するのは常にユーザー。

- **Work Item**（`docs/work-items/WORK-<slug>.md`）: 実装の正本。依頼の原文・受け入れ条件・決めたこと・結果・詰まった点まで1ファイルに残る
- **GitHub Issue**: やりたいことの入口（後でやる・共有する・night-run に渡す）。Work Item の `issue:` から指す

プランモードは「質問して承認まで実装しない」進め方を担い、ここは成果物の型と置き場所を担う。

## 「次なにやる？」と聞かれたら

`python3 scripts/work_items.py --next` の結果を伝える（進行中があればその続き、無ければ依存が片付いた ready の先頭）。一覧は引数なし。自分で Work Item を開いて並べ直さない。

## Step 1: 作るかを決める

次は Work Item にしない（そのまま実装するか口頭で答える）: タイポ・1行の修正・設定値の変更 / 調査・質問 / 会話で既にスコープと完了条件が合意済み。**迷う規模だけが対象。**

## Step 2: 依頼の原文を確保する

依頼文を**そのまま**取っておく（要約しない）。会話の外（Notion・Slack・Issue 等）にあるなら貼ってもらい、出どころのリンクも残す。レビューはこの原文と差分を突き合わせる。

## Step 3: 重複と関係を確かめる

`python3 scripts/new_doc.py grep "<キーワード>"` と `gh issue list --search "<キーワード>"` で似たものを探す。あれば新規か既存の更新かを聞く。**同じ概念なら既存の Work Item を更新する**。前提になる Work Item があれば `depends_on` に入れる。`docs/decisions/` の承認済みADRと食い違わないかも見る。

## Step 4: 観点で理解を深める

会話の中で確かめる（明らかに関係ない観点は軽く流す）:

- **Engineer**: 実現可能か・既存の構成や規約・承認済みADRと合うか・工数感・負債にならないか
- **PM**: 優先度（P0〜P3）・大きすぎれば分割（Work Item を分け `depends_on` でつなぐ）・依存
- **PO**: テスト可能な受け入れ条件にできるか・誰にどんな価値があるか
- **Designer**（UIがあれば）: 既存パターンとの一貫性・`ui-guidelines` の制約
- **専門観点**（ゲームの手触り・デバイス互換性など）: 体験・品質の懸念は、他が問題なくても流さず一緒に解消する

**原文に無い判断**は、出どころ（原文 / 確認済み / 仮決め）を控えておく。**後から覆すと影響が大きい設計の決定**（構成・ツール・データの持ち方・ワークフロー）なら、ADR を起こすかを聞く: `python3 scripts/new_doc.py adr <slug> --title "..."`（`proposed` で作られる。承認するのは人間）。

## Step 5: ドラフト → 確認

`python3 scripts/new_doc.py work <slug> --title "<タイトル>" --priority <P0-P3> [--issue <URL>] [--depends-on WORK-x]` で型どおりのファイルを作り、各見出しを埋める（依頼の原文 / 背景 / 受け入れ条件（`- [ ]`）/ スコープ / スコープ外 / 決めたこと / 実装方針 / 並列化の単位 / 想定リスク）。関係するADRは frontmatter の `adrs:` に書く。

内容を提示し、AskUserQuestion で「確定 / 直す / やめる」。**承認されるまで実装に進まない。** 確定したら `python3 scripts/check_records.py` を通す。

## Step 6: Issue も作るなら

後でやる・共有する・night-run に渡すなら Issue も作る。`gh label list` で優先度のラベルがあれば使う（**無ければ勝手に作らない**）。作成は外部の状態を変えるので、本文を見せて承認を得てから（AGENTS.md ルール4）: `gh issue create --title ... --body ...`。URL を Work Item の `issue:` に書き、`night-run-hearing` にこの URL を渡せば夜間実行に回せると添える。`gh` が無ければ（`brew install gh && gh auth login`）Work Item だけで進めてよい。
