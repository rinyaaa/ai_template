---
id: WORK-template-portability
title: 派生プロジェクトでの汎用性（テンプレート自身の記録・判定・既定ブランチ・既存hook・導入手順）
status: ready
priority: P2
depends_on: [WORK-slim-ai-harness]
adrs: []
issue: 
created_at: 2026-11-10T11:15:22+09:00
updated_at: 2026-11-10T11:19:43+09:00
blocked_reason:
design_impact: pending
design_impact_reason:
---

# 派生プロジェクトでの汎用性（テンプレート自身の記録・判定・既定ブランチ・既存hook・導入手順）

## 依頼の原文

> あとこれはテンプレとーなどでいろんなプロジェクトで汎用的にできてるかチェックして

続く依頼（同じ会話。汎用性チェック G-1〜G-8 を示し、「別の Work Item にする」案に対して）:
> それでお願いします

## 背景・なぜやるか

このリポジトリは、いろいろなプロジェクトに入れて使うテンプレート。2026-11-10 にコードと設定を読んで汎用性を確かめたところ、派生プロジェクトでそのまま壊れる箇所や、テンプレート固有のものが混ざる箇所があった（派生プロジェクトを実際に作っての試しはまだしていない）。

- G-1: テンプレート自身の Work Item・ADR が派生先に入る。`work_items.py --next` がテンプレートの作業を出す。承認済みの ADR は pre-commit が書き換えを止めるので、派生先で消せない。依頼の原文に個人のパスが入っている
- G-2: テンプレートかどうかを、マニフェスト5種（package.json / pyproject.toml / go.mod / Cargo.toml / Gemfile）が無いことで推測している（`scripts/verify_safety_net.py:178`・`scripts/health_check.py:142`）。Flutter・Java/Kotlin・Swift・.NET・PHP、requirements.txt だけの Python は、テンプレート扱いになる。すると SHA 固定と dependabot の検査で CI が落ち、健康診断も埋め忘れを見ない。似た一覧が `review_bundle.py:30`・`detect_stack.py` にもあり、中身が揃っていない
- G-3: 既定ブランチ `main` を決め打ちしている（`night-run/night_runner.py:130-131,307,322`・`night-run/docker/entrypoint.sh:40`・CI の `branches: [main]`）
- G-4: husky・lefthook・pre-commit framework が使う `core.hooksPath` とぶつかる。併用の手順が無い
- G-5: 既存のプロジェクトへの入れ方（持ち込むファイル、既存の CLAUDE.md・AGENTS.md・workflows・.cursor とぶつかったときの扱い）が書いていない
- G-6: hook と pre-commit が `python3` と sh を前提にしている。動く環境の前提が README に無い
- G-7: 汎用のドキュメントに、テンプレート固有の文が混ざっている。「参考にした別プロジェクト」への言及（非公開のローカルプロジェクトで、他の人には辿れない）・LICENSE の著作者・`verify-template.yml` の名前とコメント
- G-8: 日本語前提であることが README に書いていない

## 受け入れ条件

- [ ] G-1: 派生プロジェクトを作った直後、`work_items.py --next` と `check_records.py` がテンプレート自身の Work Item・ADR を対象にしない。テンプレート自身の記録を消すか分ける手順があり、テストで確かめる
- [ ] G-2: テンプレートかどうかを明示の目印で判定する。pubspec.yaml だけ・pom.xml だけ・requirements.txt だけのプロジェクトを、テンプレートと判定しないことをテストで確かめる。マニフェストの一覧は1か所にまとめる
- [ ] G-3: night-run と CI の既定ブランチを、決め打ちせずに求めるか設定できる。既定が master のリポジトリで動くことをテストで確かめる
- [ ] G-4: 既存の hook 管理（husky 等）があることを検出したら、`core.hooksPath` を上書きせず、既存の hook から `.githooks/pre-commit` を呼ぶ手順を案内する。安全網は弱めない（deny hook の `core.hooksPath` の検査はそのまま）
- [ ] G-5: README に、既存のプロジェクトへ入れる手順（持ち込むファイル・ぶつかったときの扱い）がある
- [ ] G-6・G-8: README に、動く環境の前提（OS・Python のバージョン・任意の依存・日本語前提）がある
- [ ] G-7: 汎用のドキュメント・スキルに、外の人が辿れない参照が無い。LICENSE と CI 名が「派生プロジェクトで埋めるもの」の表に載っている
- [ ] 一時ディレクトリに作った3通りの派生プロジェクト（pubspec.yaml だけ / husky 入りの Node / 既定が master）で、`verify_safety_net.py`・`health_check.py`・`check_records.py`・pre-commit が誤検知なく通る。結果を Evidence に書く
- [ ] 既存の検査（verify_safety_net・scripts/tests・hook の回帰・night-run のテスト・check_records・scan_agent_content）がすべて通る

