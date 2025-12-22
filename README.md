# GoodLuckFindAJob

An intelligent job application automation system that scrapes job postings, filters them based on your criteria, and generates tailored resumes using AI.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          JOB APPLICATION PIPELINE                        │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│   JD Scraper     │  Scrapes job postings from Indeed
│                  │  • Searches multiple cities/remote
│  scan_daily.py   │  • Filters by keywords & recency
│  screener.py     │  • Extracts structured JD info
└────────┬─────────┘  • Screens for visa/seniority/match
         │
         ▼
┌──────────────────────────────────────────────────────────────┐
│  Prompts Used:                                               │
│  • jd_filter.txt - Extract relevant JD information           │
│  • jd_structured_extraction.txt - Parse company/role/salary  │
│  • combined_visa_senior.txt - Filter visa/seniority          │
│  • match_screening.txt - Score fit to your profile           │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │   data/daily/   │  Stores filtered job postings
         │                 │  • good_jobs.csv (all matches)
         │  good_jobs.csv  │  • job_statuses.json (tracking)
         └────────┬────────┘  • resume_versions.json (tracking)
                  │
                  ▼
         ┌─────────────────┐
         │   offerClick    │  Web app to manage applications
         │                 │  • Browse filtered jobs
         │  (Web UI)       │  • Track application status
         └────────┬────────┘  • Trigger resume generation
                  │
                  ▼
┌──────────────────────────────────────────────────────────────┐
│   JD Converter - Tailored Resume Generator                   │
│                                                               │
│  auto_resume.py                                              │
│  ├─ Step 1: Filter JD facts (jd_filter.txt)                 │
│  ├─ Step 2: Filter your facts (facts_filter.txt)            │
│  ├─ Step 3: Generate skills section (skills.txt)            │
│  ├─ Step 4: Generate bullet content (bullets_content.txt)   │
│  ├─ Step 5: Convert to LaTeX (bullets_latex.txt)            │
│  └─ Step 6: Compile PDF resume                              │
└──────────────────┬───────────────────────────────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │  generated_CV/  │  Final tailored resumes
         │                 │  • PDF format
         │ [job_name].pdf  │  • One per job application
         └─────────────────┘
```

## Features

- **Automated Job Scraping**: Searches Indeed for jobs matching your criteria across multiple cities
- **Intelligent Filtering**: Uses AI to screen for visa sponsorship, seniority level, and profile match
- **Resume Customization**: Generates tailored resumes that highlight relevant experience for each job
- **Web Interface**: Manage job applications and track statuses through a React + FastAPI web app
- **Prompt-Driven**: Fully customizable AI prompts for each stage of the pipeline

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- OpenAI API key
- LaTeX distribution (for PDF generation)
  - **Windows**: Install MiKTeX or TeX Live
  - **macOS**: Install MacTeX
  - **Linux**: `sudo apt-get install texlive-full`

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd GoodLuckFindAJob
   ```

