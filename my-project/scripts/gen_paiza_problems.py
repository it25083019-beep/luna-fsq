# -*- coding: utf-8 -*-
"""Generate config/paiza_problems.json — Paiza-style coding/writing tasks for SE lessons."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "config" / "paiza_problems.json"


def P(
    title,
    statement,
    *,
    input_fmt,
    output_fmt,
    constraints,
    samples,
    guides,
    keywords,
    starter_py,
    starter_js="",
    workspace="code",
):
    return {
        "workspace_type": workspace,
        "problem_title_ja": title,
        "problem_ja": statement.strip(),
        "input_format_ja": input_fmt.strip(),
        "output_format_ja": output_fmt.strip(),
        "constraints_ja": constraints.strip(),
        "samples": samples,
        "method_guides": [
            {"level": i + 1, "title_ja": g[0], "body_ja": g[1], "source_ja": g[2]}
            for i, g in enumerate(guides)
        ],
        "check_keywords": keywords,
        "starter_code": {"python": starter_py, "javascript": starter_js or starter_py},
        "min_answer_chars": 40,
    }


def main() -> None:
    problems = {}

    problems["se_l1"] = P(
        "学習ログを1行出力する",
        """あなたは学習習慣アプリのログ機能を作ります。
標準入力から「日付」「学んだこと」「明日やること」を受け取り、指定フォーマットで1行出力するプログラムを作成してください。""",
        input_fmt="""入力は3行です。
1行目: 日付（例: 2026-08-27）
2行目: 学んだこと
3行目: 明日やること""",
        output_fmt="""次の形式で1行出力してください。
[日付] 学んだこと / 明日: 明日やること
末尾に改行を入れてください。""",
        constraints="各行は1文字以上100文字以下。",
        samples=[
            {
                "label_ja": "入力例1",
                "input": "2026-08-27\nポモドーロを試した\nカレンダーに枠を置く\n",
                "output": "[2026-08-27] ポモドーロを試した / 明日: カレンダーに枠を置く\n",
            }
        ],
        guides=[
            ("入力の読み方", "まずは標準入力を3行読む。Pythonなら input() を3回。", "Paiza FAQ / 標準入力"),
            ("文字列の結合", "f-string や + でフォーマットを組み立て、print する。", "公式ドキュメントの定石"),
            ("改行に注意", "余計な空行を出さない。期待出力と完全一致を目指す。", "ジャッジの基本"),
        ],
        keywords=["input", "print", "日付", "ログ"],
        starter_py="""# 学習ログを1行に整形して出力する
date = input().strip()
learned = input().strip()
tomorrow = input().strip()
# TODO: 指定フォーマットで出力
""",
    )

    problems["se_l2"] = P(
        "タスクを分解して番号付きで出力する",
        """大きな作業名が1行で与えられます。続けて分解タスクが複数行で与えられるので、
検証可能なタスク一覧を「1. …」形式で出力するプログラムを作成してください。""",
        input_fmt="""1行目: 作業名
2行目: タスク数 N
続く N 行: タスク文""",
        output_fmt="""1行目に作業名を [作業] 付きで出し、続けて番号付きタスクを出力。""",
        constraints="1 ≦ N ≦ 20",
        samples=[
            {
                "label_ja": "入力例1",
                "input": "ログイン機能\n3\nメール入力欄を置く\n送信時に検証する\nエラーを表示する\n",
                "output": "[作業] ログイン機能\n1. メール入力欄を置く\n2. 送信時に検証する\n3. エラーを表示する\n",
            }
        ],
        guides=[
            ("全体像を掴む", "まず N を読み、ループでタスクを配列に入れる。", "アルゴリズム入門の定石"),
            ("番号付け", "enumerate で 1 始まりの番号を付ける。", "Python 公式"),
            ("検証可能性", "タスク文は入力のまま使い、勝手に要約しない。", "要件分解の基本"),
        ],
        keywords=["for", "enumerate", "タスク", "N"],
        starter_py="""title = input().strip()
n = int(input())
tasks = [input().strip() for _ in range(n)]
# TODO: 指定フォーマットで出力
""",
    )

    # Handkerchief problem (user's Paiza example) — map to algorithm practice lesson
    problems["se_l4"] = P(
        "ハンカチの種類数（回転・反転同一視）",
        """パイザさんは、白黒のハンカチをたくさん持っています。コレクションの中には同じ柄のハンカチもあるため、何種類のハンカチを持っているかが気になりました。

それぞれのハンカチの大きさと模様は、縦が H マス横が W マスの HxW マスで表され、各マス目について '#' は黒色、'.' は白色で塗りつぶされていることを表します。

