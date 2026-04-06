# Agent Benchmark Runner

A robust benchmarking framework for evaluating LLM CLI agents (Claude Code, Codex) with isolated conda environments and structured output formats.

## Features

- 🔒 **Isolated Environments**: Each question runs in a fresh conda environment (default)
- 📊 **Structured Output**: Markdown files with tables, metadata, and performance metrics
- 💰 **Cost Tracking**: Detailed token usage and cost breakdowns per question
- 🔄 **Resumable**: Resume failed runs without re-running successful questions
- ⚡ **Parallel Execution**: Run multiple questions concurrently
- 📈 **Multiple LLMs**: Support for Claude and Codex CLIs
- 📝 **Rich Logging**: Structured trace files with headers and clear separation

## Quick Start

### Prerequisites

1. **Conda** (Miniconda or Anaconda)
2. **LLM CLI** installed and authenticated:
   ```bash
   # For Claude (install from https://docs.anthropic.com/en/docs/claude-code)
   # Then authenticate:
   claude login

   # For Codex (install from https://github.com/openai/codex)
   # Then authenticate:
   codex auth
   ```

**Note:** The LLM CLI must be installed at the system level and accessible in your PATH. The conda environments created per question provide Python isolation but use your system-installed CLI.

### Installation

```bash
git clone https://github.com/genentech/compbiobench-runner.git
cd compbiobench-runner
```

### Run Your First Benchmark

```bash
# Run test benchmark with Claude
python run_benchmark.py run --llm claude --model-reasoning-effort high -i test_benchmark.csv

# Run all questions with 5 parallel workers
python run_benchmark.py run --llm claude --model-reasoning-effort high -i benchmark.csv -n 5

# Keep environments for debugging failed questions
python run_benchmark.py run --llm claude --model-reasoning-effort high --keep-envs
```

## Usage

### Commands

#### 1. Run Benchmark

```bash
python run_benchmark.py run [options]
```

