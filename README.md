# Connecting to a local Ollama server

Small toolkit for talking to an [Ollama](https://ollama.com) server on
`localhost`, plus a setup script that also works inside Claude Code cloud
sandboxes.

> **想用自己的 Word 文件打造本機 AI 專家?** 完整逐步範例在
> [`fmea_expert/`](fmea_expert/README.md):ISO 14971 FMEA 風險管理計算專家
> (自訂 Ollama 模型 + Word 文件 RAG 知識庫,可在任何 .py 程式中呼叫)。

> **想把 PDF/Word/Excel/HTML 自動拆解成知識樹?** 見
> [`km_pipeline/`](km_pipeline/README.md):輸入文件,自動產生一份多分頁的
> KM 知識 Excel(WBS 樹狀結構、行動樹、康乃爾/SMART/CODE 筆記),
> 分頁結構固定、有索引頁,方便直接交給 Claude 讀取應用。

**導覽**:[檔案索引 INDEX.md](INDEX.md) ・
[GitHub 整理指南](docs/github-organization-guide.md)(命名/編碼/分類/連結規則)・
[Ollama 環境說明(HTML)](docs/ollama-guide.html) ・
每月 1 日自動執行[整理工作流程](.github/workflows/monthly-tidy.yml)並開報告 Issue。

## Quick start

```sh
./scripts/ollama-up.sh                  # install (if needed) + start server
python3 ollama_client.py --check        # verify the connection
python3 ollama_client.py "Hello there"  # chat with the first installed model
```

The client and script use `OLLAMA_HOST` (default `127.0.0.1:11434`), the same
variable the `ollama` CLI honors, so they work unchanged against any local or
remote Ollama instance.

`ollama_client.py` has no dependencies beyond the Python 3.10+ standard
library. Use it directly or copy the `chat()` / `models()` helpers into your
own code.

## On your own machine

Install Ollama normally (`curl -fsSL https://ollama.com/install.sh | sh` or
the desktop app), then:

```sh
ollama pull llama3.2          # fetch a model
python3 ollama_client.py --check
```

## In a Claude Code cloud sandbox

`scripts/ollama-up.sh` installs the official binary from **GitHub releases**
(checksum-verified) instead of `ollama.com`, because the default sandbox
network policy allows `github.com` but blocks `ollama.com`.

One caveat: pulling models needs `registry.ollama.ai`, which the default
policy also blocks. The server runs and the API responds, but no models can
be downloaded until you allow these domains in the environment's network
settings:

- `ollama.com`
- `registry.ollama.ai`

See the [Claude Code cloud environment docs](https://code.claude.com/docs/en/claude-code-on-the-web)
for how to edit the network policy. Note that sandboxes are ephemeral —
installed binaries and pulled models disappear when the container is
reclaimed, so re-run `./scripts/ollama-up.sh` at the start of a session.
