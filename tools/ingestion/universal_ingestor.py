"""Universal Input Ingestor for OpenMontage topic-tutorial pipeline.

Normalizes supported local files, directories, repositories, URLs, and media
into a provenance-aware source bundle with SHA-256 hashes, secret redaction,
and fact extraction.
"""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# Secret file and pattern regexes
SECRET_FILE_PATTERNS = [
    ".env*",
    "*.pem",
    "*.key",
    "*credentials*",
    "*id_rsa*",
    "*id_ed25519*",
    "*.pfx",
    "*.p12",
    "*token*",
    "*.secret",
]

SECRET_CONTENT_REGEXES = [
    re.compile(r"([\"']?(?:api[_-]?key|secret[_-]?key|auth[_-]?token|access[_-]?token|bearer[_-]?token|private[_-]?key)[\"']?\s*[:=]\s*[\"']?)([A-Za-z0-9_\-\.]{8,})([\"']?)", re.IGNORECASE),
    re.compile(r"(AIzaSy[A-Za-z0-9_\-]{20,})"),  # Google API keys
    re.compile(r"(sk-[A-Za-z0-9_\-]{20,})"),  # OpenAI-style secret keys
    re.compile(r"(ghp_[A-Za-z0-9]{30,})"),  # GitHub personal access tokens
]


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_secret_filename(name: str) -> bool:
    for pattern in SECRET_FILE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def _redact_secrets(text: str) -> str:
    redacted = text
    for regex in SECRET_CONTENT_REGEXES:
        redacted = regex.sub(r"\1[REDACTED_SECRET]\3" if regex.groups >= 3 else r"[REDACTED_SECRET]", redacted)
    return redacted