2. **Set up Python environment**
   ```bash
   python -m venv ppl2offer
   source ppl2offer/bin/activate  # On Windows: ppl2offer\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up frontend dependencies**
   ```bash
   cd offerClick/frontend
   npm install
   cd ../..
   ```

4. **Configure your API key**

   Set your OpenAI API key as an environment variable:

   **PowerShell (Windows):**
   ```powershell
   $env:OPENAI_API_KEY = 'your-key-here'
   ```

   **Bash (Linux/macOS):**
   ```bash
   export OPENAI_API_KEY='your-key-here'
   ```

   Or create a `.env` file in the project root:
   ```
   OPENAI_API_KEY=your-key-here
   ```

### Configuration

Before running the system, you need to set up your personal configuration files. Most configuration files have example templates that you should copy and customize.

#### 1. Resume Configuration (`config/resume.json`)

**This is the first file you should set up!**

Copy the example and customize:

```bash
cp config/resume.example.json config/resume.json
```

Edit `config/resume.json` to configure:

**a) Your Name** (Required for PDF filenames)
```json
"candidate_name": {
  "first_name": "John",
  "last_name": "Doe"
}
```

**b) AI Models** - Which OpenAI models to use:
```json
"models": {
  "jd_filter": "gpt-4o-mini",
  "facts_filter": "gpt-4o-mini",
  "skills": "gpt-5.1",         // For skills section generation
  "content": "gpt-5.1",         // For bullet content generation
  "latex": "gpt-4o-mini"        // For LaTeX formatting
}
```

**c) Experience Sections** - Map your experience files to resume sections:
```json
"experience_sections": {
  "company1": {
    "file": "company1_notes.md",                    // File in info/ directory
    "header": "Company Name | Job Title",           // Header in resume
    "marker": "%%COMPANY1_BULLETS_BLOCK%%"          // Marker in resume.tex
  }
}
```

Each experience section needs:
- A corresponding markdown file in `info/` directory
- A matching marker placeholder in `JDConverter/resume.tex`

#### 2. Resume Template (`JDConverter/resume.tex`)

Copy the example and customize:

```bash
cp JDConverter/resume.example.tex JDConverter/resume.tex
```

Edit `JDConverter/resume.tex` to set:
- Your name, contact info, and social profiles in the header
- Your education details
- Experience section headers (must match `config/resume.json`)
- Project section headers (must match `config/resume.json`)

**Important**: The markers like `%%COMPANY1_BULLETS_BLOCK%%` must match exactly with the markers in `config/resume.json`.

#### 3. Personal Information (`info/` directory)

Create your personal experience and skills files:

**Required files:**
- `skills_profile.md` - Your comprehensive skills inventory (see `info/README.md`)
- `[experience]_notes.md` - One file per experience section defined in `config/resume.json`
  - Example: If you have `"company1": {"file": "company1_notes.md", ...}`, create `info/company1_notes.md`
- `cover_letter.md` - Base cover letter template (optional)

**Format**: Each experience file should contain detailed bullet points about your work, achievements, and technical stack. The AI will filter and adapt these to match each job description.

See `info/README.md` for detailed format examples and instructions.

#### 4. Job Search Preferences (`config/search.json`)

Copy the example and customize:

```bash
cp config/search.example.json config/search.json
```

Edit `config/search.json` to set:
- **locations.cities**: Cities to search in
- **locations.remote**: Remote work preferences
- **search_terms**: Job titles and keywords to search for
- **scraper.results_per_city**: Number of results per city (default: 200)
- **scraper.days_old**: How recent jobs should be (default: 1 day)

#### 5. Screening Configuration (`config/screening.json`)

Adjust screening thresholds:
- **match_threshold**: Minimum score (0-100) for job match
- **models**: AI model to use for screening
- **max_description_length**: Maximum JD length to process

### Usage

#### Quick Start Workflow

1. **Set up configuration files** (see Configuration section above)
   ```bash
   cp config/resume.example.json config/resume.json
   cp config/search.example.json config/search.json
   cp JDConverter/resume.example.tex JDConverter/resume.tex
   ```

2. **Create your personal information files** in `info/` directory

3. **Run the full system** (Recommended)
   ```bash
   python run_system.py
   ```
   This starts:
   - Backend API at `http://localhost:8000`
   - Frontend UI at `http://localhost:5174` (opens automatically)

#### Running Individual Components

If you prefer to run components separately:

**1. Scrape Jobs from Indeed**
```bash
cd JDScraper
python scan_daily.py
```
This searches Indeed based on your `config/search.json` preferences and saves raw results to `data/daily/`.

**2. Screen and Filter Jobs with AI**
```bash
cd JDScraper
python screener.py
```
This uses AI to:
- Filter jobs by visa sponsorship requirements
- Check seniority level match
- Score your profile match for each job
- Save filtered jobs to `data/daily/good_jobs.csv`

**3. Generate Tailored Resume**

From the web UI or command line:

**Option A: From CSV file**
```bash
cd JDConverter
python auto_resume.py --jd "path/to/job_description.txt" --company "CompanyName" --role "Software Engineer"
```

**Option B: Direct text input**
```bash
cd JDConverter
python auto_resume.py --jd "Full job description text here..." --company "Google" --role "SWE"
```

The resume generator will:
1. Filter the job description for relevant requirements
2. Filter your experience notes for matching facts
3. Generate a tailored skills section
4. Generate tailored bullet points for each experience
5. Compile everything into a PDF resume
6. Save to `generated_CV/{YourName}_{Company}_{Role}_2026/`

Generated files include:
- `{YourName}_{Company}_{Role}_2026.pdf` - Final resume
- `{YourName}_{Company}_{Role}_2026.tex` - LaTeX source
- `{YourName}_{Company}_{Role}_2026_JD.txt` - Job description copy
- `{YourName}_{Company}_{Role}_2026_bullets.json` - Generated bullets (for debugging)

