#!/usr/bin/env bash
# チャット環境（Linux x64）用セットアップ。何度実行しても、揃っている物は飛ばす。
set -euo pipefail
cd "$(dirname "$0")"
VV=vv
mkdir -p "$VV"

REL=https://github.com/VOICEVOX
WHL=voicevox_core-0.17.0-cp310-abi3-manylinux_2_34_x86_64.whl
ORT=voicevox_onnxruntime-linux-x64-1.17.3
DIC=open_jtalk_dic_utf_8-1.11

fetch() {  # fetch <URL> <保存先>
  if [ -s "$2" ]; then echo "skip  $2"; return; fi
  echo "get   $2"
  curl -fsSL --retry 3 -o "$2.part" "$1" && mv "$2.part" "$2"
}

fetch "$REL/voicevox_core/releases/download/0.17.0/$WHL"                                   "$VV/$WHL"
fetch "$REL/voicevox_vvm/releases/download/0.16.4/0.vvm"                                   "$VV/0.vvm"
fetch "$REL/onnxruntime-builder/releases/download/voicevox_onnxruntime-1.17.3/$ORT.tgz"    "$VV/$ORT.tgz"
fetch "https://github.com/r9y9/open_jtalk/releases/download/v1.11.1/$DIC.tar.gz"          "$VV/$DIC.tar.gz"

[ -d "$VV/$ORT" ] || tar -xzf "$VV/$ORT.tgz" -C "$VV"
[ -d "$VV/$DIC" ] || tar -xzf "$VV/$DIC.tar.gz" -C "$VV"

python3 -c "import voicevox_core" 2>/dev/null || pip install -q "$VV/$WHL" --break-system-packages
python3 -c "import pydantic" 2>/dev/null     || pip install -q "pydantic>=2.13,<3" --break-system-packages

# 動作確認：1文だけ合成して長さを出す
python3 - <<'EOF'
import voicevox_core, pydantic
from voice import open_synth
syn = open_synth()
q = syn.create_audio_query("セットアップ完了なのだ。", 3)
wav = syn.synthesis(q, 3)
print(f"OK  voicevox_core {voicevox_core.__version__} / pydantic {pydantic.VERSION} / test wav {len(wav)} bytes")
EOF
