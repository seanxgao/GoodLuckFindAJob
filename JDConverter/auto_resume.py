import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from openai import OpenAI, AsyncOpenAI

# ================== CONFIGURATION ===================

ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent
CONFIG_DIR = PROJECT_ROOT / "config"
OUTPUT_DIR = PROJECT_ROOT / "generated_CV"
TEMPLATE_TEX = ROOT / "resume.tex"
INFO_DIR = PROJECT_ROOT / "info"
SKILLS_PROFILE = INFO_DIR / "skills_profile.md"
PROMPTS_DIR = CONFIG_DIR / "prompts" / "converter"

# OpenAI API Key from environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError(
        "OPENAI_API_KEY environment variable not set. "
        "Please set it using: $env:OPENAI_API_KEY = 'your-key-here' (PowerShell) "
        "or export OPENAI_API_KEY='your-key-here' (bash)"
    )

# Load resume configuration
with open(CONFIG_DIR / "resume.json", "r", encoding="utf-8") as f:
    RESUME_CONFIG = json.load(f)

# Extract configuration values
CANDIDATE_NAME = RESUME_CONFIG.get("candidate_name", {"first_name": "FirstName", "last_name": "LastName"})
CANDIDATE_FIRST_NAME = CANDIDATE_NAME.get("first_name", "FirstName")
CANDIDATE_LAST_NAME = CANDIDATE_NAME.get("last_name", "LastName")
CANDIDATE_FULL_NAME = f"{CANDIDATE_FIRST_NAME}_{CANDIDATE_LAST_NAME}"

JD_FILTER_MODEL = RESUME_CONFIG["models"]["jd_filter"]
FACTS_FILTER_MODEL = RESUME_CONFIG["models"]["facts_filter"]
SKILLS_MODEL = RESUME_CONFIG["models"]["skills"]
STAGE1_MODEL = RESUME_CONFIG["models"]["content"]
STAGE2_MODEL = RESUME_CONFIG["models"]["latex"]

JD_FILTER_TEMP = RESUME_CONFIG["temperatures"]["jd_filter"]
FACTS_FILTER_TEMP = RESUME_CONFIG["temperatures"]["facts_filter"]
SKILLS_TEMP = RESUME_CONFIG["temperatures"]["skills"]
CONTENT_TEMP = RESUME_CONFIG["temperatures"]["content"]
LATEX_TEMP = RESUME_CONFIG["temperatures"]["latex"]

MAX_JD_FILTER_TOKENS = RESUME_CONFIG["max_tokens"]["jd_filter"]
MAX_FACTS_FILTER_TOKENS = RESUME_CONFIG["max_tokens"]["facts_filter"]
MAX_CONTENT_TOKENS = RESUME_CONFIG["max_tokens"]["content"]
MAX_LATEX_TOKENS = RESUME_CONFIG["max_tokens"]["latex"]

# Resume Placeholders
SKILLS_PLACEHOLDER = "%%%SKILLS_BLOCK%%%"

# Build experience blocks from config
EXPERIENCE_BLOCKS = {}
for section_name, section_config in RESUME_CONFIG["experience_sections"].items():
    EXPERIENCE_BLOCKS[section_config["marker"]] = {
        "file": section_config["file"],
        "header": section_config["header"]
    }

# ================== PROMPTS ===================

def load_prompt(filename: str) -> str:
    """Load a prompt from the prompts directory"""
    prompt_path = PROMPTS_DIR / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")

# Load prompts from files
# JD_FILTER_PROMPT removed as the step is skipped
FACTS_FILTER_PROMPT = load_prompt("facts_filter.txt")
SKILLS_INSTRUCTIONS = load_prompt("skills.txt")
HIGH_LEVEL_BULLET_PROMPT = load_prompt("bullets_content.txt")
LATEX_CONVERSION_PROMPT = load_prompt("bullets_latex.txt")

