# 引き継ぎメモ：ずんだもん解説動画 自動生成プロジェクト

作成：2026/9/24（JST）／元の会話：Opus 5.5 の変更点まとめ動画の試作

---

## 1. 目的と確定事項（2026/9/24時点）

- **目的**：指示を出すと、Claude がずんだもん音声の解説動画を作れるようにする。将来的には AI エージェントに委託し、副業につなげることも視野に入れる。
- **統合**：以前からの「ゆっくり／ずんだもん動画スキル」構想（YMM4 Lite＋VOICEVOX 導入済み）と、今回のコード生成方式を1つのプロジェクトに統合する。これは確定。
- **作り方**：Python＋ffmpeg のコード方式を主軸にする。YMM4 は、手で仕上げたい回だけ使う補助の位置づけ。
- **進め方**：案Aで進める。まずチャット環境（Linux）で本体を作り、後から Windows に移植する。
- **最終形**：skill 化して、普通のチャットで指示を出すだけで動画が作れる状態にする。
- **人がやる部分**：事実確認と TikTok への投稿。どちらも自動化しない。
  - 理由：夜間エージェントの設計原則「安い検証手段がある作業だけ自動化する」「取り消せない操作は自動化しない」に従うため。
- **立ち絵**：将来、必要になったら対応する（任意）。当面は立ち絵なし。
- **投稿先の想定**：テック系の新しい TikTok アカウント。**アカウント作成・投稿はまだしていない。**

---

## 2. 現状

**試作した動画（すべてこのメモを作った会話の中で生成）**
1. 横 1280×720、約68秒、音なし
2. 横、ずんだもんナレーション＋字幕＋BGM、約2分46秒
3. 縦 1080×1920、ずんだもん＋字幕＋BGM、約2分21秒（TikTok 向け）

**まだ確認できていないこと**
- 音そのもの（Claude は音を聴けない）。確認できているのは、音量の数値と音割れがないことだけ。
- TikTok 実機で字幕などが UI にかぶらないか。
- skill に同梱できるファイル容量の上限。
- Windows の VOICEVOX アプリを HTTP API（localhost:50021 の想定）で呼べるか。

**今のコードの限界**
シーンごとに数値や配置を手書きしている。エージェントやスキルに任せるには、「台本 JSON → 動画」の形に作り直す必要がある。

---

## 3. 手持ちのファイル（src/）

| ファイル | 役割 | 依存 |
|---|---|---|
| make_video.py | 横版（音なし）。色・フォント・イージングなどの共通部品を含む | なし |
| make_video2.py | 横版＋音声・字幕・BGM | make_video.py, narration.py |
| make_vertical.py | 縦版。分割レンダリング（render_scene / finish）あり | make_video.py, narration_v.py |
| narration.py / narration_v.py | 台本。各セリフを（字幕に出す文, 読み上げ用の文）の組で持つ | なし |
| synth.py | VOICEVOX CORE で合成。`python3 synth.py <台本モジュール> <出力先>`、環境変数 SPEED で話速を指定 | voicevox_core |
| bgm.py | numpy で BGM を自作。`python3 bgm.py <秒数> <出力wav>` | numpy |

**注意**：make_vertical.py は make_video.py から共通部品を import している。make_video.py も必ず一緒に置くこと。

---

## 4. 検証済みの環境構築（チャットの Linux 環境）

**使ったもの（2026/9/23 に取得して動作を確認）**
- VOICEVOX CORE **0.17.0**：Python wheel `voicevox_core-0.17.0-cp310-abi3-manylinux_2_34_x86_64.whl`
- 音声モデル voicevox_vvm **0.16.4**：`0.vvm`（約58MB）にずんだもんが入っている
- ONNX Runtime：`voicevox_onnxruntime-linux-x64-1.17.3.tgz`（VOICEVOX 用ビルド）
- 読み上げ辞書：`open_jtalk_dic_utf_8-1.11.tar.gz`（r9y9/open_jtalk の v1.11.1）

