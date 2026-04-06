# CompBioBench Runner

A benchmarking framework for evaluating LLM CLI agents (Claude Code, Codex) with isolated conda environments and structured output formats.

## Features

- **Isolated Environments**: Each question runs in a fresh conda environment (default)
- **Structured Output**: Markdown files with tables, metadata, and performance metrics
- **Cost Tracking**: Detailed token usage and cost breakdowns per question
- **Resumable**: Resume failed runs without re-running successful questions
- **Parallel Execution**: Run multiple questions concurrently
- **Multiple LLMs**: Support for Claude and Codex CLIs
- **Rich Logging**: Structured trace files with headers and clear separation

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

# Custom model and parallel workers
python run_benchmark.py run --llm claude --model-reasoning-effort high -m claude-opus-4-5 -n 10

# Keep environments for debugging
python run_benchmark.py run --llm claude --model-reasoning-effort high --keep-envs

# Resume a failed/interrupted run
python run_benchmark.py run --llm claude --model-reasoning-effort high --resume claude_opus-4-6_20260329_120000

# Exclude specific questions
python run_benchmark.py run --llm claude --model-reasoning-effort high --exclude q1 q2 q3
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

Each `trace.md` contains a summary table, the extracted answer, and the full LLM reasoning chain with tool calls and results formatted as readable markdown.

## Model Pricing

Token pricing is hardcoded in `run_benchmark.py` and is current as of March 2026. If model pricing has changed, update the `model_pricing` dictionaries in the provider classes (`ClaudeProvider`, `CodexProvider`).

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

**How it works:**
1. The base `compbio-benchmark` environment is cloned for each question
2. Each question runs in its own isolated workspace directory
3. The cloned environment is cleaned up after completion (unless `--keep-envs`)
4. System-installed LLM CLIs are accessed via full path resolution

**Debug failed questions:**
```bash
# Keep environments to inspect state after failures
python run_benchmark.py run --llm claude --keep-envs
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

### Contributors

- [Gokcen Eraslan](https://github.com/gokceneraslan)
- [Surag Nair](https://github.com/suragnair)
- Claude Code
