#!/usr/bin/env python3
"""
Simple benchmark runner (non-agentic).

Runs benchmark questions directly against plain LLM APIs (Claude, Gemini, ChatGPT)
without workspace/file mounting and writes merged-style CSV output directly.

Output columns match `run_benchmark.py merge` format:
    - answer_{llm}_{model}
    - time_seconds_{llm}_{model}
    - input_tokens_{llm}_{model}
    - output_tokens_{llm}_{model}
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

import pandas as pd


API_KEY_ENV: dict[str, str] = {
    "claude": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "chatgpt": "OPENAI_API_KEY",
}


class APIError(Exception):
    """Raised for API request failures."""


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    response_model: str | None = None


def parse_answer(text: str) -> str:
    """Extract answer from output after the final `FINAL ANSWER:` marker."""
    if not text or not text.strip():
        return "ERROR: no output"
    if "FINAL ANSWER:" in text:
        answer = text.split("FINAL ANSWER:")[-1].strip()
        return answer if answer else "ERROR: empty answer"
    return "ERROR: no FINAL ANSWER"


def normalize_model_name(model_name: str) -> str:
    return model_name.strip().removeprefix("models/")


def model_matches_requested(requested_model: str, response_model: str | None) -> bool:
    if not response_model:
        return False
    requested = normalize_model_name(requested_model)
    used = normalize_model_name(response_model)
    return used == requested or used.startswith(f"{requested}-")


def generate_prompt(question: str, file_paths: str | None, timeout_minutes: int) -> str:
    """Prompt for non-agentic runs where file inputs are intentionally unavailable."""
    prompt_parts = [f"QUESTION: {question}", ""]

    if file_paths and str(file_paths).strip():
        prompt_parts.extend([
            "REFERENCE FILES (NOT PROVIDED IN THIS RUN):",
            str(file_paths),
            "",
        ])

    prompt_parts.extend([
        "CONTEXT:",
        "- This is a non-agentic benchmark run.",
        "- No local files, attachments, or workspace files are available.",
        "- If the question depends on missing files, give your best possible guess from prior knowledge.",
        "",
        "OUTPUT FORMAT REQUIREMENTS:",
        "When you have determined the answer, end your response with EXACTLY:",
        "",
        "FINAL ANSWER:",
        "<your answer here>",
        "",
        "IMPORTANT FORMAT RULES:",
        "1. The text 'FINAL ANSWER:' MUST be in all caps with a colon.",
        "2. Put the answer on the line(s) immediately after 'FINAL ANSWER:'.",
        "3. The answer MUST follow any format specified in the question.",
        "4. This must be the last part of your response.",
    ])
    return "\n".join(prompt_parts)


def validate_input_df(df: pd.DataFrame) -> None:
    required = ["question_id", "question", "file_paths"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    if df.empty:
        raise ValueError("Input CSV has no rows")

    if df["question_id"].isna().any():
        bad_rows = (df.index[df["question_id"].isna()] + 2).tolist()[:10]
        raise ValueError(f"Found empty question_id at CSV rows: {bad_rows}")
    if df["question"].isna().any():
        bad_rows = (df.index[df["question"].isna()] + 2).tolist()[:10]
        raise ValueError(f"Found empty question at CSV rows: {bad_rows}")

    empty_qid = df["question_id"].astype(str).str.strip() == ""
    if empty_qid.any():
        bad_rows = (df.index[empty_qid] + 2).tolist()[:10]
        raise ValueError(f"Found blank question_id at CSV rows: {bad_rows}")

    empty_question = df["question"].astype(str).str.strip() == ""
    if empty_question.any():
        bad_rows = (df.index[empty_question] + 2).tolist()[:10]
        raise ValueError(f"Found blank question at CSV rows: {bad_rows}")

    if df["question_id"].duplicated().any():
        dups = df[df["question_id"].duplicated(keep=False)]["question_id"].unique()
        raise ValueError(f"Duplicate question_id values found: {', '.join(str(x) for x in dups[:10])}")


def post_json(url: str, headers: dict[str, str], payload: dict, timeout_seconds: int) -> dict:
    """HTTP POST JSON helper."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise APIError(f"HTTP {exc.code}: {err_body[:500]}") from exc
    except urllib.error.URLError as exc:
        raise APIError(f"Network error: {exc}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise APIError(f"Invalid JSON response: {body[:500]}") from exc


def extract_text_from_openai_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif "text" in item:
                    text_parts.append(str(item.get("text", "")))
        return "".join(text_parts)
    return str(content)


def call_claude(model: str, prompt: str, timeout_seconds: int) -> LLMResponse:
    api_key = os.environ.get(API_KEY_ENV["claude"])
    if not api_key:
        raise APIError(f"Missing environment variable: {API_KEY_ENV['claude']}")

    response = post_json(
        url="https://us.aigw.galileo.roche.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        payload={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout_seconds=timeout_seconds,
    )

    choices = response.get("choices", [])
    text = ""
    if choices:
        message = choices[0].get("message", {})
        text = extract_text_from_openai_content(message.get("content", ""))

    usage = response.get("usage", {})
    return LLMResponse(
        text=text.strip(),
        input_tokens=int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        output_tokens=int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        response_model=str(response.get("model", "")).strip() or None,
    )

def call_gemini(model: str, prompt: str, timeout_seconds: int) -> LLMResponse:
    api_key = os.environ.get(API_KEY_ENV["gemini"])
    if not api_key:
        raise APIError(f"Missing environment variable: {API_KEY_ENV['gemini']}")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{urllib.parse.quote(model)}:generateContent?key={urllib.parse.quote(api_key)}"
    )
    response = post_json(
        url=url,
        headers={},
        payload={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
            },
        },
        timeout_seconds=timeout_seconds,
    )

    text_parts: list[str] = []
    candidates = response.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if isinstance(part, dict) and "text" in part:
                text_parts.append(str(part.get("text", "")))

    usage = response.get("usageMetadata", {})
    response_model = response.get("modelVersion") or response.get("model")
    return LLMResponse(
        text="".join(text_parts).strip(),
        input_tokens=int(usage.get("promptTokenCount", 0) or 0),
        output_tokens=int(usage.get("candidatesTokenCount", 0) or 0),
        response_model=(str(response_model).strip() if response_model is not None else None),
    )


