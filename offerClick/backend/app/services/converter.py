import sys
import os
import json
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Generator, AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

import asyncio

# Thread pool for running synchronous subprocess
executor = ThreadPoolExecutor(max_workers=4)

# OpenAI client for cover letter generation
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None

async def generate_resume_for_job_stream(job_id: str, job_data: dict):
    """
    Generate resume by calling the JDConverter/auto_resume.py script asynchronously.
    Yields stdout lines for real-time feedback.
    """
    print(f"[DEBUG] generate_resume_for_job_stream called for job_id: {job_id}")

    # Locate the auto_resume.py script
    workspace_root = Path(__file__).resolve().parents[4]
    jd_converter_dir = workspace_root / "JDConverter"
    auto_resume_script = jd_converter_dir / "auto_resume.py"

    print(f"[DEBUG] Paths - workspace_root: {workspace_root}")
    print(f"[DEBUG] Paths - jd_converter_dir: {jd_converter_dir}")
    print(f"[DEBUG] Paths - auto_resume_script: {auto_resume_script}")

    if not auto_resume_script.exists():
        raise FileNotFoundError(f"auto_resume.py not found at {auto_resume_script}")

    # Prepare the JD text
    # Since we no longer store raw JD, we reconstruct a "Structured JD" 
    # from the fields we do have (tech stack, responsibilities, etc.)
    # This acts as the input for auto_resume.py
    jd_raw = job_data.get("jd_raw", "")
    
    if jd_raw and len(jd_raw) > 100:
        # Fallback: if by chance we still have the raw JD (legacy data), use it
        jd_text = jd_raw
    else:
        # Reconstruct JD from structured fields
        company = job_data.get("company", "Unknown Company")
        role = job_data.get("role", "Unknown Role")
        
        jd_structured = job_data.get("jd_structured", {})
        
        tech_stack = "N/A"
        responsibilities = "N/A"
        experience = "N/A"
        
        if isinstance(jd_structured, dict):
            tech_stack = jd_structured.get("technical_stack", "N/A")
            responsibilities = jd_structured.get("key_responsibilities", "N/A")
            experience = jd_structured.get("required_experience", "N/A")
        
        # Format as a pseudo-JD that our prompts can understand
        jd_text = f"""
JOB TITLE: {role}
COMPANY: {company}

[TECHNICAL STACK]
{tech_stack}

[KEY RESPONSIBILITIES]
{responsibilities}

[REQUIRED EXPERIENCE]
{experience}
"""

    # Create a temporary file for the JD
    # Note: NamedTemporaryFile is blocking but fast enough for small text.
    # For strict async, we could use aiofiles, but this is negligible.
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as tmp_jd:
        tmp_jd.write(jd_text)
        tmp_jd_path = tmp_jd.name

    try:
        cmd = [sys.executable, "-u", str(auto_resume_script), "--jd", tmp_jd_path]

        # Add company and role if available to influence filename generation via prompt context
        if job_data.get('company'):
            cmd.extend(["--company", str(job_data.get('company'))])

        if job_data.get('role'):
            cmd.extend(["--role", str(job_data.get('role'))])

        print(f"[DEBUG] Command to execute: {' '.join(cmd)}")
        print(f"[DEBUG] Working directory: {jd_converter_dir}")
        print(f"[DEBUG] OPENAI_API_KEY in env: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")

        # Use synchronous subprocess (works reliably on Windows)
        # Stream output in real-time using queue
        import queue
        import threading

        output_queue = queue.Queue()
        full_output = []

        def run_subprocess():
            """Run subprocess and put output into queue"""
            process = subprocess.Popen(
                cmd,
                cwd=jd_converter_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=os.environ.copy(),
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True
            )

            for line in process.stdout:
                line = line.strip()
                if line:
                    full_output.append(line)
                    output_queue.put(('line', line))
                    print(f"[SCRIPT] {line}")  # Echo to backend console

            returncode = process.wait()
            output_queue.put(('done', returncode))

        # Start subprocess in thread
        thread = threading.Thread(target=run_subprocess, daemon=True)
        thread.start()

        # Yield lines as they come in
        while True:
            await asyncio.sleep(0.05)  # Small delay to prevent busy waiting

            # Check if there's new output
            while not output_queue.empty():
                msg_type, msg_data = output_queue.get_nowait()

                if msg_type == 'line':
                    yield msg_data
                elif msg_type == 'done':
                    returncode = msg_data
                    # Process any remaining items in queue
                    while not output_queue.empty():
                        try:
                            msg_type, msg_data = output_queue.get_nowait()
                            if msg_type == 'line':
                                yield msg_data
                        except queue.Empty:
                            break
                    # Exit the outer loop
                    break
            else:
                # Continue outer loop if we didn't break
                continue
            # If we broke from inner loop, break outer loop too
            break

        if returncode != 0:
            # Include the last few lines of output for debugging
            error_context = "\n".join(full_output[-10:]) if full_output else "No output captured"
            raise RuntimeError(
                f"Resume generation script failed with return code {returncode}. "
                f"Last output:\n{error_context}"
            )

        # Parse stdout to find the generated PDF path
        output_text = "\n".join(full_output)
        
        pdf_path = None
        match = re.search(r"\[OK\] Built PDF.*?->\s*(.+?\.pdf)", output_text, re.IGNORECASE)
        if match:
            pdf_path = match.group(1).strip()
        
        if not pdf_path:
             match_fallback = re.search(r"(?:->\s*|Successfully generated:?\s*)(.*?\.pdf)", output_text, re.IGNORECASE)
             if match_fallback:
                 pdf_path = match_fallback.group(1).strip()

        if not pdf_path:
            # Provide more context for debugging
            output_snippet = output_text[-500:] if len(output_text) > 500 else output_text
            raise RuntimeError(
                f"Could not determine generated PDF path from script output. "
                f"Output snippet:\n{output_snippet}"
            )

        pdf_path_obj = Path(pdf_path)
        if not pdf_path_obj.exists():
            raise FileNotFoundError(f"Generated PDF not found at {pdf_path}")

        text_path = str(pdf_path_obj.with_name(pdf_path_obj.name.replace(".pdf", "_JD.txt")))
        version_id = pdf_path_obj.stem

        # Read generated bullets if available
        bullets_path = pdf_path_obj.with_name(f"{version_id}_bullets.json")
        bullets_data = {}
        if bullets_path.exists():
            try:
                # synchronous read is fine here as it's fast JSON
                with open(bullets_path, "r", encoding="utf-8") as f:
                    raw_bullets = json.load(f)
                    # Normalize keys for frontend
                    mapping = {
                        "%%SPECTRAL_BULLETS_BLOCK%%": "scope",
                        "%%EDGE_BULLETS_BLOCK%%": "edge",
                        "%%WHISPER_BULLETS_BLOCK%%": "whisper",
                        "%%ALIBABA_BULLETS_BLOCK%%": "alibaba",
                        "%%CRAES_BULLETS_BLOCK%%": "craes"
                    }
                    for marker, content in raw_bullets.items():
                        field_name = mapping.get(marker, marker)
                        bullets_data[field_name] = content
            except Exception as e:
                print(f"[WARN] Failed to read bullets json: {e}")

        result = {
            "pdf_path": str(pdf_path_obj),
            "text_path": text_path,
            "version_id": version_id,
            "created_at": datetime.now().isoformat(),
            "bullets": bullets_data
        }
        
        import json
        yield f"__RESULT__:{json.dumps(result)}"

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"[ERROR] Exception in generate_resume_for_job_stream: {e}")
        print(error_traceback)
        yield f"[ERROR] {str(e)}"
        raise
    finally:
        if os.path.exists(tmp_jd_path):
            try:
                os.unlink(tmp_jd_path)
            except Exception:
                pass

