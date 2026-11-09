# Note Workflow — 記事制作と公開後の観測を管理する

[![CI](https://github.com/taki-codes/note-auto-post-portfolio/actions/workflows/verify.yml/badge.svg)](https://github.com/taki-codes/note-auto-post-portfolio/actions/workflows/verify.yml)

[設計・コードの読みどころと検証結果](docs/portfolio.md)

noteの記事制作を、テーマごとの資料・進捗・公開台帳・観測記録に分けて管理するローカルワークフローです。Python CLIでひな形の作成、編集前の履歴保存、公開済み記事の登録、観測値の保存と期限管理を行います。

## ブラウザー調査から公開後の観測まで

実際の記事制作では、AIエージェントによるブラウザー操作と、Python CLIによる記録管理を組み合わせました。

| 工程 | 実際に行ったこと |
| --- | --- |
| 需要調査 | ラッコキーワードで検索候補を取得し、note内検索で全記事と有料記事の公開範囲を比較。検索語・出典・確認日を調査シートに記録し、確認した事実と需要の仮説を分けました。 |
| 構成と下書き | 調査を踏まえて無料部分と有料部分の役割を設計し、構成案・下書き・公開後の改善案をテンプレートで整理しました。 |
| 公開準備と公開 | 本人の指示に基づいてnoteの編集・公開画面を操作し、タイトル・タグ・有料ライン・販売設定を確認。公開完了の表示と公開URLを確認しました。 |
| 公開後の記録 | 公開済み記事を台帳へ登録し、確認できた観測値と取得条件を保存。CLIで観測期限と状態を管理します。 |

ブラウザーでの調査・公開を含む運用全体のうち、このリポジトリで試せるのはテンプレートとローカルの記録処理です。調査シートの構成と、架空データでの観測・期限処理を確認できます。[調査テンプレート](templates/01_research.md) · [架空データのデモ](#通信しないデモ)

## 主な機能

- テーマ別フォルダーと9種類のMarkdownひな形を作成。同名テーマは連番にして既存資料を保持
- 編集前のファイルを日時付きの `.history/` に保存
- 公開済み記事をCSV台帳へ登録し、公開日から90日後の観測期限を計算
- スキ・閲覧数・購入数を、取得日時・情報元・取得方法とともにJSONへ記録
- 記事ごとの観測を一時停止・再開し、期限後は最終記録を保存して完了へ移行
- 観測時期の目安を、台帳を変更せず一覧表示

## 技術と設計

Python 3.10以上の標準ライブラリだけを使用します。追加パッケージ、APIキー、環境変数の設定は不要です。

| 設計 | 実装上の工夫 |
| --- | --- |
| 記録の検証 | ID、URL、台帳の列、日付、重複、負の観測値などを保存前に確認 |
| 不明とゼロの区別 | 未取得の数値は `null`、実測したゼロは `0` として保存 |
| 更新履歴 | CSVの更新前に旧版を退避し、一時ファイルから置換 |
| 時刻の扱い | 時刻付き入力にはタイムゾーンを必須とし、日本時間へ正規化 |
| ファイル操作の範囲 | プロジェクト外への履歴保存を拒否 |
| 観測の状態遷移 | 期限後の最終記録を先に保存し、その後に台帳を完了へ更新 |

CLIは外部サイトへの通信、ログイン、記事の投稿・公開、予約の登録を行いません。調査や公開、定期実行は別の工程として扱います。

## クイックスタート

```powershell
git clone https://github.com/taki-codes/note-auto-post-portfolio.git
cd note-auto-post-portfolio

python scripts/note_workflow.py --help
python scripts/note_workflow.py new-theme --slug sample-topic --theme '記事のテーマ'
```

`themes/YYYY-MM-DD_sample-topic/` に、素材、進捗、調査、構成、下書き、集客案のひな形を作成します。日付は日本時間です。

既存資料を変更する前には、対象の相対パスを指定して履歴を保存します。

```powershell
python scripts/note_workflow.py checkpoint themes/対象フォルダー/02_article_plan.md
```

### 公開済み記事の登録

次の `ACCOUNT`、`ARTICLE`、日時、テーマは、実際に公開済みの記事の値へ置き換えます。`--confirmed-published` は利用者による確認を表し、CLIによる公開操作や公開状態の取得ではありません。

```powershell
python scripts/note_workflow.py register --id article-001 --theme '記事のテーマ' --url 'https://note.com/ACCOUNT/n/ARTICLE' --published-at '2026-11-01T12:00:00+09:00' --access-type free --confirmed-published
```

`--access-type` は `free`、`paid`、`membership`、`mixed` から選択します。未来の日付、重複する記事IDやURL、共有キーなどのクエリを含むURLは登録を拒否します。

### 観測・状態管理

```powershell
# 7・14・30・60・90日の目安と期限到達を確認
python scripts/note_workflow.py due

# 許容された方法で確認した値だけを入力。未取得の数値引数は省略
python scripts/note_workflow.py observe --id article-001 --source '確認した記事URL' --method '手動確認' --likes 3 --notes '閲覧数・購入数は未取得'

# 一時停止。再開時は --status active を指定
python scripts/note_workflow.py set-status --id article-001 --status paused --reason '一時停止の理由'

# 期限到達後の最終記録。数値を取得できなかった理由も記録可能
python scripts/note_workflow.py observe --id article-001 --source '確認対象のURL' --method '手動確認' --final --notes '期限到達。数値は未取得'
```

`observe` は期限当日以降の記録を最終記録として扱い、台帳を `completed` へ更新します。`--final` を期限前に指定するとエラーになります。一時停止中も、期限到達後は最終記録の対象です。

## ディレクトリ

```text
scripts/note_workflow.py  CLIと記録処理
tests/                   一時フォルダーを使うライフサイクルテスト
templates/               新テーマのひな形
themes/                  テーマ別の制作資料
compliance/              サービス利用条件の確認記録
published_articles.csv   公開済み記事の台帳
monitoring/              観測結果と運用手順
proposals/               根拠と仮説を分けた改善案
.history/                編集前の履歴（Git対象外）
```

設計と操作例は [コードの案内](docs/portfolio.md) を参照してください。この公開用ソースには、個別の記事制作手順・公開設定・観測運用の記録を含めていません。定期実行は利用環境ごとに別途設定します。

## 通信しないデモ

```sh
python examples/run_demo.py
python examples/run_demo.py --out demo-records
```

架空の公開情報・観測値を一時ディレクトリで処理します。実際の台帳は変更しません。`--out` は存在しない保存先を指定してください。

## テスト

```powershell
python -B -m unittest discover -s tests -v
```

2026年11月8日にWindows / Python 3.13.1で既存3テストの成功を確認しました。期限と状態遷移、不正入力時の台帳保持、同名テーマを上書きしない動作を、一時フォルダー内で検証します。外部サービスの取得・公開処理は検証対象に含みません。

## 制約と今後の改善

- 同時書き込み用のロックはありません。台帳を変更するコマンドは並列実行しないでください。
- 台帳の値と観測結果は利用者が確認して入力します。数値の真正性や、URL先の公開状態を自動検証する機能はありません。
- `due` は観測時期の目安です。予約の作成やバックグラウンド実行は行いません。
- `themes/` や観測記録には個別の制作資料が含まれます。共有する際は、公開可能な資料とコードの範囲を確認してください。

## ライセンス

現時点ではリポジトリにライセンスファイルを設定していません。コード、記事、画像それぞれの再利用条件は別途確認してください。

## この公開用ソースについて

[元のコードとの差分・含める範囲](PORTFOLIO-SOURCE.md)を参照してください。個別の運用情報と元のGit履歴を含まない公開用ソースです。
