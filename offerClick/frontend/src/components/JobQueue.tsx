import { useEffect, useRef, useState } from 'react';
import type { Job } from '../api/client';
import { useJobStore } from '../stores/jobStore';
import { MapPin, Star, CheckCircle, XCircle, ChevronDown, ChevronRight, Building, Plus, AlertTriangle } from 'lucide-react';
import { AddJobModal } from './AddJobModal';

interface JobQueueProps {
  jobs: Job[];
  onSelectJob: (jobId: string) => void;
}

interface CompanyGroup {
  company: string;
  jobs: Job[];
}

export function JobQueue({ jobs, onSelectJob }: JobQueueProps) {
  const { selectedJobId, sortBy, setSortBy, filterStatus, setFilterStatus } = useJobStore();
  const [expandedCompanies, setExpandedCompanies] = useState<Set<string>>(new Set());
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  
  // Use a map of refs to scroll to the selected item
  const itemRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  // Filter jobs
  const filteredJobs = jobs.filter((job) => {
    if (filterStatus === 'all') return true;
    if (filterStatus === 'manual') {
        // Check source first (reliable), fallback to visa_analysis (legacy)
        if (job.source && (job.source.includes('Manual') || job.source === 'Manual-Simple')) {
            return true;
        }
        const text = (job.visa_analysis || "").toUpperCase();
        return text.includes("MANUAL OVERRIDE");
    }
    return job.status === filterStatus;
  });

  // Sort jobs
  const sortedJobs = [...filteredJobs].sort((a, b) => {
    switch (sortBy) {
      case 'match_score':
        return b.match_score - a.match_score;
      case 'company':
        return a.company.localeCompare(b.company);
      case 'starred':
        if (a.status === 'starred' && b.status !== 'starred') return -1;
        if (a.status !== 'starred' && b.status === 'starred') return 1;
        return b.match_score - a.match_score;
      default:
        return 0;
    }
  });

  // Group jobs by company if sorting by company
  const groupedJobs: (Job | CompanyGroup)[] = [];
  if (sortBy === 'company') {
    let currentGroup: CompanyGroup | null = null;
    
    sortedJobs.forEach((job) => {
      if (!currentGroup || currentGroup.company !== job.company) {
        if (currentGroup) {
          // If previous group has > 1 job, add as group. Else add as individual job.
          if (currentGroup.jobs.length > 1) {
            groupedJobs.push(currentGroup);
          } else {
            groupedJobs.push(currentGroup.jobs[0]);
          }
        }
        currentGroup = { company: job.company, jobs: [job] };
      } else {
        currentGroup.jobs.push(job);
      }
    });
    
    // Add last group
    if (currentGroup) {
      if (currentGroup.jobs.length > 1) {
        groupedJobs.push(currentGroup);
      } else {
        groupedJobs.push(currentGroup.jobs[0]);
      }
    }
  }

  // Scroll to selected job when it changes
  useEffect(() => {
    if (selectedJobId) {
      // If the selected job is inside a collapsed group, expand it first
      if (sortBy === 'company') {
        const job = jobs.find(j => j.id === selectedJobId);
        if (job) {
          // Check if this company needs expanding
          const isGrouped = sortedJobs.filter(j => j.company === job.company).length > 1;
          if (isGrouped && !expandedCompanies.has(job.company)) {
             setExpandedCompanies(prev => new Set(prev).add(job.company));
             // Wait for render cycle to scroll? Usually React handles this well enough
          }
        }
      }

      // Small timeout to allow expansion rendering
      setTimeout(() => {
        const element = itemRefs.current.get(selectedJobId);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      }, 50);
    }
  }, [selectedJobId, sortBy]); 

  const toggleCompany = (company: string) => {
    setExpandedCompanies(prev => {
      const next = new Set(prev);
      if (next.has(company)) next.delete(company);
      else next.add(company);
      return next;
    });
  };

  const getStatusIcon = (status: Job['status']) => {
    switch (status) {
      case 'applied':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'skipped':
        return <XCircle className="w-4 h-4 text-gray-400" />;
      case 'starred':
        return <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />;
      default:
        return null;
    }
  };

  const getWarningIcon = (job: Job) => {
    // Check if visa_analysis contains warning keywords
    // Keywords from backend: "MANUAL OVERRIDE", "Visa Check Failed", "Senior Check Failed", "REJECT", "SENIOR"
    const text = (job.visa_analysis || "").toUpperCase();
    const hasWarning = text.includes("MANUAL OVERRIDE") || 
                       text.includes("VISA CHECK FAILED") || 
                       text.includes("SENIOR CHECK FAILED") ||
                       // Also check raw results if present in a structured way (though current backend lumps it in string)
                       (job.status === 'not_applied' && (text.includes("REJECT") || text.includes("SENIOR")));
                       
    if (hasWarning) {
        return (
            <div className="relative group ml-1">
                <AlertTriangle className="w-4 h-4 text-red-500" />
                <div className="absolute left-0 bottom-full mb-1 hidden group-hover:block w-48 p-2 bg-red-800 text-white text-xs rounded shadow-lg z-50">
                    {job.visa_analysis ? job.visa_analysis.split('|')[0].substring(0, 100) + "..." : "Warning"}
                </div>
            </div>
        );
    }
    return null;
  };

  const renderJobItem = (job: Job) => (
    <button
      key={job.id}
      ref={(el) => {
        if (el) itemRefs.current.set(job.id, el);
        else itemRefs.current.delete(job.id);
      }}
      onClick={() => onSelectJob(job.id)}
      className={`w-full text-left p-4 hover:bg-gray-100 transition-colors border-b border-gray-200 ${
        selectedJobId === job.id ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''
      }`}
    >
      <div className="flex items-start justify-between mb-1">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1">
             <div className="font-semibold text-sm truncate">{job.company}</div>
             {getWarningIcon(job)}
          </div>
          <div className="text-xs text-gray-600 truncate">{job.role}</div>
        </div>
        {getStatusIcon(job.status)}
      </div>
      
      <div className="flex items-center gap-2 mt-2">
        <span className="text-xs font-medium text-blue-600">
          {job.match_score}/100
        </span>
        <span className="text-xs text-gray-500 flex items-center gap-1">
          <MapPin className="w-3 h-3" />
          {job.remote ? '远程 (Remote)' : job.location}
        </span>
      </div>
      
      <div className="flex flex-wrap gap-1 mt-2">
        {job.tags.slice(0, 3).map((tag) => (
          <span
            key={tag}
            className="text-xs px-1.5 py-0.5 bg-gray-200 text-gray-700 rounded"
          >
            {tag}
          </span>
        ))}
      </div>
    </button>
  );

  return (
    <div className="h-full flex flex-col bg-gray-50 border-r border-gray-200">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">职位队列 (Job Queue)</h2>
            <button
                onClick={() => setIsAddModalOpen(true)}
                className="p-1.5 bg-blue-50 text-blue-600 rounded hover:bg-blue-100 transition-colors"
                title="Manually Add Job"
            >
                <Plus className="w-4 h-4" />
            </button>
        </div>
        
        {/* Sort Options */}
        <div className="mb-2">
          <label className="text-xs font-medium text-gray-600 mb-1 block">排序方式 (Sort by):</label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as any)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1"
          >
            <option value="match_score">匹配度 (Match Score)</option>
            <option value="company">公司名 (Company)</option>
            <option value="starred">收藏优先 (Starred First)</option>
          </select>
        </div>

        {/* Filter Options */}
        <div>
          <label className="text-xs font-medium text-gray-600 mb-1 block">筛选 (Filter):</label>
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as any)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1"
          >
            <option value="all">全部 (All)</option>
            <option value="not_applied">未申请 (Not Applied)</option>
            <option value="applied">已申请 (Applied)</option>
            <option value="skipped">已跳过 (Skipped)</option>
            <option value="starred">已收藏 (Starred)</option>
            <option value="manual">手动添加 (Manual)</option>
          </select>
        </div>
      </div>

      {/* Job List */}
      <div className="flex-1 overflow-y-auto">
        {sortedJobs.length === 0 ? (
          <div className="p-4 text-center text-gray-500 text-sm">未找到职位</div>
        ) : (
          <div className="divide-y divide-gray-200">
            {sortBy === 'company' ? (
              // Grouped Render
              groupedJobs.map((item, index) => {
                // If it's a single job
                if ('id' in item) {
                  return renderJobItem(item as Job);
                }
                
                // It's a group
                const group = item as CompanyGroup;
                const isExpanded = expandedCompanies.has(group.company);
                
                return (
                  <div key={`group-${group.company}-${index}`} className="border-b border-gray-200 bg-white">
                    <button 
                      onClick={() => toggleCompany(group.company)}
                      className="sticky top-0 z-10 w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors shadow-sm"
                    >
                      <div className="flex items-center gap-2 font-semibold text-sm text-gray-700">
                        <Building className="w-4 h-4 text-gray-500" />
                        {group.company}
                        <span className="text-xs font-normal text-gray-500 bg-gray-200 px-1.5 rounded-full">
                          {group.jobs.length}
                        </span>
                      </div>
                      {isExpanded ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
                    </button>
                    
                    {isExpanded && (
                      <div className="pl-4 border-l-4 border-gray-100">
                        {group.jobs.map(job => renderJobItem(job))}
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              // Flat Render (Match Score / Starred)
              sortedJobs.map((job) => renderJobItem(job))
            )}
          </div>
        )}
      </div>

      <AddJobModal 
        isOpen={isAddModalOpen} 
        onClose={() => setIsAddModalOpen(false)} 
      />
    </div>
  );
}