# Keep the original function for backward compatibility if needed, or redirect it
async def generate_resume_for_job(job_id: str, job_data: dict) -> Dict[str, str]:
    """
    Synchronous wrapper that consumes the async generator and returns the final result.
    """
    generator = generate_resume_for_job_stream(job_id, job_data)
    result = None
    async for line in generator:
        if line.startswith("__RESULT__:"):
            import json
            result = json.loads(line[11:])
        else:
            print(f"[STREAM] {line}")

    if result:
        return result
    raise RuntimeError("Stream finished but no result returned")


def generate_cover_letter(job_data: dict, custom_prompt: str = None) -> str:
    """
    Generate a cover letter for a job application.

    Args:
        job_data: Job information (company, role, jd_structured, etc.)
        custom_prompt: Custom application question (optional). If None, generates a general cover letter.

    Returns:
        Generated cover letter text
    """
    if not openai_client:
        raise ValueError("OpenAI API key not configured. Cannot generate cover letter.")

    # Locate files
    workspace_root = Path(__file__).resolve().parents[4]
    prompts_dir = workspace_root / "config" / "prompts" / "converter"
    info_dir = workspace_root / "info"

    cover_letter_prompt_file = prompts_dir / "cover_letter.txt"
    cover_letter_info_file = info_dir / "cover_letter.md"

    # Load prompt
    if not cover_letter_prompt_file.exists():
        raise FileNotFoundError(f"Cover letter prompt not found at {cover_letter_prompt_file}")

    system_prompt_template = cover_letter_prompt_file.read_text(encoding="utf-8")

    # Load background information
    background_info = ""
    if cover_letter_info_file.exists():
        background_info = cover_letter_info_file.read_text(encoding="utf-8")
    else:
        print(f"[WARN] Cover letter background info not found at {cover_letter_info_file}")
        background_info = "(No background information provided)"

    # Build JD context
    company = job_data.get("company", "Unknown Company")
    role = job_data.get("role", "Unknown Role")

    # ===== DYNAMIC INJECTION: Inject company and role into system prompt =====
    # This gives the AI stronger context about the specific application
    system_prompt = system_prompt_template + f"""

---

IMPORTANT CONTEXT FOR THIS APPLICATION:
- Target Company: {company}
- Target Role: {role}

When writing, keep this specific company and role in mind. Tailor your language and examples to align with what {company} would value in a {role}.
"""
    jd_structured = job_data.get("jd_structured", {})

    tech_stack = jd_structured.get("technical_stack", "N/A")
    responsibilities = jd_structured.get("key_responsibilities", "N/A")
    experience = jd_structured.get("required_experience", "N/A")

    jd_context = f"""
[JOB DESCRIPTION]
Company: {company}
Role: {role}

Technical Stack: {tech_stack}
Key Responsibilities: {responsibilities}
Required Experience: {experience}
"""

    # Determine application question
    if custom_prompt and custom_prompt.strip():
        application_question = f"[APPLICATION QUESTION]\n{custom_prompt.strip()}"
    else:
        application_question = "[APPLICATION QUESTION]\nGeneral Cover Letter (no specific prompt provided)"

    # Build user prompt
    user_prompt = f"""{jd_context}

{application_question}

[BACKGROUND INFORMATION]
{background_info}

---

Generate an appropriate response based on the job description, application question, and background information provided.
"""

    # Call OpenAI
    try:
        print(f"[INFO] Generating cover letter for {company} - {role}")
        if custom_prompt:
            print(f"[INFO] Custom prompt: {custom_prompt[:100]}...")

        response = openai_client.chat.completions.create(
            model="gpt-4o",  # Use a good model for writing
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,  # Creative but not too random
            max_tokens=800,  # Enough for a full cover letter
        )

        cover_letter = response.choices[0].message.content.strip()
        print(f"[OK] Generated cover letter ({len(cover_letter)} chars)")

        return cover_letter

    except Exception as e:
        print(f"[ERROR] Failed to generate cover letter: {e}")
        raise