def call_chatgpt(model: str, prompt: str, timeout_seconds: int) -> LLMResponse:
    api_key = os.environ.get(API_KEY_ENV["chatgpt"])
    if not api_key:
        raise APIError(f"Missing environment variable: {API_KEY_ENV['chatgpt']}")

    response = post_json(
        url="https://us.aigw.galileo.roche.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        payload={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout_seconds=timeout_seconds,
    )

    choices = response.get("choices", [])
    text = ""
    if choices:
        message = choices[0].get("message", {})
        text = extract_text_from_openai_content(message.get("content", ""))

    usage = response.get("usage", {})
    return LLMResponse(
        text=text.strip(),
        input_tokens=int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        output_tokens=int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        response_model=str(response.get("model", "")).strip() or None,
    )


CALLERS = {
    "claude": call_claude,
    "gemini": call_gemini,
    "chatgpt": call_chatgpt,
}


def output_columns(prefix: str) -> tuple[str, str, str, str]:
    return (
        f"answer_{prefix}",
        f"time_seconds_{prefix}",
        f"input_tokens_{prefix}",
        f"output_tokens_{prefix}",
    )


def ensure_columns(df: pd.DataFrame, prefix: str) -> tuple[str, str, str, str]:
    cols = output_columns(prefix)
    for col in cols:
        if col not in df.columns:
            df[col] = None
    return cols


def atomic_save_csv(df: pd.DataFrame, output_path: str) -> None:
    tmp = f"{output_path}.tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, output_path)


def is_successful_answer(value) -> bool:
    if pd.isna(value):
        return False
    s = str(value).strip()
    return bool(s) and not s.startswith("ERROR:")


def load_dataframe(input_path: str, output_path: str, resume: bool) -> pd.DataFrame:
    input_df = pd.read_csv(input_path)
    validate_input_df(input_df)

    if not resume:
        return input_df.copy()

    if not os.path.exists(output_path):
        print(f"Resume requested but output file does not exist yet: {output_path}. Starting fresh.")
        return input_df.copy()

    out_df = pd.read_csv(output_path)
    if "question_id" not in out_df.columns:
        raise ValueError(f"Output file missing 'question_id' column: {output_path}")

    value_cols = [
        c for c in out_df.columns
        if c.startswith("answer_")
        or c.startswith("time_seconds_")
        or c.startswith("input_tokens_")
        or c.startswith("output_tokens_")
    ]
    if not value_cols:
        return input_df.copy()

    merged = input_df.merge(
        out_df[["question_id", *value_cols]],
        on="question_id",
        how="left",
    )
    return merged


def validate_runtime_args(args) -> None:
    if not args.input or not str(args.input).strip():
        raise ValueError("Missing required --input path")
    if not args.output or not str(args.output).strip():
        raise ValueError("Missing required --output path")
    if not os.path.exists(args.input):
        raise ValueError(f"Input CSV not found: {args.input}")

    output_dir = os.path.dirname(os.path.abspath(args.output))
    if output_dir and not os.path.exists(output_dir):
        raise ValueError(f"Output directory does not exist: {output_dir}")

    if args.timeout <= 0:
        raise ValueError("--timeout must be > 0")
    if args.retries < 0:
        raise ValueError("--retries must be >= 0")
    if args.retry_backoff_seconds < 0:
        raise ValueError("--retry-backoff-seconds must be >= 0")


