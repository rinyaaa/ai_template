---
id: ADR-work-items-and-decisions
title: 作業はWork Item、設計の決定はADRに残す
status: accepted
supersedes: []
depends_on: []
created_at: 2026-11-10T00:28:35+09:00
updated_at: 2026-11-10T11:19:12+09:00
effective_at: 2026-11-10T11:19:12+09:00
---

# 作業はWork Item、設計の決定はADRに残す

## 背景

計画書（`docs/plans/`）は状態・優先度・依存を持たず、作業記録（`docs/history/`）はその内容と重なっていた。設計の決定を残し、守らせる仕組みも無かった。ユーザーの言葉:「WorkItemとかADRとかって今できてる？」「historyっているかな？」。2026-11-09〜10 の会話（`WORK-slim-ai-harness`）で決めた。依頼の原文はその Work Item にある。

## 決定

- 作業1件ごとの正本は Work Item（`docs/work-items/WORK-<slug>.md`）。状態・優先度・依存・関係するADR・Issue の URL を frontmatter に持ち、本文に依頼の原文・受け入れ条件・決めたこと・Evidence・詰まった点を書く。計画書と作業記録はここに統合し、`docs/plans/`・`docs/history/` は廃止する
- 設計の決定は ADR（`docs/decisions/ADR-<slug>.md`）。追記型で、承認済みのものは書き換えず、変えるときは新しいADRで `supersedes` する
- ID は意味のある固定の slug（連番・日付を入れない）。一覧はファイルの frontmatter から作る（索引を手で書かない）
- 決まりは `scripts/check_records.py` で検査し、pre-commit は承認済みADRの「決定」「理由」の書き換えを止める
- GitHub Issue は「やりたいことの入口」、Work Item は「実装の正本」
- 進捗の一覧（`CURRENT.md`）は置かず、`work_items.py --next` で代える

## 理由

- 1件の作業の情報が1ファイルにまとまり、次の作業を機械的に選べる
- 決定を追記型にすると、当時の理由が残り、「いつの間にか変わった」を防げる
- 比べた案: (a) 計画書と作業記録を残して Work Item を足す → 置き場所が3つになり、どれが正か迷う。(b) `CURRENT.md` も入れる → 毎回書き直す手間とトークンがかかる割に、`--next` で足りる
- 参考: 参考にした別プロジェクト の `manage-work-items`・`docs/decisions/`・`check_docs.py`

## 影響

- Work Item を作らない小さな作業は記録が残らない（git の履歴だけ）
- 検査は記録の形と関係だけを見る。判断や理由が正しいかはレビューで見る
- 既存の作業記録2件は Work Item に移した（`WORK-harness-template` は当時の依頼の原文が無い）