# Load patches
try:
    WHISPER_PATCH = load_prompt("patch4whispMin.txt")
except FileNotFoundError:
    WHISPER_PATCH = ""



# ================== PREPROCESSING FUNCTIONS ===================

# filter_jd function removed as we now rely on upstream structured extraction.

async def filter_facts_async(client: AsyncOpenAI, facts: str, filtered_jd: str) -> str:
    """
    Filter facts to extract only relevant achievements and details for this specific JD.
    """
    user_content = f"""[FILTERED JD REQUIREMENTS]
{filtered_jd}

[EXPERIENCE FACTS TO FILTER]
{facts}
"""
    try:
        response = await client.chat.completions.create(
            model=FACTS_FILTER_MODEL,
            messages=[
                {"role": "system", "content": FACTS_FILTER_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=FACTS_FILTER_TEMP,
            max_completion_tokens=MAX_FACTS_FILTER_TOKENS,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[!] Error filtering facts: {e}")
        # Fallback: return truncated original
        return facts[:1500]


# ================== HELPER FUNCTIONS (Bullets) ===================

def generate_bullets(
    client: OpenAI,
    facts: str,
    jd: str,
    role: str,
    company: str,
    header: str
) -> List[str]:
    """
    Stage 1: Generate plain text bullets using the high-quality model.
    """
    user_content = f"""
[JOB_TITLE]
{role}

[COMPANY]
{company}

[RESUME_SECTION_HEADER]
{header}

[JOB_DESCRIPTION_SNIPPET]
{jd[:4000]}

[EXTRACTED_FACTS]
{facts}

[TASK]
Draft exactly 4 high-quality plain-text bullets based on the instructions.
"""
    try:
        response = client.chat.completions.create(
            model=STAGE1_MODEL,
            messages=[
                {"role": "system", "content": HIGH_LEVEL_BULLET_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=CONTENT_TEMP,
            max_completion_tokens=MAX_CONTENT_TOKENS,
        )
        content = response.choices[0].message.content.strip()
        # Extract non-empty lines
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        # Remove potential numbering (1. , - , • ) if the model adds them despite instructions
        clean_lines = []
        for line in lines:
            # Strip common list markers
            if line.startswith(("- ", "* ", "• ")):
                line = line[2:]
            elif line[0].isdigit() and line[1:3] in (". ", ") "):
                line = line[3:] # approximate
            clean_lines.append(line)
        
        return clean_lines[:4] # Ensure max 4
    except Exception as e:
        print(f"[!] Error in Stage 1 (Content): {e}")
        return []

def convert_to_latex(
    client: OpenAI,
    bullets: List[str]
) -> str:
    """
    Stage 2: Convert plain text bullets to LaTeX using the cheaper model.
    """
    if not bullets:
        return ""

    user_content = "Please convert these bullets to LaTeX:\n\n" + "\n".join(bullets)

    try:
        response = client.chat.completions.create(
            model=STAGE2_MODEL,
            messages=[
                {"role": "system", "content": LATEX_CONVERSION_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=LATEX_TEMP,
            max_tokens=MAX_LATEX_TOKENS,
        )
        content = response.choices[0].message.content.strip()
        # Clean up code fences if present
        if content.startswith("```"):
            content = content.replace("```latex", "").replace("```", "")
        return content.strip()
    except Exception as e:
        print(f"[!] Error in Stage 2 (LaTeX): {e}")
        # Fallback: simple wrapping
        items = "\n".join([r"\item " + b for b in bullets])
        return "\\begin{itemize}\n" + items + "\n\\end{itemize}"


# ================== ASYNC HELPER FUNCTIONS (Bullets) ===================

async def generate_bullets_async(
    client: AsyncOpenAI,
    facts: str,
    jd: str,
    role: str,
    company: str,
    header: str,
    extra_prompt: str = ""
) -> List[str]:
    """
    Stage 1 (Async): Generate plain text bullets using the high-quality model.
    """
    user_content = f"""
[JOB_TITLE]
{role}

[COMPANY]
{company}

[RESUME_SECTION_HEADER]
{header}

[JOB_DESCRIPTION_SNIPPET]
{jd[:4000]}

[EXTRACTED_FACTS]
{facts}

[TASK]
Draft exactly 4 high-quality plain-text bullets based on the instructions.{extra_prompt}
"""
    try:
        response = await client.chat.completions.create(
            model=STAGE1_MODEL,
            messages=[
                {"role": "system", "content": HIGH_LEVEL_BULLET_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=CONTENT_TEMP,
            max_completion_tokens=MAX_CONTENT_TOKENS,
        )
        content = response.choices[0].message.content.strip()
        # Extract non-empty lines
        lines = [line.strip() for line in content.splitlines() if line.strip()]
        # Remove potential numbering (1. , - , • ) if the model adds them despite instructions
        clean_lines = []
        for line in lines:
            # Strip common list markers
            if line.startswith(("- ", "* ", "• ")):
                line = line[2:]
            elif line[0].isdigit() and line[1:3] in (". ", ") "):
                line = line[3:] # approximate
            clean_lines.append(line)

        return clean_lines[:4] # Ensure max 4
    except Exception as e:
        print(f"[!] Error in Stage 1 (Content - Async): {e}")
        return []

async def convert_to_latex_async(
    client: AsyncOpenAI,
    bullets: List[str]
) -> str:
    """
    Stage 2 (Async): Convert plain text bullets to LaTeX using the cheaper model.
    """
    if not bullets:
        return ""

    user_content = "Please convert these bullets to LaTeX:\n\n" + "\n".join(bullets)

    try:
        response = await client.chat.completions.create(
            model=STAGE2_MODEL,
            messages=[
                {"role": "system", "content": LATEX_CONVERSION_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=LATEX_TEMP,
            max_tokens=MAX_LATEX_TOKENS,
        )
        content = response.choices[0].message.content.strip()
        # Clean up code fences if present
        if content.startswith("```"):
            content = content.replace("```latex", "").replace("```", "")
        return content.strip()
    except Exception as e:
        print(f"[!] Error in Stage 2 (LaTeX - Async): {e}")
        # Fallback: simple wrapping
        items = "\n".join([r"\item " + b for b in bullets])
        return "\\begin{itemize}\n" + items + "\n\\end{itemize}"

async def generate_all_bullets_async(
    client: AsyncOpenAI,
    filtered_jd: str,
    role: str,
    company: str
) -> tuple[dict, dict]:
    """
    Generate all bullets for all experience blocks in parallel with preprocessing.
    Returns (bullets_map, raw_bullets_data)
    """
    bullets_map = {}
    raw_bullets_data = {}

    # Step 1: Filter facts for all sections in parallel
    filter_tasks = []
    markers = []
    configs = []
    all_facts = []

    for marker, config in EXPERIENCE_BLOCKS.items():
        note_file = INFO_DIR / config["file"]
        if not note_file.exists():
            print(f"       [!] Note file not found: {note_file}")
            bullets_map[marker] = ""
            raw_bullets_data[marker] = []
            continue

        facts = note_file.read_text(encoding="utf-8")
        all_facts.append(facts)
        markers.append(marker)
        configs.append(config)

        # Create async task for facts filtering
        filter_tasks.append(filter_facts_async(client, facts, filtered_jd))

    # Run all facts filtering in parallel
    print("    -> [Async] Filtering facts for all sections in parallel...")
    all_filtered_facts = await asyncio.gather(*filter_tasks)

    # Step 2: Generate bullets using filtered facts
    bullet_tasks = []
    for i, filtered_facts in enumerate(all_filtered_facts):
        # Apply patch for Whisper project only
        current_marker = markers[i]
        extra_instructions = ""
        if current_marker == "%%WHISPER_BULLETS_BLOCK%%" and WHISPER_PATCH:
            extra_instructions = "\n\n" + WHISPER_PATCH

        bullet_tasks.append(
            generate_bullets_async(
                client=client,
                facts=filtered_facts,
                jd=filtered_jd,
                role=role,
                company=company,
                header=configs[i]["header"],
                extra_prompt=extra_instructions
            )
        )

    # Run all content generation tasks in parallel
    print("    -> [Async] Generating bullets for all sections in parallel...")
    all_raw_bullets = await asyncio.gather(*bullet_tasks)

    # Now convert all to LaTeX in parallel
    latex_tasks = []
    for raw_bullets in all_raw_bullets:
        latex_tasks.append(convert_to_latex_async(client, raw_bullets))

    print("    -> [Async] Converting bullets to LaTeX in parallel...")
    all_latex = await asyncio.gather(*latex_tasks)

    # Assemble results
    for i, marker in enumerate(markers):
        raw_bullets = all_raw_bullets[i]
        latex_code = all_latex[i]

        raw_bullets_data[marker] = raw_bullets

        # Indent for the TeX file
        formatted_lines = [line.strip() for line in latex_code.splitlines() if line.strip()]
        bullets_map[marker] = "\n".join("    " + line for line in formatted_lines)

    return bullets_map, raw_bullets_data


# ================== HELPER FUNCTIONS (Skills & Core) ===================

def load_skill_profile():
    if not SKILLS_PROFILE.exists():
        print(f"[!] Error: Skills profile not found at {SKILLS_PROFILE}")
        sys.exit(1)
    return SKILLS_PROFILE.read_text(encoding="utf-8")

def find_pdflatex_path():
    if shutil.which("pdflatex"):
        return "pdflatex"
    
    search_paths = [
        r"H:\texlive\2025\bin\windows",
        r"C:\texlive\2024\bin\win32",
        r"C:\Program Files\MiKTeX\miktex\bin\x64"
    ]
    
    # Check VSCode settings
    settings_path = ROOT.parent / ".vscode" / "settings.json"
    if settings_path.exists():
        try:
            content = settings_path.read_text(encoding="utf-8")
            data = json.loads(content)
            tools = data.get("latex-workshop.latex.tools", [])
            for tool in tools:
                if tool.get("name") == "pdflatex":
                    env_path = tool.get("env", {}).get("PATH", "")
                    if env_path:
                        paths = env_path.replace("${env:PATH}", "").split(";")
                        search_paths.extend(paths)
        except Exception:
            pass

    for path in search_paths:
        if not path.strip():
            continue
        candidate = Path(path.strip()) / "pdflatex.exe"
        if candidate.exists():
            return str(candidate)
            
    return "pdflatex"

def get_vscode_env():
    env = os.environ.copy()
    settings_path = ROOT.parent / ".vscode" / "settings.json"
    if not settings_path.exists():
        return env
    try:
        content = settings_path.read_text(encoding="utf-8")
        data = json.loads(content)
        tools = data.get("latex-workshop.latex.tools", [])
        for tool in tools:
            if tool.get("name") == "pdflatex":
                extra_path = tool.get("env", {}).get("PATH", "")
                if extra_path:
                    final_path = extra_path.replace("${env:PATH}", env.get("PATH", ""))
                    env["PATH"] = final_path
                    return env
    except Exception:
        pass
    return env

def call_openai_for_skills(client: OpenAI, jd_text: str, skills: str) -> str:
    instructions = (
        SKILLS_INSTRUCTIONS +
        "\n\nHere is the COMPLETE SKILL INVENTORY (the ONLY allowed sources):\n\n" +
        skills
    )
    try:
        completion = client.chat.completions.create(
            model=SKILLS_MODEL,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": f"Job description:\n{jd_text}"}
            ],
            temperature=SKILLS_TEMP,
        )
        return completion.choices[0].message.content
    except Exception as e:
        print(f"[!] OpenAI API Error (Skills): {e}")
        raise

def parse_skills_output(raw: str):
    if "===== Skills Section =====" not in raw:
        raise ValueError("Missing Skills Section in model output")
    if "===== Resume Filename =====" not in raw:
        raise ValueError("Missing Resume Filename in model output")

    skills_part = raw.split("===== Skills Section =====", 1)[1]
    skills_block, rest = skills_part.split("===== Resume Filename =====", 1)
    skills_block = skills_block.strip()

    filename_candidates = [line.strip() for line in rest.splitlines() if line.strip()]
    if not filename_candidates:
        raise ValueError("No filename found in model output")

    ai_filename = filename_candidates[0]

    # Sanitize filename (remove invalid characters)
    ai_filename = "".join(c for c in ai_filename if c.isalnum() or c in ("_", "-", "."))

    if not ai_filename.endswith(".pdf"):
        ai_filename += ".pdf"

    # Prepend candidate name from config to the filename
    # AI generates: Company_Role_2026.pdf
    # We want: FirstName_LastName_Company_Role_2026.pdf
    filename = f"{CANDIDATE_FULL_NAME}_{ai_filename}"

    return skills_block, filename

def get_target_info_from_filename(filename: str):
    base = filename.replace(".pdf", "")
    if base.startswith("badbadcompany_"):
        base = base.replace("badbadcompany_", "")
    parts = base.split("_")
    if len(parts) >= 4:
        company = parts[2]
        role = parts[3]
        return company, role
    return "Unknown Company", "Software Engineer"

def cleanup_intermediate_files(folder: Path, keep_files: set):
    extensions_to_remove = {
        ".aux", ".log", ".out", ".toc", ".synctex.gz", 
        ".fdb_latexmk", ".fls", ".bbl", ".blg"
    }
    for item in folder.iterdir():
        if item.name in keep_files:
            continue
        if item.suffix in extensions_to_remove:
            try:
                item.unlink()
            except Exception:
                pass

def save_raw_bullets(folder: Path, filename: str, bullets_data: dict):
    folder.mkdir(parents=True, exist_ok=True)
    json_path = folder / filename.replace(".pdf", "_bullets.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(bullets_data, f, indent=2, ensure_ascii=False)
        print(f"[OK] Saved raw bullets -> {json_path}")
    except Exception as e:
        print(f"[!] Error saving raw bullets: {e}")

def build_resume(skills_tex: str, bullets_map: dict, folder: Path, jd_text: str, filename: str):
    folder.mkdir(parents=True, exist_ok=True)

    jd_filename = filename.replace(".pdf", "_JD.txt")
    (folder / jd_filename).write_text(jd_text, encoding="utf-8")

    if not TEMPLATE_TEX.exists():
        print(f"[!] Error: Template file not found at {TEMPLATE_TEX}")
        return

    template = TEMPLATE_TEX.read_text(encoding="utf-8")
    final_tex = template.replace(SKILLS_PLACEHOLDER, skills_tex)
    
    for marker, content in bullets_map.items():
        if content:
             final_tex = final_tex.replace(marker, content)
        else:
             final_tex = final_tex.replace(marker, "% (No bullets generated)")
    
    tex_filename = filename.replace(".pdf", ".tex")
    resume_path = folder / tex_filename
    resume_path.write_text(final_tex, encoding="utf-8")

    pdflatex_cmd = find_pdflatex_path()
    build_env = get_vscode_env()
    
    success = False
    
    print(f"[*] Compiling PDF using: {pdflatex_cmd}...")

    # Method 1
    try:
        cmd = [pdflatex_cmd, "-interaction=nonstopmode", "-file-line-error", tex_filename]
        subprocess.run(
            cmd, 
            cwd=folder, 
            check=True, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            env=build_env
        )
        print(f"[OK] Built PDF -> {folder / filename}")
        success = True
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass 
    
    # Method 2 (Fallback to shell)
    if not success and pdflatex_cmd == "pdflatex":
        try:
            bash_cmd = f'pdflatex -interaction=nonstopmode -file-line-error "{tex_filename}"'
            subprocess.run(
                ["bash", "-c", bash_cmd], 
                cwd=folder, 
                check=True, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL,
                env=build_env
            )
            print(f"[OK] Built PDF (via bash) -> {folder / filename}")
            success = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    expected_pdf = folder / filename
    if expected_pdf.exists():
        if not success:
             print(f"[OK] Built PDF (with warnings) -> {expected_pdf}")
        cleanup_intermediate_files(folder, keep_files={filename, jd_filename, tex_filename})
    else:
        print(f"[!] Warning: Could not compile PDF automatically.")
        print(f"    - Manual compilation required for: {folder / tex_filename}")

# ================== MAIN ===================

def main():
    parser = argparse.ArgumentParser(description="Generate tailored resume for a specific JD.")
    parser.add_argument("--jd", required=True, help="Path to the Job Description text file.")
    parser.add_argument("--company", help="Target Company Name", default=None)
    parser.add_argument("--role", help="Target Role Name", default=None)
    args = parser.parse_args()

    jd_path = Path(args.jd)
    if not jd_path.exists():
        print(f"[!] JD file not found: {jd_path}")
        return

    print(f"=== Processing JD: {jd_path.name} ===")
    
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        skills_profile = load_skill_profile()
        jd_text = jd_path.read_text(encoding="utf-8")

        # 1. Generate Skills & Filename
        print("    -> Generating Skills & Filename...")
        
        # Inject explicit company/role into JD text for the model if provided
        context_header = ""
        if args.company:
            context_header += f"TARGET COMPANY NAME: {args.company}\n"
        if args.role:
            context_header += f"TARGET ROLE TITLE: {args.role}\n"
            
        full_context_for_skills = context_header + "\n" + jd_text if context_header else jd_text
        
        skills_raw = call_openai_for_skills(client, full_context_for_skills, skills_profile)
        skills_tex, filename = parse_skills_output(skills_raw)
        
        # 2. Extract Target Info
        company, role = get_target_info_from_filename(filename)
        print(f"    -> Target: {company} | Role: {role}")

        # 3. Use JD directly (Skipping redundant filtering step as input is already pre-structured)
        # Previously we ran filter_jd here, but now we rely on the upstream structured extraction
        print("    -> Using provided JD text directly (assuming structured input)...")
        filtered_jd = jd_text

        # 4. Prepare output folder
        folder_name = filename[:-4] if filename.endswith(".pdf") else filename
        folder = OUTPUT_DIR / folder_name
        folder.mkdir(parents=True, exist_ok=True)

        # 5. Cache filtered JD to JSON file (for reference and reuse)
        filtered_jd_data = {
            "original_jd_length": len(jd_text),
            "filtered_jd_length": len(filtered_jd),
            "reduction_ratio": "0.0% (No Filter)",
            "filtered_jd": filtered_jd,
            "company": company,
            "role": role
        }
        filtered_jd_path = folder / f"{folder_name}_filtered_jd.json"
        with open(filtered_jd_path, "w", encoding="utf-8") as f:
            json.dump(filtered_jd_data, f, indent=2, ensure_ascii=False)
        print(f"       [Cached] JD saved to {filtered_jd_path.name}")

        # 6. Generate Bullets (Async - Parallel with preprocessing)
        print("    -> Generating bullets for all sections using async API...")
        async_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        bullets_map, raw_bullets_data = asyncio.run(
            generate_all_bullets_async(
                client=async_client,
                filtered_jd=filtered_jd,
                role=role,
                company=company
            )
        )

        # 7. Save outputs and build resume
        save_raw_bullets(folder, filename, raw_bullets_data)
        build_resume(skills_tex, bullets_map, folder, jd_text, filename)
        
        print("\n[Done] Resume generation complete.")

    except Exception as e:
        print(f"[!] Fatal Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

