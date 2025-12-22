import { useState, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, RotateCw } from 'lucide-react';
import { type Job, type ResumeGenerationResult, API_BASE_URL } from '../../api/client';

import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';

// Configure worker
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString();

interface PdfPreviewPanelProps {
  job: Job;
  resumeResult: ResumeGenerationResult | null;
}

export function PdfPreviewPanel({ job, resumeResult }: PdfPreviewPanelProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [pageNumber, setPageNumber] = useState<number>(1);
  const [scale, setScale] = useState<number>(1.0);
  const [rotation, setRotation] = useState<number>(0);
  const [containerWidth, setContainerWidth] = useState<number>(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const latestVersion = resumeResult || (job.resume_versions && job.resume_versions.length > 0 ? job.resume_versions[job.resume_versions.length - 1] : null);

  // Resize observer for responsive width
  useEffect(() => {
    if (!containerRef.current) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect) {
          setContainerWidth(entry.contentRect.width);
        }
      }
    });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
    setNumPages(numPages);
    setPageNumber(1);
  }

  if (!latestVersion) {
    return (
      <div className="h-full flex items-center justify-center text-gray-400 bg-gray-50 border-l border-gray-200">
        <div className="text-center">
          <p>Resume Preview</p>
          <p className="text-xs mt-2">Generate a resume to see preview here</p>
        </div>
      </div>
    );
  }

  // Use the download endpoint
  const pdfUrl = `${API_BASE_URL}/jobs/${job.id}/resume/${latestVersion.version_id}/download`;

  return (
    <div className="h-full bg-gray-100 flex flex-col border-l border-gray-200">
      {/* Toolbar */}
      <div className="flex items-center justify-between p-2 bg-white border-b border-gray-200 shadow-sm z-10 gap-2">
        <div className="flex items-center gap-2 shrink-0">
           <button
             onClick={() => setPageNumber(p => Math.max(1, p - 1))}
             disabled={pageNumber <= 1}
             className="p-1 hover:bg-gray-100 rounded disabled:opacity-30"
           >
             <ChevronLeft className="w-4 h-4" />
           </button>
           <span className="text-sm text-gray-600">
             {pageNumber} / {numPages || '-'}
           </span>
           <button
             onClick={() => setPageNumber(p => Math.min(numPages, p + 1))}
             disabled={pageNumber >= numPages}
             className="p-1 hover:bg-gray-100 rounded disabled:opacity-30"
           >
             <ChevronRight className="w-4 h-4" />
           </button>
        </div>

        {/* Filename Display */}
        <div className="flex-1 text-xs text-gray-500 text-center truncate font-mono select-all" title={latestVersion.pdf_path}>
           {latestVersion.pdf_path.split(/[\\/]/).pop()}
        </div>

        <div className="flex items-center gap-2 shrink-0">
           <button
             onClick={() => setScale(s => Math.max(0.5, s - 0.1))}
             className="p-1 hover:bg-gray-100 rounded"
             title="Zoom Out"
           >
             <ZoomOut className="w-4 h-4" />
           </button>
           <span className="text-sm text-gray-600 w-12 text-center">
             {Math.round(scale * 100)}%
           </span>
           <button
             onClick={() => setScale(s => Math.min(2.0, s + 0.1))}
             className="p-1 hover:bg-gray-100 rounded"
             title="Zoom In"
           >
             <ZoomIn className="w-4 h-4" />
           </button>
           <div className="w-px h-4 bg-gray-300 mx-1" />
           <button
             onClick={() => setRotation(r => (r + 90) % 360)}
             className="p-1 hover:bg-gray-100 rounded"
             title="Rotate"
           >
             <RotateCw className="w-4 h-4" />
           </button>
        </div>
      </div>

      {/* PDF Container */}
      <div 
        ref={containerRef}
        className="flex-1 overflow-auto bg-gray-500/10 p-4 flex justify-center items-start"
      >
        {containerWidth > 0 && (
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            loading={
              <div className="flex items-center justify-center h-64 text-gray-500">
                Loading PDF...
              </div>
            }
            error={
              <div className="flex flex-col items-center justify-center h-64 text-red-500 gap-2">
                <p>Failed to load PDF.</p>
                <p className="text-xs text-gray-400">Backend might be down or file missing.</p>
              </div>
            }
            className="shadow-lg"
          >
            <Page
              pageNumber={pageNumber}
              width={containerWidth * 0.9 * scale} // 90% of container width * scale
              rotate={rotation}
              className="bg-white"
              renderTextLayer={true}
              renderAnnotationLayer={true}
            />
          </Document>
        )}
      </div>
    </div>
  );
}
