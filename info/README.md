# Personal Information Directory

This directory contains your personal experience notes and profiles used for resume generation.

## Required Files

Create the following markdown files in this directory based on the experiences configured in `config/resume.json`:

### Experience Notes Files

Each experience section should have its own markdown file with detailed bullet points:

- `alibaba_notes.md` - Your work experience at Alibaba (or rename based on your experience)
- `CRAES_notes.md` - Research experience details
- `VAD_notes.md` - Project: Whisper Minimal + TinyVAD transcription pipeline
- `EDGE_notes.md` - Project: EDGE (Embedded Dynamic Graph Engine for Memory)
- `SCOPE_notes.md` - Project: SCOPE (Spectral Clustering for Optimized Pattern Estimation)

### Other Files

- `skills_profile.md` - Comprehensive inventory of your skills, technologies, and capabilities
- `cover_letter.md` - Base cover letter template or key points

## File Format

Each experience notes file should contain detailed bullet points about your responsibilities, achievements, and technical work. The resume generator will:

1. Filter relevant facts based on the job description
2. Generate tailored bullet points highlighting matching experience
3. Format them into LaTeX for the final resume

### Example Structure for Experience Files

```markdown
# [Company/Project Name] — [Role]

## Key Achievements

- Detailed achievement with metrics and impact
- Technical implementation details
- Technologies used and problems solved

## Responsibilities

- Day-to-day responsibilities
- Team collaboration and leadership
- Specific technical contributions

## Technical Stack

- Programming languages
- Frameworks and tools
- Infrastructure and systems
```

## Privacy Note

These files contain personal information and are excluded from version control via `.gitignore`. Make sure to keep them secure and never commit them to public repositories.