N 枚のハンカチの情報が与えられるので、何種類のハンカチを持っているかを求めるプログラムを作成してください。

回転・反転するとすべて同じ模様になるものは同一種類とします。

ハンカチの大きさはすべて同じでないこともあることに注意してください。""",
        input_fmt="""入力は次のフォーマットで与えられます。
N
X_1
X_2
...
X_N

・1 行目: ハンカチの枚数 N
・続く各 X_k:
H W
p_1
...
p_H
（H 行の各 p_i は長さ W の '.' / '#' 文字列）""",
        output_fmt="""所持しているハンカチの種類数を整数1行で出力してください。
末尾に改行を入れ、余計な文字・空行を含めないでください。""",
        constraints="""1 ≦ N ≦ 10
1 ≦ H_i, W_i ≦ 100
p は '.' または '#'""",
        samples=[
            {
                "label_ja": "入力例1",
                "input": "5\n3 3\n.#.\n###\n##.\n3 3\n...\n###\n#..\n3 3\n.#.\n###\n.##\n3 3\n..#\n###\n...\n3 3\n...\n###\n#..\n",
                "output": "1\n",
                "note_ja": "回転・反転で同一とみなせるため種類は1。",
            },
            {
                "label_ja": "入力例2",
                "input": "5\n3 2\n##\n..\n.#\n3 2\n.#\n##\n#.\n2 1\n.\n#\n2 1\n#\n.\n2 3\n#..\n.##\n",
                "output": "3\n",
            },
        ],
        guides=[
            (
                "同一視の定義を決める",
                "各ハンカチについて、回転0/90/180/270と左右反転後の回転をすべて生成し、その中の『辞書順最小』を正規形にする。",
                "競技プログラミング定石（正規化）",
            ),
            (
                "集合で種類を数える",
                "正規形（タプルや文字列化）を set に入れて len(set) が答え。",
                "AtCoder/Paiza 解説でよくある手法",
            ),
            (
                "サイズが違う場合",
                "H,W が異なる模様は回転しても一致しない。正規形に H,W も含めるか、グリッドそのものをキーにする。",
                "問題文の注意点",
            ),
            (
                "実装の切り分け",
                "rotate / flip / canonicalize / read_one を関数に分けるとデバッグしやすい。",
                "フォーラムの定石",
            ),
        ],
        keywords=["rotate", "set", "grid", "H", "W", "正規"],
        starter_py="""import sys

def rotate(g):
    # 90度右回転
    h, w = len(g), len(g[0])
    return [''.join(g[h-1-r][c] for r in range(h)) for c in range(w)]

def flip(g):
    return [row[::-1] for row in g]

def canonicalize(g):
    forms = []
    cur = g
    for _ in range(4):
        forms.append(tuple(cur))
        forms.append(tuple(flip(cur)))
        cur = rotate(cur)
    return min(forms)

# TODO: N 枚読んで種類数を出力
""",
    )

    problems["se_l6"] = P(
        "配列の合計と平均を出力する",
        """N 個の整数が与えられます。合計と平均（小数第1位まで）を出力するプログラムを作成してください。""",
        input_fmt="1行目: N\n2行目: N個の整数（空白区切り）",
        output_fmt="1行目: 合計\n2行目: 平均（小数第1位、四捨五入ではなくフォーマットで1桁）",
        constraints="1 ≦ N ≦ 100 / 各値は 0〜1000",
        samples=[{"label_ja": "入力例1", "input": "3\n10 20 30\n", "output": "60\n20.0\n"}],
        guides=[
            ("合計", "sum(list) を使う。", "Python 標準"),
            ("平均", "合計/N。f'{avg:.1f}' で1桁表示。", "書式指定の定石"),
        ],
        keywords=["sum", "平均", "N"],
        starter_py="""n = int(input())
vals = list(map(int, input().split()))
# TODO
""",
    )

    problems["se_l7"] = P(
        "HTML風タグを数える",
        """1行の文字列 S が与えられます。'<…>' 形式のタグが何個あるかを数えて出力してください（入れ子なし・単純カウント）。""",
        input_fmt="1行: 文字列 S",
        output_fmt="タグ数（整数1行）",
        constraints="1 ≦ |S| ≦ 200",
        samples=[{"label_ja": "入力例1", "input": "Hello <b>world</b>!\n", "output": "2\n"}],
        guides=[
            ("走査", "文字を見て '<' と '>' のペアを数える。", "パーサ入門"),
            ("単純化", "この問題は入れ子なし。スタック不要でも解ける。", "問題の簡略化"),
        ],
        keywords=["tag", "count", "string"],
        starter_py="""s = input().strip()
# TODO: <...> の個数
""",
    )

    problems["se_l7b"] = P(
        "フォームイベントのログを整形する",
        """Webページのフォームで発生したイベントログが時系列で与えられます。
