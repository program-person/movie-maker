# Claude Code（ひの Windows PC）での手順

## 現状（2026/9/30）：動画の生成は未対応

今のコードは Linux 前提で書かれていて、Windows ではそのまま動かない。

- 音声合成：Linux 用の VOICEVOX CORE（setup.sh・voice.py）
- 描画と描画前チェック：フォントの場所が `/usr/share/fonts/...` 固定（draw.py）

Windows 対応（VOICEVOX アプリの HTTP API への切り替え、フォントの場所の設定化）はステップ6の予定。
それまでは、この環境で `setup.sh`・`build.py voice / scene / finish / check` を実行しない。

## この環境でできること

1. 題材を調べ、台本 JSON を書く（書き方は SKILL.md）。リポジトリ内の `samples/` 以外、たとえば `scripts/<名前>.json` に置く。
2. スキーマの検証だけ行う：`python schema.py scripts/<名前>.json`（pydantic だけで動く）。
   はみ出しなどの描画前チェックは、この環境では行えないと人に伝える。
3. 台本と「確認してほしい事実の一覧」を人に渡して終わる。
   動画にするときは、claude.ai のチャットでこの台本を渡して作ってもらう。

## ステップ6のあとで書き足すこと

- VOICEVOX アプリの起動確認（`http://localhost:50021` に接続できるか）
- 各コマンドの実行手順と、描画の分け方。Claude Code のコマンドは既定2分・上限10分で時間切れになり、
  時間切れのコマンドは止まらず裏で続く（公式ドキュメント tools-reference の「Timeout and output limits」、2026/9/30 確認）。
  チャットの300秒とは条件が違うので、分割の要否は改めて決める。
