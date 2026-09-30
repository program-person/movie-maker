# movie-maker 引き継ぎメモ（技術）

台本 JSON から、ずんだもん音声（VOICEVOX）の縦型解説動画を生成する Python＋ffmpeg のパイプライン。

最終更新：2026/9/29（JST）

---

## 1. 現状

| ステップ | 内容 | 状態 |
|---|---|---|
| 1 | 台本 JSON のスキーマ（Pydantic） | 実装済み |
| 2 | 縦切り：hook / list の2型で JSON → 動画 | 実装済み・チャット環境で実行確認（2026/9/28） |
| 3 | 残り5型（tier / bars / price / cards / end）を追加し、legacy の Opus 5.5 縦型動画を JSON だけで再現 | 実装済み・legacy と全シーン画素一致を確認（2026/9/29） |
| 4 | 自動チェック（長さ・音量・字幕はみ出し・行頭禁則・speak の英字など） | 実装済み・チャット環境で実行確認（2026/9/29） |
| 5 | skill 化（SKILL.md に台本の書き方・セットアップ・分割描画の手順） | SKILL.md 作成・チャット環境で手順どおりに1本通して確認。ひが claude.ai の別チャットで skill を使い、台本で止まって確認を求める → 動画作成まで動いたことを確認（2026/9/30） |
| 6 | Windows 対応（音声合成を CORE / VOICEVOX アプリの HTTP API で差し替え可能に） | **次はここ**（Claude Code で進める。着手メモは 11 章） |
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
| samples/ | 台本サンプル（opus55_slice.json：hook＋list、opus55_full.json：全7型・9シーン） |
| tests/compare_legacy.py | legacy と新描画を同じ cue で全コマ画素比較（ステップ3の合格判定） |
| lint.py | 描画前チェック（はみ出し・重なり・枠からのはみ出し・行頭禁則・speak の英字）。`check` / `voice` / `all` から自動で呼ばれる |
| .claude/skills/movie-maker/ | skill 本体。SKILL.md（共通：流れ・台本の書き方）＋ references/chat.md（claude.ai）・claude-code.md（Windows、現状は台本作成まで）。Claude Code はこの場所から自動で読み込む。claude.ai にはこのフォルダを zip にしてアップロード |
| tests/schema_negative.py | わざと壊した台本26件がスキーマで弾かれるか |
| tests/lint_negative.py | わざと壊した台本12件を lint が見つけるか |
| tests/verify_negative.py | 完成 mp4 をわざと壊した5件を verify が見つけるか |
| legacy/ | 旧試作（手書きシーン版）。ステップ3の配置・数値の参照元。make_vertical.py は make_video.py を import する |

生成物（git 管理外）：`vv/`（VOICEVOX 一式、約100MB）、`build/<台本名>/`（音声・シーン動画・中間ファイル）。

---

## 3. 使い方

```
bash setup.sh
python3 build.py check   台本.json              # スキーマ検証＋描画前チェック（lint）
python3 build.py voice   台本.json              # 合成し、読みのカナを表示 → 目で確認
python3 build.py scene   台本.json <番号>       # シーン1つを描画（1コマンド300秒制限のため分割）
python3 build.py finish  台本.json <出力.mp4>   # 結合＋声＋BGM＋音量調整 → 最後に verify
python3 build.py verify  台本.json <出力.mp4>   # 描画後チェック（形式・コマ数・音声の長さ・音量）
python3 build.py all     台本.json <出力.mp4>   # 短い台本なら一括
python3 build.py preview 台本.json <番号> <秒> <出力.png>

python3 tests/schema_negative.py                                   # スキーマの異常系
python3 tests/lint_negative.py                                     # 描画前チェックの異常系
python3 tests/verify_negative.py 台本.json 完成.mp4                 # 描画後チェックの異常系（完成品が必要）
python3 tests/compare_legacy.py samples/opus55_full.json <新> <旧>  # 仮の声（全セリフ3秒）で全コマ比較
python3 tests/compare_legacy.py … --real --step 5                   # 合成済みの実際の長さで、5コマおき
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
    "audio": {"lufs": -14.0, "true_peak": -1.0},
    "credit": "出典：…（画面下に出す表記）",
    "sources": [{"label": "…", "url": "https://…"}]
  },
  "scenes": [ {"type": "hook", …}, {"type": "list", …} ]
}
```

