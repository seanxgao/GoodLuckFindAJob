import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { jobsApi } from '../api/client';
import { useJobStore } from '../stores/jobStore';
import { X, Plus, Save, Sparkles } from 'lucide-react';

interface AddJobModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AddJobModal({ isOpen, onClose }: AddJobModalProps) {
  const queryClient = useQueryClient();
  const { setSelectedJobId } = useJobStore();
  const [mode, setMode] = useState<'simple' | 'advanced'>('simple');
  const [formData, setFormData] = useState({
    title: '',
    company: '',
    location: '',
    description: '',
    url: '',
    is_remote: false,
  });
  const [simpleJdText, setSimpleJdText] = useState('');
  const [error, setError] = useState<string | null>(null);

  const addJobMutation = useMutation({
    mutationFn: (data: typeof formData) => jobsApi.addManual(data),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      onClose();

      // Select the new job
      if (result && result.job_id) {
          setSelectedJobId(result.job_id);
      }

      // Reset form
      setFormData({
        title: '',
        company: '',
        location: '',
        description: '',
        url: '',
        is_remote: false,
      });
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  const addJobSimpleMutation = useMutation({
    mutationFn: (jd_text: string) => jobsApi.addManualSimple(jd_text),
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['jobs'] });
      onClose();

      // Select the new job
      if (result && result.job_id) {
          setSelectedJobId(result.job_id);
      }

      // Reset form
      setSimpleJdText('');
    },
    onError: (err: Error) => {
      setError(err.message);
    },
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (mode === 'simple') {
      if (!simpleJdText.trim()) {
        setError("JD text is required");
        return;
      }
      addJobSimpleMutation.mutate(simpleJdText);
    } else {
      if (!formData.description.trim()) {
        setError("Description is required");
        return;
      }
      addJobMutation.mutate(formData);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Plus className="w-5 h-5 text-blue-600" />
            手动添加职位 (Manual Add Job)
          </h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-full">
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Mode Toggle */}
        <div className="px-6 pt-4 pb-2">
          <div className="inline-flex rounded-lg bg-gray-100 p-1 w-full">
            <button
              type="button"
              onClick={() => setMode('simple')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'simple'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Sparkles className="w-4 h-4" />
              Simple Mode (AI Extract)
            </button>
            <button
              type="button"
              onClick={() => setMode('advanced')}
              className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                mode === 'advanced'
                  ? 'bg-white text-blue-600 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Plus className="w-4 h-4" />
              Advanced Mode
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6 overflow-y-auto flex-1 space-y-4">
          {error && (
            <div className="bg-red-50 text-red-700 p-3 rounded text-sm border border-red-200">
              {error}
            </div>
          )}

          {mode === 'simple' ? (
            // Simple Mode: Just paste JD text
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Paste Full Job Description
                <span className="text-xs font-normal text-gray-500 ml-2">
                  (AI will extract company, title, location, etc.)
                </span>
              </label>
              <textarea
                required
                rows={15}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                value={simpleJdText}
                onChange={(e) => setSimpleJdText(e.target.value)}
                placeholder="Paste the entire job posting here...

Example:
Software Engineer at Google
Location: Mountain View, CA
We are looking for...
[Full JD text including all details]"
              />
            </div>
          ) : (
            // Advanced Mode: Manual fields
            <>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Company *</label>
              <input
                type="text"
                required
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={formData.company}
                onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                placeholder="e.g. Amazon"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Job Title *</label>
              <input
                type="text"
                required
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                placeholder="e.g. SDE II"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Location</label>
              <input
                type="text"
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                placeholder="e.g. Seattle, WA"
              />
            </div>
            <div className="flex items-center pt-6">
                <label className="flex items-center gap-2 cursor-pointer">
                    <input 
                        type="checkbox" 
                        checked={formData.is_remote}
                        onChange={(e) => setFormData({...formData, is_remote: e.target.checked})}
                        className="w-4 h-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Remote?</span>
                </label>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Job URL (Optional)</label>
            <input
              type="url"
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              value={formData.url}
              onChange={(e) => setFormData({ ...formData, url: e.target.value })}
              placeholder="https://..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Full Job Description * 
              <span className="text-xs font-normal text-gray-500 ml-2">(Will be screened & extracted)</span>
            </label>
            <textarea
              required
              rows={10}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Paste the full JD text here..."
            />
          </div>
            </>
          )}
        </form>

        <div className="p-4 border-t border-gray-200 bg-gray-50 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={addJobMutation.isPending || addJobSimpleMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {(addJobMutation.isPending || addJobSimpleMutation.isPending) ? (
                <>Processing...</>
            ) : (
                <>
                    {mode === 'simple' ? <Sparkles className="w-4 h-4" /> : <Save className="w-4 h-4" />}
                    {mode === 'simple' ? 'AI Extract & Add' : 'Analyze & Add'}
                </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

