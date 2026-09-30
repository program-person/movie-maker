# claude.ai のチャット環境での手順

前提：Linux のコンテナ。セッションが変わると中身が消える。1コマンドの実行は300秒まで。
ネット接続が必要（コードは GitHub、音声合成の一式は setup.sh が取ってくる）。

## 1. 準備（毎回。すでにあれば更新だけ）

```bash
cd /home/claude
if [ -d movie-maker ]; then git -C movie-maker pull -q; else git clone -q --depth 1 https://github.com/program-person/movie-maker.git; fi
cd movie-maker && bash setup.sh
```

- setup.sh は初回 10 秒前後、揃っていれば数秒。最後に `OK voicevox_core …` と出れば成功。
- clone や setup が失敗したら、エラー文を人に見せて止まる（別の入手先を勝手に使わない）。

## 2. 台本

- 置き場所：`/mnt/user-data/outputs/<英数字の名前>.json`（例 `opus55.json`）。
  中間ファイルは `build/<名前>/` にできるので、名前は英数字とハイフンにする。
- `python3 build.py check /mnt/user-data/outputs/<名前>.json` が通るまで直す。
- 確認待ちで止まるときは、台本ファイルを present_files で渡し、事実の一覧を本文に書く。

### 確認のあとで再開するとき

- `/home/claude/movie-maker` や台本ファイルが消えていたら、1 の準備からやり直し、
  台本は前に渡した内容（と人の修正）で書き直す。
- 人が直した点を台本に反映したら、もう一度 `check` を通す。

## 3. 読み上げ

```bash
python3 build.py voice /mnt/user-data/outputs/<名前>.json
```

- 全セリフのカナが出る。カタカナの固有名詞・数字・漢字の読み（例：「行」がギョウかコウか）を見る。
- 直すときは speak を書き換えて `voice` をやり直す（speak を変えると、古い音声のまま描画しようとしても止まる）。

## 4. 描画（シーンごとに分ける）

```bash
python3 build.py scene /mnt/user-data/outputs/<名前>.json 0
python3 build.py scene /mnt/user-data/outputs/<名前>.json 1
# …最後のシーンまで
```

- 描画には動画の長さの約 1.3〜2.2 倍かかる（2026/9/29 の実測）。
  1回のコマンドで描くシーンは、動画の長さの合計が 60 秒以内になるようにまとめる
  （例：`for s in 0 1 2; do python3 build.py scene … $s; done`）。
- 1シーンだけで 60 秒を超えるなら、台本側でシーンを分ける。
- 見た目を1コマだけ確かめたいとき：`python3 build.py preview 台本.json <シーン番号> <秒> /tmp/p.png` → view で見る。

## 5. 仕上げと受け渡し

```bash
python3 build.py finish /mnt/user-data/outputs/<名前>.json /mnt/user-data/outputs/<名前>.mp4
```

- 最後に verify（コマ数・音声の長さ・音量）が走る。`→ OK` を確認する。NG なら原因を直すまで渡さない。
- present_files で mp4 と台本 JSON を渡す。本文には次を書く：
  - 動画の長さ、verify の結果（ラウドネス・トゥルーピーク）
  - 読みで気になった箇所
  - 確認してほしい事実の一覧
  - 投稿の説明欄に入れる出典とクレジット（`VOICEVOX:ずんだもん`、BGM は自作）