**ずんだもんのスタイルID**
- 0.vvm：ノーマル=3、あまあま=1、ツンツン=7、セクシー=5
- 5.vvm：ささやき=22、ヒソヒソ=38

**ダウンロードURL（直接指定）**
```
https://github.com/VOICEVOX/voicevox_core/releases/download/0.17.0/voicevox_core-0.17.0-cp310-abi3-manylinux_2_34_x86_64.whl
https://github.com/VOICEVOX/voicevox_vvm/releases/download/0.16.4/0.vvm
https://github.com/VOICEVOX/onnxruntime-builder/releases/download/voicevox_onnxruntime-1.17.3/voicevox_onnxruntime-linux-x64-1.17.3.tgz
https://github.com/r9y9/open_jtalk/releases/download/v1.11.1/open_jtalk_dic_utf_8-1.11.tar.gz
```
wheel のインストール：`pip install <whl> --break-system-packages`

**最小の呼び出し例（0.17.0 の実物で API を確認済み）**
```python
from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
ort = Onnxruntime.load_once(filename=".../lib/libvoicevox_onnxruntime.so.1.17.3")
syn = Synthesizer(ort, OpenJtalk(".../open_jtalk_dic_utf_8-1.11"))
with VoiceModelFile.open(".../0.vvm") as m:
    syn.load_voice_model(m)
q = syn.create_audio_query("読み上げる文", 3)   # 3 = ずんだもんノーマル
q.speed_scale = 1.25
wav = syn.synthesis(q, 3)                      # 出力は WAV（24kHz / モノラル / 16bit）
kana = "".join(m.text for ap in q.accent_phrases for m in ap.moras)  # 読み確認用
```

**フォント**：`/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc` の index=0 が Noto Sans CJK JP。

---

## 5. ハマりどころと対策

- **GitHub API の回数制限**：共有 IP のため、公式ダウンローダー（download-linux-x64）は API の回数制限で失敗した。上の直接 URL を使う。最新版を調べたいときは、API ではなく `releases/latest` のリダイレクト先や `releases/expanded_assets/<tag>` の HTML から取る。
- **1コマンド300秒の制限**
  - `nohup … &` で裏に回しても、コマンドが終わると一緒に止まった。
  - 対策：シーンごとに `seg_N.mp4` へ描画し、複数回のコマンドに分けてから `ffmpeg -f concat` で結合する。
- **描画速度**：1080×1920 で実時間の約1.5倍かかる（11.9秒のシーンに17.4秒）。
- **読み間違い**
  - 英語の固有名詞は、読み上げ側の文をカタカナにする（Opus → オーパス）。
  - 「C言語」は「スィー言語」と読まれたので、「しー言語」に変えた。
  - 対策の基本：合成時に全セリフのカナを出力して目で確認する。
- **字幕の改行**
  - 句読点で区切ったまとまりごとに詰める。
  - 英数字のかたまりは途中で切らない。
  - 句読点や小さい文字を行頭に置かない。
  - 箇条書きの本文は `\n` で手動改行する。
- **フレーム数の丸め誤差**：シーン単位で描くと、全体で最大0.1秒程度ずれる可能性がある。後半の1コマで字幕とナレーションが合っていることは確認済み。

---

## 6. 縦型の仕様（現行値）

- **画面**：1080×1920、30fps、H.264（crf 21）、AAC 192k。
- **TikTok の UI を避ける配置**
  - 本文は x 70〜940 に収める（右のボタン列を避ける）。
  - 字幕枠の下端は y=1470。
  - 出典とクレジットは y 1500〜1540。
  - 下部の説明文エリア（y 1580 以降の想定）には何も置かない。
- **タイミング**
  - ナレーションの長さからシーンの長さを自動で決める。
  - 各要素は、対応するセリフの開始に合わせて表示する。
  - 間の長さ：PRE 0.45秒 / GAP 0.22秒 / POST 0.6秒。話速は1.25倍。
