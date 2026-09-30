"""台本JSONのスキーマ定義

対応する型：hook（つかみ）／list（箇条書き・注意点）／tier（位置づけ）／bars（棒グラフ）／
price（料金の比較）／cards（数字を大きく見せる事例）／end（締め）
型を増やすときは、Scene の Union に追加し、timed() で cue を持つ要素を返す。
"""
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


def _blank(v) -> bool:
    """空白（改行・全角スペース含む）だけの文字列が入っていれば True（リストの中も見る）"""
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, list):
        return any(_blank(x) for x in v)
    return False


class Strict(BaseModel):
    # extra="forbid"：定義にないキー（打ち間違いなど）があったらエラーにする
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def no_blank(cls, v):
        # min_length=1 だけだと " " や "\n" が通るので、空白だけの文字列はここで弾く
        if _blank(v):
            raise ValueError("空白だけの文字列は使えません")
        return v


# ---------- 共通部品 ----------
class Line(Strict):
    """セリフ1つ。text は字幕、speak は読み上げ用（英語の固有名詞はカタカナにする）"""
    text: str = Field(min_length=1)
    speak: str = Field(min_length=1)


class Source(Strict):
    label: str = Field(min_length=1)
    url: HttpUrl


class Voice(Strict):
    # 今は使っていない（既存の台本が通るよう残している）。実際のエンジンは実行環境で決まる（voice.engine_name）
    engine: Literal["core"] = "core"
    style_id: int = 3                         # 3 = ずんだもんノーマル
    speed: float = Field(default=1.25, gt=0.5, le=2.0)


class Audio(Strict):
    """仕上げの音量目標。finish で loudnorm（2パス）をかけ、verify で確かめる"""
    lufs: float = Field(default=-14.0, ge=-24, le=-8)       # ラウドネスの目標（許容 ±1.0 LU）
    true_peak: float = Field(default=-1.0, ge=-6, le=0)     # トゥルーピークの上限（dBTP）


class Meta(Strict):
    title: str = Field(min_length=1)
    format: Literal["vertical"] = "vertical"  # 横型は必要になったら追加
    voice: Voice = Voice()
    audio: Audio = Audio()
    credit: str = Field(min_length=1)         # 画面下に出す出典表記（シーンごとに上書き可）
    sources: list[Source] = Field(min_length=1)  # 出典URLは必須


# 色は名前で指定する（実際の色は draw.PALETTE）
Color = Literal["fg", "sub", "acc", "warn", "gray", "blue"]


class Timed(Strict):
    """表示タイミング：lines の cue 番目（0始まり）のセリフ開始から delay 秒後"""
    cue: int
    delay: float = Field(default=0.0, ge=0, le=5)


class Cued(Timed):
    text: str = Field(min_length=1)


class SceneBase(Strict):
    lines: list[Line] = Field(min_length=1)
    credit: Optional[str] = None              # None なら meta.credit を使う

    def timed(self) -> list[tuple[str, Timed]]:
        """cue を持つ要素の一覧（範囲チェック用）。型ごとに上書きする"""
        return []

    @model_validator(mode="after")
    def check_cues(self):
        for where, x in self.timed():
            if not 0 <= x.cue < len(self.lines):
                raise ValueError(f"{where} の cue={x.cue} が範囲外（lines は {len(self.lines)} 個）")
        return self


def _opt(name, x):
    return [(name, x)] if x else []


def _each(name, xs):
    return [(f"{name}[{i}]", x) for i, x in enumerate(xs)]


class Header(SceneBase):
    num: str = Field(pattern=r"^\d{2}$")          # 見出しの番号 "05" など
    title: str = Field(min_length=1)


# ---------- シーンの型 ----------
class HookScene(SceneBase):
    type: Literal["hook"]
    title: list[str] = Field(min_length=1, max_length=2)  # 大きいアクセント色の行
    lead: str = Field(min_length=1)                        # 白い中サイズの行
    big: str = Field(min_length=1)                         # 一番強い情報（ポップして出る）
    ask: Optional[Cued] = None                             # 「何が変わった？」など

    def timed(self): return _opt("ask", self.ask)


class ListItem(Timed):
    main: str = Field(min_length=1)   # "\n" で手動改行できる
    note: Optional[str] = None


