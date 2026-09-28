# movie-maker 引き継ぎメモ（技術）

台本 JSON から、ずんだもん音声（VOICEVOX）の縦型解説動画を生成する Python＋ffmpeg のパイプライン。

最終更新：2026/9/28（JST）

---

## 1. 現状

| ステップ | 内容 | 状態 |
|---|---|---|
| 1 | 台本 JSON のスキーマ（Pydantic） | 実装済み |
| 2 | 縦切り：hook / list の2型で JSON → 動画 | 実装済み・チャット環境で実行確認（2026/9/28） |
| 3 | 残り5型（tier / bars / price / cards / end）を追加し、legacy の Opus 5.5 縦型動画を JSON だけで再現 | **次はここ** |
| 4 | 自動チェック（長さ・音量・字幕はみ出し・行頭禁則・speak の英字など） | 未着手 |
| 5 | skill 化（SKILL.md に台本の書き方・セットアップ・分割描画の手順） | 未着手 |
| 6 | Windows 対応（音声合成を CORE / VOICEVOX アプリの HTTP API で差し替え可能に） | 未着手 |
| 7 | （任意）立ち絵：口パク・まばたき・表情 | 未着手 |

範囲の方針：事実確認と投稿は人が行い、自動化しない。パイプラインの責任範囲は動画ファイルの生成まで。

---

## 2. ファイル構成

| ファイル | 役割 |
|---|---|
| setup.sh | VOICEVOX 一式と Python 依存を揃える。再実行すると揃っている物は飛ばす（初回約12秒、2回目約3秒） |
| build.py | CLI 本体。タイムライン計算・フレーム描画・声トラック・最終合成 |
| schema.py | 台本 JSON の Pydantic モデル。単体で `python3 schema.py 台本.json` で検証可 |
| voice.py | VOICEVOX CORE で全セリフを合成。durations.json と kana.txt（読み確認）を出力 |
| draw.py | 描画の共通部品（色・フォント・イージング・折り返し・見出し・字幕・クレジット） |
| scenes.py | シーン型ごとの描画関数と `RENDERERS = {type: 関数}` の対応表 |
| bgm.py | numpy で BGM を生成。`python3 bgm.py <秒数> <出力wav>` |
| samples/ | 台本サンプル（opus55_slice.json：hook＋list） |
| legacy/ | 旧試作（手書きシーン版）。ステップ3の配置・数値の参照元。make_vertical.py は make_video.py を import する |

生成物（git 管理外）：`vv/`（VOICEVOX 一式、約100MB）、`build/<台本名>/`（音声・シーン動画・中間ファイル）。

---

## 3. 使い方

```
bash setup.sh
python3 build.py check   台本.json              # 検証だけ
python3 build.py voice   台本.json              # 合成し、読みのカナを表示 → 目で確認
python3 build.py scene   台本.json <番号>       # シーン1つを描画（1コマンド300秒制限のため分割）
python3 build.py finish  台本.json <出力.mp4>   # 結合＋声＋BGM
python3 build.py all     台本.json <出力.mp4>   # 短い台本なら一括
python3 build.py preview 台本.json <番号> <秒> <出力.png>
```

チャット環境はセッションごとにリセットされるので、毎回 `setup.sh` から。
`voice` の後に台本の speak や voice 設定を変えると、`scene` / `finish` は止まる（manifest.json と照合）。

---

## 4. 台本 JSON の仕様

```json
{
  "meta": {
    "title": "…",
    "format": "vertical",
    "voice": {"engine": "core", "style_id": 3, "speed": 1.25},
    "credit": "出典：…（画面下に出す表記）",
    "sources": [{"label": "…", "url": "https://…"}]
  },
  "scenes": [ {"type": "hook", …}, {"type": "list", …} ]
}
```

共通ルール
- 定義にないキーはエラー（`extra="forbid"`）。打ち間違い検出のため。
- `sources` は1件以上必須（URL 形式を検証）。
- 各シーンは `lines: [{"text": 字幕, "speak": 読み上げ}]` を1つ以上持つ。**speak は省略不可**（字幕と同じ文でも書く）。英語の固有名詞は speak 側をカタカナに。
- `cue` は「lines の何番目のセリフの開始に合わせて表示するか」（0始まり）。範囲外はエラー。
- シーンの `credit` を書くと、そのシーンだけ meta.credit を上書き。

hook（つかみ）

| キー | 型 | 説明 |
|---|---|---|
| title | str 1〜2個 | 大きいアクセント色の行 |
| lead | str | 白い中サイズの行（1.2秒で表示、描画側で固定） |
| big | str | 一番強い情報（2.6秒でポップ表示、描画側で固定） |
| ask | {text, cue} 任意 | 「何が変わった？」など |

list（箇条書き・注意点）

