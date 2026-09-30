# Claude Code（ひの Windows PC）での手順

前提：Windows 11・PowerShell。音声合成は VOICEVOX アプリ（エンジン）の HTTP API を使う。
コマンドは既定2分・上限10分で時間切れになる（時間切れのコマンドは止まらず裏で続く）。
Python は必ずリポジトリの `.venv\Scripts\python.exe` で動かす（`python3` は使わない）。

## 1. 準備（初回と、依存が変わったとき）

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

- フォント（Noto Sans CJK、`fonts\`）・`.venv`・Python の依存を揃え、ffmpeg と VOICEVOX を確認する。
  揃っていれば3秒ほど。最後に `setup OK` と出れば成功。
- `[要対応]` が出たら、その内容を人に見せる。VOICEVOX に接続できないだけなら、2 の手順で起動してよい。

## 2. VOICEVOX の起動確認（読み上げの前に毎回）

```powershell
Invoke-RestMethod http://127.0.0.1:50021/version
```

- バージョン（例 `0.25.2`）が返れば起動済み。
- 接続できなければ、画面なしでエンジンだけ起動し、数秒待ってからもう一度確かめる：
  `Start-Process "C:\Program Files\VOICEVOX\vv-engine\run.exe" -WindowStyle Hidden`
- それでもつながらなければ人に伝えて止まる（アプリを入れ直すなどはしない）。

## 3. 台本

- 置き場所：`scripts\<英数字の名前>.json`。中間ファイルは `build\<名前>\` にできる。
- `.venv\Scripts\python.exe build.py check scripts\<名前>.json` が通るまで直す。
- 確認待ちで止まるときは、台本のパスを示し、事実の一覧を本文に書く。

## 4. 読み上げ

```powershell
.venv\Scripts\python.exe build.py voice scripts\<名前>.json
```

- 先頭の `# 音声エンジン：http（…）` で、HTTP 経由で合成したことがわかる。
- 全セリフのカナが出る。見る点・直し方は chat.md の「3. 読み上げ」と同じ。

## 5. 描画

```powershell
.venv\Scripts\python.exe build.py scene scripts\<名前>.json 0
.venv\Scripts\python.exe build.py scene scripts\<名前>.json 1
# …最後のシーンまで
```

- 描画には動画の長さの約 0.9〜1.4 倍かかる（2026/9/30、opus55_full の9シーンで実測）。
  1回のコマンドで描くシーンは、動画の長さの合計が 60 秒以内になるようにまとめる
  （例：`foreach ($s in 0..2) { .venv\Scripts\python.exe build.py scene scripts\<名前>.json $s }`）。
  長くなりそうなら、PowerShell ツールの timeout を 600000（10分）にする。
- 短い台本（合計 60 秒くらいまで）は `all` で一括でもよい（opus55_slice 32.8 秒で約1分）。
- 1コマだけ確かめたいとき：`.venv\Scripts\python.exe build.py preview scripts\<名前>.json <シーン番号> <秒> build\p.png` → Read で見る。

## 6. 仕上げと受け渡し

```powershell
.venv\Scripts\python.exe build.py finish scripts\<名前>.json build\<名前>.mp4
```

- 最後に verify が走る。`→ OK` を確認する。NG なら原因を直すまで渡さない。
- mp4 と台本のパスを示す。本文に書くことは chat.md の「5. 仕上げと受け渡し」と同じ。
