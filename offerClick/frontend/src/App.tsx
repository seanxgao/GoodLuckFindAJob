import { useState, useEffect } from 'react';
import { QueryClient, QueryClientProvider, useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Layout } from './components/Layout';
import { JobQueue } from './components/JobQueue';
import { MainPanel } from './components/JobDetail/MainPanel';
import { PdfPreviewPanel } from './components/JobDetail/PdfPreviewPanel';
import { useJobStore } from './stores/jobStore';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { jobsApi } from './api/client';
import type { Job, ResumeGenerationResult } from './api/client';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function AppContent() {
  const { selectedJobId, setSelectedJobId, sortBy, setSortBy, filterStatus, setFilterStatus } = useJobStore();
  const [resumeResults, setResumeResults] = useState<Record<string, ResumeGenerationResult>>({});
  const [applyingJobIds, setApplyingJobIds] = useState<Set<string>>(new Set());
  const [applyProgressMap, setApplyProgressMap] = useState<Record<string, string[]>>({});
  const queryClient = useQueryClient();

  // Fetch all jobs
  const { data: jobs = [], isLoading, error } = useQuery({
    queryKey: ['jobs'],
    queryFn: jobsApi.getAll,
  });

  // Effect to handle URL synchronization (Initial Load)
  // URL has priority over localStorage - if URL has a jobId, use it
  useEffect(() => {
    if (jobs.length > 0) {
      const params = new URLSearchParams(window.location.search);

      // Load Sort & Filter
      const urlSort = params.get('sortBy');
      const urlFilter = params.get('filter');

      if (urlSort && ['match_score', 'company', 'starred'].includes(urlSort)) {
        setSortBy(urlSort as any);
      }
      if (urlFilter && ['all', 'not_applied', 'applied', 'skipped', 'starred'].includes(urlFilter)) {
        setFilterStatus(urlFilter as any);
      }

      // Load Selection - URL has priority
      const urlJobId = params.get('jobId');
      if (urlJobId) {
        const exists = jobs.find(j => j.id === urlJobId);
        if (exists) {
          setSelectedJobId(urlJobId);
        }
      } else if (!selectedJobId && jobs.length > 0) {
        // If no URL param and no selection, select first job
        setSelectedJobId(jobs[0].id);
      }
    }
  }, [jobs]); // Run once when jobs load

  // Effect to update URL when state changes
  useEffect(() => {
    const url = new URL(window.location.href);
    
    if (selectedJobId) url.searchParams.set('jobId', selectedJobId);
    else url.searchParams.delete('jobId');
    
    url.searchParams.set('sortBy', sortBy);
    url.searchParams.set('filter', filterStatus);
    
    window.history.pushState({}, '', url.toString());
  }, [selectedJobId, sortBy, filterStatus]);

  // Fetch selected job details
  const { data: selectedJob } = useQuery({
    queryKey: ['job', selectedJobId],
    queryFn: () => jobsApi.getById(selectedJobId!),
    enabled: !!selectedJobId,
  });

  // Update status mutation
  const updateStatusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: Job['status'] }) =>
      jobsApi.updateStatus(id, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      if (selectedJobId) {
        queryClient.invalidateQueries({ queryKey: ['job', selectedJobId] });
      }
    },
  });

  // Apply mutation
  const applyMutation = useMutation({
    mutationFn: async (id: string) => {
      setApplyProgressMap((prev) => ({ ...prev, [id]: [] })); // Clear/Init progress for this job
      setApplyingJobIds((prev) => new Set(prev).add(id));
      
      return jobsApi.apply(id, (msg) => {
        setApplyProgressMap((prev) => ({
          ...prev,
          [id]: [...(prev[id] || []), msg]
        }));
      });
    },
    onSuccess: (result, jobId) => {
      setResumeResults((prev) => ({ ...prev, [jobId]: result }));
      setApplyingJobIds((prev) => {
        const next = new Set(prev);
        next.delete(jobId);
        return next;
      });
      // Optional: keep progress for a while or clear it? keeping it for now in case user switches back
      
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
    },
    onError: (error, jobId) => {
      console.error('Apply error:', error);
      // Ensure jobId is removed even on error to prevent frozen UI
      setApplyingJobIds((prev) => {
        const next = new Set(prev);
        next.delete(jobId);
        return next;
      });
      setApplyProgressMap((prev) => ({
        ...prev,
        [jobId]: [...(prev[jobId] || []), `Error: ${error.message}`]
      }));
    },
  });

  // Delete generated resume mutation
  const deleteResumeMutation = useMutation({
    mutationFn: (id: string) => jobsApi.deleteGenerated(id),
    onSuccess: (_, jobId) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      queryClient.invalidateQueries({ queryKey: ['job', jobId] });
      // Clear local result if any
      setResumeResults((prev) => {
        const next = { ...prev };
        delete next[jobId];
        return next;
      });
    },
  });

  // Delete job mutation
  const deleteJobMutation = useMutation({
    mutationFn: (id: string) => jobsApi.deleteJob(id),
    onSuccess: (_, jobId) => {
      // Refresh job list
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      // Clear local result if any
      setResumeResults((prev) => {
        const next = { ...prev };
        delete next[jobId];
        return next;
      });
      // Select the next job or first job after deletion
      const currentJobs = queryClient.getQueryData<Job[]>(['jobs']) || jobs;
      if (currentJobs.length > 0) {
        setSelectedJobId(currentJobs[0].id);
      } else {
        setSelectedJobId(null);
      }
    },
  });

  const handleSelectJob = (jobId: string) => {
    setSelectedJobId(jobId);
  };

  const handleApply = async (jobId: string) => {
    // Prevent re-applying if already running for THIS job
    if (applyingJobIds.has(jobId)) return;
    applyMutation.mutate(jobId);
  };

  const handleDeleteResume = (jobId: string) => {
    deleteResumeMutation.mutate(jobId);
  };

  const handleDeleteJob = (jobId: string) => {
    deleteJobMutation.mutate(jobId);
  };

  const handleSkip = (jobId: string) => {
    updateStatusMutation.mutate({ id: jobId, status: 'skipped' });
  };

  const handleSkipAsApplied = (jobId: string) => {
    updateStatusMutation.mutate({ id: jobId, status: 'applied' });
  };

  const handleStar = (jobId: string) => {
    const job = jobs.find((j) => j.id === jobId);
    const newStatus = job?.status === 'starred' ? 'not_applied' : 'starred';
    updateStatusMutation.mutate({ id: jobId, status: newStatus });
  };

  // Setup keyboard shortcuts
  useKeyboardShortcuts(jobs, handleApply, handleSkip, handleStar);

  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-gray-100">
        <div className="text-gray-600 text-lg">Loading jobs...</div>
      </div>
    );
  }

  if (error) {
    let errorMessage = 'Unknown error';
    let errorDetail = '';
    
    if (error instanceof Error) {
      errorMessage = error.message;
      // Check if it's a network error
      if (error.message.includes('Network Error') || error.message.includes('ERR_CONNECTION_REFUSED') || error.message.includes('Failed to fetch')) {
        errorDetail = '无法连接到后端服务器。请确认：\n1. 后端服务器是否正在运行\n2. 后端是否运行在 http://localhost:8000\n3. 防火墙是否阻止了连接';
      } else if (error.message.includes('404')) {
        errorDetail = 'API 端点未找到。请检查后端路由配置。';
      } else if (error.message.includes('500')) {
        errorDetail = '服务器内部错误。请检查后端日志。';
      } else {
        errorDetail = error.stack || '';
      }
    }
    
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-gray-100">
        <div className="text-red-600 max-w-2xl p-6">
          <div className="text-xl font-semibold mb-2">Error loading jobs</div>
          <div className="text-sm mb-2 font-mono bg-red-50 p-2 rounded">{errorMessage}</div>
          {errorDetail && (
            <div className="text-xs mt-2 text-gray-600 whitespace-pre-line bg-gray-50 p-3 rounded">
              {errorDetail}
            </div>
          )}
          <div className="text-xs mt-4 text-gray-500">
            <div className="font-semibold mb-1">Troubleshooting steps:</div>
            <ul className="list-disc list-inside space-y-1">
              <li>确保后端服务器正在运行（运行 start_backend.bat 或 cd backend && python run.py）</li>
              <li>检查后端是否在 http://localhost:8000 运行</li>
              <li>在浏览器中访问 http://localhost:8000 查看后端是否响应</li>
              <li>检查浏览器控制台（F12）查看详细错误信息</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  return (
    <Layout
      queuePanel={
        <JobQueue jobs={jobs} onSelectJob={handleSelectJob} />
      }
      mainPanel={
        selectedJob ? (
          <MainPanel
            job={selectedJob}
            onApply={() => handleApply(selectedJob.id)}
            onDeleteResume={() => handleDeleteResume(selectedJob.id)}
            onSkipAsApplied={() => handleSkipAsApplied(selectedJob.id)}
            onDeleteJob={() => handleDeleteJob(selectedJob.id)}
            isApplying={applyingJobIds.has(selectedJob.id)}
            progressLogs={applyProgressMap[selectedJob.id] || []}
            resumeResult={resumeResults[selectedJob.id] || (selectedJob.resume_versions && selectedJob.resume_versions.length > 0 ? selectedJob.resume_versions[selectedJob.resume_versions.length - 1] : null)}
          />
        ) : (
          <div className="h-full flex items-center justify-center text-gray-500">
            Select a job to view details
          </div>
        )
      }
      previewPanel={
        selectedJob ? (
          <PdfPreviewPanel 
            job={selectedJob} 
            resumeResult={resumeResults[selectedJob.id] || (selectedJob.resume_versions && selectedJob.resume_versions.length > 0 ? selectedJob.resume_versions[selectedJob.resume_versions.length - 1] : null)}
          />
        ) : (
          <div className="h-full flex items-center justify-center text-gray-400 text-sm p-8 text-center">
             Select a job to view preview
          </div>
        )
      }
    />
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;