## スコープ

G-1〜G-8 の修正と、そのテスト・README・スキル（主に `claude-project-setup`・`project-health-check`）の更新。

## スコープ外

- Windows でのネイティブ対応（PowerShell 版の hook 等）。今回は前提を書くだけにする（確認済み。下の「決めたこと」）
- 英語化・多言語化
- night-run-hearing の Antigravity 手順が参照する `.agents/hooks.json` / `deny_dangerous_agy.py`（WORK-slim-ai-harness でスコープ外として記録済み）

## 決めたこと

- 確認済み: ドラフトの内容で確定（ユーザーの回答:「確定」）
- 確認済み: WORK-slim-ai-harness には混ぜず、別の Work Item にする（ユーザーの言葉: 「それでお願いします」）
- 仮決め: `depends_on: [WORK-slim-ai-harness]`。触るファイル（verify_safety_net.py・health_check.py・README 等）が、未コミットのまま WORK-slim-ai-harness で変わっているため
- 確認済み: 優先度 P2（ユーザーの回答:「P2 のまま」）
- 確認済み: Windows はネイティブ対応せず、前提（macOS / Linux / WSL）を README に書くだけにする（ユーザーの回答:「前提を書くだけ」）
- 仮決め: G-1（テンプレート自身の記録の扱い）と G-2（判定の目印）は、構成とワークフローの決定にあたる。着手時に方式を比べ、ADR を起こすかを聞く

## 実装方針

1. G-2 から始める。判定の目印（案: `config/template.json` の `is_template: true`。セットアップで消す）と、マニフェストの一覧を1か所にまとめる（案: `scripts/_stack.py`）。verify_safety_net・health_check・review_bundle・detect_stack から使う
2. G-1。案A: テンプレート自身の記録を `docs/template/` などへ移し、検査と一覧の対象から外す。案B: `claude-project-setup` に「テンプレート自身の記録を片付けて新しく始める」手順とスクリプトを足す。比べて ADR にする
3. G-3。既定ブランチを `origin/HEAD` から求める（`review_bundle.py:55` の処理を共通化する）。night-run は環境変数でも指定できるようにする
4. G-4〜G-8 は、README とスキルの更新が中心
5. 一時ディレクトリで3通りの派生プロジェクトを作り、通しで確かめる

## 並列化の単位

直列（G-1〜G-3 が同じ検査スクリプトを触るため）

## 想定リスク・確認事項

- G-1 で記録を動かすと、WORK-slim-ai-harness が参照しているパスとリンクが変わる。verify_safety_net のリンク検査で確かめる
- G-2 で判定を変えると、テンプレート自身の CI の検査（SHA 固定など）が外れる危険がある。テンプレート自身では今までどおり効くことをテストで確かめる
- G-4 の検出のために deny hook に例外を足すことはしない（安全網を弱めない）

## Evidence

<!-- 完了時に: 変えたファイル・検証したコマンドと結果・PR -->

## 詰まった点・知見

<!-- 完了時に: 詰まった点となぜそうなったか / 次に同じ領域を触る人が知っていると得をすること。効くものは CLAUDE.md かスキルへ昇格させ「→ 昇格」と添える -->