共通ルール
- 定義にないキーはエラー（`extra="forbid"`）。打ち間違い検出のため。
- `sources` は1件以上必須（URL 形式を検証）。
- 空白（改行・全角スペース含む）だけの文字列はエラー。
- `meta.audio` は省略可（既定 −14 LUFS / −1.0 dBTP）。finish がこの目標に合わせ、verify が ±1.0 LU・上限以下かを確かめる。
- 各シーンは `lines: [{"text": 字幕, "speak": 読み上げ}]` を1つ以上持つ。**speak は省略不可**（字幕と同じ文でも書く）。英語の固有名詞は speak 側をカタカナに。
- `cue` は「lines の何番目のセリフの開始に合わせて表示するか」（0始まり）。範囲外はエラー。
- `cue` を持つ要素はすべて任意の `delay`（秒、0〜5、既定0）を持てる。表示時刻 = cue のセリフ開始 + delay。
- 色は名前で指定：`fg`（白）/ `sub`（薄い灰）/ `acc`（オレンジ）/ `warn`（黄）/ `gray`（濃い灰）/ `blue`。実際の色は draw.py の `PALETTE`。
- シーンの `credit` を書くと、そのシーンだけ meta.credit を上書き。

hook（つかみ）

| キー | 型 | 説明 |
|---|---|---|
| title | str 1〜2個 | 大きいアクセント色の行 |
| lead | str | 白い中サイズの行（1.2秒で表示、描画側で固定） |
| big | str | 一番強い情報（2.6秒でポップ表示、描画側で固定） |
| ask | {text, cue, delay?} 任意 | 「何が変わった？」など |

list（箇条書き・注意点）

| キー | 型 | 説明 |
|---|---|---|
| num | "05" 形式 | 見出し番号 |
| title | str | 見出し |
| style | "normal" / "warn" | warn は「!」＋黄色 |
| items | 1〜3個 {main, note?, cue, delay?} | main は `\n` で手動改行可 |

tier / bars / price / cards は list と同じく `num`（"01" 形式）と `title`（見出し）が必須。

tier（位置づけ）

| キー | 型 | 説明 |
|---|---|---|
| intro | {text, cue, delay?} 任意 | 見出し下の小さい説明 |
| tiers | 2〜3個 {name, desc, color, highlight?, cue, delay?} | 上から順。間に ▲ が入る。highlight=true は枠が横幅いっぱい |

bars（棒グラフ）

| キー | 型 | 説明 |
|---|---|---|
| legend | 1〜3個 {name, color} | 系列。color が "acc" の系列だけ数値もオレンジ |
| rows | 1〜3個 {label, sublabel?, values, cue, delay?} | values は legend と同数・0〜max。棒は cue の0.2秒後から1.2秒で伸びる |
| max | 数値（既定100） | 棒の最大幅に当たる値 |
| unit | 3文字まで（既定 "%"） | 数値の後ろに付く |

price（料金の比較）

| キー | 型 | 説明 |
|---|---|---|
| intro | {text, cue, delay?} 任意 | 見出し下の小さい説明 |
| rows | 1〜3個 {name, old, new, change, cue, delay?} | 表示用の文字列。new は0.25秒、change は0.45秒遅れて出る |
| summary | {lines: 1〜2個, cue, delay?} 任意 | オレンジの帯。1行目が大きい |
| note | {text, cue, delay?} 任意 | 帯の下の小さい注記 |

cards（数字を大きく見せる事例）

| キー | 型 | 説明 |
|---|---|---|
| items | 1〜2個 {big, mid, rest, cue, delay?} | big は大きいオレンジの数字、mid はその右、rest は下の段。3枚目は字幕と重なるため不可 |

end（締め。見出しなし）

| キー | 型 | 説明 |
|---|---|---|
| items | 1〜5個 {text, size, color?, y, cue, delay?} | 中央揃えで y（文字の上端、200〜1250）に置く。size は30〜130 |

---

## 5. 設計判断の記録

