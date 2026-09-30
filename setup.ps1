# Windows（Claude Code）用セットアップ。何度実行しても、揃っている物は飛ばす。
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
# Linux のチャット環境は setup.sh を使う。音声合成は VOICEVOX アプリの HTTP API（voice.py の http）。
# 注意：Windows PowerShell 5.1 が日本語を読めるよう、このファイルは BOM 付き UTF-8 で保存する。
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"   # 進捗表示があると Invoke-WebRequest が極端に遅くなる
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Set-Location $PSScriptRoot

# Linux の /usr/share/fonts/opentype/noto と同じ OTC 形式（index 0 = JP）。文字幅をそろえて lint の判定を一致させる
$FontRelease = "https://raw.githubusercontent.com/notofonts/noto-cjk/Sans2.004/Sans/OTC"
$FontNames = @("NotoSansCJK-Bold.ttc", "NotoSansCJK-Regular.ttc")
$VoicevoxUrl = if ($env:VOICEVOX_URL) { $env:VOICEVOX_URL } else { "http://127.0.0.1:50021" }
$VoicevoxEngineExe = "C:\Program Files\VOICEVOX\vv-engine\run.exe"
$RequiredFilters = @("loudnorm", "ebur128", "sidechaincompress", "amix")
$problems = @()

function Get-File([string]$Url, [string]$Destination) {
    if ((Test-Path $Destination) -and (Get-Item $Destination).Length -gt 0) { Write-Host "skip  $Destination"; return }
    Write-Host "get   $Destination"
    # 途中で切れた不完全なファイルを「揃っている」と誤認しないよう、.part に落としてから名前を変える
    Invoke-WebRequest -Uri $Url -OutFile "$Destination.part" -UseBasicParsing
    Move-Item "$Destination.part" $Destination -Force
}

# ---------- フォント ----------
New-Item -ItemType Directory -Force fonts | Out-Null
foreach ($name in $FontNames) { Get-File "$FontRelease/$name" "fonts\$name" }

# ---------- Python（venv） ----------
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "make  .venv"
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "venv を作れませんでした（python が PATH にあるか確認）" }
}
$Python = ".venv\Scripts\python.exe"
# PowerShell 5.1 は外部コマンドの引数に含まれる " を壊すので、Python のコードは ' だけで書く
& $Python -c 'import importlib.util as u, sys; sys.exit(0 if all(u.find_spec(m) for m in [''numpy'', ''PIL'', ''pydantic'']) else 1)'
if ($LASTEXITCODE -ne 0) {
    Write-Host "pip   numpy Pillow pydantic"
    & $Python -m pip install -q --disable-pip-version-check numpy Pillow "pydantic>=2.13,<3"
    if ($LASTEXITCODE -ne 0) { throw "pip install に失敗しました" }
}

# ---------- ffmpeg ----------
foreach ($tool in @("ffmpeg", "ffprobe")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { $problems += "$tool が PATH にありません（例：winget install Gyan.FFmpeg）" }
}
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    $filters = (ffmpeg -hide_banner -filters) -join "`n"
    foreach ($filter in $RequiredFilters) {
        if ($filters -notmatch "\s$filter\s") { $problems += "ffmpeg に $filter フィルタがありません（full ビルドを入れる）" }
    }
}

# ---------- VOICEVOX ----------
$voicevoxVersion = $null
try { $voicevoxVersion = Invoke-RestMethod -Uri "$VoicevoxUrl/version" -TimeoutSec 3 } catch { }
if (-not $voicevoxVersion) {
    $hint = if (Test-Path $VoicevoxEngineExe) { "起動：Start-Process `"$VoicevoxEngineExe`" -WindowStyle Hidden" } else { "VOICEVOX（https://voicevox.hiroshiba.jp/）を入れて起動" }
    $problems += "VOICEVOX に接続できません（$VoicevoxUrl）。$hint"
}

# ---------- 動作確認：フォントを読み、VOICEVOX が動いていれば1文だけ合成する ----------
$check = @'
import pydantic, PIL
from draw import F
F(40); F(40, bold=False)
msg = f'OK  pydantic {pydantic.VERSION} / Pillow {PIL.__version__} / fonts'
try:
    from voice import HttpEngine
    wav, kana = HttpEngine().speak('セットアップ完了なのだ。', 3, 1.25)
    msg += f' / VOICEVOX test wav {len(wav)} bytes（{kana}）'
except SystemExit:
    msg += ' / VOICEVOX 未確認'
print(msg)
'@
if ($voicevoxVersion) { Write-Host "VOICEVOX engine $voicevoxVersion" }
& $Python -c $check
if ($LASTEXITCODE -ne 0) { $problems += "Python の動作確認に失敗しました（上の出力を参照）" }

if ($problems.Count -gt 0) {
    Write-Host ""
    foreach ($problem in $problems) { Write-Host "[要対応] $problem" }
    exit 1
}
Write-Host "setup OK"
