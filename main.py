#!/usr/bin/env python3
"""CLI prototype for Risk Factor Comparison App
"""

import os
import textwrap
import json
import re
from typing import Dict, List
from jsonschema import validate
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

CATEGORIES = ["Strategic", "Financial", "Legal", "Operational", "Technology"]

SCHEMA = {
    "type": "object",
    "properties": {cat: {"type": "array", "items": {"type": "string"}} for cat in CATEGORIES},
    "required": CATEGORIES,
    "additionalProperties": False,
}

# path for persisted companies dictionary
DATA_FILE = os.path.join(os.path.dirname(__file__), "companies_data.json")

def sanitize(name: str) -> str:
    return name.strip()

def extract_json_from_text(text: str) -> dict:
    """Attempt to extract a JSON object from arbitrary text.

    Tries direct json.loads first, then searches for the first balanced {...} block.
    Raises ValueError if no JSON object can be parsed.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # find first '{' and match balanced braces
        start = text.find("{")
        if start == -1:
            raise ValueError("No JSON object found in text")
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    fragment = text[start : i + 1]
                    try:
                        return json.loads(fragment)
                    except Exception:
                        break
        # fallback: try regex to find a JSON-like substring
        matches = re.findall(r"(\{.*\})", text, flags=re.DOTALL)
        for m in matches:
            try:
                return json.loads(m)
            except Exception:
                continue
        raise ValueError("Could not extract valid JSON from text")
    
def validate_and_normalize(data: dict, top_n: int = 3) -> Dict[str, List[str]]:
    """Validate that `data` matches the risk categories schema and normalize lists.

    Returns a dict mapping each category to a list of up to `top_n` cleaned strings.
    Raises ValidationError on failure.
    """
    try:
        validate(instance=data, schema=SCHEMA)
    except JSONSchemaValidationError as e:
        raise ValidationError(f"Schema validation error: {e.message}")

    out: Dict[str, List[str]] = {}
    for cat in CATEGORIES:
        items = data.get(cat, [])
        normalized = []
        for it in items:
            if isinstance(it, str):
                s = it.strip()
                if s:
                    normalized.append(s)
            else:
                # ignore non-string items
                continue
            if len(normalized) >= top_n:
                break
        out[cat] = normalized
    return out


class ValidationError(Exception):
    pass

class RiskCLI:
    def __init__(self):
        self.adapter = LLMAdapter()
        # companies -> category -> list of risk texts
        self.companies: Dict[str, Dict[str, List[str]]] = {}
        # load persisted companies if available
        self.load_companies()

    def load_companies(self) -> None:
        """Load companies dictionary from DATA_FILE if present.

        If the file is missing or invalid, start with an empty dict.
        """
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                # Basic validation: must be a dict mapping to dicts
                if isinstance(data, dict):
                    # ensure each company has all categories
                    for name, entry in list(data.items()):
                        if not isinstance(entry, dict):
                            # skip malformed company entry
                            continue
                        # ensure keys for categories exist and are lists
                        normalized = {c: (list(entry.get(c, [])) if isinstance(entry.get(c, []), list) else []) for c in CATEGORIES}
                        data[name] = normalized
                    self.companies = data
                else:
                    print("Warning: companies data file has unexpected format; starting fresh.")
                    self.companies = {}
        except Exception as e:
            print("Failed to load companies data; starting with empty dataset. Error:", e)
            self.companies = {}

    def save_companies(self) -> None:
        """Persist the current `self.companies` dictionary to DATA_FILE."""
        try:
            # ensure directory exists
            dirpath = os.path.dirname(DATA_FILE)
            if dirpath and not os.path.exists(dirpath):
                os.makedirs(dirpath, exist_ok=True)
            with open(DATA_FILE, "w", encoding="utf-8") as fh:
                json.dump(self.companies, fh, indent=2, ensure_ascii=False)
        except Exception:
            # re-raise to allow caller to handle logging
            raise

    def run(self):
        print("Risk Factor Comparison App — CLI Prototype (Chunk 3)")
        try:
            while True:
                print("")
                print("Commands: (1) add  (2) list  (3) show  (4) exit  (h) help")
                cmd = input("Enter command: ").strip().lower()
                if cmd in ("1", "add"):
                    self.command_add()
                elif cmd in ("2", "list"):
                    self.command_list()
                elif cmd in ("3", "show"):
                    self.command_show()
                elif cmd in ("4", "exit"):
                    print("Exiting. Goodbye.")
                    break
                elif cmd in ("h", "help"):
                    self.print_help()
                else:
                    print("Unknown command. Type 'h' for help.")
        except (KeyboardInterrupt, EOFError):
            print("\nInterrupted. Saving data and exiting.")
        finally:
            try:
                self.save_companies()
            except Exception as e:
                print("Failed to save companies data:", e)

    def print_help(self):
        print(textwrap.dedent(
            """
            add     - Enter 1-5 company names (comma separated) to fetch and store categorized risks.
            list    - List companies stored in memory and a summary of categories present.
            show    - Display a matrix of companies × categories (top 3 risks each).
            exit    - Exit the program.
            """
        ))

    def command_add(self):
        raw = input("Enter 1-5 company names (comma separated): ")
        names = [sanitize(n) for n in raw.split(",") if sanitize(n)]
        if not (1 <= len(names) <= 5):
            print("Please enter between 1 and 5 company names.")
            return
        for name in names:
            # Check if company already exists in the dictionary
            if name in self.companies:
                total_risks = sum(len(self.companies[name][c]) for c in CATEGORIES)
                print(f"Company '{name}' already in database with {total_risks} risk items. Skipping fetch.")
                continue
            # Company not found, fetch new risks from LLM
            print(f"Fetching risks for: {name} ...")
            risks = self.adapter.get_company_risks(name, top_n=3)
            # ensure structure
            if name not in self.companies:
                self.companies[name] = {c: [] for c in CATEGORIES}
            for cat in CATEGORIES:
                items = risks.get(cat, [])
                # avoid duplicates
                for it in items:
                    if it not in self.companies[name][cat]:
                        self.companies[name][cat].append(it)
            print(f"Stored {sum(len(self.companies[name][c]) for c in CATEGORIES)} risk items for {name}.")
            # Save immediately after modifying the dictionary
            try:
                self.save_companies()
            except Exception as e:
                print(f"Warning: Failed to save data after adding {name}: {e}")

    def command_list(self):
        if not self.companies:
            print("No companies stored yet.")
            return
        for name, data in self.companies.items():
            counts = {c: len(data.get(c, [])) for c in CATEGORIES}
            print(f"- {name}: {counts}")

    def command_show(self):
        if not self.companies:
            print("No company data to show. Please add a company first.")
            return
        # header
        header = ["Company"] + CATEGORIES
        print(" | ".join(header))
        print("-" * 80)
        for name, data in self.companies.items():
            row = [name]
            for c in CATEGORIES:
                items = data.get(c, [])[:3]
                cell = "; ".join(items) if items else "-"
                row.append(cell)
            print(" | ".join(row))

class LLMAdapter:
    """Simple LLM adapter with a deterministic mock mode and optional OpenAI integration.

    Mode selection via env var `LLM_MODE` (values: "mock" or "openai").
    OpenAI usage requires `OPENAI_API_KEY` in the environment.
    """

    def __init__(self, mode: str = None):
        self.mode = (mode or os.getenv("LLM_MODE", "mock")).lower()
        self.openai = None
        # in-memory cache: key=(company_name_lower, top_n) -> normalized result dict
        self._cache = {}
        # simple counter to help tests and observability in prototype
        self._api_calls = 0

        if self.mode == "openai":
            key = os.getenv("OPENAI_API_KEY")
            if not key:
                print("OPENAI_API_KEY not found in env; falling back to mock mode.")
                self.mode = "mock"
            else:
                try:
                    # Prefer the new OpenAI client (openai>=1.0.0)
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=key)
                        self.openai = client
                        self._openai_new_client = True
                    except Exception:
                        # Fall back to older openai module interface
                        import openai as openai_module
                        openai_module.api_key = key
                        self.openai = openai_module
                        self._openai_new_client = False
                except Exception as e:
                    print("Failed to import openai library; falling back to mock mode.", e)
                    self.mode = "mock"

    def get_company_risks(self, company_name: str, top_n: int = 3) -> Dict[str, List[str]]:
        """Return cached results when available; otherwise fetch and cache them."""
        key = (company_name.strip().lower(), int(top_n))
        if key in self._cache:
            return self._cache[key]

        # not cached — call the model/provider
        self._api_calls += 1
        if self.mode == "mock":
            result = self._mock_risks(company_name, top_n)
        elif self.mode == "openai":
            result = self._openai_risks(company_name, top_n)
        else:
            result = self._mock_risks(company_name, top_n)

        # store in cache
        self._cache[key] = result
        return result

    @property
    def api_call_count(self) -> int:
        return self._api_calls

    def clear_cache(self):
        self._cache.clear()

    def cache_keys(self):
        return list(self._cache.keys())

    def _mock_risks(self, company_name: str, top_n: int) -> Dict[str, List[str]]:
        # Deterministic, readable mock output for local testing.
        out = {}
        seed = company_name.lower().split()[0]
        for i, cat in enumerate(CATEGORIES):
            out[cat] = [f"{cat} risk {j+1} for {company_name}" for j in range(top_n)]
        return out

    def _openai_risks(self, company_name: str, top_n: int) -> Dict[str, List[str]]:
        prompt = (
            f"Extract the top {top_n} risk excerpts for the company named \"{company_name}\" "
            "and return a JSON object with the following keys: Strategic, Financial, Legal, Operational, Technology." 
            "Each key must map to a list of strings (risk excerpts). Return only valid JSON."
        )
        try:
            if getattr(self, "_openai_new_client", False):
                # openai.OpenAI client (>=1.0.0)
                resp = self.openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                # Support both attribute access and dict-like access
                try:
                    content = resp.choices[0].message.content
                except Exception:
                    content = resp["choices"][0]["message"]["content"]
            else:
                # Legacy openai package interface
                resp = self.openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                content = resp["choices"][0]["message"]["content"]
            # Try to parse and validate JSON robustly
            try:
                raw = None
                try:
                    raw = extract_json_from_text(content)
                except Exception as e:
                    print("Failed to extract JSON from model output; falling back to mock. Error:", e)
                    return self._mock_risks(company_name, top_n)

                try:
                    normalized = validate_and_normalize(raw, top_n=top_n)
                    return normalized
                except Exception as e:
                    print("Validation of model JSON failed; falling back to mock. Error:", e)
                    return self._mock_risks(company_name, top_n)
            except Exception as e:
                print("LLM validation integration failed; falling back to mock. Error:", e)
                return self._mock_risks(company_name, top_n)
        except Exception as e:
            print("OpenAI query failed, falling back to mock. Error:", e)
            return self._mock_risks(company_name, top_n)


if __name__ == "__main__":
    cli = RiskCLI()
    cli.run()
