from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from typing import List
import json
import shutil
from pathlib import Path
from app.models import Job, JobUpdate, JobStatus, ResumeGenerationResult
from app.repository import JobRepository
from app.services.converter import generate_resume_for_job_stream, generate_resume_for_job, generate_cover_letter
from app.services.manual_add import process_manual_job, process_manual_job_simple
from pydantic import BaseModel

router = APIRouter(prefix="/jobs", tags=["jobs"])
repository = JobRepository()

class ManualJobRequest(BaseModel):
    title: str
    company: str
    location: str
    description: str
    url: str = ""
    is_remote: bool = False

class ManualJobSimpleRequest(BaseModel):
    jd_text: str

@router.post("/manual")
async def manual_add_job(request: ManualJobRequest):
    """Manually add a job description to the system"""
    try:
        # Process the job
        result = process_manual_job(request.model_dump())
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Manual add failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process manual job: {str(e)}")

@router.post("/manual-simple")
async def manual_add_job_simple(request: ManualJobSimpleRequest):
    """Manually add a job from raw JD text (simpler mode - extracts metadata automatically)"""
    try:
        # Process the job
        result = process_manual_job_simple(request.jd_text)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[ERROR] Manual add (simple) failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to process manual job (simple): {str(e)}")


@router.get("", response_model=List[Job])
async def get_all_jobs():
    """Get all jobs"""
    try:
        print("[DEBUG] /jobs endpoint called")
        jobs = repository.get_all()
        print(f"[DEBUG] Returning {len(jobs)} jobs to client")
        return jobs
    except FileNotFoundError as e:
        print(f"[ERROR] FileNotFoundError: {e}")
        raise HTTPException(
            status_code=404,
            detail=f"Data file not found. {str(e)} Please ensure the data file exists at the expected location."
        )
    except Exception as e:
        print(f"[ERROR] Exception in get_all_jobs: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load jobs: {str(e)}"
        )


@router.get("/{job_id}", response_model=Job)
async def get_job(job_id: str):
    """Get a single job by ID"""
    job = repository.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=Job)
async def update_job(job_id: str, update: JobUpdate):
    """Update job status"""
    if update.status is None:
        raise HTTPException(status_code=400, detail="Status is required")
    
    job = repository.update_status(job_id, update.status)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/apply")
