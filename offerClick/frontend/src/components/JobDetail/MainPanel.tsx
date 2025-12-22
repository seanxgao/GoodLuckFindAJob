import { useState } from 'react';
import type { Job, ResumeGenerationResult } from '../../api/client';
import { jobsApi } from '../../api/client';
import { Building2, MapPin, ExternalLink, CheckCircle, Copy, Check, FolderOpen, FileText, ChevronDown, ChevronUp } from 'lucide-react';
import { ResumeProgressBar } from '../ResumeProgressBar';

interface MainPanelProps {
  job: Job;
  onApply: () => void;
  onDeleteResume: () => void;
  onSkipAsApplied: () => void;
  onDeleteJob: () => void;
  isApplying: boolean;
  progressLogs?: string[];
  resumeResult: ResumeGenerationResult | null;
}

export function MainPanel({ job, onApply, onDeleteResume, onSkipAsApplied, onDeleteJob, isApplying, progressLogs = [], resumeResult }: MainPanelProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [isOpeningFolder, setIsOpeningFolder] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Cover letter state
  const [showCoverLetter, setShowCoverLetter] = useState(false);
  const [customPrompt, setCustomPrompt] = useState('');
  const [generatedCoverLetter, setGeneratedCoverLetter] = useState<string | null>(null);
  const [isGeneratingCoverLetter, setIsGeneratingCoverLetter] = useState(false);

  // Progress logs state
  const [showDetailedLogs, setShowDetailedLogs] = useState(false);

  const copyToClipboard = async (text: string, id: string) => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        setCopiedId(id);
        setTimeout(() => setCopiedId(null), 2000);
      } else {
        alert('Clipboard access denied or not available.');
      }
    } catch (err) {
      console.error('Failed to copy:', err);
      alert('Copy failed. Please copy manually.');
    }
  };

  const openFolder = async (filePath: string) => {
    try {
      setIsOpeningFolder(true);
      await jobsApi.openFolder(filePath);
      // Visual feedback
      setCopiedId('folder-open');
      setTimeout(() => setCopiedId(null), 2000);
    } catch (err) {
      console.error('Failed to open folder:', err);
      alert('Failed to open folder on server. Make sure the backend is running locally.');
    } finally {
      setIsOpeningFolder(false);
    }
  };

  const handleGenerateCoverLetter = async () => {
    try {
      setIsGeneratingCoverLetter(true);
      setGeneratedCoverLetter(null);

      const result = await jobsApi.generateCoverLetter(job.id, customPrompt);
      setGeneratedCoverLetter(result.cover_letter);
    } catch (err) {
      console.error('Failed to generate cover letter:', err);
      alert('Failed to generate cover letter. Check the backend console for errors.');
    } finally {
      setIsGeneratingCoverLetter(false);
    }
  };

  const renderBulletBlock = (title: string, bullets: string[] | undefined, id: string) => {
    if (!bullets || bullets.length === 0) return null;
    return (
      <div className="bg-white rounded-lg p-3 border border-gray-200 text-sm">
        <div className="flex items-center justify-between mb-2">
           <h4 className="font-semibold text-gray-700">{title}</h4>
           <button
             onClick={() => copyToClipboard(bullets.map(b => `• ${b}`).join('\n'), id)}
             className="p-1 hover:bg-gray-100 rounded text-gray-500 hover:text-blue-600 transition-colors"
             title="Copy Bullets"
           >
             {copiedId === id ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
           </button>
        </div>
        <div className="space-y-1">
          {bullets.map((bullet, idx) => (
            <div key={idx} className="text-gray-600 pl-2 border-l-2 border-gray-100">
              {bullet}
            </div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="h-full overflow-y-auto p-6 bg-white border-r border-gray-200 flex flex-col gap-6">
      
      {/* 1. Header Info */}
      <div>
        <h1 className="text-xl font-bold text-gray-900 mb-1">
          <a 
            href={(() => {
                if (!job.url) return '#';
                if (!job.url.startsWith('http')) return `https://${job.url}`;
                return job.url;
            })()} 
            target="_blank" 
            rel="noopener noreferrer"
            className="hover:text-blue-600 hover:underline flex items-center gap-2"
          >
            {job.role}
            <ExternalLink className="w-4 h-4 text-gray-400" />
          </a>
        </h1>
        <div className="flex items-center gap-2 text-gray-700 mb-2">
          <Building2 className="w-4 h-4" />
          <span className="font-medium">{job.company}</span>
        </div>
        <div className="flex items-center gap-2 text-sm text-gray-500 mb-3">
          <div className="flex items-center gap-1">
            <MapPin className="w-3 h-3" />
            <span>{job.remote ? 'Remote' : job.location}</span>
          </div>
          {job.source && job.source !== 'Unknown' && (
            <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
              {job.source}
            </span>
          )}
        </div>
        
        {/* Structured JD Information - Plain Text */}
        <div className="text-sm text-gray-700 space-y-1">
          <div>
            <span className="font-semibold">Salary: </span>
            <span className="font-medium">
              {job.jd_structured.salary_is_estimated
                ? `(${job.jd_structured.salary_range || "Not provided"})`
                : (job.jd_structured.salary_range || "Not provided")
              }
            </span>
          </div>
          <div>
            <span className="font-semibold">Stack: </span>
            {job.jd_structured.technical_stack || "N/A"}
          </div>
          <div>
            <span className="font-semibold">Experience: </span>
            {job.jd_structured.required_experience || "N/A"}
          </div>
          <div>
            <span className="font-semibold">Responsibilities: </span>
            {job.jd_structured.key_responsibilities && job.jd_structured.key_responsibilities !== "N/A"
              ? (
                  <ul className="list-disc pl-5 mt-1 space-y-1">
                    {job.jd_structured.key_responsibilities.split('|').map((item, idx) => (
                       <li key={idx} className="text-gray-700">{item.trim()}</li>
                    ))}
                  </ul>
                )
              : "N/A"
            }
          </div>
          {job.jd_structured.success_metrics && job.jd_structured.success_metrics !== "N/A" && (
            <div>
              <span className="font-semibold">Metrics: </span>
              {job.jd_structured.success_metrics}
            </div>
          )}
        </div>
      </div>

      {/* 2. Core Strengths (Strong Fit) */}
      <div>
        <h3 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
          <CheckCircle className="w-4 h-4 text-green-600" />
          核心优势 (Core Strengths)
        </h3>
        <ul className="space-y-2">
          {job.match_explanation.strong_fit.map((point, idx) => (
            <li key={idx} className="text-sm text-gray-700 bg-green-50 rounded p-3 border border-green-100">
              {point}
            </li>
          ))}
        </ul>
      </div>

      {/* 3. Resume Generation Action */}
      <div className="pt-2">
          {/* Show resume actions if resume exists, regardless of status */}
          {(job.status === 'applied' || resumeResult) && (
             <div className="space-y-3">
               <button
                 onClick={() => {
                   if (window.confirm('Are you sure you want to delete the generated resume files? This cannot be undone.\n\n确定要删除生成的简历文件吗？')) {
                      setIsDeleting(true);
                      onDeleteResume();
                      // Reset state after a delay or let parent handle it. 
                      // Ideally parent triggers re-render, but we set local state to show feedback.
                      setTimeout(() => setIsDeleting(false), 2000); 
                   }
                 }}
                 disabled={isDeleting}
                 className="w-full bg-green-100 hover:bg-red-100 text-green-800 hover:text-red-800 text-sm font-medium py-2 px-4 rounded text-center border border-green-200 hover:border-red-200 transition-colors group relative"
               >
                 {isDeleting ? 'Deleting...' : (
                   <>
                    <span className="group-hover:hidden">已申请 / Resume Ready</span>
                    <span className="hidden group-hover:inline font-bold">删除生成文件 (Delete Generated)</span>
                   </>
                 )}
               </button>

               {/* Quick Actions for Generated Resume */}
               {resumeResult && (
                 <div className="flex gap-2">
                  <button
                    onClick={() => {
                      // Get folder path by removing filename
                      const folderPath = resumeResult.pdf_path.substring(0, resumeResult.pdf_path.lastIndexOf('\\'));
                      copyToClipboard(folderPath, 'pdf-path');
                    }}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded text-sm font-medium border border-blue-200 transition-colors"
                    title="复制文件夹路径"
                  >
                    {copiedId === 'pdf-path' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    Copy Path
                  </button>
                  <button
                    onClick={() => openFolder(resumeResult.pdf_path)}
                    disabled={isOpeningFolder}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded text-sm font-medium border border-gray-200 transition-colors disabled:opacity-50"
                    title="打开文件夹"
                  >
                    {copiedId === 'folder-open' ? <Check className="w-4 h-4" /> : <FolderOpen className="w-4 h-4" />}
                    {isOpeningFolder ? 'Opening...' : 'Open Folder'}
                  </button>
                 </div>
               )}
             </div>
          )}

          {/* Show generate button only if no resume exists and status is not applied */}
          {job.status !== 'applied' && !resumeResult && (
            <div className="space-y-2">
              <button
                onClick={onApply}
                disabled={isApplying}
                className="w-full bg-gray-900 hover:bg-black disabled:bg-gray-400 text-white font-medium py-2.5 px-4 rounded transition-colors text-sm"
              >
                {isApplying ? '正在生成简历...' : '生成简历 (Generate Resume)'}
              </button>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    if (window.confirm('跳过此工作并标记为已申请？\n\n这将标记为已申请状态，但不会生成简历。')) {
                      onSkipAsApplied();
                    }
                  }}
                  className="flex-1 bg-gray-200 hover:bg-gray-300 text-gray-700 font-medium py-2 px-4 rounded transition-colors text-sm"
                >
                  跳过 (标记为已申请)
                </button>
                <button
                  onClick={() => {
                    if (window.confirm('永久删除此职位？\n\n这将从 good_jobs.csv 中删除该职位及所有相关文件，无法恢复！')) {
                      onDeleteJob();
                    }
                  }}
                  className="flex-1 bg-red-100 hover:bg-red-200 text-red-700 font-medium py-2 px-4 rounded transition-colors text-sm"
                >
                  删除 (Delete)
                </button>
              </div>
            </div>
          )}
  
          {/* Progress Bar */}
          {isApplying && (
            <div className="mt-3 space-y-2">
              <ResumeProgressBar logs={progressLogs} />

              {/* Collapsible detailed logs */}
              {progressLogs.length > 0 && (
                <>
                  <button
                    onClick={() => setShowDetailedLogs(!showDetailedLogs)}
                    className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 transition-colors"
                  >
                    {showDetailedLogs ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                    {showDetailedLogs ? 'Hide' : 'Show'} detailed logs
                  </button>

                  {showDetailedLogs && (
                    <div className="bg-gray-900 text-gray-300 text-xs p-3 rounded font-mono max-h-32 overflow-y-auto">
                      {progressLogs.map((log, i) => (
                        <div key={i} className="whitespace-pre-wrap border-b border-gray-800 py-1 last:border-0">
                          {log}
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          )}
      </div>

      {/* 4. Bullets for Copying */}
      <div className="pt-2 border-t border-gray-100">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">Bullets for Copying</h3>
        
        <div className="space-y-4">
           {/* If we have a newly generated resumeResult, use its bullets as they are the most up-to-date.
               Otherwise, fall back to job.recommended_projects which is hydrated from the latest version on load. */}
           
           {(() => {
             // Prefer resumeResult bullets if available and not empty, otherwise job.recommended_projects
             const resumeBullets = resumeResult?.bullets;
             const hasResumeBullets = resumeBullets && 
               Object.keys(resumeBullets).length > 0 && 
               Object.values(resumeBullets).some(arr => arr && arr.length > 0);
             
             const bulletsSource = hasResumeBullets ? resumeBullets : job.recommended_projects;
             
             // Check if we have any bullets at all
             const hasAnyBullets = (bulletsSource?.scope?.length ?? 0) > 0 || 
                                   (bulletsSource?.edge?.length ?? 0) > 0 || 
                                   (bulletsSource?.whisper?.length ?? 0) > 0 ||
                                   (bulletsSource?.alibaba?.length ?? 0) > 0 || 
                                   (bulletsSource?.craes?.length ?? 0) > 0;

             if (!hasAnyBullets) {
               return (
                  <div className="text-xs text-gray-400 text-center italic">
                    No specific bullets recommended yet. Generate resume to update.
                  </div>
               );
             }

             return (
               <>
                 {renderBulletBlock("Alibaba Cloud — Internship", bulletsSource?.alibaba, "alibaba")}
                 {renderBulletBlock("CRAES — Research Assistant", bulletsSource?.craes, "craes")}
                 {/* Projects hidden as per user request */}
                 {/* {renderBulletBlock("SCOPE — Spectral Clustering", bulletsSource?.scope, "scope")} */}
                 {/* {renderBulletBlock("EDGE — Neural-Hop Retrieval", bulletsSource?.edge, "edge")} */}
                 {/* {renderBulletBlock("Whisper — Streaming ASR", bulletsSource?.whisper, "whisper")} */}
               </>
             );
           })()}
        </div>
      </div>

      {/* 5. Cover Letter Generator */}
      <div className="pt-2 border-t border-gray-100">
        <button
          onClick={() => setShowCoverLetter(!showCoverLetter)}
          className="w-full flex items-center justify-between text-sm font-semibold text-gray-900 mb-3 hover:text-blue-600 transition-colors"
        >
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4" />
            Cover Letter Generator
          </div>
          {showCoverLetter ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </button>

        {showCoverLetter && (
          <div className="space-y-3">
            {/* Input for custom prompt */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">
                Application Question (Optional)
              </label>
              <textarea
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                placeholder="Paste the application question here, or leave blank for a general cover letter..."
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                rows={3}
              />
              <p className="text-xs text-gray-500 mt-1">
                e.g., "Why do you want to work at [Company]?" or "Tell us about a challenging project you worked on."
              </p>
            </div>

            {/* Generate button */}
            <button
              onClick={handleGenerateCoverLetter}
              disabled={isGeneratingCoverLetter}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium py-2 px-4 rounded transition-colors text-sm"
            >
              {isGeneratingCoverLetter ? 'Generating...' : 'Generate Cover Letter'}
            </button>

            {/* Generated cover letter display */}
            {generatedCoverLetter && (
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-gray-700 text-sm">Generated Cover Letter</h4>
                  <button
                    onClick={() => copyToClipboard(generatedCoverLetter, 'cover-letter')}
                    className="p-1 hover:bg-gray-200 rounded text-gray-500 hover:text-blue-600 transition-colors"
                    title="Copy to Clipboard"
                  >
                    {copiedId === 'cover-letter' ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                  </button>
                </div>
                <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {generatedCoverLetter}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

    </div>
  );
}

