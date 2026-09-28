"""台本JSONのスキーマ定義（ステップ1）

対応する型：hook（つかみ）／list（箇条書き・注意点）
型を増やすときは、Scene の Union に追加する。
"""
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class Strict(BaseModel):
    # extra="forbid"：定義にないキー（打ち間違いなど）があったらエラーにする
    model_config = ConfigDict(extra="forbid")


# ---------- 共通部品 ----------
class Line(Strict):
    """セリフ1つ。text は字幕、speak は読み上げ用（英語の固有名詞はカタカナにする）"""
    text: str = Field(min_length=1)
    speak: str = Field(min_length=1)


class Source(Strict):
    label: str = Field(min_length=1)
    url: HttpUrl


class Voice(Strict):
    engine: Literal["core"] = "core"          # 将来 "http"（Windows の VOICEVOX アプリ）を追加予定
    style_id: int = 3                         # 3 = ずんだもんノーマル
    speed: float = Field(default=1.25, gt=0.5, le=2.0)


class Meta(Strict):
    title: str = Field(min_length=1)
    format: Literal["vertical"] = "vertical"  # 横型は必要になったら追加
    voice: Voice = Voice()
    credit: str = Field(min_length=1)         # 画面下に出す出典表記（シーンごとに上書き可）
    sources: list[Source] = Field(min_length=1)  # 出典URLは必須


class SceneBase(Strict):
    lines: list[Line] = Field(min_length=1)
    credit: Optional[str] = None              # None なら meta.credit を使う

    def _check_cue(self, cue: int, where: str):
        if not 0 <= cue < len(self.lines):
            raise ValueError(f"{where} の cue={cue} が範囲外（lines は {len(self.lines)} 個）")


class Cued(Strict):
    """表示タイミングを lines の何番目のセリフに合わせるか（0始まり）"""
    text: str = Field(min_length=1)
    cue: int


# ---------- シーンの型 ----------
class HookScene(SceneBase):
    type: Literal["hook"]
    title: list[str] = Field(min_length=1, max_length=2)  # 大きいアクセント色の行
    lead: str = Field(min_length=1)                        # 白い中サイズの行
    big: str = Field(min_length=1)                         # 一番強い情報（ポップして出る）
    ask: Optional[Cued] = None                             # 「何が変わった？」など

    @model_validator(mode="after")
    def check_cues(self):
        if self.ask:
            self._check_cue(self.ask.cue, "ask")
        return self


class ListItem(Strict):
    main: str = Field(min_length=1)   # "\n" で手動改行できる
    note: Optional[str] = None
    cue: int


class ListScene(SceneBase):
    type: Literal["list"]
    num: str = Field(pattern=r"^\d{2}$")          # 見出しの番号 "05" など
    title: str = Field(min_length=1)
    style: Literal["normal", "warn"] = "normal"   # warn = 「!」マーク＋黄色
    items: list[ListItem] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def check_cues(self):
        for i, it in enumerate(self.items):
            self._check_cue(it.cue, f"items[{i}]")
        return self


# type の値を見て、どのクラスで検証するかを決める（discriminated union）
Scene = Annotated[Union[HookScene, ListScene], Field(discriminator="type")]


class Script(Strict):
    meta: Meta
    scenes: list[Scene] = Field(min_length=1)


def load(path: str) -> Script:
    with open(path, encoding="utf-8") as f:
        return Script.model_validate_json(f.read())


if __name__ == "__main__":
    import sys
    s = load(sys.argv[1])
    print(f"OK: {s.meta.title} / {len(s.scenes)} シーン / "
          f"セリフ {sum(len(sc.lines) for sc in s.scenes)} 個")