class ListScene(Header):
    type: Literal["list"]
    style: Literal["normal", "warn"] = "normal"   # warn = 「!」マーク＋黄色
    items: list[ListItem] = Field(min_length=1, max_length=3)

    def timed(self): return _each("items", self.items)


class Tier(Timed):
    name: str = Field(min_length=1)
    desc: str = Field(min_length=1)
    color: Color
    highlight: bool = False            # True なら枠を横幅いっぱいにして目立たせる


class TierScene(Header):
    """位置づけ（上から順に並べ、間に ▲ を入れる）"""
    type: Literal["tier"]
    intro: Optional[Cued] = None       # 見出し下の小さい説明
    tiers: list[Tier] = Field(min_length=2, max_length=3)   # 上から順

    def timed(self): return _opt("intro", self.intro) + _each("tiers", self.tiers)


class Series(Strict):
    name: str = Field(min_length=1)
    color: Color                       # "acc" の系列だけ数値もアクセント色になる


class BarRow(Timed):
    label: str = Field(min_length=1)            # 左の見出し（日本語）
    sublabel: Optional[str] = None              # 右寄せの小さい文字（テスト名など）
    values: list[float] = Field(min_length=1)   # legend と同じ順・同じ個数


class BarsScene(Header):
    """棒グラフ（行ごとに系列の数だけ棒が伸びる）"""
    type: Literal["bars"]
    legend: list[Series] = Field(min_length=1, max_length=3)
    rows: list[BarRow] = Field(min_length=1, max_length=3)
    max: float = Field(default=100, gt=0)       # 棒の長さの基準（この値で最大幅）
    unit: str = Field(default="%", max_length=3)

    def timed(self): return _each("rows", self.rows)

    @model_validator(mode="after")
    def check_values(self):
        for i, r in enumerate(self.rows):
            if len(r.values) != len(self.legend):
                raise ValueError(f"rows[{i}].values は {len(self.legend)} 個必要（legend と同数）")
            if any(not 0 <= v <= self.max for v in r.values):
                raise ValueError(f"rows[{i}].values に 0〜{self.max:g} の範囲外の値")
        return self


class PriceRow(Timed):
    name: str = Field(min_length=1)
    old: str = Field(min_length=1)     # 表示用の文字列（"$5" など）
    new: str = Field(min_length=1)
    change: str = Field(min_length=1)  # 右端の変化率（"−20%" など）


class Summary(Timed):
    lines: list[str] = Field(min_length=1, max_length=2)   # 1行目が大きい


class PriceScene(Header):
    """料金の比較（旧 → 新）とまとめの帯"""
    type: Literal["price"]
    intro: Optional[Cued] = None
    rows: list[PriceRow] = Field(min_length=1, max_length=3)
    summary: Optional[Summary] = None
    note: Optional[Cued] = None        # 帯の下の小さい注記（※…）

    def timed(self):
        return (_opt("intro", self.intro) + _each("rows", self.rows)
                + _opt("summary", self.summary) + _opt("note", self.note))


class Card(Timed):
    big: str = Field(min_length=1)     # 大きい数字（"68万行" など）
    mid: str = Field(min_length=1)     # big の右に続く文
    rest: str = Field(min_length=1)    # 下の段


class CardsScene(Header):
    """数字を大きく見せる事例カード"""
    type: Literal["cards"]
    items: list[Card] = Field(min_length=1, max_length=2)   # 3枚目は字幕と重なる

    def timed(self): return _each("items", self.items)


class EndText(Cued):
    size: int = Field(ge=30, le=130)
    color: Color = "fg"
    y: int = Field(ge=200, le=1250)    # 文字の上端（中央揃え）。字幕枠は y≈1300 から


class EndScene(SceneBase):
    """締め（見出しなし、中央揃えの文字を自由に置く）"""
    type: Literal["end"]
    items: list[EndText] = Field(min_length=1, max_length=5)

    def timed(self): return _each("items", self.items)


# type の値を見て、どのクラスで検証するかを決める（discriminated union）
Scene = Annotated[Union[HookScene, ListScene, TierScene, BarsScene, PriceScene, CardsScene, EndScene],
                  Field(discriminator="type")]


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