- スキーマ：型ごとに厳密な discriminated union（`type` の値で検証するクラスを切り替える）。Pydantic 2.13.5 で実行確認。
- 描画の割り当て：`type → 描画関数` の対応表（dict）。モデルに render() を持たせる案は、検証だけしたい場面でも描画部品が必要になるため不採用。
- タイムライン：シーンの長さを先にフレーム数に丸めてから開始時刻を積む。映像と声の位置が一致する（旧版は最大0.1秒ずれる可能性があった）。
- 型を追加する手順：schema.py にモデルを書いて `Scene` の Union に追加し、`timed()` で cue を持つ要素を返す（範囲チェックは共通） → scenes.py に関数を書いて `RENDERERS` に登録。
- 色：台本では名前で指定（色コードは不可）。打ち間違いをスキーマで弾け、色味の変更が draw.py の1か所で済むため（2026/9/29、ひが選択）。
- セリフ開始からのずらし：要素ごとの任意 `delay`（2026/9/29、ひが選択）。描画側の固定値は、hook の lead/big、bars の棒、price の new/change のように型の演出として決まっているものだけ。
- 再現の判定：legacy の描画関数と同じ cue を渡して全コマの画素差分がゼロであること（2026/9/29、ひが選択）。仮の声の長さ（全セリフ3秒）で全コマ、実際の長さで5コマおきを確認済み。
- end は配置が不規則（行間がそろっていない）ため、y と size を台本で直接指定する形にした。
- 描画前チェック（2026/9/29、ひが選択）：描画関数は変えず、ImageDraw の代わりに記録係（lint.Recorder）を渡して、描いた文字・枠の外接矩形で判定する。どの要素が原因かを名指しできるため、画像の画素で調べる案より優先した。全要素が出そろった状態（t=1e4）で判定する。
- lint の重さ：はみ出し・重なり・枠またぎはエラー（止める）、行頭禁則・speak の英字は警告（「AI」のようにそのままで正しく読まれる英字があるため）。許可する英字は lint.SPEAK_OK。
- 音量（2026/9/29、ひが選択）：finish で loudnorm を2パス（1回目で測定→2回目に反映）。目標は −14 LUFS / −1.0 dBTP。TikTok は公式の数値を出しておらず、−14 LUFS・−1 dBTP は一般的な目安（要検証）。AAC でピークが約0.2dB上がるので loudnorm には上限より0.5dB低い値を渡す（build.TP_MARGIN）。
- 1コマ落ち（2026/9/29、ひが選択）：finish の `-shortest` を外し、verify でコマ数の完全一致を確かめる。
- skill（2026/9/30）：claude.ai 向けを主にする（もとの目的が「普通のチャットで指示して作れる」こと）。skill は1つにして環境別の手順を references/ に分ける。claude.ai の skill は Claude Code にも同期されるため、別名で2つ作ると同時に読み込まれて取り合いになる。
- skill の frontmatter は name と description だけ（claude.ai のアップロードで使える項目に限る）。description は claude.ai の上限200文字以内（現在99文字）。
- コードの持ち込み（2026/9/30、ひが選択）：claude.ai では skill の手順で GitHub から clone する（同梱しない）。コードの更新は push だけで反映される。
- 確認待ち（2026/9/30、ひと合意）：台本ができたら既定で止め、台本と「確認してほしい事実の一覧」を出す。依頼文に「確認なしで」などの明示があるときだけ止めない。Claude の判断では省かない。

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
- 描画速度：実時間の約1.3〜2.2倍（2026/9/29〜30 の実測。zunda-rules 40.8秒 → 4シーンで68秒。list 20.3秒 → 44秒、bars 20.7秒 → 31秒、end 9.5秒 → 13秒）。1分を超えるシーンは300秒に近づく（原因未調査・要検証）。
- 以前の finish は `-shortest` で最後の1コマが落ちていた（AAC 化した音声が約0.3ミリ秒短いため）→ `-shortest` を外して解消（2026/9/29）。
- ffprobe の音声 duration は AAC の前後の詰め物を含み、実際より長く出る（opus55_full で 140.800s、実際は 140.736s）。verify は音声を復号して長さを数える。loudnorm 後も声の位置のずれは 0ms（8kHz で相互相関を取って確認）。
- 元のミックスは、瞬間的な山が平均より約20dB高い（−20.1 LUFS に対して −0.4 dBTP）。このため loudnorm は同じ倍率をかけるだけでは目標を満たせず、自動追従（dynamic）方式に切り替わる。声の抑揚が少し平らになる方向だが、ひが opus55_full を聴いて問題なしと確認（2026/9/30）。
- 読み間違い：「C言語」→「スィー言語」と読まれた（「しー言語」に）。`voice` の kana 出力で必ず確認。「AI」は「エエアイ」で問題なし。
- VOICEVOX の出力は冒頭に約0.1秒強の無音がある（声の実際の開始は cue の約0.14秒後）。
- bgm.py：動画の長さが1小節（2.727秒）の倍数をわずかに超えると落ちていた → エンベロープとフェードの長さを区間長で頭打ちにして修正済み。
- 字幕の改行：句読点で区切ったまとまりごとに詰める／英数字のかたまりは切らない／句読点・小さい文字を行頭に置かない。

---

## 8. 縦型の仕様（現行値）