- **ミックス**
  - 声の音量 ×1.25、BGM の音量 ×0.2。
  - サイドチェインコンプレッサーで、声が鳴っている間は BGM を下げる。
  - 最後に alimiter で音割れを防ぐ。
  - 実測値：全体の平均 −24dB、最大 −0.4dB。
- **BGM**：88BPM、コード進行 Cmaj7→G→Am7→Fmaj7、パッド・ベース・アルペジオ・軽いリズム。
- **冒頭**：最初の1秒で一番強い情報（例：「約40%安く」）を出す。

---

## 7. 規約・投稿まわり

- **VOICEVOX 音声モデルの規約**
  - 商用・非商用とも利用可。
  - アプリへの組み込み・再配布も可。
  - 「VOICEVOX を使ったとわかるクレジット」が必要。
- **ずんだもん**：「VOICEVOX:ずんだもん」のクレジットで商用・非商用とも利用可。詳細は https://zunko.jp/con_ongen_kiyaku.html
- **動画への表記**：動画内と説明欄の両方にクレジットと出典を入れる。
- **TikTok の AI ラベル**：公式の対象は「リアルな合成コンテンツ」。ずんだもん音声が該当するかは解釈が分かれる（要検証）。投稿時に「AI生成コンテンツ」トグルをオンにするのが無難。
- **立ち絵**
  - Claude はずんだもんの絵を自分では描かない（既存キャラクターのため）。配布されている素材を使う。
  - 口と目の開閉がパーツ分けされた素材が扱いやすい。
  - 素材ごとの規約（商用可否・クレジット・skill への同梱可否）と、公式のキャラクター利用ガイドラインは、素材を決めてから確認する。
- **事実確認**：ニュース解説は、数字や事実の誤りが致命的。台本には出典 URL を必須にする。

---

## 8. 次のステップ（案A）

1. **仕様決め**：台本 JSON の形式と、シーンの型の一覧を決める。 ← **ここから開始**
2. **縦切り**：シーンの型2つだけで「JSON → 動画」を最後まで通す。
3. **型をそろえる**：Opus 5.5 の縦型動画を JSON だけで再現できたら合格。
4. **自動チェック**：長さ・音量・字幕のはみ出し・行頭の句読点を機械で検査する。エージェントに任せるための「安い検証手段」になる。
5. **skill 化**：SKILL.md に、台本の書き方（出典必須）・セットアップ・分割描画の手順を書く。普通のチャットで1本作らせて確かめる。
6. **Windows 対応と夜間エージェント連携**：音声合成部分だけ差し替えられる作りにする（CORE／アプリの HTTP API）。エージェントがやるのは動画ファイルの生成まで。
7. **（任意）立ち絵対応**：口パク・まばたき・表情の切り替え。

**要検討**：本数は「1日1本」が当初の目安だった。ただ、事実確認の手間を考えると、週2〜3本から始めて手間を測るのが現実的（提案段階・未決定）。

---

## 付録：台本 JSON のたたき台（未決定・ステップ1で議論する用）

```json
{
  "meta": {"title": "...", "format": "vertical", "voice": {"engine": "core", "style_id": 3, "speed": 1.25},
           "sources": [{"label": "Anthropic公式発表", "url": "https://..."}]},
  "scenes": [
    {"type": "hook", "big": "約40%安く", "lines": [{"text": "字幕の文", "speak": "読み上げの文"}]},
    {"type": "bars", "title": "性能テストの結果", "series": ["Opus 5", "Opus 5.5"],
     "rows": [{"label": "コマンドライン作業", "values": [52.3, 66.4], "cue": 1}],
     "lines": [...]}
  ]
}
```
シーンの型の候補：hook（つかみ）／tier（階層図）／bars（棒グラフ）／price（比較カード）／cards（事例）／list（箇条書き・注意点）／end（締め）