**Command Line Options:**
- `--jd`: Job description file path or text (required)
- `--company`: Company name (required)
- `--role`: Role title (required)

## Project Structure

```
GoodLuckFindAJob/
├── JDScraper/              # Job scraping and filtering
│   ├── scan_daily.py       # Main scraper script
│   └── screener.py         # AI-powered job screening
│
├── JDConverter/            # Resume generation
│   ├── auto_resume.py      # Main resume generator
│   └── resume.tex          # LaTeX template
│
├── offerClick/             # Web application
│   ├── backend/            # FastAPI backend
│   └── frontend/           # React frontend
│
├── config/                 # Configuration files
│   ├── prompts/            # AI prompts for each stage
│   │   ├── scraper/        # Job filtering prompts
│   │   └── converter/      # Resume generation prompts
│   ├── resume.json         # Resume generation config
│   ├── screening.json      # Screening thresholds
│   └── search.json         # Job search preferences (create from example)
│
├── info/                   # Personal information (gitignored)
│   ├── README.md           # Instructions for setup
│   └── *.md                # Your experience notes and skills
│
├── data/
│   └── daily/              # Generated data
│       ├── good_jobs.csv   # Filtered job postings
│       ├── job_statuses.json      # Application tracking (gitignored)
│       └── resume_versions.json   # Resume versions (gitignored)
│
├── generated_CV/           # Generated resumes (gitignored)
│
└── run_system.py           # Launch full web app
```

## Prompt Customization

All AI prompts are stored in `config/prompts/` as text files. You can customize them to match your style and requirements.

### Scraper Prompts (`config/prompts/scraper/`)

| Prompt File | Purpose | Model Used |
|-------------|---------|------------|
| `jd_filter.txt` | Extract relevant info from job descriptions | gpt-4o-mini |
| `jd_structured_extraction.txt` | Parse company, role, salary | gpt-4o-mini |
| `jd_metadata_extraction.txt` | Extract metadata for tracking | gpt-4o-mini |
| `combined_visa_senior.txt` | Filter by visa sponsorship & seniority | gpt-4o-mini |
| `match_screening.txt` | Score job-profile fit | gpt-4o-mini |

### Converter Prompts (`config/prompts/converter/`)

| Prompt File | Purpose | Model Used |
|-------------|---------|------------|
| `facts_filter.txt` | Filter relevant facts from your experience | gpt-4o-mini |
| `skills.txt` | Generate skills section | gpt-5.1 |
| `bullets_content.txt` | Generate resume bullet content | gpt-5.1 |
| `bullets_latex.txt` | Convert to LaTeX format | gpt-4o-mini |
| `cover_letter.txt` | Generate cover letter | gpt-5.1 |

## Tips

1. **Start Small**: Run the scraper with `results_per_city: 50` first to test
2. **Check Prompts**: Review and customize prompts to match your style
3. **Iterate on Experience Notes**: The better your `info/*.md` files, the better the resumes
4. **Monitor Costs**: Each resume generation uses multiple API calls
5. **Use Web UI**: The offerClick web app makes it easier to manage multiple applications

## Privacy & Security

- All personal information is excluded from git via `.gitignore`
- Your experience notes, skills profile, and generated resumes are never committed
- API keys should be stored in environment variables, never in code
- Job tracking data stays local

## Troubleshooting

**LaTeX compilation fails**
- Ensure you have a LaTeX distribution installed
- Check `JDConverter/resume.tex` for syntax errors

**API rate limits**
- Reduce `results_per_city` in `config/search.json`
- Add delays between API calls if needed

**No jobs found**
- Broaden your `search_terms` in `config/search.json`
- Increase `days_old` to search older postings
- Check if Indeed is accessible in your region

## Contributing

Feel free to customize this system for your needs! The prompt-driven architecture makes it easy to adapt to different job search strategies.

## Before Sharing

**IMPORTANT**: Before sharing this project or pushing to GitHub, see `BEFORE_SHARING.md` for a comprehensive checklist to ensure no personal information is leaked.

Quick check:
```bash
# Verify personal files are ignored
git status

# Review what will be committed
git add -n .
```

## License

MIT License - feel free to use and modify for your job search!