- 1080×1920、30fps、H.264（crf 21, preset fast）、AAC 192k。
- 配置（縦型 SNS の UI を避ける）：本文 x 70〜940／字幕枠の下端 y=1470／出典・クレジット y 1500〜1540／y 1580 以降は何も置かない。
- 間：最初のシーンの前 0.3秒、各シーンの前 0.45秒、セリフ間 0.22秒、シーン後 0.6秒（最後は1.2秒）。話速 1.25。
- ミックス：声 ×1.25、BGM ×0.2、サイドチェインで声の間は BGM を下げる → loudnorm（2パス）。実測（2026/9/29）：opus55_full 140.7秒・opus55_slice 32.8秒とも −14.3 LUFS / −1.3 dBTP。
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
- lint の安全範囲の上端 y=150 は仮の値（縦型SNSの上部タブを避ける目安）。実機で未確認。
- lint が見ていないもの：出てくる途中（フェード・スライド中）の重なり／枠どうしの重なり／文字が別の枠の内側に完全に入り込む場合。
- Claude Code（Windows）では動画を作れない（音声合成が Linux 用 CORE、フォントの場所が Linux 固定）。ステップ6で対応。
- opus55_full.json の sources は Anthropic 公式の1件だけ。注意点シーンの出典（Artificial Analysis、Wccftech 経由）の URL が入っていない。また各 URL が実在するかも未確認（事実確認は人が行う範囲）。

---

## 11. ステップ6 着手メモ（Claude Code 向け、2026/9/30 作成）

ステップ6は、ひの Windows PC 上の Claude Code で進める（チャットの Linux 環境では Windows・VOICEVOX アプリでの確認ができないため）。
このメモは、チャット側で Linux 環境からコードを読んで洗い出したもの。**Windows では一つも実行していない。**

### 目的

Windows の Claude Code から `build.py check → voice → scene → finish` を通し、verify が OK の mp4 を作れるようにする。
チャット環境（Linux・VOICEVOX CORE）で今の動作が壊れないこと。

### コードから見つけた Linux 依存（未実行・要確認）

| 場所 | 内容 | Windows で起きそうなこと |
|---|---|---|
| voice.py | Linux 用の VOICEVOX CORE（`.so`、manylinux の wheel）を読み込む | 動かない。音声合成の差し替えが必要 |
| setup.sh | bash スクリプト。Linux 用の一式を取ってくる | そのままでは使えない |
| draw.py | フォントの場所が `/usr/share/fonts/opentype/noto/…` 固定 | 描画・lint・preview がすべて止まる |
| build.py の BGM 生成 | `subprocess.run(["python3", …bgm.py…])` | Windows では `python3` というコマンドがないことが多い。`sys.executable` にすれば環境に依らない |
| lint.py など | 表示に「⏎」などを使う | 出力が cp932（Windows の日本語の既定の文字コード）だと表示で落ちる可能性（推測） |
| ffmpeg / ffprobe | PATH から呼ぶ | 入っていなければ入れる。ebur128・loudnorm・sidechaincompress が使えるビルドか確認 |

ファイルの読み書きは、日本語を含むものは `encoding="utf-8"` 指定済み。指定のない箇所（durations.json・segs.txt）は ASCII だけなので影響しない見込み。

### 決めること（着手前にひと相談）

1. 音声合成のつなぎ方
   - VOICEVOX アプリの HTTP API（アプリを起動しておき `http://localhost:50021` の audio_query → synthesis を呼ぶ想定・要確認）
   - Windows 用の VOICEVOX CORE を入れる（Windows 版の wheel・ランタイムがあるか要確認）
   - schema.py の `meta.voice.engine` は今 `"core"` だけ。差し替え口として値を足す想定（コメントに `"http"` 予定と書いてある）
2. フォント
   - Noto Sans CJK（OFL ライセンスで再配布可）を取ってきて使う → Linux と同じ見た目・同じ文字幅。legacy との画素比較・lint の結果もそろう見込み（Pillow や FreeType の版の違いで細かくずれる可能性はある・要検証）
   - Windows に入っているフォント（游ゴシックなど）を使う → 手軽だが文字幅が変わり、lint の結果も画素比較も Linux と一致しなくなる
   - どちらにしても、場所を環境変数か設定で変えられるようにする
3. セットアップの方法：setup.sh の Windows 版（PowerShell）を作るか、Python で書き直して両環境で共通にするか
4. 描画の分け方：Claude Code のコマンドは既定2分・上限10分で時間切れになり、時間切れのコマンドは裏で続く（公式ドキュメント tools-reference、2026/9/30 確認）。シーンごとに分けるかを決める

### 着手前に手元で確かめること

- VOICEVOX アプリが起動し、ずんだもんで喋るか（2026/9/7 に導入済みとの報告あり。現在の状態は未確認）
- アプリ起動中にブラウザで `http://localhost:50021/docs` が開けるか（API の説明ページ・要確認）
- `ffmpeg -version`・`python --version`（または `py --version`）の結果
- Claude Code のシェルが PowerShell か Git Bash か

### 終わりの条件（案）

- Windows：samples/opus55_slice.json で `all` が通り、verify が OK。
- Linux：push 後に claude.ai のチャット環境で、`tests/` の3本と `compare_legacy.py`（全シーン）が今まで通り通ることを確認する（Windows の Claude Code からは確かめられない）。
- `.claude/skills/movie-maker/references/claude-code.md` を、実際に動いた手順に書き換える。

