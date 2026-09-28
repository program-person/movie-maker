import json, wave, os
from voicevox_core.blocking import Onnxruntime, OpenJtalk, Synthesizer, VoiceModelFile
import sys, importlib
N = importlib.import_module(sys.argv[1] if len(sys.argv)>1 else "narration").N
OUT = sys.argv[2] if len(sys.argv)>2 else "voice"
ort = Onnxruntime.load_once(filename="vv/voicevox_onnxruntime-linux-x64-1.17.3/lib/libvoicevox_onnxruntime.so.1.17.3")
syn = Synthesizer(ort, OpenJtalk("vv/open_jtalk_dic_utf_8-1.11"))
with VoiceModelFile.open("vv/0.vvm") as m: syn.load_voice_model(m)
os.makedirs(OUT, exist_ok=True)
meta = []
for s, lines in enumerate(N):
    row = []
    for i, (disp, spk) in enumerate(lines):
        q = syn.create_audio_query(spk, 3)
        q.speed_scale = float(os.environ.get("SPEED", "1.15"))
        wav = syn.synthesis(q, 3)
        fn = f"{OUT}/{s}_{i}.wav"; open(fn, "wb").write(wav)
        with wave.open(fn) as w: dur = w.getnframes() / w.getframerate()
        kana = "".join(m.text for ap in q.accent_phrases for m in ap.moras)
        print(f"{s}-{i} {dur:.2f}s  {kana}")
        row.append(dur)
    meta.append(row)
json.dump(meta, open(f"{OUT}/durations.json", "w"))