各ログは「イベント名 値」です。submit が来た時点までの入力値をまとめ、
指定フォーマットで1行出力するプログラムを作成してください。

これはブラウザの input / change / submit イベントを扱う練習課題です。""",
        input_fmt="""1行目: ログ行数 N
続く N 行: EVENT VALUE
EVENT は input / change / submit のいずれか。
submit の VALUE はボタン名。""",
        output_fmt="""submit が出現した行で、その時点の最新 input/change 値を使って
submit=<btn> name=<name> email=<email>
の形式で1行出力（無い項目は空文字）。submit が複数なら行を複数出す。""",
        constraints="1 ≦ N ≦ 100",
        samples=[
            {
                "label_ja": "入力例1",
                "input": "5\ninput name=taro\ninput email=a@b.c\nchange email=a@b.co\nsubmit send\ninput name=jiro\n",
                "output": "submit=send name=taro email=a@b.co\n",
            }
        ],
        guides=[
            (
                "状態を持つ",
                "name/email などの現在値を辞書で保持し、input/change で更新する。",
                "フロントイベント処理の定石",
            ),
            (
                "submit で確定",
                "submit が来たら現在の辞書を1行に整形して出力する。",
                "フォーム送信のモデル化",
            ),
            (
                "キーの更新",
                "VALUE が key=value 形式。split('=', 1) で分ける。",
                "文字列処理 FAQ",
            ),
        ],
        keywords=["submit", "input", "dict", "form", "event"],
        starter_py="""n = int(input())
state = {}
for _ in range(n):
    parts = input().split(None, 1)
    event = parts[0]
    payload = parts[1] if len(parts) > 1 else ""
    # TODO: input/change で state 更新、submit で出力
""",
        starter_js="""const fs = require('fs');
const lines = fs.readFileSync(0, 'utf8').trim().split(/\\n/);
let n = Number(lines[0]);
let state = {};
// TODO
""",
    )

    problems["se_l7c"] = P(
        "静的ページのリンク数を数える",
        """HTML風テキストが複数行で与えられます。href="..." の出現回数を数えて出力してください。""",
        input_fmt="1行目: 行数 N / 続く N 行: テキスト",
        output_fmt="href の個数（整数1行）",
        constraints="1 ≦ N ≦ 50",
        samples=[
            {
                "label_ja": "入力例1",
                "input": "2\n<a href=\"/a\">A</a>\n<a href='/b'>B</a>\n",
                "output": "2\n",
            }
        ],
        guides=[
            ("正規表現", "re.findall(r'href\\\\s*=', text, re.I) など。", "MDN / Python re"),
            ("単純カウント", "文字列 'href=' と \"href=\" を数えてもよい。", "簡易解法"),
        ],
        keywords=["href", "count", "html"],
        starter_py="""n = int(input())
text = '\\n'.join(input() for _ in range(n))
# TODO
""",
    )

    problems["se_l10"] = P(
        "JSON風キーを抽出する",
        """1行の JSON 風オブジェクト（ネストなし）からキー名をすべて抽出し、辞書順で出力してください。""",
        input_fmt='1行: {"a":1,"b":2} のような文字列',
        output_fmt="キーを1行ずつ辞書順",
        constraints="キーは英小文字のみ",
        samples=[{"label_ja": "入力例1", "input": '{"name":"luna","lv":2}\n', "output": "lv\nname\n"}],
        guides=[
            ("正規表現", 'キーは "name": のように並ぶ。正規表現で "([a-z]+)" を取る。', "JSON基礎"),
            ("ソート", "sorted(set(keys)) で出力。", "定石"),
        ],
        keywords=["json", "key", "sorted"],
        starter_py="""import re
s = input().strip()
# TODO
""",
    )

    problems["se_l11"] = P(
        "デバッグログのERROR行を数える",
        """ログが複数行与えられます。'ERROR' を含む行数を出力してください。""",
        input_fmt="1行目 N / 続く N 行ログ",
        output_fmt="ERROR行数",
        constraints="1 ≦ N ≦ 200",
        samples=[{"label_ja": "入力例1", "input": "3\nINFO ok\nERROR fail\nWARN x\n", "output": "1\n"}],
        guides=[
            ("行ごと判定", "'ERROR' in line", "ログ解析の基本"),
        ],
        keywords=["ERROR", "count", "log"],
        starter_py="""n = int(input())
# TODO
""",
    )

    # Fill remaining SE learning lessons with lighter Paiza-style tasks derived later in merge if missing
    data = {"version": "1.0", "problems": problems}
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", OUT, "count", len(problems))


if __name__ == "__main__":
    main()
