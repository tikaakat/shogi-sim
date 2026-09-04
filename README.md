# shogi-sim

CIRCUIT SHOGI EVOLUTION の学習パイプライン。GitHub Actions上で
やねうら王（MATERIAL版）をビルドし、個性を持つ将棋AIを世代交代・交配させる。

## セットアップ手順

### 1. このリポジトリの構成をアップロード
`shogi_sim/`, `scripts/`, `.github/workflows/evolve.yml`, `run_evolution.py`,
`requirements.txt` を、GitHubの`shogi-sim`リポジトリにそのままアップロードする。
`data/`フォルダは空のまま（初回実行時に自動生成される）でよいが、
Gitが空フォルダを追跡できないので `data/.gitkeep`（中身は空でよい）を1つ置いておく。

### 2. GitHub Secretsの設定
リポジトリの Settings → Secrets and variables → Actions → New repository secret
で、以下を登録する（Xserverへの自動アップロード用）。

| Secret名 | 内容 |
|---|---|
| `XSERVER_HOST` | XserverのSSHホスト名（サーバーパネルで確認） |
| `XSERVER_USER` | SSHユーザー名 |
| `XSERVER_SSH_PASSWORD` | SSHパスワード（鍵認証にする場合は別途ワークフロー修正が必要） |
| `XSERVER_SSH_PORT` | SSHポート番号（Xserverは通常 `10022`） |
| `XSERVER_TARGET_DIR` | アップロード先。例: `/home/xs281342/shogi2/colab_export/` |
| `IMPORT_SECRET_KEY` | `import_from_colab.php` の `IMPORT_SECRET_KEY` と同じ値 |

### 3. 実行方法
GitHubリポジトリの「Actions」タブ →「Evolve Shogi Individuals」→
「Run workflow」ボタンを押す（世代数などはその場で指定可能）。
スマホのブラウザからでも実行できる。

実行が終わると：
- `data/individuals.json` / `data/matches.json` がリポジトリにコミットされる（全履歴がGit上に残る）
- 自動的にXserverへアップロードされる
- `import_from_colab.php` が自動で呼ばれ、DBに反映される

つまり、ボタンを押すだけで学習→Xserver反映まで完結する。

## ローカル/Colabでのテスト実行

```bash
pip install -r requirements.txt
bash scripts/build_yaneuraou.sh /tmp/YaneuraOu
python run_evolution.py \
  --engine-path /tmp/YaneuraOu/source/YaneuraOu-by-gcc \
  --data-dir data \
  --generations 2
```

## 設計メモ
- 個体は「やねうら王のMultiPV上位候補手」の中から、個性パラメータ
  （攻撃性・玉の安全重視度・駒の価値観）でボーナスを加点して1手を選ぶ
  （`shogi_sim/personality.py`）。最善手から200点以内の候補のみが対象。
- 世代交代は Elo 上位 + 「個性が際立つ個体」を別枠で残す方式
  （`select_survivors`）。Elo上位だけで選抜すると個性が均一化するため。
- ベンチマーク相手はやねうら王の思考時間を短く（既定80ms）することで
  強さを抑え、「将棋ウォーズ1級〜初段」程度を狙う。強すぎる場合は
  `--opponent-think-ms` をさらに下げる。
