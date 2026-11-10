# ADR（設計の決定の記録）

構成・ツール・ワークフロー・データの持ち方など、**後から覆すと影響が大きい決定**を `ADR-<slug>.md` に残す。小さな修正ごとには作らない。

- 作る: `python3 scripts/new_doc.py adr <slug> --title "..." [--supersedes ADR-old]`（`proposed` で作られる）
- 検査: `python3 scripts/check_records.py`

## 決まり

- `status`: `proposed`（提案中）→ `accepted`（承認。人間が決める）/ `rejected`（却下）。置き換えられたら `superseded`
- **承認済みのADRは書き換えない。** 決定を変えるときは新しいADRを作り `supersedes: [ADR-old]` で置き換え、新しいADRを承認したら古い方を `superseded` にする（古い方の本文と理由は残す）。pre-commit が承認済みADRの「決定」「理由」の書き換えを止める
- `accepted` / `superseded` には `effective_at`（有効になった日時）と、「## 背景」「## 決定」「## 理由」「## 影響」の本文が要る（空・TODO は不可）
- 変更の範囲でコードと承認済みのADRが食い違うときは、レビューで見送れない。コードを直すか、新しいADRで置き換える
- 過去の理由が分からないときは、調べた資料と分からない範囲を書く。今日の推測を当時の判断として書かない
- 日時はタイムゾーン付きの ISO-8601。一覧は frontmatter から作るので、ファイルを改名しない