async def apply_to_job(job_id: str):
    """Generate resume for a job and mark as applied. Streams progress updates."""
    job = repository.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    async def generate_stream():
        try:
            print(f"[DEBUG] Starting resume generation stream for job {job_id}")
            job_dict = job.model_dump()
            # Use the async generator to stream updates
            print(f"[DEBUG] Creating generator for job: {job_dict.get('company')} - {job_dict.get('role')}")
            generator = generate_resume_for_job_stream(job_id, job_dict)
            print(f"[DEBUG] Generator created, starting to iterate...")
            
            result_data = None
            
            async for update in generator:
                if update.startswith("__RESULT__:"):
                    # Final result
                    result_data = json.loads(update[11:])
                    yield f"data: {json.dumps({'type': 'result', 'data': result_data})}\n\n"
                else:
                    # Progress update
                    yield f"data: {json.dumps({'type': 'progress', 'message': update})}\n\n"
            
            if result_data:
                # Update repository with final result
                repository.add_resume_version(job_id, result_data)
                repository.update_status(job_id, JobStatus.APPLIED)
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                
        except Exception as e:
            import traceback
            error_tb = traceback.format_exc()
            print(f"[ERROR] Streaming generation failed: {e}")
            print(f"[ERROR] Traceback:\n{error_tb}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


@router.post("/{job_id}/cover-letter")
async def generate_cover_letter_for_job(job_id: str, request: dict):
    """Generate a cover letter for a job application"""
    job = repository.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        custom_prompt = request.get("custom_prompt", "")
        job_dict = job.model_dump()

        cover_letter = generate_cover_letter(job_dict, custom_prompt)

        return {
            "cover_letter": cover_letter,
            "job_id": job_id,
            "company": job.company,
            "role": job.role
        }
    except Exception as e:
        print(f"[ERROR] Cover letter generation failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate cover letter: {str(e)}"
        )


@router.get("/{job_id}/resume/{version_id}/download")
async def download_resume(job_id: str, version_id: str, inline: bool = False):
    """Download a specific resume version PDF"""
    job = repository.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    target_version = None
    for v in job.resume_versions:
        if v.version_id == version_id:
            target_version = v
            break
    
    if not target_version:
        raise HTTPException(status_code=404, detail="Resume version not found")
    
    file_path = Path(target_version.pdf_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Resume file not found on server")
        
    return FileResponse(
        path=file_path, 
        filename=file_path.name if not inline else None,
        media_type='application/pdf',
        content_disposition_type='inline' if inline else 'attachment'
    )


@router.delete("/{job_id}/generated")
async def delete_generated_files(job_id: str):
    """Delete generated resume files and revert status"""
    job = repository.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    deleted_paths = []

    # Load raw versions from file to modify them
    resume_file = repository.data_file.parent / "resume_versions.json"
    all_versions = {}
    try:
        with open(resume_file, "r", encoding="utf-8") as f:
            all_versions = json.load(f)
    except:
        pass

    if job_id in all_versions:
        # Iterate over versions for this job and delete folders
        for ver in all_versions[job_id]:
            pdf_path = Path(ver.get("pdf_path", ""))

            # Identify the parent folder to delete
            # Typically: .../generated_CV/FirstName_LastName_Company_Role_2026/file.pdf
            folder = pdf_path.parent

            # Safety check: ensure we are deleting from "generated" folder
            # to avoid accidental deletion of other things if path is weird
            if "generated_CV" in str(folder) and folder.exists() and folder.is_dir():
                 try:
                    shutil.rmtree(folder)
                    deleted_paths.append(str(folder))
                    print(f"[INFO] Deleted folder: {folder}")
                 except Exception as e:
                    print(f"[ERROR] Error deleting {folder}: {e}")
            elif not folder.exists():
                 print(f"[INFO] Folder already gone: {folder}")

        # Remove versions for this job
        del all_versions[job_id]

        # Save back
        with open(resume_file, "w", encoding="utf-8") as f:
            json.dump(all_versions, f, indent=2, ensure_ascii=False)

    # Reset status
    repository.update_status(job_id, JobStatus.NOT_APPLIED)

    return {"status": "cleared", "deleted_paths": deleted_paths}


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """Delete a job post from good_jobs.csv and clean up all associated files"""
    job = repository.get_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    deleted_paths = []

    # First, delete generated resume files if they exist
    resume_file = repository.data_file.parent / "resume_versions.json"
    if resume_file.exists():
        try:
            with open(resume_file, "r", encoding="utf-8") as f:
                all_versions = json.load(f)

            if job_id in all_versions:
                # Iterate over versions for this job and delete folders
                for ver in all_versions[job_id]:
                    pdf_path = Path(ver.get("pdf_path", ""))
                    folder = pdf_path.parent

                    # Safety check: ensure we are deleting from "generated_CV" folder
                    if "generated_CV" in str(folder) and folder.exists() and folder.is_dir():
                        try:
                            shutil.rmtree(folder)
                            deleted_paths.append(str(folder))
                            print(f"[INFO] Deleted folder: {folder}")
                        except Exception as e:
                            print(f"[ERROR] Error deleting {folder}: {e}")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # Now delete the job from the CSV and all data files
    success = repository.delete_job(job_id)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete job from data files")

    return {
        "status": "deleted",
        "job_id": job_id,
        "deleted_paths": deleted_paths
    }


from pydantic import BaseModel

class OpenFolderRequest(BaseModel):
    path: str

@router.post("/open_folder")
async def open_folder(request: OpenFolderRequest):
    """Open the folder containing the resume in the OS file explorer"""
    path = Path(request.path)
    
    # Check if it exists
    if not path.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    
    # If it's a file, get the parent directory
    if path.is_file():
        folder = path.parent
    else:
        folder = path
        
    import os
    import subprocess
    import platform
    
    try:
        if platform.system() == "Windows":
            os.startfile(str(folder))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
        return {"status": "opened", "path": str(folder)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open folder: {e}")