**Options:**
- `--llm {claude,codex}` - LLM to use (default: claude)
- `-m, --model MODEL` - Model name(s), comma-separated for multiple (default: provider's default)
- `-i, --input FILE` - Input CSV file (default: benchmark.csv)
- `-n, --parallel N` - Parallel workers (default: 5)
- `-t, --timeout MIN` - Timeout per question in minutes (default: 120)
- `--model-reasoning-effort EFFORT` - **(Required)** Reasoning effort level (Claude: low|medium|high|max; Codex: minimal|low|medium|high|xhigh)
- `--permission-mode {default,acceptEdits,dontAsk,skip}` - Permission mode (default: skip - fully automated)
- `--keep-envs` - Keep cloned conda environments after completion (for debugging)
- `--resume RUN_NAME` - Resume a specific run by folder name (e.g., `claude_opus-4-6_20260329_120000`)
- `--resume-clean-workspace` - With `--resume`, clear each rerun question workspace before execution
- `--results-dir DIR` - Output directory (default: benchmark_runs)
- `--reverse` - Run questions in reverse order
- `--exclude ID [ID ...]` - Question IDs to exclude (e.g., `--exclude q1 q2 q3`)

**Examples:**

```bash
# Basic run with defaults (fully automated, no prompts)
python run_benchmark.py run --llm claude --model-reasoning-effort high

# Resume a specific run by folder name
python run_benchmark.py run --llm claude --model-reasoning-effort high --resume claude_opus-4-6_20260329_120000

# Resume and reset workspace for rerun questions
python run_benchmark.py run --llm claude --model-reasoning-effort high --resume claude_opus-4-6_20260329_120000 --resume-clean-workspace

# Keep environments for debugging
python run_benchmark.py run --llm claude --model-reasoning-effort high --keep-envs

# Run with permission prompts (not recommended for automation)
python run_benchmark.py run --llm claude --model-reasoning-effort high --permission-mode default

# Custom model and parallel workers
python run_benchmark.py run --llm claude --model-reasoning-effort high -m claude-opus-4-5 -n 10

# Long-running questions with 3 hour timeout
python run_benchmark.py run --llm claude --model-reasoning-effort high -t 180

# Exclude specific questions
python run_benchmark.py run --llm claude --model-reasoning-effort high --exclude q1 q2 q3

# Run in reverse order
python run_benchmark.py run --llm claude --model-reasoning-effort high --reverse
```

#### 2. Run All LLMs

```bash
python run_benchmark.py run-all [options]
```

Runs benchmark with all available LLMs (Claude, Codex) and merges results.

**Examples:**

```bash
# Run all LLMs with defaults
python run_benchmark.py run-all --model-reasoning-effort high

# Specify output file
python run_benchmark.py run-all --model-reasoning-effort high -o results.csv
```

#### 3. Merge Results

```bash
python run_benchmark.py merge [options]
```

Merge results from multiple benchmark runs.

**Options:**
- `--runs-dir DIR` - Directory with run results (default: benchmark_runs)
- `-i, --input FILE` - Base CSV with questions (default: benchmark.csv)
- `-o, --output FILE` - Output CSV file (default: benchmark_results.csv)

**Examples:**

```bash
# Merge all runs
python run_benchmark.py merge

# Custom paths
python run_benchmark.py merge --runs-dir my_runs -o merged.csv
```

## Input Format

### Benchmark CSV Format

The benchmark CSV must have:

- `question_id` - Unique identifier
- `question` - The question text
- `file_paths` - Comma-separated file paths for LLM access
- `difficulty` - (Optional) Difficulty rating (1-5)
- `domain` - (Optional) Domain category
- `curator_name` - (Optional) Who created the question

**Example:**

```csv
question_id,question,file_paths,difficulty,domain
variant-lookup-q001,"What is the genomic position of rs1801133?",/data/variants.vcf,1.0,Genomics
gene-analysis-q002,"Analyze the expression of BRCA1 in sample1",/data/expression.tsv,2.5,Transcriptomics
```

## Output Format

Each benchmark run creates a timestamped directory with per-question subdirectories:

```
benchmark_runs/
└── claude_claude-opus-4-6_20260324_170425/
    ├── run_metadata.json              # Run configuration
    ├── benchmark.log                  # Full execution log
    └── questions/
        ├── question-id-q001/
        │   ├── prompt.md              # 📖 Input prompt sent to LLM
        │   ├── result.json            # 🤖 Full results with metadata
        │   ├── trace.md               # 📖 Formatted reasoning chain
        │   ├── raw_stdout.jsonl       # Raw CLI stdout (JSONL)
        │   ├── raw_stderr.txt         # Raw CLI stderr
        │   └── workspace/             # Isolated work directory
        └── question-id-q002/
            ├── prompt.md
            ├── result.json
            ├── trace.md
            ├── raw_stdout.jsonl
            ├── raw_stderr.txt
            └── workspace/
```

**Output files per question:**
- **prompt.md** - The exact prompt sent to the LLM
- **result.json** - Complete results including answer, tokens, cost, and raw output
- **trace.md** - Human-readable formatted trace with tables and tool calls
- **raw_stdout.jsonl** - Raw JSONL output from the CLI
- **raw_stderr.txt** - Raw stderr output from the CLI

### Rich Trace Files

Each `trace.md` file contains a summary table followed by the LLM's reasoning chain:

```markdown
# Trace: question-id-q001

## Summary

| Field | Value |
|-------|-------|
| **LLM** | claude (claude-opus-4-5) |
| **Timestamp** | 2026-02-20T00:18:09.118593 |
| **Elapsed** | 39.47s |
| **Return Code** | 0 |
| **Input Tokens** | 63 |
| **Output Tokens** | 1,121 |
| **Cost** | $0.3331 |

## Answer

chrX:47574285

## LLM Response

**Claude:** I need to find the genomic position...

**Tool: Bash**
\`\`\`bash
curl -s "https://api.example.com/variant/rs123456"
\`\`\`

**Result:**
\`\`\`
{"position": "chrX:47574285"}
\`\`\`

**Claude:** Based on the API response...

FINAL ANSWER:
chrX:47574285
```

Both providers (Claude, Codex) produce consistently formatted traces with:
- `**Provider:** message` - Assistant reasoning and explanations
- `**Provider (thinking):** message` - Internal reasoning (Codex)
- `**Tool: Name** \`detail\`` - Tool calls with parameters
- `**Result:** \`\`\`output\`\`\`` - Tool outputs in code blocks

## Configuration

The script uses an LLM provider class architecture. Each provider (Claude, Codex) is a subclass of `LLMProvider` with:

- `name` - Provider identifier
- `default_model` - Default model to use
- `model_pricing` - Pricing dictionary for cost calculation
- `build_command()` - Build CLI command for execution
- `parse_output()` - Parse CLI output into rich trace and usage stats

**Adding a new provider:**

1. Create a new class extending `LLMProvider`
2. Add to `LLM_PROVIDERS` registry
3. Implement `build_command()` and `parse_output()`
4. Add model pricing

**Example:**

```python
class MyProvider(LLMProvider):
    name = "myllm"
    default_model = "my-model-1"
    model_pricing = {"my-model-1": (1.00, 5.00)}  # (input, output) per 1M tokens

    def build_command(self, model: str, prompt: str, data_dir: str) -> list[str]:
        return ["myllm", "--model", model, "-p", prompt]

    def parse_output(self, stdout: str, model: str) -> tuple[str, dict]:
        # Parse output, return (trace_text, usage_dict)
        ...
```

## Model Pricing

Token pricing is automatically calculated based on `MODEL_PRICING` in the script.

Current models (verify at provider pricing pages):

- **Claude**: Opus 4.5/4.6 ($5/$25 per 1M tokens), Sonnet 4.5/4.6 ($3/$15), Haiku 4.5 ($1/$5) — also includes cache write/read pricing tiers
- **Codex**: GPT-5.4 ($2.50/$15), GPT-5.3-codex ($1.75/$14), GPT-5.1-codex-mini ($0.25/$2) per 1M tokens

## Environment Management

### Base Environment (`environment.yml`)

The base conda environment is defined in `environment.yml` and includes:

- **Python 3.11** with scientific computing packages (numpy, pandas, scipy)
- **Bioinformatics tools** (biopython, pysam, pybedtools)
- **Data analysis** (matplotlib, seaborn, scikit-learn)
- **Node.js** (required for Codex CLI)

**Setup:**
```bash
# Create the base environment
conda env create -f environment.yml

# Or update existing environment
conda env update -f environment.yml
```

### Conda Isolation (Default)

**Why isolation?**
- ✅ Prevents cross-contamination between questions
- ✅ Ensures reproducible results
- ✅ Catches environment-dependent bugs
- ✅ Clean slate for each question

**How it works:**
1. The base `compbio-benchmark` environment is cloned for each question
2. Each question runs in its own isolated workspace directory
3. The cloned environment is cleaned up after completion (unless `--keep-envs`)
4. System-installed LLM CLIs are accessed via full path resolution

**Important Notes:**
- The LLM CLIs (claude, codex) must be installed at the system level
- CLIs are typically installed via npm and reside in `~/.miniforge3/bin/` or similar
- The script automatically resolves full CLI paths for use inside cloned environments
- Make sure CLIs are authenticated before running benchmarks

**Performance:**
- Env cloning: ~5-15 seconds per question (using mamba)
- Env cleanup: ~5-10 seconds per question
- Trade-off: Slower but more reliable

**Debug failed questions:**
```bash
# Keep environments to inspect state after failures
python run_benchmark.py run --llm claude --keep-envs
```

## Resume Failed Runs

If a run fails or is interrupted:

```bash
# Resume a specific run by folder name
python run_benchmark.py run --llm claude --model-reasoning-effort high --resume claude_opus-4-6_20260329_120000

# Resume and clear workspace before rerunning failed questions
python run_benchmark.py run --llm claude --model-reasoning-effort high --resume claude_opus-4-6_20260329_120000 --resume-clean-workspace
```

The runner:
- ✅ Skips questions with successful results
- ✅ Re-runs failed questions
- ✅ Appends to existing log
- ✅ Preserves previous results

## Cost Tracking

All costs are automatically calculated and tracked:

- Per-question costs in output files
- Total cost in console output
- Token breakdowns (input, output, cached)
- Cost summaries in merged CSV

**Example output:**

```
Done! OK: 2 | Errors: 0 | Total Cost: $0.6483
```

## Development

### Adding New LLM Backend

1. Create a new class extending `LLMProvider`
2. Implement `build_command()` and `parse_output()` methods
3. Add model pricing dictionary
4. Register in `LLM_PROVIDERS` dictionary
5. Test with small benchmark

### Running Tests

```bash
# Test with small dataset (serial)
python run_benchmark.py run --llm claude --model-reasoning-effort high -i test_benchmark.csv -n 1

# Test with env retention for debugging
python run_benchmark.py run --llm claude --model-reasoning-effort high -i test_benchmark.csv --keep-envs

# Test all providers
python run_benchmark.py run-all --model-reasoning-effort high -i test_benchmark.csv
```