def run_provider(
    df: pd.DataFrame,
    provider: str,
    model: str,
    output_path: str,
    timeout_minutes: int, 
    retries: int,
    retry_backoff_seconds: float,
    resume: bool,
    dry_run: bool,
) -> None:
    prefix = f"{provider}_{model}"
    answer_col, time_col, input_col, output_col = ensure_columns(df, prefix)
    total = len(df)
    pending = 0
    if resume:
        for _, row in df.iterrows():
            if not is_successful_answer(row.get(answer_col)):
                pending += 1
    else:
        pending = total

    print(f"\nRunning {provider}/{model} | questions: {total} | to_run: {pending} | resume: {resume}")

    if not dry_run and not os.environ.get(API_KEY_ENV[provider]):
        raise RuntimeError(f"Missing environment variable: {API_KEY_ENV[provider]}")

    completed = 0
    successes = 0
    errors = 0

    for idx, row in df.iterrows():
        question_id = row["question_id"]

        if resume and is_successful_answer(row.get(answer_col)):
            continue

        question = str(row["question"])
        file_paths = row.get("file_paths") if "file_paths" in df.columns and pd.notna(row.get("file_paths")) else None
        prompt = generate_prompt(question, file_paths, timeout_minutes)

        started = time.time()
        raw_response = ""
        input_tokens = 0
        output_tokens = 0
        answer = ""

        if dry_run:
            raw_response = "Dry run response.\n\nFINAL ANSWER:\nDRY_RUN"
            answer = "DRY_RUN"
        else:
            last_error = ""
            for attempt in range(retries + 1):
                try:
                    resp = CALLERS[provider](model, prompt, timeout_minutes * 60)
                    if not model_matches_requested(model, resp.response_model):
                        raise APIError(
                            f"requested model '{model}', but API response model was "
                            f"'{resp.response_model or 'missing'}'"
                        )
                    raw_response = resp.text
                    input_tokens = resp.input_tokens
                    output_tokens = resp.output_tokens
                    answer = parse_answer(raw_response)
                    break
                except Exception as exc:
                    last_error = str(exc)
                    if attempt < retries:
                        sleep_for = retry_backoff_seconds * (2 ** attempt)
                        time.sleep(sleep_for)
            if not answer:
                answer = f"ERROR: {last_error[:300]}"

        elapsed = round(time.time() - started, 2)

        df.at[idx, answer_col] = answer
        df.at[idx, time_col] = elapsed
        df.at[idx, input_col] = input_tokens
        df.at[idx, output_col] = output_tokens

        atomic_save_csv(df, output_path)

        completed += 1
        is_error = answer.startswith("ERROR:")
        if is_error:
            errors += 1
        else:
            successes += 1

        status = "ERR" if is_error else "OK "
        print(
            f"[{completed:3d}/{pending:3d}] "
            f"{str(question_id)[:36]:<36} | {elapsed:6.2f}s | {status}"
        )

    print(
        f"Finished {provider}/{model}: "
        f"ok={successes}, errors={errors}"
    )


def cmd_run(args) -> None:
    validate_runtime_args(args)
    provider = args.llm
    model = args.model

    df = load_dataframe(args.input, args.output, args.resume)
    run_provider(
        df=df,
        provider=provider,
        model=model,
        output_path=args.output,
        timeout_minutes=args.timeout,
        retries=args.retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        resume=args.resume,
        dry_run=args.dry_run,
    )


def cmd_run_all(args) -> None:
    validate_runtime_args(args)
    model_map = {
        "claude": args.claude_model,
        "gemini": args.gemini_model,
        "chatgpt": args.chatgpt_model,
    }

    df = load_dataframe(args.input, args.output, args.resume)

    for provider in ("claude", "gemini", "chatgpt"):
        if not args.dry_run and not os.environ.get(API_KEY_ENV[provider]):
            raise RuntimeError(f"Missing environment variable: {API_KEY_ENV[provider]}")

        run_provider(
            df=df,
            provider=provider,
            model=model_map[provider],
            output_path=args.output,
            timeout_minutes=args.timeout,
            retries=args.retries,
            retry_backoff_seconds=args.retry_backoff_seconds,
            resume=args.resume,
            dry_run=args.dry_run,
        )

    atomic_save_csv(df, args.output)
    print(f"\nSaved merged-format output: {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simple non-agentic benchmark runner")
    subparsers = parser.add_subparsers(dest="command")

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("-i", "--input", required=True, help="Input benchmark CSV")
        p.add_argument("-o", "--output", required=True, help="Output CSV (merged-style)")
        p.add_argument("--resume", action="store_true", help="Resume from existing output CSV")
        p.add_argument("-t", "--timeout", type=int, default=2, help="Timeout per question (minutes)")
        p.add_argument("--retries", type=int, default=2, help="Retries per question on API failure")
        p.add_argument("--retry-backoff-seconds", type=float, default=30, help="Base backoff for retries")
        p.add_argument("--dry-run", action="store_true", help="No API calls; write placeholder answers")

    p_run = subparsers.add_parser("run", help="Run benchmark with one provider")
    add_common(p_run)
    p_run.add_argument("--llm", choices=["claude", "gemini", "chatgpt"], required=True)
    p_run.add_argument("-m", "--model", required=True, help="Model name")
    p_run.set_defaults(func=cmd_run)

    p_all = subparsers.add_parser("run-all", help="Run benchmark with claude, gemini, chatgpt")
    add_common(p_all)
    p_all.add_argument("--claude-model", required=True)
    p_all.add_argument("--gemini-model", required=True)
    p_all.add_argument("--chatgpt-model", required=True)
    p_all.set_defaults(func=cmd_run_all)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()
