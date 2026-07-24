# BLACK Kaggle CABT Entrypoint Contract

## 結論

提出用 `main.py` は、通常のファイル実行ではなく Kaggle CABT の次の実行方式を基準にする。

```python
exec(code_object, env)
```

この環境では `__file__` が定義されない場合がある。したがって、提出用エントリポイントで `Path(__file__)` を直接使ってはならない。

## 必須条件

- `__file__` の直接参照禁止
- `/home/...`、`/tmp/...`、`/kaggle/...`、`/kaggle_simulations/...` のハードコード禁止
- 実行環境が用意した `cwd` と `sys.path` を利用する
- `globals().get("__file__")` は任意候補としてのみ利用可能
- 生成後の提出アーカイブを展開し、`__file__` のない名前空間で実際に `exec()` する
- step 0 のデッキハンドシェイクと step 1 の通常Actionまで確認する

## 禁止例

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parent
```

Kaggle上では次の起動時例外になる。

```text
NameError: name '__file__' is not defined
```

## 推奨例

```python
from pathlib import Path
import sys

candidates = [Path.cwd()]
candidates.extend(Path(entry) for entry in sys.path if entry)
```

`__file__` を互換候補として使う必要がある場合も、直接参照せず任意値として扱う。

```python
module_file = globals().get("__file__")
if isinstance(module_file, str) and module_file:
    candidates.append(Path(module_file).resolve().parent)
```

## Gate

```bash
python scripts/static_gate.py
python -m pytest -q
```

`static_gate.py` は次を検証する。

1. ソース `main.py` のAST検査
2. 生成アーカイブ内 `main.py` のAST検査
3. 環境依存絶対パスの検出
4. `__file__` を注入しない隔離 `exec()`
5. デッキハンドシェイク
6. 最初の通常Action

このGateを通らないBundleは提出物として固定・登録・アップロードしない。