| キー | 型 | 説明 |
|---|---|---|
| num | "05" 形式 | 見出し番号 |
| title | str | 見出し |
| style | "normal" / "warn" | warn は「!」＋黄色 |
| items | 1〜3個 {main, note?, cue} | main は `\n` で手動改行可 |

ステップ3で追加する型の候補パラメータ（未確定）
- tier：intro_text, tiers[{name, desc, color}]
- bars：legend[{name, color}], rows[{label, sublabel, values[], cue}]
- price：intro_text, rows[{name, old, new, pct, cue}], summary_lines[], note
- cards：items[{big, mid, rest, cue}]
- end：lines[{text, size, color, delay}]

---

## 5. 設計判断の記録

- スキーマ：型ごとに厳密な discriminated union（`type` の値で検証するクラスを切り替える）。Pydantic 2.13.5 で実行確認。
- 描画の割り当て：`type → 描画関数` の対応表（dict）。モデルに render() を持たせる案は、検証だけしたい場面でも描画部品が必要になるため不採用。
- タイムライン：シーンの長さを先にフレーム数に丸めてから開始時刻を積む。映像と声の位置が一致する（旧版は最大0.1秒ずれる可能性があった）。
- 型を追加する手順：schema.py にモデルを書いて `Scene` の Union に追加 → scenes.py に関数を書いて `RENDERERS` に登録。

---

## 6. 環境（setup.sh の中身）

- VOICEVOX CORE 0.17.0（Python wheel）、音声モデル voicevox_vvm 0.16.4 の `0.vvm`、VOICEVOX 用 ONNX Runtime 1.17.3、Open JTalk 辞書 1.11。URL は setup.sh 参照。
- ずんだもんのスタイルID：0.vvm でノーマル=3、あまあま=1、ツンツン=7、セクシー=5。5.vvm でささやき=22、ヒソヒソ=38。
- 出力 WAV は 24kHz / モノラル / 16bit。
- フォント：`/usr/share/fonts/opentype/noto/NotoSansCJK-{Bold,Regular}.ttc` の index=0（JP）。

---

## 7. ハマりどころ

- GitHub API の回数制限（共有 IP）で公式ダウンローダーが失敗する → setup.sh はリリースの直接 URL を使う。
- 1コマンド300秒で打ち切られ、`nohup … &` でも止まる → シーン単位で `build.py scene` を分けて実行。
- 描画速度：list シーン 20.9秒の描画に44秒（実時間の約2.1倍）。1分を超えるシーンは300秒に近づく（原因未調査・要検証）。
- 読み間違い：「C言語」→「スィー言語」と読まれた（「しー言語」に）。`voice` の kana 出力で必ず確認。「AI」は「エエアイ」で問題なし。
- VOICEVOX の出力は冒頭に約0.1秒強の無音がある（声の実際の開始は cue の約0.14秒後）。
- bgm.py：動画の長さが1小節（2.727秒）の倍数をわずかに超えると落ちていた → エンベロープとフェードの長さを区間長で頭打ちにして修正済み。
- 字幕の改行：句読点で区切ったまとまりごとに詰める／英数字のかたまりは切らない／句読点・小さい文字を行頭に置かない。

---

## 8. 縦型の仕様（現行値）

- 1080×1920、30fps、H.264（crf 21, preset fast）、AAC 192k。
- 配置（縦型 SNS の UI を避ける）：本文 x 70〜940／字幕枠の下端 y=1470／出典・クレジット y 1500〜1540／y 1580 以降は何も置かない。
- 間：最初のシーンの前 0.3秒、各シーンの前 0.45秒、セリフ間 0.22秒、シーン後 0.6秒（最後は1.2秒）。話速 1.25。
- ミックス：声 ×1.25、BGM ×0.2、サイドチェインで声の間は BGM を下げる、alimiter 0.95。サンプル（32.8秒）の実測：平均 −24.4dB、最大 −3.0dB。
- BGM：88BPM、Cmaj7→G→Am7→Fmaj7、パッド・ベース・アルペジオ・軽いリズム。

---

## 9. 規約・クレジット

- VOICEVOX 音声モデル：商用・非商用とも可。VOICEVOX を使ったとわかるクレジットが必要。
- ずんだもん：「VOICEVOX:ずんだもん」のクレジットで商用・非商用とも可。詳細 https://zunko.jp/con_ongen_kiyaku.html
- 動画内（credit）と投稿の説明欄の両方にクレジットと出典を入れる。
- 立ち絵などの素材は `assets/` に置き、git に入れない（素材ごとの規約で再配布不可が多い）。
- API キー等は `.env` に置き、git に入れない。

---

## 10. 未確認事項

- TikTok 実機で字幕などが UI にかぶらないか。
- Windows の VOICEVOX アプリを HTTP API（localhost:50021 想定）で呼べるか。
- skill に同梱できるファイル容量の上限。
- 空白だけの文字列はスキーマを通ってしまう／画面からのはみ出しは未検査（ステップ4で対応）。
