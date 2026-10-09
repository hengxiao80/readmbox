# readmbox

Search and export messages from large `.mbox` files. Handles files up to 15 GB by building a SQLite FTS5 index for fast full-text search.

## Installation

Requires Python 3.13+ and [uv](https://github.com/astral-sh/uv).

The default Python version is 3.14, as specified in `.python-version`.

```bash
git clone https://github.com/YOUR_USERNAME/readmbox.git
cd readmbox
uv venv --python 3.14
uv pip install -e .
```

### Using Python 3.13

On a machine with Python 3.13 installed, run these commands after cloning the repository:

```bash
cd readmbox
uv python pin 3.13
uv sync
uv run readmbox --help
```

`uv python pin 3.13` updates `.python-version` in that checkout so subsequent `uv run` commands use Python 3.13. `uv sync` creates the virtual environment and installs the package and its dependencies. You can then use the commands below.

## Usage

### 1. Build the index

Run this once on your mbox file. The index is saved as `your_file.mbox.db` in the same directory.

```bash
uv run readmbox index archive.mbox
```

To rebuild an existing index:

```bash
uv run readmbox index archive.mbox --rebuild
```

### 2. Search

```bash
uv run readmbox search "your query" --mbox archive.mbox
```

With a date range:

```bash
uv run readmbox search "invoice" --mbox archive.mbox --from-date 2023-01-01 --to-date 2023-12-31
```

Results are displayed as a table. You will then be prompted to select which messages to save as HTML files.

### 3. Save results as HTML

After a search, you are prompted interactively:

```
Save messages as HTML? Enter numbers (e.g. 1 3 5), 'all', or press Enter to skip: 1 3
Save to directory [./saved_messages]: ./output
Saved 2 file(s) to output/
```

To skip the prompt and save all results directly:

```bash
uv run readmbox search "invoice" --mbox archive.mbox --save ./output
```

## Query syntax

The query uses SQLite FTS5 syntax:

| Pattern | Example | Meaning |
|---|---|---|
| Single word | `invoice` | Messages containing "invoice" |
| Multiple words | `invoice payment` | Both words must appear |
| Exact phrase | `"monthly invoice"` | Words in this exact order |
| OR | `invoice OR receipt` | Either word |
| NOT | `invoice NOT spam` | First word without the second |
| Prefix | `invoic*` | Words starting with "invoic" |
| Subject only | `subject: invoice` | Match only in subject |
| Body only | `body: invoice` | Match only in body |

## Options

```
readmbox index [OPTIONS] MBOX_FILE
  --rebuild       Recreate the index even if it already exists

readmbox search [OPTIONS] QUERY
  --mbox PATH          Path to the .mbox file (required)
  --from-date DATE     Start of date range, format YYYY-MM-DD
  --to-date DATE       End of date range, format YYYY-MM-DD
  --limit N            Maximum number of results (default: 50)
  --save DIR           Save all matched messages as HTML without prompting
```
