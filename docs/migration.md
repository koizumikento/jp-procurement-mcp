# 移行手順

## インストールと登録

```sh
uv add "git+https://github.com/koizumikento/jp-procurement-mcp.git@main"
```

MCPクライアントでは `jp-procurement-mcp` を登録します。登録方法は[README](../README.md#mcpクライアントに登録する)を参照してください。

## CLIとPython

このパッケージには次のコマンドとPythonモジュールが含まれます。既存の引数と公開関数を使えます。

| コマンド | Pythonモジュール | 新しいCLIの指定 |
| --- | --- | --- |
| `procurement-notices-mcp` | `procurement_notices_mcp` | `jp-procurement-mcp notices ...` |
| `procurement-awards-mcp` | `procurement_awards_mcp` | `jp-procurement-mcp awards ...` |

Pythonでは統合パッケージからも関数をインポートできます。データの出典、ページ送り、キャッシュ、認証情報の設定は各データの説明を確認してください。
