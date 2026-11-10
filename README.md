# jp-procurement-mcp

調達公告と落札実績を調べるMCPサーバーです。MCP、CLI、Pythonライブラリから同じ機能を使えます。

[準備](#準備) · [MCP登録](#mcpクライアントに登録する) · [CLI](#cliで使う) · [Python](#pythonで使う) · [移行手順](docs/migration.md)

## 準備

Python 3.12以上、[uv](https://docs.astral.sh/uv/)、Gitが必要です。

```sh
git clone https://github.com/koizumikento/jp-procurement-mcp.git
cd jp-procurement-mcp
uv sync --locked
```

APIキーは不要です。

## MCPクライアントに登録する

設定例の `/absolute/path/to/jp-procurement-mcp` をクローン先の絶対パスに置き換えます。Windowsでは `C:/projects/jp-procurement-mcp` のように書けます。

### Codex

```sh
codex mcp add jp-procurement-mcp -- uv --directory "/absolute/path/to/jp-procurement-mcp" run --locked jp-procurement-mcp
codex mcp list
```

新しいセッションで `/mcp` を開いて接続状態を確認します。

### Claude Desktop / Cursor

Claude DesktopはOSに応じて次のファイルに設定します。

- Windowsは `%APPDATA%/Claude/claude_desktop_config.json`
- macOSは `~/Library/Application Support/Claude/claude_desktop_config.json`

Cursorはプロジェクト内の `.cursor/mcp.json` を使います。`mcpServers` に次の項目を追加し、クライアントを再起動してください。

```json
{
  "mcpServers": {
    "jp-procurement-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/jp-procurement-mcp",
        "run",
        "--locked",
        "jp-procurement-mcp"
      ]
    }
  }
}
```

`uv` が見つからない場合は、`command` に実行ファイルの絶対パスを指定してください。

## ツール

データごとの入力条件、結果、出典と利用条件は、表のリンク先に記載しています。

| ツール | データと操作の説明 |
| --- | --- |
| `search_notices` | [調達公告](docs/notices.md) |
| `search_awards` | [落札実績](docs/awards.md) |
| `summarize_awards` | [落札実績](docs/awards.md) |

## CLIで使う

クローン先で実行します。取得結果はUTF-8のJSONとして標準出力に書き出します。

```sh
uv run jp-procurement-mcp notices search-notices --query 防災 --limit 3
uv run jp-procurement-mcp awards search-awards --fiscal-year 2025 --query 地図 --limit 3
```

引数の説明は、各サブコマンドに `--help` を付けて確認できます。

## Pythonで使う

自分のPythonプロジェクトの依存関係に追加します。

```sh
uv add "git+https://github.com/koizumikento/jp-procurement-mcp.git@main"
```

次のコードを `example.py` に保存し、`uv run python example.py` で実行します。

```python
import asyncio

from jp_procurement_mcp import search_notices

result = asyncio.run(search_notices(query="防災", limit=3))
print(result)
```

ツールと同じ名前の非同期関数を利用できます。すでにイベントループがある場合は、直接 `await` してください。

## 出典と利用条件

コードはMITライセンスです。データは実行時に各提供元から取得します。取得データには、データ別の説明に記載した提供元の利用条件が適用されます。

## 開発

```sh
uv sync --locked
uv run ruff check .
uv run ty check
uv run pytest
uv build
```