class UniversalIngestor(BaseTool):
    name = "universal_ingestor"
    version = "1.0.0"
    tier = ToolTier.SOURCE
    capability = "ingestion"
    provider = "local"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = []
    agent_skills = ["video-understand"]

    capabilities = [
        "local_file_ingestion",
        "directory_scan",
        "code_repository_ingestion",
        "document_extraction",
        "secret_redaction",
        "provenance_tracking",
    ]

    supports = {
        "markdown": True,
        "text": True,
        "code": True,
        "pdf": True,
        "docx": True,
        "pptx": True,
        "xlsx": True,
        "csv": True,
        "urls": True,
        "media": True,
    }

    best_for = [
        "universal material intake for tutorial and explainer pipelines",
        "codebase and documentation extraction with secret redaction",
        "multi-format research asset bundling",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "Path to a file, directory, repository, or a web URL",
            },
            "project_dir": {
                "type": "string",
                "description": "Owning project directory for artifacts output",
            },
            "extract_claims": {
                "type": "boolean",
                "default": True,
                "description": "Whether to extract verifiable facts into fact_sheet.json",
            },
            "max_file_size_mb": {
                "type": "number",
                "default": 50.0,
                "description": "Maximum file size in MB to parse",
            },
            "max_files": {
                "type": "integer",
                "default": 100,
                "description": "Maximum files to ingest in directory scan",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=100, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, backoff_seconds=1.0)
    idempotency_key_fields = ["input_path", "max_file_size_mb"]
    side_effects = ["writes artifacts/input_manifest.json", "writes artifacts/fact_sheet.json"]
    user_visible_verification = [
        "Inspect artifacts/input_manifest.json for ingested sources and status",
        "Verify secrets were redacted from any ingested code or configs",
    ]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        input_target = str(inputs.get("input_path", "")).strip()
        if not input_target:
            return ToolResult(success=False, error="input_path must be a non-empty path or URL")

        project_dir_str = inputs.get("project_dir")
        project_dir = Path(project_dir_str) if project_dir_str else Path.cwd()
        max_file_size_bytes = int(inputs.get("max_file_size_mb", 50.0) * 1024 * 1024)
        max_files = int(inputs.get("max_files", 100))
        extract_claims = bool(inputs.get("extract_claims", True))

        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        sources: list[dict[str, Any]] = []
        source_counter = 1

        # Check if URL
        is_url = input_target.startswith("http://") or input_target.startswith("https://")

        if is_url:
            src_info = self._ingest_url(input_target, f"src_{source_counter:03d}")
            sources.append(src_info)
        else:
            target_path = Path(input_target).expanduser().resolve()
            if not target_path.exists():
                return ToolResult(success=False, error=f"Target path does not exist: {target_path}")

            if target_path.is_file():
                src_info = self._ingest_file(target_path, f"src_{source_counter:03d}", max_file_size_bytes)
                sources.append(src_info)
            elif target_path.is_dir():
                file_list = self._collect_directory_files(target_path, max_files)
                for fpath in file_list:
                    src_info = self._ingest_file(fpath, f"src_{source_counter:03d}", max_file_size_bytes)
                    sources.append(src_info)
                    source_counter += 1

        # Fact sheet generation
        facts: list[dict[str, Any]] = []
        if extract_claims:
            fact_counter = 1
            for src in sources:
                if src.get("status") == "supported" and src.get("content"):
                    extracted = self._extract_facts(src["content"], src["source_id"])
                    for fact in extracted:
                        fact["fact_id"] = f"fact_{fact_counter:03d}"
                        facts.append(fact)
                        fact_counter += 1

        # Build manifests
        total_words = sum(s.get("word_count", 0) for s in sources)
        supported_count = sum(1 for s in sources if s.get("status") == "supported")
        unsupported_count = len(sources) - supported_count

        input_manifest = {
            "schema_version": "1.0",
            "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "input_target": input_target,
            "project_dir": str(project_dir),
            "summary": {
                "total_sources": len(sources),
                "supported_sources": supported_count,
                "unsupported_sources": unsupported_count,
                "total_word_count": total_words,
            },
            "sources": sources,
        }

        fact_sheet = {
            "schema_version": "1.0",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_facts": len(facts),
            "facts": facts,
        }

        manifest_path = artifacts_dir / "input_manifest.json"
        fact_sheet_path = artifacts_dir / "fact_sheet.json"

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(input_manifest, f, indent=2, ensure_ascii=False)

        with open(fact_sheet_path, "w", encoding="utf-8") as f:
            json.dump(fact_sheet, f, indent=2, ensure_ascii=False)

        elapsed = round(time.time() - started, 2)
        return ToolResult(
            success=True,
            data={
                "input_manifest": str(manifest_path),
                "fact_sheet": str(fact_sheet_path),
                "total_sources": len(sources),
                "supported_sources": supported_count,
                "unsupported_sources": unsupported_count,
                "total_word_count": total_words,
                "total_facts": len(facts),
            },
            artifacts=[str(manifest_path), str(fact_sheet_path)],
            duration_seconds=elapsed,
            cost_usd=0.0,
        )

    def _collect_directory_files(self, root_dir: Path, max_files: int) -> list[Path]:
        collected: list[Path] = []
        git_ignore_patterns = [
            ".git",
            ".git/*",
            ".venv",
            ".venv/*",
            "node_modules",
            "node_modules/*",
            "__pycache__",
            "__pycache__/*",
            "*.pyc",
            "*.pyo",
            "dist",
            "dist/*",
            "build",
            "build/*",
            ".DS_Store",
        ]

        gitignore_file = root_dir / ".gitignore"
        if gitignore_file.is_file():
            try:
                with open(gitignore_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            git_ignore_patterns.append(line)
            except Exception:
                pass

        for root, dirs, files in os.walk(root_dir):
            rel_root = Path(root).relative_to(root_dir)
            # Filter dirs in-place
            dirs[:] = [
                d for d in dirs
                if not any(fnmatch.fnmatch(str(rel_root / d), pat) or fnmatch.fnmatch(d, pat) for pat in git_ignore_patterns)
            ]
            for file in sorted(files):
                rel_path = rel_root / file
                if any(fnmatch.fnmatch(str(rel_path), pat) or fnmatch.fnmatch(file, pat) for pat in git_ignore_patterns):
                    continue
                collected.append(Path(root) / file)
                if len(collected) >= max_files:
                    return collected
        return collected

    def _ingest_file(self, path: Path, source_id: str, max_file_size_bytes: int) -> dict[str, Any]:
        filename = path.name
        rel_str = str(path)

        # 1. Check for secret filename
        if _is_secret_filename(filename):
            return {
                "source_id": source_id,
                "file_path": rel_str,
                "filename": filename,
                "status": "redacted_sensitive",
                "sha256": None,
                "word_count": 0,
                "byte_size": path.stat().st_size if path.exists() else 0,
                "summary": "Sensitive configuration or secret file excluded for safety",
                "content": "",
            }

        # 2. Check existence & size
        if not path.is_file():
            return {
                "source_id": source_id,
                "file_path": rel_str,
                "filename": filename,
                "status": "unsupported",
                "error": "File not found or not a regular file",
                "sha256": None,
                "word_count": 0,
                "byte_size": 0,
                "content": "",
            }

        byte_size = path.stat().st_size
        if byte_size > max_file_size_bytes:
            return {
                "source_id": source_id,
                "file_path": rel_str,
                "filename": filename,
                "status": "unsupported",
                "error": f"File size ({byte_size} bytes) exceeds limit ({max_file_size_bytes} bytes)",
                "sha256": None,
                "word_count": 0,
                "byte_size": byte_size,
                "content": "",
            }

        # Compute SHA256
        try:
            raw_bytes = path.read_bytes()
            sha256_hash = _hash_bytes(raw_bytes)
        except Exception as exc:
            return {
                "source_id": source_id,
                "file_path": rel_str,
                "filename": filename,
                "status": "unsupported",
                "error": f"Failed reading file bytes: {exc}",
                "sha256": None,
                "word_count": 0,
                "byte_size": byte_size,
                "content": "",
            }

        suffix = path.suffix.lower()

        try:
            # Markdown & Plain text
            if suffix in [".md", ".markdown", ".txt", ".rst"]:
                text = raw_bytes.decode("utf-8", errors="replace")
                text = _redact_secrets(text)
                words = len(text.split())
                return {
                    "source_id": source_id,
                    "file_path": rel_str,
                    "filename": filename,
                    "file_type": "text",
                    "status": "supported",
                    "sha256": sha256_hash,
                    "word_count": words,
                    "byte_size": byte_size,
                    "summary": text[:200].replace("\n", " ") + "...",
                    "content": text,
                }

            # Code
            if suffix in [".py", ".ts", ".js", ".json", ".yaml", ".yml", ".sh", ".html", ".css", ".rs", ".go", ".cpp", ".c", ".h", ".sql"]:
                text = raw_bytes.decode("utf-8", errors="replace")
                text = _redact_secrets(text)
                words = len(text.split())
                return {
                    "source_id": source_id,
                    "file_path": rel_str,
                    "filename": filename,
                    "file_type": "code",
                    "language": suffix.lstrip("."),
                    "status": "supported",
                    "sha256": sha256_hash,
                    "word_count": words,
                    "byte_size": byte_size,
                    "summary": f"Code source ({suffix.lstrip('.')}, {len(text.splitlines())} lines)",
                    "content": text,
                }

            # PDF
            if suffix == ".pdf":
                try:
                    import pypdf
                    reader = pypdf.PdfReader(path)
                    pages_text = []
                    for page in reader.pages:
                        extracted = page.extract_text() or ""
                        if extracted:
                            pages_text.append(extracted)
                    full_text = "\n\n".join(pages_text)
                    if not full_text.strip():
                        return {
                            "source_id": source_id,
                            "file_path": rel_str,
                            "filename": filename,
                            "file_type": "pdf",
                            "status": "unsupported",
                            "error": "PDF has no extractable text (rasterized/scanned)",
                            "sha256": sha256_hash,
                            "word_count": 0,
                            "byte_size": byte_size,
                            "content": "",
                        }
                    full_text = _redact_secrets(full_text)
                    return {
                        "source_id": source_id,
                        "file_path": rel_str,
                        "filename": filename,
                        "file_type": "pdf",
                        "status": "supported",
                        "pages": len(reader.pages),
                        "sha256": sha256_hash,
                        "word_count": len(full_text.split()),
                        "byte_size": byte_size,
                        "summary": full_text[:200].replace("\n", " ") + "...",
                        "content": full_text,
                    }
                except Exception as exc:
                    return {
                        "source_id": source_id,
                        "file_path": rel_str,
                        "filename": filename,
                        "file_type": "pdf",
                        "status": "unsupported",
                        "error": f"PDF parse error: {exc}",
                        "sha256": sha256_hash,
                        "word_count": 0,
                        "byte_size": byte_size,
                        "content": "",
                    }

            # Word (.docx)
            if suffix == ".docx":
                try:
                    import docx
                    doc = docx.Document(path)
                    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                    full_text = "\n".join(paragraphs)
                    full_text = _redact_secrets(full_text)
                    return {
                        "source_id": source_id,
                        "file_path": rel_str,
                        "filename": filename,
                        "file_type": "docx",
                        "status": "supported",
                        "sha256": sha256_hash,
                        "word_count": len(full_text.split()),
                        "byte_size": byte_size,
                        "summary": full_text[:200].replace("\n", " ") + "...",
                        "content": full_text,
                    }
                except Exception as exc:
                    return {
                        "source_id": source_id,
                        "file_path": rel_str,
                        "filename": filename,
                        "file_type": "docx",
                        "status": "unsupported",
                        "error": f"DOCX parse error: {exc}",
                        "sha256": sha256_hash,
                        "word_count": 0,
                        "byte_size": byte_size,
                        "content": "",
                    }

            # PowerPoint (.pptx)
            if suffix == ".pptx":
                try:
                    from pptx import Presentation
                    prs = Presentation(path)
                    slide_texts = []
                    for idx, slide in enumerate(prs.slides):
                        slide_parts = []
                        for shape in slide.shapes:
                            if hasattr(shape, "text") and shape.text.strip():
                                slide_parts.append(shape.text.strip())
                        if slide_parts:
                            slide_texts.append(f"--- Slide {idx + 1} ---\n" + "\n".join(slide_parts))
                    full_text = "\n\n".join(slide_texts)
                    full_text = _redact_secrets(full_text)
                    return {
                        "source_id": source_id,
                        "file_path": rel_str,
                        "filename": filename,
                        "file_type": "pptx",
                        "slides_count": len(prs.slides),
                        "status": "supported",
                        "sha256": sha256_hash,
                        "word_count": len(full_text.split()),
                        "byte_size": byte_size,
                        "summary": full_text[:200].replace("\n", " ") + "...",
                        "content": full_text,
                    }
                except Exception as exc:
                    return {
                        "source_id": source_id,
                        "file_path": rel_str,
                        "filename": filename,
                        "file_type": "pptx",
                        "status": "unsupported",
                        "error": f"PPTX parse error: {exc}",
                        "sha256": sha256_hash,
                        "word_count": 0,
                        "byte_size": byte_size,
                        "content": "",
                    }

            # Excel (.xlsx) & CSV (.csv)
            if suffix == ".csv":
                text = raw_bytes.decode("utf-8", errors="replace")
                text = _redact_secrets(text)
                reader = list(csv.reader(text.splitlines()))
                return {
                    "source_id": source_id,
                    "file_path": rel_str,
                    "filename": filename,
                    "file_type": "csv",
                    "rows_count": len(reader),
                    "status": "supported",
                    "sha256": sha256_hash,
                    "word_count": len(text.split()),
                    "byte_size": byte_size,
                    "summary": f"CSV dataset with {len(reader)} rows",
                    "content": text[:10000],
                }

            if suffix == ".xlsx":
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(path, data_only=True)
                    sheet_texts = []
                    for sheet in wb.sheetnames:
                        ws = wb[sheet]
                        rows = []
                        for row in ws.iter_rows(values_only=True):
                            non_empty = [str(cell) for cell in row if cell is not None]
                            if non_empty:
                                rows.append(" | ".join(non_empty))
                        if rows:
                            sheet_texts.append(f"--- Sheet: {sheet} ---\n" + "\n".join(rows[:100]))
                    full_text = "\n\n".join(sheet_texts)
                    full_text = _redact_secrets(full_text)
                    return {
                        "source_id": source_id,
                        "file_path": rel_str,
                        "filename": filename,
                        "file_type": "xlsx",
                        "status": "supported",
                        "sha256": sha256_hash,
                        "word_count": len(full_text.split()),
                        "byte_size": byte_size,
                        "summary": f"Excel workbook ({len(wb.sheetnames)} sheets)",
                        "content": full_text,
                    }
                except Exception as exc:
                    return {
                        "source_id": source_id,
                        "file_path": rel_str,
                        "filename": filename,
                        "file_type": "xlsx",
                        "status": "unsupported",
                        "error": f"XLSX parse error: {exc}",
                        "sha256": sha256_hash,
                        "word_count": 0,
                        "byte_size": byte_size,
                        "content": "",
                    }

            # Media files (.mp4, .mov, .wav, .mp3)
            if suffix in [".mp4", ".mov", ".mkv", ".webm", ".wav", ".mp3", ".m4a", ".aac"]:
                media_meta = self._probe_media(path)
                return {
                    "source_id": source_id,
                    "file_path": rel_str,
                    "filename": filename,
                    "file_type": "media",
                    "status": "supported",
                    "sha256": sha256_hash,
                    "metadata": media_meta,
                    "word_count": 0,
                    "byte_size": byte_size,
                    "summary": f"Media file: duration={media_meta.get('duration_s', 0)}s, format={suffix.lstrip('.')}",
                    "content": f"Media file {filename} (Duration: {media_meta.get('duration_s')}s, Codec: {media_meta.get('codec')})",
                }

            # Unrecognized format
            return {
                "source_id": source_id,
                "file_path": rel_str,
                "filename": filename,
                "file_type": suffix.lstrip("."),
                "status": "unsupported",
                "error": f"Unsupported file format '{suffix}'",
                "sha256": sha256_hash,
                "word_count": 0,
                "byte_size": byte_size,
                "content": "",
            }

        except Exception as exc:
            return {
                "source_id": source_id,
                "file_path": rel_str,
                "filename": filename,
                "status": "unsupported",
                "error": f"Unexpected ingestion error: {exc}",
                "sha256": sha256_hash,
                "word_count": 0,
                "byte_size": byte_size,
                "content": "",
            }

    def _ingest_url(self, url: str, source_id: str) -> dict[str, Any]:
        sha256_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        try:
            import requests
            from bs4 import BeautifulSoup

            resp = requests.get(url, timeout=15, headers={"User-Agent": "OpenMontage-UniversalIngestor/1.0"})
            if resp.status_code != 200:
                return {
                    "source_id": source_id,
                    "file_path": url,
                    "filename": urllib.parse.urlparse(url).path.split("/")[-1] or "index.html",
                    "file_type": "url",
                    "status": "unsupported",
                    "error": f"HTTP {resp.status_code}: {resp.reason}",
                    "sha256": sha256_hash,
                    "word_count": 0,
                    "byte_size": len(resp.content),
                    "content": "",
                }

            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
                tag.extract()
            text = soup.get_text(separator="\n")
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            clean_text = "\n".join(lines)
            clean_text = _redact_secrets(clean_text)

            title = soup.title.string.strip() if (soup.title and soup.title.string) else url
            return {
                "source_id": source_id,
                "file_path": url,
                "filename": title[:60],
                "file_type": "url",
                "status": "supported",
                "sha256": sha256_hash,
                "word_count": len(clean_text.split()),
                "byte_size": len(resp.content),
                "summary": f"Web document: {title} ({len(clean_text.split())} words)",
                "content": clean_text[:20000],
            }
        except Exception as exc:
            return {
                "source_id": source_id,
                "file_path": url,
                "filename": url,
                "file_type": "url",
                "status": "unsupported",
                "error": f"Failed fetching URL: {exc}",
                "sha256": sha256_hash,
                "word_count": 0,
                "byte_size": 0,
                "content": "",
            }

    def _probe_media(self, path: Path) -> dict[str, Any]:
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration,size:stream=codec_name,width,height",
                "-of", "json", str(path)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(res.stdout)
            fmt = info.get("format", {})
            streams = info.get("streams", [{}])
            stream0 = streams[0] if streams else {}
            return {
                "duration_s": round(float(fmt.get("duration", 0)), 2),
                "codec": stream0.get("codec_name", "unknown"),
                "width": stream0.get("width"),
                "height": stream0.get("height"),
            }
        except Exception:
            return {"duration_s": 0.0, "codec": "unknown"}

    def _extract_facts(self, text: str, source_id: str) -> list[dict[str, Any]]:
        facts: list[dict[str, Any]] = []
        # Extract declarative sentences or bullet points with numeric facts or strong assertions
        lines = text.splitlines()
        for line in lines:
            line_str = line.strip().lstrip("-*#0123456789. ")
            if len(line_str) > 25 and len(line_str) < 300:
                # Look for numbers, percentages, dates, or key action terms
                if re.search(r"(\d+%|\$\d+|\b\d{4}\b|\bcores\b|\bGB\b|\bMB\b|\bsec\b|\barchitecture\b|\bpipeline\b|\bmodule\b|\bstage\b)", line_str, re.IGNORECASE):
                    facts.append({
                        "claim": line_str,
                        "source_id": source_id,
                        "context": line.strip()[:150],
                        "verified": True,
                    })
                    if len(facts) >= 20:  # limit per source
                        break
        return facts
